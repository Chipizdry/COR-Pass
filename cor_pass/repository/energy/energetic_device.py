from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.database.models import AccessLevel, EnergeticDevice, EnergeticDeviceAccess


async def get_device_by_device_id(db: AsyncSession, device_id: str) -> Optional[EnergeticDevice]:
    result = await db.execute(select(EnergeticDevice).where(EnergeticDevice.device_id == device_id))
    return result.scalar_one_or_none()


async def get_device_by_id(db: AsyncSession, device_id: str) -> Optional[EnergeticDevice]:
    result = await db.execute(select(EnergeticDevice).where(EnergeticDevice.id == device_id))
    return result.scalar_one_or_none()


async def upsert_energetic_device(
    db: AsyncSession,
    *,
    device_id: str,
    owner_cor_id: str,
    name: Optional[str] = None,
    protocol: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = True,
    last_seen: Optional[datetime] = None,
) -> EnergeticDevice:
    device = await get_device_by_device_id(db, device_id)

    if device and device.owner_cor_id != owner_cor_id:
        raise HTTPException(status_code=403, detail="Устройство уже принадлежит другому пользователю")

    if device:
        device.name = name or device.name
        device.protocol = protocol if protocol is not None else device.protocol
        device.description = description if description is not None else device.description
        if is_active is not None:
            device.is_active = is_active
        device.last_seen = last_seen or datetime.utcnow()
    else:
        device = EnergeticDevice(
            device_id=device_id,
            owner_cor_id=owner_cor_id,
            name=name,
            protocol=protocol,
            description=description,
            is_active=is_active if is_active is not None else True,
            last_seen=last_seen or datetime.utcnow(),
        )
        db.add(device)

    await db.commit()
    await db.refresh(device)
    return device


async def list_devices_for_user(db: AsyncSession, cor_id: str) -> List[EnergeticDevice]:
    owned_result = await db.execute(select(EnergeticDevice).where(EnergeticDevice.owner_cor_id == cor_id))
    owned = {device.id: device for device in owned_result.scalars().all()}

    shared_result = await db.execute(
        select(EnergeticDevice)
        .join(EnergeticDeviceAccess, EnergeticDevice.id == EnergeticDeviceAccess.device_id)
        .where(EnergeticDeviceAccess.accessing_user_cor_id == cor_id)
    )
    for device in shared_result.scalars().all():
        owned.setdefault(device.id, device)

    return list(owned.values())


async def get_device_access(
    db: AsyncSession, *, device_id: str, accessing_user_cor_id: str
) -> Optional[EnergeticDeviceAccess]:
    result = await db.execute(
        select(EnergeticDeviceAccess).where(
            EnergeticDeviceAccess.device_id == device_id,
            EnergeticDeviceAccess.accessing_user_cor_id == accessing_user_cor_id,
        )
    )
    return result.scalar_one_or_none()


async def upsert_device_access(
    db: AsyncSession,
    *,
    device_id: str,
    accessing_user_cor_id: str,
    access_level: AccessLevel,
    granting_user_cor_id: Optional[str] = None,
) -> EnergeticDeviceAccess:
    access = await get_device_access(
        db, device_id=device_id, accessing_user_cor_id=accessing_user_cor_id
    )

    if access:
        access.access_level = access_level
        access.granting_user_cor_id = granting_user_cor_id or access.granting_user_cor_id
    else:
        access = EnergeticDeviceAccess(
            device_id=device_id,
            accessing_user_cor_id=accessing_user_cor_id,
            access_level=access_level,
            granting_user_cor_id=granting_user_cor_id,
        )
        db.add(access)

    await db.commit()
    await db.refresh(access)
    return access


async def list_device_accesses(db: AsyncSession, device_id: str) -> List[EnergeticDeviceAccess]:
    result = await db.execute(
        select(EnergeticDeviceAccess).where(EnergeticDeviceAccess.device_id == device_id)
    )
    return result.scalars().all()


async def list_all_devices(db: AsyncSession) -> List[EnergeticDevice]:
    """Получить все энергетические устройства (для админа)."""
    result = await db.execute(select(EnergeticDevice).order_by(EnergeticDevice.created_at.desc()))
    return result.scalars().all()


async def update_device(
    db: AsyncSession,
    *,
    device_id: str,
    owner_cor_id: str,
    name: Optional[str] = None,
    protocol: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> EnergeticDevice:
    """Обновить данные устройства (только владелец)."""
    device = await get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Устройство не найдено")
    
    if device.owner_cor_id != owner_cor_id:
        raise HTTPException(status_code=403, detail="Только владелец может изменять устройство")
    
    if name is not None:
        device.name = name
    if protocol is not None:
        device.protocol = protocol
    if description is not None:
        device.description = description
    if is_active is not None:
        device.is_active = is_active
    
    await db.commit()
    await db.refresh(device)
    return device
