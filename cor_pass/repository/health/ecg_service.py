from fastapi import UploadFile, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime
from uuid import UUID
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database import models as db_models

# Максимальный размер файла в байтах (10 МБ).
MAX_FILE_SIZE = 10 * 1024 * 1024 


async def create_ecg_measurement(
    db: AsyncSession,
    user_id: str,
    file: UploadFile,
    created_at: Optional[datetime] = None
) -> db_models.ECGMeasurement:
    """
    Сохраняет бинарные данные ЭКГ-файла в базу данных, 
    используя предоставленную модель.

    :param db: Сессия базы данных.
    :param user_id: ID пользователя, который загружает файл.
    :param file: Загружаемый файл ЭКГ.
    :param created_at: Необязательная дата и время измерения.
    :return: Созданный объект ECGMeasurement.
    """

    if not file.filename or not file.filename.lower().endswith(".cor-ekg"):
        raise HTTPException(
            status_code=400,
            detail="Неверное расширение файла. Ожидается '.cor-ekg'."
        )
    
    file_content = await file.read()
    
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Файл слишком большой. Максимальный размер: {MAX_FILE_SIZE / 1024 / 1024} МБ."
        )

    ecg_measurement = db_models.ECGMeasurement(
        user_id=user_id,
        file_data=file_content,
        file_name=file.filename,
        created_at=created_at 
    )

    db.add(ecg_measurement)
    await db.commit()
    await db.refresh(ecg_measurement)
    
    return ecg_measurement


async def get_ecg_measurement_data(db: AsyncSession, measurement_id: str) -> bytes:
    """
    Получает бинарные данные ЭКГ-измерения из базы данных.

    :param db: Сессия базы данных.
    :param measurement_id: ID измерения ЭКГ.
    :return: Бинарные данные файла.
    """
    ecg_measurement_query = await db.execute(
        select(db_models.ECGMeasurement)
        .where(db_models.ECGMeasurement.id == measurement_id)
    )
    ecg_measurement = ecg_measurement_query.scalars().first()
    return ecg_measurement.file_data



async def get_ecg_measurement(
    db: AsyncSession, 
    measurement_id: str, 
    user_id: str
) -> db_models.ECGMeasurement:
    """
    Получает запись ЭКГ-измерения из базы данных, 
    проверяя принадлежность пользователю.
    """

    result = await db.execute(
        select(db_models.ECGMeasurement).where(
            db_models.ECGMeasurement.id == measurement_id,
            db_models.ECGMeasurement.user_id == user_id
        )
    )
    ecg_entry = result.scalars().first()

    if not ecg_entry:
        raise HTTPException(
            status_code=404, 
            detail="Измерение ЭКГ не найдено или у вас нет доступа."
        )
    
    return ecg_entry