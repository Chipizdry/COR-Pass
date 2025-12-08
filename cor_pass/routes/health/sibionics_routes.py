"""
API Routes для интеграции с SIBIONICS CGM
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from loguru import logger
import hashlib

from cor_pass.database.db import get_db
from cor_pass.database.models import User
from cor_pass.database.models.health import SibionicsGlucose
from cor_pass.services.user.auth import auth_service
from sqlalchemy import select
from cor_pass.schemas import (
    SibionicsActionResponse,
    SibionicsUserAuthCreate,
    SibionicsUserAuthResponse,
    SibionicsDeviceResponse,
    SibionicsGlucoseResponse,
    SibionicsSyncRequest,
    SibionicsSyncResponse,
    SibionicsH5AuthUrlRequest,
    SibionicsH5AuthUrlResponse,
    SibionicsCallbackRequest,
    SibionicsCallbackResponse,
    SibionicsWebhookRequest,
    SibionicsWebhookResponse,
    SibionicsWebhookGlucoseRecord,
    ManualGlucoseRequest,
    ManualGlucoseResponse,
    AllDevicesGlucoseResponse,
)
from cor_pass.services.health.sibionics_service import sibionics_client
from cor_pass.repository.health import sibionics_repository


router = APIRouter(prefix="/sibionics", tags=["SIBIONICS CGM"])


@router.get(
    "/auth-url",
    response_model=SibionicsH5AuthUrlResponse,
    summary="Получить H5 Authorization URL для авторизации в Sibionics"
)
async def get_h5_authorization_url(
    request: SibionicsH5AuthUrlRequest = Depends(),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Генерирует H5 Authorization URL для авторизации пользователя в Sibionics.
    
    **Flow:**
    1. Клиент вызывает этот endpoint
    2. Получает `auth_url`
    3. Перенаправляет пользователя на этот URL (открывает в браузере/webview)
    4. Пользователь авторизуется в Sibionics
    5. **Sibionics редиректит на `redirect_url` с `biz_id` и `access_token`**
    6. Клиент парсит параметры из URL и вызывает POST `/api/sibionics/auth`
    
    **Важно:**
    - URL действителен 5 минут
    - `third_biz_id` (user.id) используется для идентификации при callback
    - **Обязательно укажите `redirect_url`** для получения `biz_id`

    callback URL после авторизации:**
    https://dev-corid.cor-medical.ua/api/sibionics/callback
    """
    from cor_pass.config.config import settings
    
    third_biz_id = str(current_user.id)
    
    # Redirect URL - куда Sibionics отправит POST запрос после авторизации

    if settings.app_env == 'development':
        default_redirect_url = "https://dev-corid.cor-medical.ua/api/sibionics/callback"
    else:
        default_redirect_url = "https://prod-corid.cor-medical.ua/api/sibionics/callback"
    
    redirect_url = request.redirect_url or default_redirect_url
    
    base_url = "https://open-auth-uat.sisensing.com"
    
    # Формируем параметры URL
    params = {
        "appKey": settings.SIBIONICS_APP_KEY,
        "thirdBizId": third_biz_id,
        "redirectUrl": redirect_url  
    }
    
    # Формируем полный URL
    from urllib.parse import urlencode
    auth_url = f"{base_url}?{urlencode(params)}"
    
    logger.info(f"Generated H5 auth URL for user {current_user.email} (user_id: {third_biz_id})")
    logger.info(f"Redirect URL: {redirect_url}")
    
    return SibionicsH5AuthUrlResponse(
        auth_url=auth_url,
        third_biz_id=third_biz_id,
        expires_in=300  # 5 минут
    )


