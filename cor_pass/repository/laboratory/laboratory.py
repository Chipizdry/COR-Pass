from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from fastapi import HTTPException, status
from cor_pass.database.models import MedicalLaboratory
from cor_pass.schemas import LaboratoryCreate, LaboratoryUpdate
import uuid


async def get_laboratory(db: AsyncSession) -> MedicalLaboratory:
    result = await db.execute(select(MedicalLaboratory))
    return result.scalars().first()


async def create_laboratory(db: AsyncSession, data: LaboratoryCreate) -> MedicalLaboratory:
    existing = await get_laboratory(db)
    if existing:
        raise HTTPException(status_code=400, detail="Запись лаборатории уже существует")

    new_lab = MedicalLaboratory(**data.dict())
    db.add(new_lab)
    await db.commit()
    await db.refresh(new_lab)
    return new_lab


async def update_laboratory(db: AsyncSession, data: LaboratoryUpdate) -> MedicalLaboratory:
    lab = await get_laboratory(db)
    if not lab:
        raise HTTPException(status_code=404, detail="Запись лаборатории не найдена")

    for field, value in data.dict(exclude_unset=True).items():
        setattr(lab, field, value)

    await db.commit()
    await db.refresh(lab)
    return lab


async def upload_lab_logo(db: AsyncSession, file_data: bytes, mime_type: str) -> MedicalLaboratory:
    lab = await get_laboratory(db)
    if not lab:
        raise HTTPException(status_code=404, detail="Запись лаборатории не найдена")

    lab.lab_logo_data = file_data
    lab.lab_logo_type = mime_type
    await db.commit()
    return lab