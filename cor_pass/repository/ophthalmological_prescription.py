from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from datetime import timedelta
from typing import List, Optional

from cor_pass.database.models import OphthalmologicalPrescription, User
from cor_pass.schemas import (
    OphthalmologicalPrescriptionCreate,
    OphthalmologicalPrescriptionRead,
    OphthalmologicalPrescriptionUpdate,
)

async def create_ophthalmological_prescription(
    db: AsyncSession,
    body: OphthalmologicalPrescriptionCreate,
    user: User,
) -> OphthalmologicalPrescription:
    """
    Создает новый офтальмологический рецепт.
    """
    new_prescription = OphthalmologicalPrescription(
        patient_id=body.patient_id,
        od_sph=body.od_sph,
        od_cyl=body.od_cyl,
        od_ax=body.od_ax,
        od_prism=body.od_prism,
        od_base=body.od_base,
        od_add=body.od_add,
        os_sph=body.os_sph,
        os_cyl=body.os_cyl,
        os_ax=body.os_ax,
        os_prism=body.os_prism,
        os_base=body.os_base,
        os_add=body.os_add,
        glasses_purpose=body.glasses_purpose,
        glasses_type=body.glasses_type,
        issue_date=body.issue_date,
        term_months=body.term_months,
        note=body.note,
        doctor_signature_id=body.doctor_signature_id,
    )

    # Рассчитать дату окончания срока действия
    if body.term_months:
        new_prescription.expires_at = new_prescription.issue_date + timedelta(days=30 * body.term_months)
    else:
        new_prescription.expires_at = new_prescription.issue_date + timedelta(days=90)

    db.add(new_prescription)
    await db.commit()
    await db.refresh(new_prescription)
    return new_prescription


async def get_prescriptions_by_patient(
    db: AsyncSession,
    patient_id: str,
) -> List[OphthalmologicalPrescription]:
    """
    Возвращает все рецепты для пациента.
    """
    result = await db.execute(
        select(OphthalmologicalPrescription)
        .where(OphthalmologicalPrescription.patient_id == patient_id)
        .order_by(OphthalmologicalPrescription.issue_date.desc())
    )
    return result.scalars().all()

async def get_prescription_by_patient_new(
    db: AsyncSession,
    patient_id: str,
) -> list[OphthalmologicalPrescriptionRead]:
    """
    Возвращает все рецепты пациента, отсортированные по дате выдачи.
    """
    result = await db.execute(
        select(OphthalmologicalPrescription)
        .where(OphthalmologicalPrescription.patient_id == patient_id)
        .order_by(OphthalmologicalPrescription.issue_date.desc())
    )
    prescriptions = result.scalars().all()

    response = [
        OphthalmologicalPrescriptionRead.model_validate(p, from_attributes=True)
        for p in prescriptions
    ]
    return response

async def get_prescription_by_id(
    db: AsyncSession,
    prescription_id: str,
) -> Optional[OphthalmologicalPrescription]:
    """
    Возвращает офтальмологический рецепт по ID.
    """
    result = await db.execute(
        select(OphthalmologicalPrescription).where(OphthalmologicalPrescription.id == prescription_id)
    )
    return result.scalar_one_or_none()


async def update_prescription(
    db: AsyncSession,
    prescription_id: str,
    body: OphthalmologicalPrescriptionUpdate,
) -> Optional[OphthalmologicalPrescription]:
    """
    Обновляет офтальмологический рецепт.
    """
    data = body.dict(exclude_unset=True)
    if "term_months" in data and "issue_date" in data:
        data["expires_at"] = data["issue_date"] + timedelta(days=30 * data["term_months"])
    elif "term_months" in data:
        result = await db.execute(
            select(OphthalmologicalPrescription.issue_date).where(OphthalmologicalPrescription.id == prescription_id)
        )
        issue_date = result.scalar_one_or_none()
        if issue_date:
            data["expires_at"] = issue_date + timedelta(days=30 * data["term_months"])

    await db.execute(
        update(OphthalmologicalPrescription)
        .where(OphthalmologicalPrescription.id == prescription_id)
        .values(**data)
    )
    await db.commit()

    result = await db.execute(
        select(OphthalmologicalPrescription).where(OphthalmologicalPrescription.id == prescription_id)
    )
    return result.scalar_one_or_none()


async def delete_prescription(
    db: AsyncSession,
    prescription_id: str,
) -> bool:
    """
    Удаляет офтальмологический рецепт.
    """
    result = await db.execute(
        delete(OphthalmologicalPrescription)
        .where(OphthalmologicalPrescription.id == prescription_id)
        .returning(OphthalmologicalPrescription.id)
    )
    deleted = result.scalar_one_or_none()
    await db.commit()
    return bool(deleted)