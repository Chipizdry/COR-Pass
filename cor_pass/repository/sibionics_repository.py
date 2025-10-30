"""
Репозиторий для работы с данными SIBIONICS CGM в базе данных
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from sqlalchemy.orm import selectinload
from loguru import logger

from cor_pass.database.models import (
    SibionicsAuth,
    SibionicsDevice,
    SibionicsGlucose,
    User
)
from cor_pass.schemas import (
    SibionicsUserAuthCreate,
    SibionicsDeviceData,
    SibionicsGlucoseData
)


async def create_or_update_user_auth(
    db: AsyncSession,
    user_id: str,
    auth_data: SibionicsUserAuthCreate
) -> SibionicsAuth:
    """
    Создает или обновляет авторизацию пользователя в SIBIONICS
    
    Args:
        db: Database session
        user_id: ID пользователя
        auth_data: Данные авторизации (biz_id)
    
    Returns:
        SibionicsAuth object
    """
    # Проверяем, существует ли уже авторизация для этого biz_id
    result = await db.execute(
        select(SibionicsAuth).where(SibionicsAuth.biz_id == auth_data.biz_id)
    )
    existing_auth = result.scalar_one_or_none()
    
    if existing_auth:
        # Обновляем существующую авторизацию
        existing_auth.user_id = user_id
        existing_auth.is_active = True
        existing_auth.updated_at = datetime.now(timezone.utc)
        logger.info(f"✅ Updated SIBIONICS auth for user {user_id}, biz_id: {auth_data.biz_id}")
        await db.commit()
        await db.refresh(existing_auth)
        return existing_auth
    
    # Создаем новую авторизацию
    new_auth = SibionicsAuth(
        user_id=user_id,
        biz_id=auth_data.biz_id,
        is_active=True
    )
    
    db.add(new_auth)
    await db.commit()
    await db.refresh(new_auth)
    
    logger.info(f"✅ Created SIBIONICS auth for user {user_id}, biz_id: {auth_data.biz_id}")
    return new_auth


async def get_user_auth_by_user_id(
    db: AsyncSession,
    user_id: str
) -> Optional[SibionicsAuth]:
    """Получает активную авторизацию пользователя"""
    result = await db.execute(
        select(SibionicsAuth)
        .where(and_(
            SibionicsAuth.user_id == user_id,
            SibionicsAuth.is_active == True
        ))
    )
    return result.scalar_one_or_none()


async def get_user_auth_by_biz_id(
    db: AsyncSession,
    biz_id: str
) -> Optional[SibionicsAuth]:
    """Получает авторизацию по biz_id"""
    result = await db.execute(
        select(SibionicsAuth).where(SibionicsAuth.biz_id == biz_id)
    )
    return result.scalar_one_or_none()


async def deactivate_user_auth(
    db: AsyncSession,
    auth_id: str
) -> bool:
    """Деактивирует авторизацию пользователя"""
    result = await db.execute(
        select(SibionicsAuth).where(SibionicsAuth.id == auth_id)
    )
    auth = result.scalar_one_or_none()
    
    if not auth:
        return False
    
    auth.is_active = False
    auth.updated_at = datetime.now(timezone.utc)
    await db.commit()
    
    logger.info(f"✅ Deactivated SIBIONICS auth: {auth_id}")
    return True


async def create_or_update_device(
    db: AsyncSession,
    auth_id: str,
    device_data: SibionicsDeviceData
) -> SibionicsDevice:
    """
    Создает или обновляет информацию об устройстве
    
    Args:
        db: Database session
        auth_id: ID авторизации
        device_data: Данные устройства от SIBIONICS API
    
    Returns:
        SibionicsDevice object
    """
    # Проверяем, существует ли устройство
    result = await db.execute(
        select(SibionicsDevice).where(
            and_(
                SibionicsDevice.auth_id == auth_id,
                SibionicsDevice.device_id == device_data.device_id
            )
        )
    )
    existing_device = result.scalar_one_or_none()
    
    # Конвертируем timestamps в datetime
    enable_time = datetime.fromtimestamp(device_data.enable_time / 1000, tz=timezone.utc) if device_data.enable_time else None
    last_time = datetime.fromtimestamp(device_data.last_time / 1000, tz=timezone.utc) if device_data.last_time else None
    
    if existing_device:
        # Обновляем существующее устройство
        existing_device.device_name = device_data.device_name
        existing_device.bluetooth_num = device_data.bluetooth_num
        existing_device.serial_no = device_data.serial_no
        existing_device.status = device_data.status
        existing_device.current_index = device_data.index
        existing_device.max_index = device_data.max_index
        existing_device.min_index = device_data.min_index
        existing_device.data_gap = device_data.data_gap
        existing_device.enable_time = enable_time
        existing_device.last_time = last_time
        existing_device.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(existing_device)
        
        logger.debug(f"Updated device: {device_data.device_id}")
        return existing_device
    
    # Создаем новое устройство
    new_device = SibionicsDevice(
        auth_id=auth_id,
        device_id=device_data.device_id,
        device_name=device_data.device_name,
        bluetooth_num=device_data.bluetooth_num,
        serial_no=device_data.serial_no,
        status=device_data.status,
        current_index=device_data.index,
        max_index=device_data.max_index,
        min_index=device_data.min_index,
        data_gap=device_data.data_gap,
        enable_time=enable_time,
        last_time=last_time
    )
    
    db.add(new_device)
    await db.commit()
    await db.refresh(new_device)
    
    logger.info(f"✅ Created new device: {device_data.device_id}")
    return new_device


async def get_devices_by_auth_id(
    db: AsyncSession,
    auth_id: str
) -> List[SibionicsDevice]:
    """Получает все устройства для авторизации"""
    result = await db.execute(
        select(SibionicsDevice)
        .where(SibionicsDevice.auth_id == auth_id)
        .order_by(desc(SibionicsDevice.created_at))
    )
    return result.scalars().all()


async def get_device_by_id(
    db: AsyncSession,
    device_db_id: str
) -> Optional[SibionicsDevice]:
    """Получает устройство по ID из БД"""
    result = await db.execute(
        select(SibionicsDevice).where(SibionicsDevice.id == device_db_id)
    )
    return result.scalar_one_or_none()


async def create_glucose_record(
    db: AsyncSession,
    device_db_id: str,
    glucose_data: SibionicsGlucoseData
) -> SibionicsGlucose:
    """
    Создает запись данных глюкозы
    
    Args:
        db: Database session
        device_db_id: ID устройства в БД
        glucose_data: Данные глюкозы от SIBIONICS API
    
    Returns:
        SibionicsGlucose object
    """
    timestamp = datetime.fromtimestamp(glucose_data.t / 1000, tz=timezone.utc)
    
    # Проверяем, существует ли уже запись с таким индексом
    result = await db.execute(
        select(SibionicsGlucose).where(
            and_(
                SibionicsGlucose.device_id == device_db_id,
                SibionicsGlucose.index == glucose_data.i
            )
        )
    )
    existing_record = result.scalar_one_or_none()
    
    if existing_record:
        # Обновляем существующую запись
        existing_record.glucose_value = glucose_data.v
        existing_record.trend = glucose_data.s
        existing_record.alarm_status = glucose_data.ast
        existing_record.timestamp = timestamp
        await db.commit()
        await db.refresh(existing_record)
        return existing_record
    
    # Создаем новую запись
    new_record = SibionicsGlucose(
        device_id=device_db_id,
        index=glucose_data.i,
        glucose_value=glucose_data.v,
        trend=glucose_data.s,
        alarm_status=glucose_data.ast,
        timestamp=timestamp
    )
    
    db.add(new_record)
    await db.commit()
    await db.refresh(new_record)
    
    return new_record


async def get_glucose_data(
    db: AsyncSession,
    device_db_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 1000
) -> List[SibionicsGlucose]:
    """
    Получает данные глюкозы для устройства
    
    Args:
        db: Database session
        device_db_id: ID устройства в БД
        start_time: Начальное время (опционально)
        end_time: Конечное время (опционально)
        limit: Максимальное количество записей
    
    Returns:
        List of SibionicsGlucose objects
    """
    query = select(SibionicsGlucose).where(SibionicsGlucose.device_id == device_db_id)
    
    if start_time:
        query = query.where(SibionicsGlucose.timestamp >= start_time)
    if end_time:
        query = query.where(SibionicsGlucose.timestamp <= end_time)
    
    query = query.order_by(desc(SibionicsGlucose.timestamp)).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()


async def get_latest_glucose_index(
    db: AsyncSession,
    device_db_id: str
) -> Optional[int]:
    """Получает последний сохраненный индекс глюкозы для устройства"""
    result = await db.execute(
        select(func.max(SibionicsGlucose.index))
        .where(SibionicsGlucose.device_id == device_db_id)
    )
    return result.scalar_one_or_none()
