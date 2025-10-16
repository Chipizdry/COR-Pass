from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from cor_pass.database.models import Medicine, MedicineSchedule, User
from cor_pass.schemas import (
    MedicineCreate,
    MedicineUpdate,
    MedicineScheduleCreate,
    MedicineScheduleUpdate,
)


async def create_medicine(
    db: AsyncSession, body: MedicineCreate, user: User
) -> Medicine:
    """
    Создает новый медикамент для текущего пользователя.
    В зависимости от способа введения сохраняет соответствующие параметры.
    """
    method = body.method_data

    new_medicine = Medicine(
        name=body.name,
        active_substance=body.active_substance,
        intake_method=method.intake_method,
        dosage=getattr(method, "dosage", None),
        unit=getattr(method, "unit", None),
        concentration=getattr(method, "concentration", None),
        volume=getattr(method, "volume", None),
        created_by=user.cor_id,
    )

    db.add(new_medicine)
    await db.commit()
    await db.refresh(new_medicine)
    return new_medicine


# async def get_user_medicines(db: AsyncSession, user: User) -> List[Medicine]:
#     """
#     Возвращает все медикаменты текущего пользователя.
#     """
#     query = (
#         select(Medicine)
#         .options(selectinload(Medicine.schedules))
#         .where(Medicine.created_by == user.cor_id)
#     )
#     result = await db.execute(query)
#     return result.scalars().unique().all()

async def get_user_medicines_with_schedules(db: AsyncSession, user: User) -> List[Medicine]:
    """
    Возвращает все медикаменты текущего пользователя.
    """
    query = (
        select(Medicine)
        .options(selectinload(Medicine.schedules))
        .where(Medicine.created_by == user.cor_id)
    )
    result = await db.execute(query)
    return result.scalars().unique().all()


async def get_medicine_by_id(db: AsyncSession, medicine_id: int):
    result = await db.execute(
        select(Medicine).filter(Medicine.id == medicine_id).options(selectinload(Medicine.schedules))
    )
    return result.scalars().first()


async def update_medicine(
    db: AsyncSession, medicine: Medicine, body: MedicineUpdate
) -> Medicine:
    """
    Обновляет данные медикамента, включая параметры способа введения.
    """
    if body.name is not None:
        medicine.name = body.name
    if body.active_substance is not None:
        medicine.active_substance = body.active_substance

    if body.method_data:
        method = body.method_data
        medicine.intake_method = method.intake_method
        medicine.dosage = getattr(method, "dosage", None)
        medicine.unit = getattr(method, "unit", None)
        medicine.concentration = getattr(method, "concentration", None)
        medicine.volume = getattr(method, "volume", None)

    db.add(medicine)
    await db.commit()
    await db.refresh(medicine)
    return medicine


async def delete_medicine(db: AsyncSession, medicine: Medicine) -> None:
    """
    Удаляет медикамент.
    """
    await db.delete(medicine)
    await db.commit()




async def create_medicine_schedule(
    db: AsyncSession, body: MedicineScheduleCreate, user: User
) -> MedicineSchedule:
    """
    Создает новое расписание приёма для медикамента.
    """
    intake_times = (
        [t.strftime("%H:%M") for t in body.intake_times] if body.intake_times else None
    )
    new_schedule = MedicineSchedule(
        medicine_id=body.medicine_id,
        user_cor_id=user.cor_id,
        start_date=body.start_date,
        duration_days=body.duration_days,
        times_per_day=body.times_per_day,
        intake_times=intake_times,
        interval_minutes=body.interval_minutes,
        notes=body.notes,
        symptomatically=body.symptomatically
    )
    db.add(new_schedule)
    await db.commit()
    await db.refresh(new_schedule)
    return new_schedule


async def get_user_schedules(db: AsyncSession, user: User) -> List[MedicineSchedule]:
    """
    Возвращает все расписания медикаментов пользователя.
    """
    result = await db.execute(
        select(MedicineSchedule).where(MedicineSchedule.user_cor_id == user.cor_id)
    )
    return result.scalars().all()

async def update_schedule(
    db: AsyncSession, schedule_id: str, body: MedicineScheduleUpdate, user: User
) -> Optional[MedicineSchedule]:
    """
    Обновляет график приема лекарства.
    """
    schedule = await db.get(MedicineSchedule, schedule_id)
    if not schedule or schedule.user_cor_id != user.cor_id:
        return None

    if body.intake_times is not None:
        schedule.intake_times = [t.strftime("%H:%M") for t in body.intake_times]

    if body.duration_days is not None:
        schedule.duration_days = body.duration_days

    if body.times_per_day is not None:
        schedule.times_per_day = body.times_per_day

    if body.interval_minutes is not None:
        schedule.interval_minutes = body.interval_minutes

    if body.notes is not None:
        schedule.notes = body.notes

    if body.symptomatically is not None:
        schedule.symptomatically = body.symptomatically

    await db.commit()
    await db.refresh(schedule)
    return schedule

async def delete_medicine_schedule(db: AsyncSession, schedule: MedicineSchedule):
    """
    Удаляет расписание приёма медикамента.
    """
    await db.delete(schedule)
    await db.commit()

def deserialize_intake_times(intake_times):
    if not intake_times:
        return None
    return [datetime.strptime(t, "%H:%M").time() for t in intake_times]