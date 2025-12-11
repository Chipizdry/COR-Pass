from typing import List, Optional
from datetime import datetime, date, time, timedelta
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from cor_pass.database.models import MedicineIntake, MedicineSchedule, MedicineIntakeStatus, User
from cor_pass.schemas import MedicineIntakeCreate, MedicineIntakeUpdate
from cor_pass.repository.medicine.first_aid_kit import get_primary_first_aid_kit


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
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict:
    """
    Получает список всех приемов пользователя с пагинацией.
    Сортировка по planned_datetime в обратном порядке.
    
    Args:
        db: AsyncSession - сессия базы данных
        user_cor_id: str - идентификатор пользователя
        page: int - номер страницы (начиная с 1)
        page_size: int - количество записей на странице
        start_date: Optional[date] - начальная дата фильтрации (включительно)
        end_date: Optional[date] - конечная дата фильтрации (включительно)
    
    Returns:
        dict - словарь с items, total, page, page_size, total_pages
    """
    # Базовое условие фильтрации
    filters = [MedicineIntake.user_cor_id == user_cor_id]
    
    # Добавляем фильтры по датам, если они указаны
    if start_date:
        filters.append(func.date(MedicineIntake.planned_datetime) >= start_date)
    if end_date:
        filters.append(func.date(MedicineIntake.planned_datetime) <= end_date)
    
    # Запрос для подсчета общего количества
    count_query = (
        select(func.count())
        .select_from(MedicineIntake)
        .where(*filters)
    )
    total = await db.scalar(count_query)

    # Запрос для получения данных с пагинацией
    query = (
        select(MedicineIntake)
        .options(
            joinedload(MedicineIntake.schedule).joinedload(MedicineSchedule.medicine)
        )
        .where(*filters)
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
    notes: Optional[str] = None,
    first_aid_kit_id: Optional[str] = None,
    taken_quantity: Optional[int] = None,
    user: Optional[User] = None
) -> MedicineIntake:
    """
    Регистрирует фактический прием симптоматического медикамента.
    
    Args:
        db: AsyncSession - сессия базы данных
        schedule: MedicineSchedule - расписание приема лекарства
        actual_datetime: datetime - фактическое время приема
        notes: Optional[str] - комментарий к приему
        first_aid_kit_id: Optional[str] - ID аптечки, если не указано - используется основная
        taken_quantity: Optional[int] - количество принятых таблеток/доз
        user: Optional[User] - пользователь (для получения основной аптечки)
        
    Returns:
        MedicineIntake - запись о приеме лекарства
    """
    if not schedule.symptomatically:
        raise ValueError("This medicine is not for symptomatic use")

    # Если аптечка не указана, используем основную
    if not first_aid_kit_id and user:
        primary_kit = await get_primary_first_aid_kit(db, user)
        if primary_kit:
            first_aid_kit_id = primary_kit.id

    intake = MedicineIntake(
        schedule_id=schedule.id,
        user_cor_id=schedule.user_cor_id,
        planned_datetime=datetime.combine(actual_datetime.date(), time(0, 0)),  
        actual_datetime=actual_datetime,  
        status=MedicineIntakeStatus.COMPLETED,
        notes=notes,
        first_aid_kit_id=first_aid_kit_id,
        taken_quantity=taken_quantity
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
                    # Преобразуем в time объект, если это строка
                    if isinstance(intake_time, str):
                        # Парсим строку формата "HH:MM" или "HH:MM:SS"
                        time_parts = intake_time.split(":")
                        if len(time_parts) == 2:
                            intake_time = time(int(time_parts[0]), int(time_parts[1]))
                        elif len(time_parts) == 3:
                            intake_time = time(int(time_parts[0]), int(time_parts[1]), int(time_parts[2]))
                    
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


async def get_dates_with_intakes_in_range(
    db: AsyncSession,
    user_cor_id: str,
    start_date: date,
    end_date: date
) -> List[date]:
    """
    Получить список уникальных дат в указанном диапазоне, когда есть запланированные приемы.
    
    Args:
        db: Сессия базы данных
        user_cor_id: COR ID пользователя
        start_date: Начальная дата диапазона (включительно)
        end_date: Конечная дата диапазона (включительно)
        
    Returns:
        Список уникальных дат (date), отсортированных по возрастанию
    """
    # Преобразуем даты в datetime для сравнения
    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(end_date, time.max)
    
    # Запрос на получение уникальных дат
    query = (
        select(func.date(MedicineIntake.planned_datetime).label('intake_date'))
        .where(
            and_(
                MedicineIntake.user_cor_id == user_cor_id,
                MedicineIntake.planned_datetime >= start_datetime,
                MedicineIntake.planned_datetime <= end_datetime
            )
        )
        .distinct()
        .order_by('intake_date')
    )
    
    result = await db.execute(query)
    dates = [row[0] for row in result.all()]
    
    return dates


async def get_grouped_intakes_by_date_range(
    db: AsyncSession,
    user_cor_id: str,
    start_date: date,
    end_date: date
):
    """
    Получить приемы лекарств, сгруппированные по дням и времени.
    
    Args:
        db: Сессия базы данных
        user_cor_id: COR ID пользователя
        start_date: Начальная дата диапазона
        end_date: Конечная дата диапазона
        
    Returns:
        Словарь с группированными приемами по дням и времени
    """
    from collections import defaultdict
    from cor_pass.schemas import GroupedMedicineIntake, DailyMedicineIntakes, GroupedMedicineIntakesResponse
    
    # Преобразуем даты в datetime
    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(end_date, time.max)
    
    # Получаем все приемы в диапазоне с связанными данными
    query = (
        select(MedicineIntake)
        .options(
            joinedload(MedicineIntake.schedule).joinedload(MedicineSchedule.medicine)
        )
        .where(
            and_(
                MedicineIntake.user_cor_id == user_cor_id,
                MedicineIntake.planned_datetime >= start_datetime,
                MedicineIntake.planned_datetime <= end_datetime
            )
        )
        .order_by(MedicineIntake.planned_datetime)
    )
    
    result = await db.execute(query)
    intakes = result.scalars().unique().all()
    
    # Группируем по дате, затем по времени
    days_dict = defaultdict(lambda: defaultdict(list))
    
    for intake in intakes:
        intake_date = intake.planned_datetime.date()
        intake_time = intake.planned_datetime.strftime("%H:%M")
        days_dict[intake_date][intake_time].append(intake)
    
    # Формируем ответ
    days = []
    
    # Названия дней недели на русском
    day_names = {
        0: "Понедельник",
        1: "Вторник",
        2: "Среда",
        3: "Четверг",
        4: "Пятница",
        5: "Суббота",
        6: "Воскресенье"
    }
    
    for intake_date in sorted(days_dict.keys(), reverse=True):
        time_groups = []
        total_intakes = 0
        
        # Сортируем по времени (внутри дня от позднего к раннему)
        for intake_time in sorted(days_dict[intake_date].keys(), reverse=True):
            medicines_at_time = days_dict[intake_date][intake_time]
            total_intakes += len(medicines_at_time)
            
            # Создаем список MedicineIntakeResponse для каждого лекарства
            medicine_responses = []
            for intake in medicines_at_time:
                medicine_responses.append({
                    'id': intake.id,
                    'schedule_id': intake.schedule_id,
                    'user_cor_id': intake.user_cor_id,
                    'planned_datetime': intake.planned_datetime,
                    'actual_datetime': intake.actual_datetime,
                    'status': intake.status,
                    'notes': intake.notes,
                    'created_at': intake.created_at,
                    'updated_at': intake.updated_at,
                    'medicine_name': intake.medicine_name,
                    'medicine_dosage': intake.medicine_dosage,
                    'medicine_unit': intake.medicine_unit,
                    'medicine_intake_method': intake.schedule.medicine.intake_method if intake.schedule and intake.schedule.medicine else None,
                })
            
            time_groups.append(GroupedMedicineIntake(
                time=intake_time,
                planned_datetime=medicines_at_time[0].planned_datetime,
                medicines=medicine_responses,
                total_count=len(medicines_at_time)
            ))
        
        day_name = day_names[intake_date.weekday()]
        
        days.append(DailyMedicineIntakes(
            intake_date=intake_date,
            day_name=day_name,
            time_groups=time_groups,
            total_intakes=total_intakes
        ))
    
    return GroupedMedicineIntakesResponse(
        days=days,
        total_days=len(days),
        date_range={
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        }
    )