import uuid
from sqlalchemy.future import select
from cor_pass.database.models import (
    AccessLevel,
    DeviceAccess,
    ManufacturedDevice,
    DeviceStatus,
    Device,
)
from sqlalchemy.ext.asyncio import AsyncSession


async def get_manufactured_device_by_token(
    db: AsyncSession, token: str
) -> ManufacturedDevice | None:
    result = await db.execute(
        select(ManufacturedDevice).where(
            ManufacturedDevice.token == token,
            ManufacturedDevice.status == DeviceStatus.MANUFACTURED,
        )
    )
    return result.scalar_one_or_none()


async def create_device(
    db: AsyncSession, token: str, name: str, user_id: str, serial_number: str, id: str
) -> Device:
    db_device = Device(
        id=id, token=token, name=name, user_id=user_id, serial_number=serial_number
    )
    db.add(db_device)
    await db.commit()
    await db.refresh(db_device)
    return db_device


async def update_manufactured_device_status(
    db: AsyncSession, manufactured_device: ManufacturedDevice, status: DeviceStatus
):
    manufactured_device.status = status
    await db.commit()
    await db.refresh(manufactured_device)


async def get_device_by_id(db: AsyncSession, device_id: str):
    device = await db.execute(select(Device).where(Device.id == device_id))
    device = device.scalar_one_or_none()
    return device


async def get_device_access(
    db: AsyncSession, device_id: int, granting_user_id: str, accessing_user_id: str
) -> DeviceAccess | None:
    result = await db.execute(
        select(DeviceAccess).where(
            DeviceAccess.device_id == device_id,
            DeviceAccess.granting_user_id == granting_user_id,
            DeviceAccess.accessing_user_id == accessing_user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_device_access(
    db: AsyncSession,
    device_id: int,
    granting_user_id: str,
    accessing_user_id: str,
    access_level: AccessLevel,
) -> DeviceAccess:
    db_access = DeviceAccess(
        device_id=device_id,
        granting_user_id=granting_user_id,
        accessing_user_id=accessing_user_id,
        access_level=access_level,
    )
    db.add(db_access)
    await db.commit()
    await db.refresh(db_access)
    return db_access


async def update_device_access(
    db: AsyncSession, device_access: DeviceAccess, access_level: AccessLevel
):
    device_access.access_level = access_level
    await db.commit()
    await db.refresh(device_access)
    return device_access


async def create_manufactured_devices_bulk(db: AsyncSession, count: int):
    new_devices = []
    for _ in range(count):
        token = str(uuid.uuid4())
        serial_number = str(uuid.uuid4().hex[:12])
        new_devices.append(ManufacturedDevice(token=token, serial_number=serial_number))
    db.add_all(new_devices)
    await db.commit()
    return new_devices
