from datetime import timezone
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from typing import List
from sqlalchemy import select


from cor_pass.database.models import BloodPressureMeasurement, User
from cor_pass.schemas import BloodPressureMeasurementCreate


from sqlalchemy.ext.asyncio import AsyncSession


async def create_measurement(
    db: AsyncSession, body: BloodPressureMeasurementCreate, user: User
) -> BloodPressureMeasurement:
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
) -> List[BloodPressureMeasurement]:
    """
    Возвращает список всех измерений артериального давления и пульса для текущего пользователя.
    """
    measurements = await db.execute(
        select(BloodPressureMeasurement)
        .where(BloodPressureMeasurement.user_id == user.id)
        .order_by(BloodPressureMeasurement.measured_at.desc())
    )
    return measurements.scalars().all()