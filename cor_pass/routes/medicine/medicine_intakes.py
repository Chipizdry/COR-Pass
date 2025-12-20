from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime

from cor_pass.database.db import get_db
from cor_pass.services.user.auth import auth_service
from cor_pass.database.models import User
from cor_pass.repository.medicine import medicine_intakes as repository
from cor_pass.schemas import (
    MedicineIntakeCreate,
    MedicineIntakeUpdate,
    MedicineIntakeResponse,
    MedicineIntakeWithKitsResponse,
    MedicineIntakeListWithKitsResponse,
    PaginatedMedicineIntakeWithKitsResponse,
    GroupedMedicineIntakesWithKitsResponse,
    PaginatedMedicineIntakeResponse,
    GroupedMedicineIntakesResponse,
    FirstAidKitRead,
)
from cor_pass.services.shared.access import user_access
from cor_pass.repository.medicine.medicine import get_user_schedule_by_id
from cor_pass.repository.medicine.first_aid_kit import get_user_first_aid_kits, get_primary_first_aid_kit

router = APIRouter(prefix="/medicine-intakes", tags=["Medicine Intakes"])

# Тестово
# @router.post(
#     "/", 
#     response_model=MedicineIntakeResponse,
#     dependencies=[Depends(user_access)],
#     summary="Создать запись о приеме медикамента"
# )
# async def create_intake(
#     intake_data: MedicineIntakeCreate,
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(auth_service.get_current_user)
# ):
#     """Создание записи о приеме лекарства"""
#     # Проверяем доступ к расписанию
#     schedule = await get_user_schedule_by_id(db=db, schedule_id=intake_data.schedule_id)
#     if not schedule or schedule.user_cor_id != current_user.cor_id:
#         raise HTTPException(status_code=404, detail="Расписание не найдено")

#     # Проверяем, что user_cor_id совпадает с текущим пользователем
#     if intake_data.user_cor_id != current_user.cor_id:
#         raise HTTPException(status_code=403, detail="Нет доступа к созданию записи для другого пользователя")

#     return await repository.create_medicine_intake(db, intake_data)