@router.post(
    "/callback",
    summary="Callback от Sibionics после H5 авторизации (webhooks)"
)
async def sibionics_authorization_callback(
    request: Request,
    callback_data: SibionicsCallbackRequest,
    db: AsyncSession = Depends(get_db),
    appid: Optional[str] = Header(None, alias="appId"),
    nonce: Optional[str] = Header(None),
    signature_app: Optional[str] = Header(None, alias="signature-app")
):
    """
    Обрабатывает callback от Sibionics после успешной H5 авторизации.
    
    **Webhook Type 201 - Authorization Success Notification**
    
    **Формат запроса:**
    ```json
    {
      "type": 201,
      "content": {
        "bizIds": ["1423159073910992896", "1423159073910992899"],
        "thirdBizId": "18000000000",
        "isAuthorized": true,
        "grantTime": 1709705256289
      }
    }
    ```
    
    **Headers (для проверки подписи):**
    - `appId`: SIBIONICS app identifier
    - `nonce`: 10-символьный random string (уникальный для каждого запроса)
    - `signature-app`: MD5(appId + nonce + body_json + sign_secret).upper()
    - `sign_secret` для UAT/Test: "1234567812345678"
    
    **Response:**
    - Успех: строка "SUCCESS" (обязательно!)
    - Sibionics делает 7 retry попыток если не получит "SUCCESS"
    - Интервалы: 30s, 2min, 10min, 1h, 2h, 6h, 1 day
    
    **Автоматический процесс:**
    1. Sibionics отправляет POST запрос type=201 с массивом `bizIds`
    2. Проверяем подпись в headers (signature verification)
    3. Находим пользователя по `thirdBizId` (user.id)
    4. Сохраняем первый `biz_id` из массива (основной)
    5. Возвращаем "SUCCESS"
    
    **Важно:**
    - Этот endpoint вызывается Sibionics, не клиентом
    - Не требует авторизации (публичный webhook)
    - `thirdBizId` это `user.id` пользователя из вашей системы
    - `bizIds` - массив, берем первый элемент как основной
    - Должен быть идемпотентным (может быть вызван несколько раз)
    """
    try:
        # Проверяем подпись (signature verification)
        from cor_pass.config.config import settings
        
        if appid and nonce and signature_app:
            # Получаем body как JSON string
            body_bytes = await request.body()
            body_str = body_bytes.decode('utf-8')
            
            # sign_secret для UAT/Test
            sign_secret = "1234567812345678"
            
            # Вычисляем подпись: MD5(appId + nonce + body + secret).upper()
            sign_string = f"{appid}{nonce}{body_str}{sign_secret}"
            calculated_signature = hashlib.md5(sign_string.encode()).hexdigest().upper()
            
            if calculated_signature != signature_app:
                logger.warning(
                    f"Invalid signature from Sibionics. "
                    f"Expected: {calculated_signature}, Got: {signature_app}"
                )
                # Не блокируем пока, только логируем
                # return {"error": "Invalid signature"}
        
        # Проверяем тип события
        if callback_data.type != 201:
            logger.warning(f"Unexpected callback type: {callback_data.type}")
            return "SUCCESS"  # Sibionics требует "SUCCESS" для остановки retry
        
        # Проверяем статус авторизации
        if not callback_data.content.isAuthorized:
            logger.warning(f"Authorization rejected for thirdBizId: {callback_data.content.thirdBizId}")
            return "SUCCESS"  # Обработали, больше не присылать
        
        # Проверяем что есть bizIds
        if not callback_data.content.bizIds:
            logger.error("No bizIds in callback content")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No bizIds provided in callback"
            )
        
        # Находим пользователя по user.id (который был передан как thirdBizId)
        from sqlalchemy import select
        from cor_pass.database.models import User
        
        # thirdBizId это строка (UUID user.id)
        user_id = callback_data.content.thirdBizId
        
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            logger.error(f"User not found for thirdBizId: {callback_data.content.thirdBizId}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found for thirdBizId: {callback_data.content.thirdBizId}"
            )
        
        # Используем первый biz_id из массива как основной
        primary_biz_id = callback_data.content.bizIds[0]
        
        # Создаем или обновляем авторизацию
        auth_data = SibionicsUserAuthCreate(biz_id=primary_biz_id)
        
        auth = await sibionics_repository.create_or_update_user_auth(
            db=db,
            user_id=user.id,
            auth_data=auth_data
        )
        
        logger.info(
            f"✅ Sibionics callback type 201 processed: user {user.email} (user_id: {user.id}) "
            f"linked to biz_ids: {callback_data.content.bizIds} (primary: {primary_biz_id})"
        )
        
        # Sibionics требует строку "SUCCESS" для подтверждения
        return "SUCCESS"
        
    except HTTPException as he:
        # Для 404 (user not found) возвращаем SUCCESS чтобы не было retry
        if he.status_code == status.HTTP_404_NOT_FOUND:
            logger.error(f"User not found, returning SUCCESS to prevent retry")
            return "SUCCESS"
        raise
    except Exception as e:
        logger.error(f"❌ Error processing Sibionics callback: {e}", exc_info=True)
        # Для критичных ошибок возвращаем error для retry
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process callback: {str(e)}"
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
        if auth.biz_id:
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
    
    if not auth.biz_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Business ID (biz_id) not found. Please complete H5 authorization first."
        )
    
    try:
        devices_synced = 0
        total_records_added = 0
        total_records_updated = 0
        sync_details = []
        
        # Получаем список устройств с SIBIONICS используя biz_id
        logger.info(f"🔄 Starting device sync for user {current_user.email} (bizId: {auth.biz_id})")
        device_list_response = await sibionics_client.get_device_list(
            biz_id=auth.biz_id,
            page_num=1,
            page_size=100
        )
        
        devices_from_api = device_list_response.get("records", [])
        
        logger.info(f"📦 Received {len(devices_from_api)} devices from SIBIONICS API")
        logger.debug(f"   API response summary: total={device_list_response.get('total')}, page={device_list_response.get('currentPage')}/{device_list_response.get('totalPage')}")
        
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
                
                logger.info(f"🔄 Processing device: {device_data.device_name} (ID: {device_data.device_id})")
                logger.debug(f"   Device details: status={device_data.status}, index={device_data.index}, maxIndex={device_data.maxIndex}")
                
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
                
                logger.info(f"   Requesting glucose data from index {start_index} (last saved: {last_index or 'none'})")
                
                # Получаем все страницы данных глюкозы с SIBIONICS
                current_page = 1
                total_pages = 1
                all_glucose_records = []
                
                while current_page <= total_pages:
                    glucose_response = await sibionics_client.get_device_glucose_data(
                        biz_id=auth.biz_id,
                        device_id=device_data.device_id,
                        index=start_index,
                        page_num=current_page,
                        page_size=sync_request.page_size
                    )
                    
                    page_records = glucose_response.get("records", [])
                    all_glucose_records.extend(page_records)
                    
                    # Обновляем total_pages на первой итерации
                    if current_page == 1:
                        total_pages = glucose_response.get("totalPage", 1)
                        total_count = glucose_response.get("total", 0)
                        logger.info(
                            f"   📥 Starting glucose sync: {total_count} total records across {total_pages} pages"
                        )
                    
                    logger.debug(f"      Page {current_page}/{total_pages}: {len(page_records)} records")
                    current_page += 1
                
                logger.info(f"   ✅ Fetched all {len(all_glucose_records)} glucose records from API")
                if all_glucose_records:
                    logger.debug(
                        f"      Index range: {all_glucose_records[0].get('i')} → {all_glucose_records[-1].get('i')}"
                    )
                
                # Сохраняем данные глюкозы
                for glucose_dict in all_glucose_records:
                    try:
                        from cor_pass.schemas import SibionicsGlucoseData
                        glucose_data = SibionicsGlucoseData(**glucose_dict)
                        
                        # Проверяем, существует ли запись (правильный SQLAlchemy запрос)
                        stmt = select(SibionicsGlucose).where(
                            SibionicsGlucose.device_id == device.id,
                            SibionicsGlucose.index == glucose_data.i
                        )
                        result = await db.execute(stmt)
                        existing_record = result.scalar_one_or_none()
                        
                        glucose_record = await sibionics_repository.create_glucose_record(
                            db=db,
                            device_db_id=device.id,
                            glucose_data=glucose_data
                        )
                        
                        # Определяем, была ли запись обновлена или добавлена
                        if existing_record:
                            device_records_updated += 1
                        else:
                            device_records_added += 1
                            
                    except Exception as record_error:
                        logger.warning(
                            f"Failed to process glucose record at index {glucose_dict.get('i')}: {record_error}"
                        )
                        continue
                
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


