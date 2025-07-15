from datetime import datetime
import uuid
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional

from cor_pass.repository import records as repository_record
from cor_pass.database.db import get_db
from cor_pass.repository.blood_pressure import create_measurement, get_measurements
from cor_pass.schemas import (
    BloodPressureMeasurementCreate,
    BloodPressureMeasurementResponse,
    BloodPressureMeasures,
    CreateRecordModel,
    NewBloodPressureMeasurementResponse,
    RecordResponse,
    TonometrIncomingData,
    UpdateRecordModel,
    MainscreenRecordResponse,
)
from cor_pass.database.models import User
from cor_pass.config.config import settings
from cor_pass.services.auth import auth_service
from loguru import logger
from cor_pass.services.access import user_access

from cor_pass.services.cipher import decrypt_data, decrypt_user_key
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/measurements/blood_pressure", tags=["Blood Pressure Measurements"])

@router.post(
    "/",
    response_model=BloodPressureMeasurementResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_access)],
    summary="Добавить новое измерение артериального давления"
)
async def create_bp_measurement(
    body: BloodPressureMeasurementCreate,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db)
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
        user_id= new_measurement.user_id,
        created_at= new_measurement.created_at
    )
    return response




@router.get(
    "/",
    response_model=List[BloodPressureMeasurementResponse],
    dependencies=[Depends(user_access)],
    summary="Получить все измерения артериального давления текущего пользователя"
)
async def get_pb_measurements(
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Возвращает список всех измерений артериального давления и пульса для текущего пользователя.
    """
    measurements = await get_measurements(db=db, user=current_user)
    return measurements



@router.post(
    "/record",
    response_model=NewBloodPressureMeasurementResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_service.get_current_user)],
    summary="Принять данные измерения давления от тонометра в реальном формате"
)
async def receive_tonometer_data(
    incoming_data: TonometrIncomingData,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    systolic_pressure_val: Optional[int] = None
    diastolic_pressure_val: Optional[int] = None
    pulse_val: Optional[int] = None

    if len(incoming_data.results_list) >= 3:
        try:
            clean_systolic_str = incoming_data.results_list[0].measures.strip('"')
            systolic_pressure_val = int(clean_systolic_str)
            logger.debug(f"Извлечено систолическое давление: {systolic_pressure_val}")

            clean_diastolic_str = incoming_data.results_list[1].measures.strip('"')
            diastolic_pressure_val = int(clean_diastolic_str)
            logger.debug(f"Извлечено диастолическое давление: {diastolic_pressure_val}")

            clean_pulse_str = incoming_data.results_list[2].measures.strip('"')
            pulse_val = int(clean_pulse_str)
            logger.debug(f"Извлечен пульс: {pulse_val}")

        except ValueError as e:
            logger.error(f"Ошибка преобразования строковых мер в число: {e}. Проверьте формат данных (measures: \"123\" или \"\\\"123\\\"\").")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат числовых значений в measurements (measures должны быть строками-числами)."
            )
        except IndexError:
            logger.error("Недостаточно элементов в списке результатов для извлечения давления и пульса.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неполные данные измерений: ожидалось как минимум 3 значения (систолическое, диастолическое, пульс)."
            )
    else:
        logger.error(f"Ожидалось как минимум 3 элемента в 'results', получено {len(incoming_data.results_list)}. Неполные данные.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неполные данные измерений: ожидалось как минимум 3 значения (систолическое, диастолическое, пульс)."
        )

    if systolic_pressure_val is None or diastolic_pressure_val is None:
        logger.error("Систолическое или диастолическое давление не были успешно извлечены из входящих данных.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось извлечь валидные измерения давления (систолического/диастолического) из запроса."
        )

    try:
        measurement_data = BloodPressureMeasurementCreate(
            systolic_pressure=systolic_pressure_val,
            diastolic_pressure=diastolic_pressure_val,
            pulse=pulse_val, 
            measured_at=incoming_data.created_at
        )

        new_measurement = await create_measurement(db=db, body=measurement_data, user=current_user)
        return NewBloodPressureMeasurementResponse(
            id=new_measurement.id,
            systolic_pressure=new_measurement.systolic_pressure,
            diastolic_pressure=new_measurement.diastolic_pressure,
            pulse=new_measurement.pulse,
            measured_at=new_measurement.measured_at,
            user_id=new_measurement.user_id,
            created_at=new_measurement.created_at
        )

    except Exception as e:
        import traceback
        logger.error(f"Ошибка при сохранении объединенного измерения: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Не удалось сохранить объединенное измерение: {e}")
