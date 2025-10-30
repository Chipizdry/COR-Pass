"""
API Routes для интеграции с SIBIONICS CGM
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from loguru import logger

from cor_pass.database.db import get_db
from cor_pass.database.models import User
from cor_pass.services.auth import auth_service
from cor_pass.schemas import (
    SibionicsUserAuthCreate,
    SibionicsUserAuthResponse,
    SibionicsDeviceResponse,
    SibionicsGlucoseResponse,
    SibionicsSyncRequest,
    SibionicsSyncResponse
)
from cor_pass.services.sibionics_service import sibionics_client
from cor_pass.repository import sibionics_repository


router = APIRouter(prefix="/sibionics", tags=["SIBIONICS CGM"])


@router.post(
    "/auth",
    response_model=SibionicsUserAuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Связать аккаунт SIBIONICS с пользователем"
)
async def create_user_authorization(
    auth_data: SibionicsUserAuthCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Создает связь между пользователем COR-ID и аккаунтом SIBIONICS.
    
    После того как пользователь авторизовался через H5 страницу SIBIONICS,
    партнерское приложение получает `biz_id` через callback.
    Этот endpoint сохраняет связь user_id ↔ biz_id в БД.
    """
    try:
        # Создаем или обновляем авторизацию
        auth = await sibionics_repository.create_or_update_user_auth(
            db=db,
            user_id=current_user.id,
            auth_data=auth_data
        )
        
        logger.info(f"✅ User {current_user.email} linked to SIBIONICS biz_id: {auth_data.biz_id}")
        
        return SibionicsUserAuthResponse.model_validate(auth)
        
    except Exception as e:
        logger.error(f"❌ Error creating SIBIONICS authorization: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create authorization: {str(e)}"
        )


@router.get(
    "/auth",
    response_model=SibionicsUserAuthResponse,
    summary="Получить информацию об авторизации SIBIONICS"
)
async def get_user_authorization(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Получает информацию об авторизации пользователя в SIBIONICS
    """
    auth = await sibionics_repository.get_user_auth_by_user_id(
        db=db,
        user_id=current_user.id
    )
    
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SIBIONICS authorization not found for this user"
        )
    
    return SibionicsUserAuthResponse.model_validate(auth)


@router.delete(
    "/auth",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отозвать авторизацию SIBIONICS"
)
async def revoke_user_authorization(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Отзывает авторизацию пользователя в SIBIONICS.
    Удаляет связь с аккаунтом SIBIONICS и отзывает доступ на стороне SIBIONICS.
    """
    # Получаем авторизацию пользователя
    auth = await sibionics_repository.get_user_auth_by_user_id(
        db=db,
        user_id=current_user.id
    )
    
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SIBIONICS authorization not found"
        )
    
    try:
        # Отзываем авторизацию на стороне SIBIONICS
        await sibionics_client.revoke_authorization(biz_id=auth.biz_id)
        
        # Деактивируем авторизацию в БД
        await sibionics_repository.deactivate_user_auth(db=db, auth_id=auth.id)
        
        logger.info(f"✅ Revoked SIBIONICS authorization for user {current_user.email}")
        
    except Exception as e:
        logger.error(f"❌ Error revoking SIBIONICS authorization: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke authorization: {str(e)}"
        )


@router.get(
    "/devices",
    response_model=List[SibionicsDeviceResponse],
    summary="Получить список устройств CGM"
)
async def get_devices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Получает список устройств CGM пользователя из БД.
    Для синхронизации свежих данных с SIBIONICS используйте endpoint /sync
    """
    # Получаем авторизацию пользователя
    auth = await sibionics_repository.get_user_auth_by_user_id(
        db=db,
        user_id=current_user.id
    )
    
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SIBIONICS authorization not found. Please authorize first."
        )
    
    # Получаем устройства из БД
    devices = await sibionics_repository.get_devices_by_auth_id(
        db=db,
        auth_id=auth.id
    )
    
    return [SibionicsDeviceResponse.model_validate(device) for device in devices]


@router.get(
    "/devices/{device_id}/glucose",
    response_model=List[SibionicsGlucoseResponse],
    summary="Получить данные глюкозы для устройства"
)
async def get_device_glucose_data(
    device_id: str,
    start_time: Optional[datetime] = Query(None, description="Start time (ISO 8601)"),
    end_time: Optional[datetime] = Query(None, description="End time (ISO 8601)"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum number of records"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Получает данные глюкозы для конкретного устройства из БД.
    
    device_id - это ID устройства в нашей БД (не SIBIONICS device_id).
    """
    # Получаем устройство и проверяем права доступа
    device = await sibionics_repository.get_device_by_id(db=db, device_db_id=device_id)
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Проверяем, принадлежит ли устройство текущему пользователю
    auth = await sibionics_repository.get_user_auth_by_user_id(
        db=db,
        user_id=current_user.id
    )
    
    if not auth or device.auth_id != auth.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this device"
        )
    
    # Получаем данные глюкозы
    glucose_data = await sibionics_repository.get_glucose_data(
        db=db,
        device_db_id=device_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit
    )
    
    return [SibionicsGlucoseResponse.model_validate(record) for record in glucose_data]


