from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.models import CerboMeasurement, EnergeticSchedule
from cor_pass.schemas import (
    EnergeticScheduleBase,
    EnergeticScheduleCreate,
    FullDeviceMeasurementCreate,
    FullDeviceMeasurementResponse,
)
from loguru import logger


async def create_full_device_measurement(
    db: AsyncSession, data: FullDeviceMeasurementCreate
) -> FullDeviceMeasurementResponse:
    """Сохраняет полное измерение устройства в базу данных."""
    try:
        db_measurement = CerboMeasurement(**data.model_dump())
        db.add(db_measurement)
        await db.commit()
        await db.refresh(db_measurement)
        return FullDeviceMeasurementResponse.model_validate(db_measurement)
    except Exception as e:
        logger.error(f"Error saving full device measurement to DB: {e}", exc_info=True)
        raise


async def get_device_measurements_paginated(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 10,
    object_name: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Tuple[List[CerboMeasurement], int]:
    """
    Получает записи CerboMeasurement с пагинацией и необязательными фильтрами.
    """
    query = select(CerboMeasurement)
    count_query = select(func.count()).select_from(CerboMeasurement)

    if object_name:
        query = query.where(CerboMeasurement.object_name == object_name)
        count_query = count_query.where(CerboMeasurement.object_name == object_name)

    if start_date:
        query = query.where(CerboMeasurement.measured_at >= start_date)
        count_query = count_query.where(CerboMeasurement.measured_at >= start_date)

    if end_date:
        query = query.where(CerboMeasurement.measured_at <= end_date)
        count_query = count_query.where(CerboMeasurement.measured_at <= end_date)

    offset = (page - 1) * page_size
    query = (
        query.offset(offset)
        .limit(page_size)
        .order_by(CerboMeasurement.measured_at.desc())
    )

    result = await db.execute(query)
    measurements = result.scalars().all()

    total_count_result = await db.execute(count_query)
    total_count = total_count_result.scalar_one()

    return measurements, total_count


async def create_schedule(
    db: AsyncSession, schedule_data: EnergeticScheduleCreate
) -> EnergeticSchedule:
    """Создает новое расписание в базе данных."""
    duration_delta = timedelta(
        hours=schedule_data.duration_hours, minutes=schedule_data.duration_minutes
    )

    temp_start_datetime = datetime.combine(
        datetime.min.date(), schedule_data.start_time
    )
    calculated_end_time = (temp_start_datetime + duration_delta).time()

    db_schedule = EnergeticSchedule(
        start_time=schedule_data.start_time,
        duration=duration_delta,
        end_time=calculated_end_time,
        grid_feed_w=schedule_data.grid_feed_w,
        battery_level_percent=schedule_data.battery_level_percent,
        charge_battery_value=schedule_data.charge_battery_value,
        is_manual_mode=schedule_data.is_manual_mode,
    )
    db.add(db_schedule)
    await db.commit()
    await db.refresh(db_schedule)
    return db_schedule


async def get_schedule_by_id(
    db: AsyncSession, schedule_id: str
) -> Optional[EnergeticSchedule]:
    """Получает расписание по его ID."""
    result = await db.execute(
        select(EnergeticSchedule).where(EnergeticSchedule.id == schedule_id)
    )
    return result.scalars().first()


async def get_all_schedules(db: AsyncSession) -> List[EnergeticSchedule]:
    """Получает все расписания (активные и неактивные), отсортированные по времени начала."""
    result = await db.execute(
        select(EnergeticSchedule).order_by(EnergeticSchedule.start_time)
    )
    return result.scalars().all()


async def update_schedule(
    db: AsyncSession, schedule_id: str, schedule_data: EnergeticScheduleBase
) -> Optional[EnergeticSchedule]:
    """Обновляет существующее расписание по ID."""
    db_schedule = await get_schedule_by_id(db, schedule_id)
    if not db_schedule:
        return None

    duration_delta = timedelta(
        hours=schedule_data.duration_hours, minutes=schedule_data.duration_minutes
    )

    temp_start_datetime = datetime.combine(
        datetime.min.date(), schedule_data.start_time
    )
    calculated_end_time = (temp_start_datetime + duration_delta).time()

    db_schedule.start_time = schedule_data.start_time
    db_schedule.duration = duration_delta
    db_schedule.end_time = calculated_end_time
    db_schedule.grid_feed_w = schedule_data.grid_feed_w
    db_schedule.battery_level_percent = schedule_data.battery_level_percent
    db_schedule.charge_battery_value = schedule_data.charge_battery_value
    db_schedule.is_manual_mode = schedule_data.is_manual_mode

    await db.commit()
    await db.refresh(db_schedule)
    return db_schedule


async def delete_schedule(db: AsyncSession, schedule_id: str) -> bool:
    """Удаляет расписание по ID."""
    result = await db.execute(
        delete(EnergeticSchedule).where(EnergeticSchedule.id == schedule_id)
    )
    await db.commit()
    return result.rowcount > 0


async def update_schedule_is_active_status(
    db: AsyncSession, schedule_id: str, is_active_status: bool
):
    """Обновляет статус активности расписания."""
    stmt = (
        update(EnergeticSchedule)
        .where(EnergeticSchedule.id == schedule_id)
        .values(is_active=is_active_status)
    )
    await db.execute(stmt)
    await db.commit()