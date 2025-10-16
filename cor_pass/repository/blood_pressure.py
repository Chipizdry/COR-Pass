from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Tuple

from typing import List
from sqlalchemy import func, select


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


async def get_measurements_paginated(
    db: AsyncSession,
    user_id: str,
    page: int = 1,
    page_size: int = 10,
    period: Optional[str] = None,  # all | week | month | custom
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Tuple[List[BloodPressureMeasurement], int]:
    """
    Возвращает список измерений давления и пульса с пагинацией и фильтрами по времени.
    """

    query = select(BloodPressureMeasurement).where(BloodPressureMeasurement.user_id == user_id)
    count_query = select(func.count()).select_from(BloodPressureMeasurement).where(
        BloodPressureMeasurement.user_id == user_id
    )

    now = datetime.utcnow()

    # --- фильтрация по периоду ---
    if period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now.replace(day=1)  # с начала месяца
    elif period == "all":
        start_date = None
        end_date = None

    if start_date:
        query = query.where(BloodPressureMeasurement.measured_at >= start_date)
        count_query = count_query.where(BloodPressureMeasurement.measured_at >= start_date)

    if end_date:
        query = query.where(BloodPressureMeasurement.measured_at <= end_date)
        count_query = count_query.where(BloodPressureMeasurement.measured_at <= end_date)

    # --- пагинация ---
    offset = (page - 1) * page_size
    query = query.order_by(BloodPressureMeasurement.measured_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    measurements = result.scalars().all()

    total_count_result = await db.execute(count_query)
    total_count = total_count_result.scalar_one()

    return measurements, total_count