@router.post(
    "/sync",
    response_model=SibionicsSyncResponse,
    summary="Синхронизировать данные с SIBIONICS"
)
async def sync_devices_and_data(
    sync_request: SibionicsSyncRequest = SibionicsSyncRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Синхронизирует данные устройств и глюкозы с SIBIONICS Platform.
    
    1. Получает список устройств с SIBIONICS
    2. Сохраняет/обновляет информацию об устройствах в БД
    3. Для каждого устройства получает новые данные глюкозы
    4. Сохраняет данные глюкозы в БД
    """
    # Получаем авторизацию пользователя
    auth = await sibionics_repository.get_user_auth_by_user_id(
        db=db,
        user_id=current_user.id
    )
    
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SIBIONICS authorization not found. Please authorize first."
        )
    
    try:
        devices_synced = 0
        total_records_added = 0
        total_records_updated = 0
        sync_details = []
        
        # Получаем список устройств с SIBIONICS
        logger.info(f"🔄 Starting device sync for user {current_user.email}")
        device_list_response = await sibionics_client.get_device_list(
            biz_id=auth.biz_id,
            page_num=1,
            page_size=100
        )
        
        devices_from_api = device_list_response.get("records", [])
        
        if not devices_from_api:
            logger.warning(f"No devices found for user {current_user.email}")
            return SibionicsSyncResponse(
                devices_synced=0,
                total_records_added=0,
                total_records_updated=0,
                sync_timestamp=datetime.now(timezone.utc),
                details=[]
            )
        
        # Обрабатываем каждое устройство
        for device_data_dict in devices_from_api:
            try:
                from cor_pass.schemas import SibionicsDeviceData
                device_data = SibionicsDeviceData(**device_data_dict)
                
                # Сохраняем/обновляем устройство в БД
                device = await sibionics_repository.create_or_update_device(
                    db=db,
                    auth_id=auth.id,
                    device_data=device_data
                )
                
                devices_synced += 1
                device_records_added = 0
                device_records_updated = 0
                
                # Получаем последний сохраненный индекс
                last_index = await sibionics_repository.get_latest_glucose_index(
                    db=db,
                    device_db_id=device.id
                )
                
                # Определяем стартовый индекс для синхронизации
                start_index = last_index + 1 if last_index else sync_request.start_index
                
                # Получаем данные глюкозы с SIBIONICS
                glucose_response = await sibionics_client.get_device_glucose_data(
                    biz_id=auth.biz_id,
                    device_id=device_data.device_id,
                    index=start_index,
                    page_num=1,
                    page_size=sync_request.page_size
                )
                
                glucose_records = glucose_response.get("records", [])
                
                # Сохраняем данные глюкозы
                for glucose_dict in glucose_records:
                    from cor_pass.schemas import SibionicsGlucoseData
                    glucose_data = SibionicsGlucoseData(**glucose_dict)
                    
                    # Проверяем, существует ли запись
                    existing_count = await db.execute(
                        f"SELECT COUNT(*) FROM sibionics_glucose WHERE device_id = '{device.id}' AND index = {glucose_data.i}"
                    )
                    
                    glucose_record = await sibionics_repository.create_glucose_record(
                        db=db,
                        device_db_id=device.id,
                        glucose_data=glucose_data
                    )
                    
                    # Определяем, была ли запись обновлена или добавлена
                    # (упрощенно считаем новыми все записи)
                    device_records_added += 1
                
                total_records_added += device_records_added
                total_records_updated += device_records_updated
                
                sync_details.append({
                    "device_id": device.device_id,
                    "device_name": device.device_name,
                    "records_added": device_records_added,
                    "records_updated": device_records_updated
                })
                
                logger.info(f"✅ Synced device {device.device_name}: {device_records_added} new records")
                
            except Exception as device_error:
                logger.error(f"❌ Error syncing device: {device_error}", exc_info=True)
                sync_details.append({
                    "device_id": device_data_dict.get("deviceId", "unknown"),
                    "error": str(device_error)
                })
                continue
        
        logger.info(f"✅ Sync completed: {devices_synced} devices, {total_records_added} new records")
        
        return SibionicsSyncResponse(
            devices_synced=devices_synced,
            total_records_added=total_records_added,
            total_records_updated=total_records_updated,
            sync_timestamp=datetime.now(timezone.utc),
            details=sync_details
        )
        
    except Exception as e:
        logger.error(f"❌ Error during SIBIONICS sync: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )
