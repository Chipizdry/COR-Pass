from io import BytesIO
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status

from typing import Optional
from datetime import datetime

from fastapi.responses import StreamingResponse

from cor_pass.database.db import get_db
from cor_pass.repository import ecg_service
from cor_pass.schemas import (
    ECGMeasurementResponse,
)
from cor_pass.database.models import User
from cor_pass.services.auth import auth_service
from loguru import logger
from cor_pass.services.access import user_access

from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix="/measurements/ecg", tags=["ECG Measurements"]
)

@router.post("/upload", 
            response_model=ECGMeasurementResponse,
            status_code=status.HTTP_201_CREATED,
            dependencies=[Depends(user_access)],
            summary="Добавить Кор-файл измерения ЭКГ",)
async def upload_ecg(
    file: UploadFile = File(...),
    created_at: Optional[datetime] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Загрузка файла с ЭКГ-измерением и сохранение его в базу данных.
    Принимает файл и опционально время, когда было сделано измерение.
    """
    try:
        new_ecg = await ecg_service.create_ecg_measurement(
            db=db,
            user_id=current_user.id,
            file=file,
            created_at=created_at
        )
        return new_ecg
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Произошла непредвиденная ошибка: {e}"
        )
    

@router.get("/{measurement_id}/raw", response_class=StreamingResponse, response_model=None)
async def get_raw_ecg_data(
    measurement_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Выводит сырые (raw) бинарные данные измерения ЭКГ по его ID.
    """

    ecg_entry = await ecg_service.get_ecg_measurement(
        db=db,
        measurement_id=measurement_id,
        user_id=current_user.id
    )

    return StreamingResponse(
        content=BytesIO(ecg_entry.file_data),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={ecg_entry.file_name}"}
    )