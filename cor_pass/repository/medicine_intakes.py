from typing import List, Optional
from datetime import datetime, date, time, timedelta
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from cor_pass.database.models import MedicineIntake, MedicineSchedule, MedicineIntakeStatus
from cor_pass.schemas import MedicineIntakeCreate, MedicineIntakeUpdate


async def create_medicine_intake(
    db: AsyncSession,
    intake_data: MedicineIntakeCreate,
) -> MedicineIntake:
    intake = MedicineIntake(
        schedule_id=intake_data.schedule_id,
        user_cor_id=intake_data.user_cor_id,
        planned_datetime=intake_data.planned_datetime,
        status=intake_data.status,
        notes=intake_data.notes
    )
    db.add(intake)
    await db.commit()
    await db.refresh(intake)
    return intake


async def get_medicine_intake(
    db: AsyncSession,
    intake_id: str,
) -> Optional[MedicineIntake]:
    query = (
        select(MedicineIntake)
        .options(
            joinedload(MedicineIntake.schedule).joinedload(MedicineSchedule.medicine)
        )
        .where(MedicineIntake.id == intake_id)
    )
    result = await db.execute(query)
    return result.unique().scalar_one_or_none()


async def update_medicine_intake(
    db: AsyncSession,
    intake_id: str,
    intake_data: MedicineIntakeUpdate,
) -> Optional[MedicineIntake]:
    query = (
        select(MedicineIntake)
        .options(
            joinedload(MedicineIntake.schedule).joinedload(MedicineSchedule.medicine)
        )
        .where(MedicineIntake.id == intake_id)
    )
    result = await db.execute(query)
    intake = result.unique().scalar_one_or_none()
    
    if not intake:
        return None

    for field, value in intake_data.model_dump(exclude_unset=True).items():
        setattr(intake, field, value)

    if intake_data.status == MedicineIntakeStatus.COMPLETED and not intake.actual_datetime:
        intake.actual_datetime = datetime.now()

    await db.commit()
    await db.refresh(intake)
    return intake


async def get_schedule_intakes(
    db: AsyncSession,
    schedule_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[MedicineIntake]:
    query = (
        select(MedicineIntake)
        .options(
            joinedload(MedicineIntake.schedule).joinedload(MedicineSchedule.medicine)
        )
        .where(MedicineIntake.schedule_id == schedule_id)
    )
    
    if start_date:
        query = query.where(MedicineIntake.planned_datetime >= datetime.combine(start_date, time.min))
    if end_date:
        query = query.where(MedicineIntake.planned_datetime <= datetime.combine(end_date, time.max))
    
    query = query.order_by(MedicineIntake.planned_datetime)
    result = await db.execute(query)
    return result.scalars().unique().all()


async def get_user_intakes_by_date(
    db: AsyncSession,
    user_cor_id: str,
    target_date: date,
) -> List[MedicineIntake]:
    """
    Получает все приемы пользователя на конкретную дату.
    """
    query = (
        select(MedicineIntake)
        .options(
            joinedload(MedicineIntake.schedule).joinedload(MedicineSchedule.medicine)
        )
        .where(
            and_(
                MedicineIntake.user_cor_id == user_cor_id,
                MedicineIntake.planned_datetime >= datetime.combine(target_date, time.min),
                MedicineIntake.planned_datetime <= datetime.combine(target_date, time.max)
            )
        )
        .order_by(MedicineIntake.planned_datetime)
    )
    
    result = await db.execute(query)
    return result.unique().scalars().all()


async def get_paginated_user_intakes(
    db: AsyncSession,
    user_cor_id: str,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    Получает список всех приемов пользователя с пагинацией.
    Сортировка по planned_datetime в обратном порядке.
    """
    count_query = (
        select(func.count())
        .select_from(MedicineIntake)
        .where(MedicineIntake.user_cor_id == user_cor_id)
    )
    total = await db.scalar(count_query)


    query = (
        select(MedicineIntake)
        .options(
            joinedload(MedicineIntake.schedule).joinedload(MedicineSchedule.medicine)
        )
        .where(MedicineIntake.user_cor_id == user_cor_id)
        .order_by(MedicineIntake.planned_datetime.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


async def record_symptomatic_intake(
    db: AsyncSession,
    schedule: MedicineSchedule,
    actual_datetime: datetime,
    notes: Optional[str] = None
) -> MedicineIntake:
    """
    Регистрирует фактический прием симптоматического медикамента.
    
    Args:
        db: AsyncSession - сессия базы данных
        schedule: MedicineSchedule - расписание приема лекарства
        actual_datetime: datetime - фактическое время приема
        notes: Optional[str] - комментарий к приему
        
    Returns:
        MedicineIntake - запись о приеме лекарства
    """
    if not schedule.symptomatically:
        raise ValueError("This medicine is not for symptomatic use")

    intake = MedicineIntake(
        schedule_id=schedule.id,
        user_cor_id=schedule.user_cor_id,
        planned_datetime=datetime.combine(actual_datetime.date(), time(0, 0)),  
        actual_datetime=actual_datetime,  
        status=MedicineIntakeStatus.COMPLETED,
        notes=notes
    )
    db.add(intake)
    await db.commit()
    
    query = (
        select(MedicineIntake)
        .options(
            joinedload(MedicineIntake.schedule).joinedload(MedicineSchedule.medicine)
        )
        .where(MedicineIntake.id == intake.id)
    )
    result = await db.execute(query)
    loaded_intake = result.unique().scalar_one()
    
    return loaded_intake





async def generate_schedule_intakes(
    db: AsyncSession,
    schedule: MedicineSchedule,
) -> List[MedicineIntake]:
    """
    Генерирует записи о приеме лекарств на основе расписания
    """
    intakes = []
    current_date = schedule.start_date
    end_date = current_date + timedelta(days=schedule.duration_days) if schedule.duration_days else None

    while not end_date or current_date <= end_date:
        if schedule.symptomatically:
            # Для симптоматического приема создаем одну запись на день
            planned_datetime = datetime.combine(current_date, time(0, 0))
            intake = MedicineIntake(
                schedule_id=schedule.id,
                user_cor_id=schedule.user_cor_id,
                planned_datetime=planned_datetime,
                status=MedicineIntakeStatus.PLANNED,
                notes="При необходимости"
            )
            intakes.append(intake)
        else:
            # Для регулярного приема
            if schedule.intake_times:
                # Если указаны конкретные времена приема
                for intake_time in schedule.intake_times:
                    planned_datetime = datetime.combine(current_date, intake_time)
                    intake = MedicineIntake(
                        schedule_id=schedule.id,
                        user_cor_id=schedule.user_cor_id,
                        planned_datetime=planned_datetime,
                        status=MedicineIntakeStatus.PLANNED
                    )
                    intakes.append(intake)
            elif schedule.interval_minutes:
                # Если указан интервал
                current_time = datetime.combine(current_date, time(8, 0))  # Начинаем с 8 утра
                end_time = datetime.combine(current_date, time(22, 0))    # Заканчиваем в 22:00
                
                while current_time <= end_time:
                    intake = MedicineIntake(
                        schedule_id=schedule.id,
                        user_cor_id=schedule.user_cor_id,
                        planned_datetime=current_time,
                        status=MedicineIntakeStatus.PLANNED
                    )
                    intakes.append(intake)
                    current_time += timedelta(minutes=schedule.interval_minutes)

        current_date += timedelta(days=1)

    db.add_all(intakes)
    await db.commit()
    
    return intakes