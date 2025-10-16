from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional

from cor_pass.database.db import get_db
from cor_pass.repository.blood_pressure import create_measurement, get_measurements, get_measurements_paginated
from cor_pass.repository.patient import get_patient_by_corid
from cor_pass.repository.person import get_user_by_corid
from cor_pass.schemas import (
    BloodPressureMeasurementCreate,
    BloodPressureMeasurementResponse,
    PaginatedBloodPressureResponse,
)
from cor_pass.database.models import User
from cor_pass.services.auth import auth_service
from loguru import logger
from cor_pass.services.access import user_access, doctor_access

from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix="/measurements/blood_pressure", tags=["Blood Pressure Measurements"]
)


@router.post(
    "/",
    response_model=BloodPressureMeasurementResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_access)],
    summary="Добавить новое измерение артериального давления",
)
async def create_bp_measurement(
    body: BloodPressureMeasurementCreate,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Добавляет новое измерение артериального давления и пульса для текущего пользователя.
    """
    new_measurement = await create_measurement(db=db, body=body, user=current_user)
    response = BloodPressureMeasurementResponse(
        systolic_pressure=new_measurement.systolic_pressure,
        diastolic_pressure=new_measurement.diastolic_pressure,
        pulse=new_measurement.pulse,
        measured_at=new_measurement.measured_at,
        id=new_measurement.id,
        user_id=new_measurement.user_id,
        created_at=new_measurement.created_at,
    )
    return response


@router.get(
    "/my",
    response_model=List[BloodPressureMeasurementResponse],
    dependencies=[Depends(user_access)],
    summary="Получить все измерения артериального давления текущего пользователя",
)
async def get_pb_measurements(
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает список всех измерений артериального давления и пульса для текущего пользователя.
    """
    measurements = await get_measurements(db=db, user=current_user)
    return measurements



@router.get(
    "/list",
    response_model=PaginatedBloodPressureResponse,
    dependencies=[Depends(doctor_access)],
    summary="Получить измерения артериального давления и пульса пациента",
)
async def get_pb_measurements(
    patient_cor_id: str,
    page: int = Query(1, ge=1, description="Номер страницы (начиная с 1)"),
    page_size: int = Query(10, ge=1, le=1000, description="Количество элементов на странице"),
    period: Optional[str] = Query("all", regex="^(all|week|month|custom)$", description="Период выборки: all, week, month, custom"),
    start_date: Optional[datetime] = Query(None, description="Начальная дата (только если period=custom), ISO 8601, например '2023-01-01T00:00:00'"),
    end_date: Optional[datetime] = Query(None, description="Конечная дата (только если period=custom), ISO 8601, например '2023-01-01T00:00:00'"),
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает список измерений давления и пульса пациента с фильтрами и пагинацией:
    - all: все время
    - week: последняя неделя
    - month: текущий месяц
    - custom: от start_date до end_date
    """
    user = await get_user_by_corid(db=db, cor_id=patient_cor_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User/Patient not found"
        )
    measurements, total = await get_measurements_paginated(
        db=db,
        user_id=user.id,
        page=page,
        page_size=page_size,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )

    return PaginatedBloodPressureResponse(
        items=measurements,
        total=total,
        page=page,
        page_size=page_size,
    )