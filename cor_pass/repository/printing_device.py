import uuid
from fastapi import HTTPException, status
from sqlalchemy.future import select
from cor_pass.database.models import PrintingDevice
from cor_pass.schemas import (
    CreatePrintingDevice,
    ResponsePrintingDevice,
    UpdatePrintingDevice,
)
from sqlalchemy.ext.asyncio import AsyncSession


async def create_printing_device(db: AsyncSession, body: CreatePrintingDevice):
    db_printing_device = PrintingDevice(
        device_class=body.device_class,
        device_identifier=body.device_identifier,
        subnet_mask=body.subnet_mask,
        gateway=body.gateway,
        ip_address=body.ip_address,
        port=body.port,
        comment=body.comment,
        location=body.location,
    )
    try:
        db.add(db_printing_device)
        await db.commit()
        await db.commit()
        await db.refresh(db_printing_device)
        return db_printing_device
    except Exception as e:
        await db.rollback()
        raise e


async def get_all_printing_devices(
    skip: int, limit: int, db: AsyncSession
) -> list[ResponsePrintingDevice]:

    stmt = select(PrintingDevice).offset(skip).limit(limit)
    result = await db.execute(stmt)
    printing_devices = result.scalars().all()
    return list(printing_devices)


async def get_printing_device_by_id(
    uuid: str, db: AsyncSession
) -> ResponsePrintingDevice | None:

    stmt = select(PrintingDevice).where(PrintingDevice.id == uuid)
    result = await db.execute(stmt)
    printing_device = result.scalar_one_or_none()
    return printing_device


async def get_printing_device_by_device_identifier(
    device_identifier: str, db: AsyncSession
) -> ResponsePrintingDevice | None:

    stmt = select(PrintingDevice).where(
        PrintingDevice.device_identifier == device_identifier
    )
    result = await db.execute(stmt)
    printing_device = result.scalar_one_or_none()
    return printing_device

async def get_printing_device_by_device_class(
    device_class: str, db: AsyncSession
) -> ResponsePrintingDevice | None:

    stmt = select(PrintingDevice).where(
        PrintingDevice.device_class == device_class
    )
    result = await db.execute(stmt)
    printing_device = result.scalar_one_or_none()
    return printing_device


async def update_printing_device(
    uuid: str, body: UpdatePrintingDevice, db: AsyncSession
):

    stmt = select(PrintingDevice).where(PrintingDevice.id == uuid)
    result = await db.execute(stmt)
    printing_device = result.scalar_one_or_none()
    existing_identifier_device = await get_printing_device_by_device_identifier(
        device_identifier=body.device_identifier, db=db
    )
    if (
        existing_identifier_device
        and existing_identifier_device.id != printing_device.id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device identifier already exists",
        )
    if printing_device:
        printing_device.device_class = body.device_class
        printing_device.device_identifier = body.device_identifier
        printing_device.subnet_mask = body.subnet_mask
        printing_device.gateway = body.gateway
        printing_device.ip_address = body.ip_address
        printing_device.port = body.port
        printing_device.comment = body.comment
        printing_device.location = body.location
    try:
        await db.commit()
        await db.refresh(printing_device)
        return printing_device
    except Exception as e:
        await db.rollback()
        raise e


async def delete_printing_device_by_id(uuid: str, db: AsyncSession):

    stmt = select(PrintingDevice).where(PrintingDevice.id == uuid)
    result = await db.execute(stmt)
    printing_device = result.scalar_one_or_none()
    if not printing_device:
        raise HTTPException(
            status_code=404,
            detail= "Device not found"
        )
    await db.delete(printing_device)
    await db.commit()
    return