@router.post(
    "/webhook",
    response_model=SibionicsWebhookResponse,
    summary="Webhook для push уведомлений от Sibionics (шаг 6 на схеме)"
)
async def sibionics_device_data_webhook(
    webhook_data: SibionicsWebhookRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Принимает push уведомления от Sibionics о новых данных устройств.
    
    **Автоматический процесс:**
    1. Пользователь носит CGM устройство
    2. Устройство загружает данные в Sibionics Platform
    3. Sibionics отправляет webhook на этот endpoint с новыми данными
    4. Данные автоматически сохраняются в вашей БД
    
    **Типы событий (event_type):**
    - `new_data` — новые данные глюкозы
    - `device_online` — устройство онлайн
    - `device_offline` — устройство офлайн
    - `low_battery` — низкий заряд батареи
    - `alert` — тревожное событие (гипо/гипергликемия)
    
    **Важно:**
    - Этот endpoint вызывается Sibionics, не клиентом
    - Не требует авторизации (публичный webhook)
    - Должен быть доступен через HTTPS для продакшна
    - Нужно настроить webhook URL в панели Sibionics Partner
    
    **Webhook URL для настройки в Sibionics:**
    ```
    https://ваш-домен.com/api/sibionics/webhook
    ```
    """
    try:
        logger.info(
            f"📥 Received Sibionics webhook: "
            f"event={webhook_data.event_type}, "
            f"biz_id={webhook_data.biz_id}, "
            f"device_id={webhook_data.device_id}"
        )
        
        # Находим авторизацию по biz_id
        auth = await sibionics_repository.get_user_auth_by_biz_id(
            db=db,
            biz_id=webhook_data.biz_id
        )
        
        if not auth:
            logger.warning(f"Authorization not found for biz_id: {webhook_data.biz_id}")
            # Возвращаем success=True чтобы Sibionics не повторял запрос
            return SibionicsWebhookResponse(
                success=True,
                message=f"Authorization not found for biz_id: {webhook_data.biz_id}",
                records_processed=0
            )
        
        # Находим или создаем устройство
        from cor_pass.schemas import SibionicsDeviceData
        
        # Если в webhook есть данные устройства, обновляем
        if webhook_data.device_data:
            device_info = webhook_data.device_data
            device_data = SibionicsDeviceData(
                device_id=webhook_data.device_id,
                device_name=device_info.device_name or f"CGM Device {webhook_data.device_id}",
                device_type=device_info.device_type or "CGM",
                last_sync_time=device_info.last_sync_time or webhook_data.timestamp,
                battery_level=device_info.battery_level
            )
        else:
            # Минимальные данные устройства
            device_data = SibionicsDeviceData(
                device_id=webhook_data.device_id,
                device_name=f"CGM Device {webhook_data.device_id}",
                device_type="CGM",
                last_sync_time=webhook_data.timestamp
            )
        
        device = await sibionics_repository.create_or_update_device(
            db=db,
            auth_id=auth.id,
            device_data=device_data
        )
        
        records_processed = 0
        
        # Обрабатываем данные глюкозы (если есть)
        if webhook_data.glucose_records:
            logger.info(f"Processing {len(webhook_data.glucose_records)} glucose records")
            
            for glucose_record in webhook_data.glucose_records:
                try:
                    from cor_pass.schemas import SibionicsGlucoseData
                    
                    glucose_data = SibionicsGlucoseData(
                        i=glucose_record.i,
                        v=glucose_record.v,
                        t=glucose_record.t,
                        trend=glucose_record.trend
                    )
                    
                    await sibionics_repository.create_glucose_record(
                        db=db,
                        device_db_id=device.id,
                        glucose_data=glucose_data
                    )
                    
                    records_processed += 1
                    
                except Exception as record_error:
                    logger.error(f"Error processing glucose record: {record_error}")
                    continue
        
        # Логируем специальные события
        if webhook_data.event_type == "device_offline":
            logger.warning(f"⚠️ Device {webhook_data.device_id} went offline")
        elif webhook_data.event_type == "low_battery":
            logger.warning(f"🔋 Low battery on device {webhook_data.device_id}")
        elif webhook_data.event_type == "alert":
            logger.warning(f"🚨 Alert from device {webhook_data.device_id}")
        
        logger.info(
            f"✅ Webhook processed: {records_processed} glucose records saved "
            f"for device {device.device_name}"
        )
        
        return SibionicsWebhookResponse(
            success=True,
            message=f"Webhook processed successfully",
            records_processed=records_processed
        )
        
    except Exception as e:
        logger.error(f"❌ Error processing Sibionics webhook: {e}", exc_info=True)
        # Возвращаем success=False чтобы Sibionics знал о проблеме
        return SibionicsWebhookResponse(
            success=False,
            message=f"Error processing webhook: {str(e)}",
            records_processed=0
        )


@router.get(
    "/actions",
    response_model=List[SibionicsActionResponse],
    summary="Получить действия пользователя (еда, спорт, лекарства, инсулин, сон и т.д.)"
)
async def get_user_actions(
    action_type: Optional[int] = Query(
        None,
        description="Тип действия: 1=еда, 2=спорт, 3=лекарства, 4=инсулин, 5=сон, 6=fingerBlood, 7=самочувствие"
    ),
    begin_time: Optional[int] = Query(
        None,
        description="Начальное время (milliseconds timestamp)"
    ),
    page_num: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(100, ge=1, le=1000, description="Размер страницы"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Получает действия пользователя из Sibionics (еда, спорт, лекарства и т.д.).
    
    **Типы действий:**
    - `1`: Еда (diet) - eventType: Breakfast/Lunch/Dinner, eventDetail: название еды
    - `2`: Спорт (sports) - eventType: тип спорта, eventConsume: калории
    - `3`: Лекарства (drug) - eventDetail: название, eventConsume: доза, unit: единица измерения
    - `4`: Инсулин (insulin) - eventDetail: название, eventConsume: доза
    - `5`: Сон (sleep) - длительность между actionTime и actionEndTime
    - `6`: Finger Blood (fingerBlood) - eventDetail: значение глюкозы из пальца
    - `7`: Самочувствие (feeling) - eventDetail: описание состояния
    
    **Примеры использования:**
    ```
    GET /api/sibionics/actions                     # Все действия
    GET /api/sibionics/actions?action_type=1       # Только еда
    GET /api/sibionics/actions?action_type=6       # Только finger blood тесты
    GET /api/sibionics/actions?begin_time=1660545180000  # С определенного времени
    ```
    
    **Важно:** Данные берутся напрямую из Sibionics API (не кешируются в БД).
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
    
    if not auth.biz_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Business ID (biz_id) not found. Please complete H5 authorization first."
        )
    
    try:
        # Получаем действия с Sibionics API
        response = await sibionics_client.get_user_actions(
            biz_id=auth.biz_id,
            action_type=action_type,
            begin_time=begin_time,
            page_num=page_num,
            page_size=page_size
        )
        
        records = response.get("records", [])
        
        # Преобразуем в Pydantic модели
        from cor_pass.schemas import SibionicsActionResponse
        actions = []
        for record in records:
            try:
                actions.append(SibionicsActionResponse(**record))
            except Exception as e:
                logger.warning(f"Failed to parse action record: {e}, data: {record}")
                continue
        
        logger.info(f"✅ Retrieved {len(actions)} user actions for {current_user.email}")
        
        return actions
        
    except Exception as e:
        logger.error(f"❌ Error fetching user actions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user actions: {str(e)}"
        )


@router.post(
    "/manual-glucose",
    response_model=ManualGlucoseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ручное добавление значения глюкозы"
)
async def add_manual_glucose(
    body: ManualGlucoseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Добавляет вручную введённое значение глюкозы.
    
    - Используется виртуальное устройство типа "manual"

    **Параметры:**
    - `glucose_value` - Уровень глюкозы в mmol/L (0-33.3) 
    - `timestamp` - Время измерения

    """
    try:

        manual_device = await sibionics_repository.get_or_create_manual_device(
            db=db,
            user_id=current_user.id
        )
        
        measurement_time = body.timestamp or datetime.now(timezone.utc)
        

        glucose_record = await sibionics_repository.create_manual_glucose_record(
            db=db,
            device_db_id=manual_device.id,
            glucose_value=body.glucose_value,
            timestamp=measurement_time,
            trend=None,
            alarm_status=None
        )
        
        logger.info(
            f"✅ Manual glucose added for user {current_user.email}: "
            f"{body.glucose_value} mmol/L at {measurement_time}"
        )
        
        return ManualGlucoseResponse.model_validate(glucose_record)
        
    except Exception as e:
        logger.error(f"❌ Error adding manual glucose: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add manual glucose: {str(e)}"
        )


@router.get(
    "/all-devices-glucose",
    response_model=List[AllDevicesGlucoseResponse],
    summary="Получить данные глюкозы со всех устройств пользователя"
)
async def get_all_devices_glucose(
    start_time: Optional[datetime] = Query(None, description="Начало периода (ISO 8601)"),
    end_time: Optional[datetime] = Query(None, description="Конец периода (ISO 8601)"),
    limit_per_device: int = Query(1000, ge=1, le=10000, description="Макс. записей с каждого устройства"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Получает данные глюкозы со всех устройств пользователя (CGM и ручной ввод).
    
    **Типы устройств:**
    - `cgm` - Устройства SIBIONICS CGM (требуют авторизацию)
    - `manual` - Виртуальное устройство для ручного ввода
    
    **Параметры:**
    - `start_time` - Начало периода (опционально)
    - `end_time` - Конец периода (опционально)
    - `limit_per_device` - Макс. записей с каждого устройства (по умолчанию 1000)
    
    """
    try:
        all_devices_data = await sibionics_repository.get_all_user_devices_with_glucose(
            db=db,
            user_id=current_user.id,
            start_time=start_time,
            end_time=end_time,
            limit_per_device=limit_per_device
        )
        
        logger.info(
            f"✅ Retrieved glucose data from {len(all_devices_data)} devices "
            f"for user {current_user.email}"
        )
        
        return all_devices_data
        
    except Exception as e:
        logger.error(f"❌ Error fetching all devices glucose: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch glucose data: {str(e)}"
        )

