from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.database.db import get_db
from cor_pass.schemas import (
    CreatePrintingDevice,
    ResponcePrintingDevice,
    UpdatePrintingDevice,
)
from cor_pass.repository.printing_device import (
    create_printing_device,
    get_all_printing_devices,
    get_printing_device_by_id,
    update_printing_device,
    delete_printing_device_by_id,
    get_printing_device_by_device_identifier,
)
from cor_pass.services.logger import logger
from cor_pass.services.access import admin_access


router = APIRouter(prefix="/printing_devices", tags=["Printing Devices"])


@router.post(
    "/",
    dependencies=[Depends(admin_access)],
    response_model=ResponcePrintingDevice,
    status_code=201,
)
async def create_new_printing_device(
    body: CreatePrintingDevice, db: AsyncSession = Depends(get_db)
):
    """Создает новое устройство печати."""

    existing_device = await get_printing_device_by_device_identifier(
        device_identifier=body.device_identifier, db=db
    )
    if existing_device:
        logger.debug(f"{body.device_identifier} already exist")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Device already exists"
        )
    return await create_printing_device(db=db, body=body)


@router.get(
    "/all",
    dependencies=[Depends(admin_access)],
    response_model=List[ResponcePrintingDevice],
)
async def read_printing_devices(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    """Возвращает список всех устройств печати с пагинацией."""
    return await get_all_printing_devices(skip=skip, limit=limit, db=db)


@router.get(
    "/{printing_device_id}",
    dependencies=[Depends(admin_access)],
    response_model=ResponcePrintingDevice,
)
async def read_printing_device(
    printing_device_id: str, db: AsyncSession = Depends(get_db)
):
    """Возвращает устройство печати по его ID."""
    printing_device = await get_printing_device_by_id(uuid=printing_device_id, db=db)
    if not printing_device:
        raise HTTPException(status_code=404, detail="Printing device not found")
    return printing_device


@router.put(
    "/{printing_device_id}",
    dependencies=[Depends(admin_access)],
    response_model=ResponcePrintingDevice,
)
async def update_printing_device_by_id(
    printing_device_id: str,
    body: UpdatePrintingDevice,
    db: AsyncSession = Depends(get_db),
):
    """Обновляет устройство печати по его ID."""
    printing_device = await update_printing_device(
        uuid=printing_device_id, body=body, db=db
    )
    if not printing_device:
        raise HTTPException(status_code=404, detail="Printing device not found")
    return printing_device


@router.delete(
    "/{printing_device_id}", dependencies=[Depends(admin_access)], status_code=204
)
async def delete_printing_device(
    printing_device_id: str, db: AsyncSession = Depends(get_db)
):
    """Удаляет устройство печати по его ID."""
    result = await delete_printing_device_by_id(uuid=printing_device_id, db=db)
    if result is None:
        raise HTTPException(status_code=404, detail="Printing device not found")
    return