@router.post(
    "/symptomatic/{schedule_id}",
    response_model=MedicineIntakeResponse,
    dependencies=[Depends(user_access)],
    summary="Зарегистрировать симптоматический прием"
)
async def create_symptomatic_intake(
    schedule_id: str,
    notes: Optional[str] = None,
    first_aid_kit_id: Optional[str] = None,
    taken_quantity: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Регистрация симптоматического приема лекарства.
    
    Параметры:
    - schedule_id: ID расписания
    - notes: Комментарий к приёму (опционально)
    - first_aid_kit_id: ID аптечки для списания (опционально, по умолчанию - основная)
    - taken_quantity: Количество принятых таблеток/доз (опционально)
    """
    schedule = await get_user_schedule_by_id(db=db, schedule_id=schedule_id)
    if not schedule or schedule.user_cor_id != current_user.cor_id:
        raise HTTPException(status_code=404, detail="Расписание не найдено")

    try:
        intake = await repository.record_symptomatic_intake(
            db=db,
            schedule=schedule,
            actual_datetime=datetime.now(),
            notes=notes,
            first_aid_kit_id=first_aid_kit_id,
            taken_quantity=taken_quantity,
            user=current_user
        )
        return intake
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch(
    "/{intake_id}", 
    response_model=MedicineIntakeResponse,
    dependencies=[Depends(user_access)],
    summary="Обновить статус приема"
)
async def update_intake(
    intake_id: str,
    intake_data: MedicineIntakeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """Обновление статуса приема лекарства"""
    intake = await repository.get_medicine_intake(db=db, intake_id=intake_id)
    if not intake:
        raise HTTPException(status_code=404, detail="Запись о приеме не найдена")

    if intake.user_cor_id != current_user.cor_id:
        raise HTTPException(status_code=403, detail="Нет доступа к обновлению этой записи")

    # Если аптечка не указана и у записи её нет — подставляем основную
    if not intake_data.first_aid_kit_id and not intake.first_aid_kit_id:
        primary_kit = await get_primary_first_aid_kit(db=db, user=current_user)
        if primary_kit:
            intake_data.first_aid_kit_id = primary_kit.id

    intake = await repository.update_medicine_intake(db=db, intake_id=intake_id, intake_data=intake_data)

    return intake


@router.get(
    "/available-kits",
    response_model=List[FirstAidKitRead],
    dependencies=[Depends(user_access)],
    summary="Получить список доступных аптечек для списания"
)
async def get_available_first_aid_kits(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Возвращает список всех аптечек пользователя.
    Основная аптечка отмечена флагом is_primary=True.
    Используется при регистрации приёма лекарства для выбора аптечки.
    """
    kits = await get_user_first_aid_kits(db=db, user=current_user)
    return kits


@router.get(
    "/schedule/{schedule_id}", 
    response_model=MedicineIntakeListWithKitsResponse,
    dependencies=[Depends(user_access)],
    summary="Получить историю приемов по расписанию"
)
async def get_schedule_intakes(
    schedule_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """Получение истории приемов лекарства по расписанию"""
    schedule = await get_user_schedule_by_id(db=db, schedule_id=schedule_id)
    if not schedule or schedule.user_cor_id != current_user.cor_id:
        raise HTTPException(status_code=404, detail="Расписание не найдено")

    items = await repository.get_schedule_intakes(
        db=db,
        schedule_id=schedule_id,
        start_date=start_date,
        end_date=end_date
    )
    available_kits_raw = await get_user_first_aid_kits(db=db, user=current_user)
    available_kits = [FirstAidKitRead.model_validate(k, from_attributes=True) for k in available_kits_raw]
    default_kit_id = next((kit.id for kit in available_kits if getattr(kit, "is_primary", False)), None)

    return MedicineIntakeListWithKitsResponse(
        items=items,
        available_kits=available_kits,
        default_first_aid_kit_id=default_kit_id,
    )


@router.get(
    "/calendar/{date}",
    response_model=MedicineIntakeListWithKitsResponse,
    dependencies=[Depends(user_access)],
    summary="Получить все приемы на конкретную дату"
)
async def get_calendar_intakes(
    date: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Получение всех приемов лекарств на конкретную дату.
    """
    items = await repository.get_user_intakes_by_date(
        db=db,
        user_cor_id=current_user.cor_id,
        target_date=date
    )
    available_kits_raw = await get_user_first_aid_kits(db=db, user=current_user)
    available_kits = [FirstAidKitRead.model_validate(k, from_attributes=True) for k in available_kits_raw]
    default_kit_id = next((kit.id for kit in available_kits if getattr(kit, "is_primary", False)), None)

    return MedicineIntakeListWithKitsResponse(
        items=items,
        available_kits=available_kits,
        default_first_aid_kit_id=default_kit_id,
    )


@router.get(
    "/calendar/month/{year}/{month}",
    response_model=List[date],
    dependencies=[Depends(user_access)],
    summary="Получить даты с запланированными приемами в месяце"
)
async def get_calendar_month_dates(
    year: int = Path(..., ge=1900, le=2100, description="Год"),
    month: int = Path(..., ge=1, le=12, description="Месяц (1-12)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Получение списка дат в указанном месяце, когда есть запланированные приемы лекарств.
    
    Возвращает массив дат (без времени), чтобы отобразить индикаторы на календаре.
    
    Параметры:
    - year: год (например, 2025)
    - month: месяц от 1 до 12 (например, 10 = октябрь)
    
    Пример:
    - GET /calendar/month/2025/10 - вернет все даты октября 2025, когда есть приемы
    
    Ответ: ["2025-10-05", "2025-10-12", "2025-10-18", "2025-10-25"]
    """
    from calendar import monthrange
    
    # Определяем первый и последний день месяца
    first_day = date(year, month, 1)
    last_day_num = monthrange(year, month)[1]
    last_day = date(year, month, last_day_num)
    
    return await repository.get_dates_with_intakes_in_range(
        db=db,
        user_cor_id=current_user.cor_id,
        start_date=first_day,
        end_date=last_day
    )


@router.get(
    "/history",
    response_model=PaginatedMedicineIntakeWithKitsResponse,
    dependencies=[Depends(user_access)],
    summary="Получить историю всех приемов с пагинацией"
)
async def get_user_intake_history(
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(20, ge=1, le=100, description="Количество записей на странице"),
    start_date: Optional[date] = Query(None, description="Начальная дата фильтрации (включительно)"),
    end_date: Optional[date] = Query(None, description="Конечная дата фильтрации (включительно)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Получение истории всех приемов лекарств с пагинацией.
    Сортировка по planned_datetime в обратном порядке (сначала новые).
    
    Параметры:
    - page: номер страницы (начиная с 1)
    - page_size: количество записей на странице (1-100)
    - start_date: начальная дата для фильтрации (опционально)
    - end_date: конечная дата для фильтрации (опционально)
    
    Примеры использования:
    - Все приемы: /history?page=1&page_size=20
    - За период: /history?start_date=2025-01-01&end_date=2025-01-31
    - С определенной даты: /history?start_date=2025-01-01
    - До определенной даты: /history?end_date=2025-12-31
    
    """
    # Валидация дат
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Начальная дата не может быть позже конечной даты"
        )
    
    base = await repository.get_paginated_user_intakes(
        db=db,
        user_cor_id=current_user.cor_id,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date
    )

    available_kits_raw = await get_user_first_aid_kits(db=db, user=current_user)
    available_kits = [FirstAidKitRead.model_validate(k, from_attributes=True) for k in available_kits_raw]
    default_kit_id = next((kit.id for kit in available_kits if getattr(kit, "is_primary", False)), None)

    return PaginatedMedicineIntakeWithKitsResponse(
        **base,
        available_kits=available_kits,
        default_first_aid_kit_id=default_kit_id,
    )


@router.get(
    "/grouped",
    response_model=GroupedMedicineIntakesWithKitsResponse,
    dependencies=[Depends(user_access)],
    summary="Получить приемы сгруппированные по дням и времени"
)
async def get_grouped_intakes(
    start_date: Optional[date] = Query(None, description="Начальная дата (по умолчанию: сегодня - 7 дней)"),
    end_date: Optional[date] = Query(None, description="Конечная дата (по умолчанию: сегодня)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Получение приемов лекарств, сгруппированных по дням и времени.
    
    Группировка:
    1. По дням (каждая дата - отдельная группа)
    2. Внутри дня - по времени (все лекарства на 18:00 вместе, на 10:00 вместе и т.д.)
    
    Сортировка: от новых к старым (сегодня -> вчера -> прошлое)
    
    Параметры:
    - start_date: начальная дата (по умолчанию - сегодня - 7 дней)
    - end_date: конечная дата (по умолчанию - сегодня)
    
    Примеры:
    - Последняя неделя: GET /grouped
    - Конкретная неделя: GET /grouped?start_date=2025-10-22&end_date=2025-10-29
    - Месяц: GET /grouped?start_date=2025-10-01&end_date=2025-10-31
    
    """
    # Валидация и установка значений по умолчанию
    from datetime import timedelta
    
    if not end_date:
        end_date = date.today()
    
    if not start_date:
        start_date = end_date - timedelta(days=7)
    
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Начальная дата не может быть позже конечной даты"
        )
    
    base = await repository.get_grouped_intakes_by_date_range(
        db=db,
        user_cor_id=current_user.cor_id,
        start_date=start_date,
        end_date=end_date
    )

    available_kits_raw = await get_user_first_aid_kits(db=db, user=current_user)
    available_kits = [FirstAidKitRead.model_validate(k, from_attributes=True) for k in available_kits_raw]
    default_kit_id = next((kit.id for kit in available_kits if getattr(kit, "is_primary", False)), None)

    return GroupedMedicineIntakesWithKitsResponse(
        **(base.model_dump(by_alias=True) if hasattr(base, "model_dump") else base),
        available_kits=available_kits,
        default_first_aid_kit_id=default_kit_id,
    )