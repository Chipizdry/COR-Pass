from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from cor_pass.database.models import PrescriptionFile
import uuid


async def create_prescription_file(
    db: AsyncSession,
    *,
    user_cor_id: str,
    file_name: str,
    file_type: str,
    file_size_kb: float,
    file_data: bytes,
    issue_date=None,
) -> PrescriptionFile:
    new_file = PrescriptionFile(
        id=str(uuid.uuid4()),
        user_cor_id=user_cor_id,
        file_name=file_name,
        file_type=file_type,
        file_size_kb=file_size_kb,
        file_data=file_data,
        issue_date=issue_date,
    )
    db.add(new_file)
    await db.commit()
    await db.refresh(new_file)
    return new_file


async def get_user_prescriptions(db: AsyncSession, user_cor_id: str):
    result = await db.execute(
        select(PrescriptionFile)
        .where(PrescriptionFile.user_cor_id == user_cor_id)
        .order_by(PrescriptionFile.uploaded_at.desc())
    )
    return result.scalars().all()


async def get_prescription_file(db: AsyncSession, file_id: str, user_cor_id: str):
    result = await db.execute(
        select(PrescriptionFile)
        .where(PrescriptionFile.id == file_id, PrescriptionFile.user_cor_id == user_cor_id)
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="Файл не найден")
    return file


async def delete_prescription_file(db: AsyncSession, file_id: str, user_cor_id: str):
    file = await get_prescription_file(db, file_id, user_cor_id)
    await db.delete(file)
    await db.commit()