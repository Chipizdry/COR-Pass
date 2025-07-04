from datetime import timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from typing import List
from sqlalchemy import and_, select


from cor_pass.database.models import BloodPressureMeasurement, User, Record, Tag
from cor_pass.schemas import BloodPressureMeasurementCreate, CreateRecordModel, UpdateRecordModel
from cor_pass.services.cipher import encrypt_data, decrypt_data, decrypt_user_key

from sqlalchemy.ext.asyncio import AsyncSession



async def create_measurement(
    db: AsyncSession, body: BloodPressureMeasurementCreate, user: User
)-> BloodPressureMeasurement:
    """
    Добавляет новое измерение артериального давления и пульса для текущего пользователя.
    """
    if body.measured_at.tzinfo is not None:
        measured_at_utc = body.measured_at.astimezone(timezone.utc)
    else:
        measured_at_utc = body.measured_at


    measured_at_naive = measured_at_utc.replace(tzinfo=None)
    new_measurement = BloodPressureMeasurement(
        user_id=user.id,
        systolic_pressure=body.systolic_pressure,
        diastolic_pressure=body.diastolic_pressure,
        pulse=body.pulse,
        measured_at=measured_at_naive,
    )
    db.add(new_measurement)
    await db.commit()
    await db.refresh(new_measurement)
    return new_measurement

async def get_measurements(
    db: AsyncSession, user: User
)-> List[BloodPressureMeasurement]:
    """
    Возвращает список всех измерений артериального давления и пульса для текущего пользователя.
    """
    # Запрос измерений для текущего пользователя, сортировка по убыванию даты измерения
    measurements = await db.execute(
        select(BloodPressureMeasurement)
        .where(BloodPressureMeasurement.user_id == user.id)
        .order_by(BloodPressureMeasurement.measured_at.desc())
    )
    return measurements.scalars().all()