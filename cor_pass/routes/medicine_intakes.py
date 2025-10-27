from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime

from cor_pass.database.db import get_db
from cor_pass.services.auth import auth_service
from cor_pass.database.models import User
from cor_pass.repository import medicine_intakes as repository
from cor_pass.schemas import (
    MedicineIntakeCreate,
    MedicineIntakeUpdate,
    MedicineIntakeResponse,
    PaginatedMedicineIntakeResponse
)
from cor_pass.services.access import user_access
from cor_pass.repository.medicine import get_user_schedule_by_id

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """Регистрация симптоматического приема лекарства"""
    schedule = await get_user_schedule_by_id(db=db, schedule_id=schedule_id)
    if not schedule or schedule.user_cor_id != current_user.cor_id:
        raise HTTPException(status_code=404, detail="Расписание не найдено")

    try:
        return await repository.record_symptomatic_intake(
            db=db,
            schedule=schedule,
            actual_datetime=datetime.now(),
            notes=notes
        )
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

    return await repository.update_medicine_intake(db=db, intake_id=intake_id, intake_data=intake_data)


@router.get(
    "/schedule/{schedule_id}", 
    response_model=List[MedicineIntakeResponse],
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

    return await repository.get_schedule_intakes(
        db=db,
        schedule_id=schedule_id,
        start_date=start_date,
        end_date=end_date
    )


@router.get(
    "/calendar/{date}",
    response_model=List[MedicineIntakeResponse],
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
    return await repository.get_user_intakes_by_date(
        db=db,
        user_cor_id=current_user.cor_id,
        target_date=date
    )


@router.get(
    "/history",
    response_model=PaginatedMedicineIntakeResponse,
    dependencies=[Depends(user_access)],
    summary="Получить историю всех приемов с пагинацией"
)
async def get_user_intake_history(
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(20, ge=1, le=100, description="Количество записей на странице"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Получение истории всех приемов лекарств с пагинацией.
    Сортировка по planned_datetime в обратном порядке (сначала новые).
    """
    return await repository.get_paginated_user_intakes(
        db=db,
        user_cor_id=current_user.cor_id,
        page=page,
        page_size=page_size
    )