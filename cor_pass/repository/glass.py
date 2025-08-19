import asyncio
from datetime import datetime, time
import time as t
from io import BytesIO
import os
import socket
import tempfile
from threading import Timer
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.schemas import ChangeGlassStaining, Glass as GlassModelScheema, GlassPrinting, GlassResponseForPrinting, PrintLabel
from typing import Any, Dict, List
from sqlalchemy.orm import selectinload, joinedload
from cor_pass.database import models as db_models
from cor_pass.repository import case as repository_cases
from cor_pass.services.glass_and_cassette_printing import print_labels
from loguru import logger
from cor_pass.config.config import settings
from smb.SMBConnection import SMBConnection

async def get_glass(db: AsyncSession, glass_id: int) -> GlassModelScheema | None:
    """Асинхронно получает конкретное стекло, связанное с кассетой по её ID и номеру."""
    result = await db.execute(
        select(db_models.Glass).where(db_models.Glass.id == glass_id)
    )
    glass_db = result.scalar_one_or_none()
    if glass_db:
        return GlassModelScheema.model_validate(glass_db)

    return None

async def get_glass_preview_png(db: AsyncSession, glass_id: str):
    """
    Получает запись Glass по ID с проверкой наличия preview_url.
    """
    result = await db.execute(
        select(db_models.Glass)
        .options(
            joinedload(db_models.Glass.cassette)
            .joinedload(db_models.Cassette.sample)
            .joinedload(db_models.Sample.case)
        )
        .where(db_models.Glass.id == glass_id)
    )
    glass = result.scalars().first()
    if glass is None:
        return None
    # if not glass.preview_url:
    #     logger.error(f"preview_url не задан для стекла с ID {glass_id}")
    #     return None
    logger.debug(f"Найдено стекло с ID {glass_id}, preview_url: {glass.preview_url}")
    return glass

async def fetch_file_from_smb(path: str) -> str:
    """
    Загружает файл с SMB-сервера во временный файл и возвращает путь к нему.
    """
    loop = asyncio.get_running_loop()

    def _read_file():
        conn = SMBConnection(
            settings.smb_user,
            settings.smb_pass,
            my_name=socket.gethostname(),
            remote_name=settings.remote_name,
            use_ntlm_v2=True,
            is_direct_tcp=True,
        )
        if not conn.connect(settings.smb_server_ip, 445):
            logger.error(f"Не удалось подключиться к SMB-серверу {settings.smb_server_ip}")
            raise RuntimeError("Failed to connect to SMB server")

        prefix = f"\\\\{settings.smb_server_ip}\\{settings.smb_share}\\"
        if path.startswith(prefix):
            relative_path = path[len(prefix):].strip("/\\")
        else:
            relative_path = path.strip("/\\")

        logger.debug(f"Загрузка файла с SMB: {relative_path}")

        try:
            file_info = conn.getAttributes(settings.smb_share, relative_path)
            filesize = getattr(file_info, "file_size", None)
            if filesize is None:
                logger.error(f"Не удалось получить размер файла для {relative_path}")
                raise ValueError("Cannot get filesize from SMB file_info")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                start_time = datetime.now()
                conn.retrieveFile(settings.smb_share, relative_path, temp_file)
                temp_file.flush()
                logger.debug(f"Время загрузки файла: {datetime.now() - start_time} секунд")

                temp_file.seek(0, os.SEEK_END)
                file_size = temp_file.tell()
                if file_size != filesize:
                    logger.error(f"Ожидалось {filesize} байт, но записано {file_size} байт")
                    raise RuntimeError(f"Expected {filesize} bytes, but wrote {file_size} bytes")
                
                return temp_file.name
        finally:
            conn.close()

    return await loop.run_in_executor(None, _read_file)


async def fetch_file_from_smb_with_timeout(path: str) -> str:
    """
    Загружает файл с SMB-сервера во временный файл и возвращает путь к нему.
    """
    loop = asyncio.get_running_loop()

    def _read_file():
        conn = SMBConnection(
            settings.smb_user,
            settings.smb_pass,
            my_name=socket.gethostname(),
            remote_name=settings.remote_name,
            use_ntlm_v2=True,
            is_direct_tcp=True,
        )
        if not conn.connect(settings.smb_server_ip, 445):
            logger.error(f"Не удалось подключиться к SMB-серверу {settings.smb_server_ip}")
            raise RuntimeError("Failed to connect to SMB server")


        prefix = f"\\\\{settings.smb_server_ip}\\{settings.smb_share}\\"
        if path.startswith(prefix):
            relative_path = path[len(prefix):].strip("/\\")
        else:
            relative_path = path.strip("/\\")

        logger.debug(f"Загрузка файла с SMB: {relative_path}")

        try:
            file_info = conn.getAttributes(settings.smb_share, relative_path)
            filesize = getattr(file_info, "file_size", None)
            if filesize is None:
                logger.error(f"Не удалось получить размер файла для {relative_path}")
                raise ValueError("Cannot get filesize from SMB file_info")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                start_time = datetime.now()
                conn.retrieveFile(settings.smb_share, relative_path, temp_file)
                temp_file.flush()
                logger.debug(f"Время загрузки файла: {datetime.now() - start_time} секунд")

                temp_file.seek(0, os.SEEK_END)
                file_size = temp_file.tell()
                if file_size != filesize:
                    logger.error(f"Ожидалось {filesize} байт, но записано {file_size} байт")
                    raise RuntimeError(f"Expected {filesize} bytes, but wrote {file_size} bytes")
                
                return temp_file.name
        finally:
            conn.close()


    return await loop.run_in_executor(None, _read_file)


async def fetch_png_from_smb(path: str) -> BytesIO:
    """
    Загружает PNG-файл с SMB-сервера и возвращает его содержимое в BytesIO.
    """
    try:
        temp_file_path = await fetch_file_from_smb_with_timeout(path)
        try:
            with open(temp_file_path, "rb") as f:
                buf = BytesIO(f.read())
                logger.debug(f"PNG-файл успешно загружен в память: {path}")
                return buf
        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                logger.debug(f"Временный файл {temp_file_path} удалён")
    except Exception as e:
        logger.error(f"Ошибка при загрузке PNG-файла {path}: {str(e)}")
        raise

async def get_glass_svs(db: AsyncSession, glass_id: str):
    """
    Получает запись Glass по ID с проверкой наличия scan_url.
    """
    result = await db.execute(
        select(db_models.Glass)
        .options(
            joinedload(db_models.Glass.cassette)
            .joinedload(db_models.Cassette.sample)
            .joinedload(db_models.Sample.case)
        )
        .where(db_models.Glass.id == glass_id)
    )
    glass = result.scalars().first()
    if glass is None:
        logger.error(f"Стекло с ID {glass_id} не найдено")
        return None
    if not glass.scan_url:
        logger.error(f"scan_url не задан для стекла с ID {glass_id}")
        return None
    logger.debug(f"Найдено стекло с ID {glass_id}, scan_url: {glass.scan_url}")
    return glass

async def create_glass(
    db: AsyncSession,
    cassette_id: str,
    staining_type: db_models.StainingType = db_models.StainingType.HE,
    num_glasses: int = 1,
    printing: bool = False,
) -> List[GlassModelScheema]:
    """
    Асинхронно создает указанное количество стекол для существующей кассеты,
    обеспечивая последовательную нумерацию даже после удаления стекол.
    Обновляет счетчики стекол в кассете, семпле и кейсе.
    """

    cassette_result = await db.execute(
        select(db_models.Cassette)
        .where(db_models.Cassette.id == cassette_id)
        .options(
            selectinload(db_models.Cassette.sample).selectinload(db_models.Sample.case)
        )
    )
    db_cassette = cassette_result.scalar_one_or_none()
    if not db_cassette:
        raise ValueError(f"Кассету с ID {cassette_id} не найдено")

    db_sample = await db.get(db_models.Sample, db_cassette.sample_id)
    if not db_sample:
        raise ValueError(f"Семпл с ID {db_cassette.sample_id} не найден")

    db_case = await db.get(db_models.Case, db_sample.case_id)

    created_glasses: List[db_models.Glass] = []

    existing_glasses_result = await db.execute(
        select(db_models.Glass.glass_number)
        .where(db_models.Glass.cassette_id == db_cassette.id)
        .order_by(db_models.Glass.glass_number)
    )
    existing_glass_numbers = {
        result[0] for result in existing_glasses_result.fetchall()
    }

    next_glass_number = 0
    for _ in range(num_glasses):
        while next_glass_number in existing_glass_numbers:
            next_glass_number += 1

        db_glass = db_models.Glass(
            cassette_id=db_cassette.id,
            glass_number=next_glass_number,
            staining=staining_type,
            is_printed=printing,
        )
        db.add(db_glass)
        created_glasses.append(db_glass)
        existing_glass_numbers.add(next_glass_number)
        next_glass_number += 1

        db_cassette.glass_count += 1
        db_sample.glass_count += 1
        db_case.glass_count += 1

    await db.commit()

    await db.refresh(db_cassette)
    await db.refresh(db_sample)
    await db.refresh(db_case)
    for glass in created_glasses:
        await db.refresh(glass)
        await repository_cases._update_ancestor_statuses_from_glass(db=db, glass=glass)

    return [
        GlassModelScheema.model_validate(glass).model_dump()
        for glass in created_glasses
    ]


async def delete_glasses(db: AsyncSession, glass_ids: List[str]) -> Dict[str, Any]:
    """Асинхронно удаляет несколько стекол по их ID."""
    deleted_count = 0
    not_found_ids: List[str] = []

    for glass_id in glass_ids:
        result = await db.execute(
            select(db_models.Glass).where(db_models.Glass.id == glass_id)
        )
        db_glass = result.scalar_one_or_none()
        if db_glass:

            cassette_result = await db.execute(
                select(db_models.Cassette)
                .where(db_models.Cassette.id == db_glass.cassette_id)
                .options(
                    selectinload(db_models.Cassette.sample).selectinload(
                        db_models.Sample.case
                    )
                )
            )
            db_cassette = cassette_result.scalar_one_or_none()
            if not db_cassette:
                raise ValueError(f"Касету з ID {db_glass.cassette_id} не знайдено")

            sample_result = await db.execute(
                select(db_models.Sample)
                .where(db_models.Sample.id == db_cassette.sample_id)
                .options(selectinload(db_models.Sample.case))
            )
            db_sample = sample_result.scalar_one_or_none()
            if not db_sample:
                raise ValueError(f"Семпл с ID {db_cassette.sample_id} не найден")

            db_case_id = db_sample.case_id
            db_case = await repository_cases.get_single_case(db=db, case_id=db_case_id)

            db_sample = db_sample
            db_case = db_case
            await repository_cases._update_ancestor_statuses_from_glass(
                db=db, glass=db_glass
            )
            await db.delete(db_glass)
            deleted_count += 1

            db_cassette.glass_count -= 1
            db_sample.glass_count -= 1
            db_case.glass_count -= 1
            await db.commit()
            await db.refresh(db_cassette)
            await db.refresh(db_sample)
            await db.refresh(db_case)
        else:
            not_found_ids.append(glass_id)

    await db.commit()

    response = {"deleted_count": deleted_count}
    if not_found_ids:
        response["not_found_ids"] = not_found_ids
    response["message"] = f"Успешно удалено {deleted_count} стекол."
    if not_found_ids:
        response["message"] += f" Стекла с ID {', '.join(not_found_ids)} не найдены."

    return response


async def change_staining(
    db: AsyncSession, glass_id: int, body: ChangeGlassStaining
) -> GlassModelScheema | None:
    """Асинхронно получает конкретное стекло, связанное с кассетой по её ID и номеру."""
    result = await db.execute(
        select(db_models.Glass).where(db_models.Glass.id == glass_id)
    )
    glass_db = result.scalar_one_or_none()
    if glass_db:
        glass_db.staining = body.staining_type
        await db.commit()
        await db.refresh(glass_db)
        return GlassModelScheema.model_validate(glass_db)

    return None


async def change_printing_status(
    db: AsyncSession, glass_id: int, printing: bool
) -> GlassModelScheema | None:
    """Меняем статус печати стекла"""
    result = await db.execute(
        select(db_models.Glass).where(db_models.Glass.id == glass_id)
    )
    glass_db = result.scalar_one_or_none()
    if glass_db:
        glass_db.is_printed = printing
        await db.commit()
        await db.refresh(glass_db)
        await repository_cases._update_ancestor_statuses_from_glass(
            db=db, glass=glass_db
        )
        return GlassModelScheema.model_validate(glass_db)

    return None


async def get_full_glass_info(db: AsyncSession, glass_id: str) -> GlassResponseForPrinting:
    result = await db.execute(
        select(db_models.Glass).where(db_models.Glass.id == glass_id)
    )
    db_glass = result.scalar_one_or_none()
    if db_glass:

        cassette_result = await db.execute(
            select(db_models.Cassette)
            .where(db_models.Cassette.id == db_glass.cassette_id)
            .options(
                selectinload(db_models.Cassette.sample).selectinload(
                    db_models.Sample.case
                )
            )
        )
        db_cassette = cassette_result.scalar_one_or_none()
        if not db_cassette:
            raise ValueError(f"Касету з ID {db_glass.cassette_id} не знайдено")

        sample_result = await db.execute(
            select(db_models.Sample)
            .where(db_models.Sample.id == db_cassette.sample_id)
            .options(selectinload(db_models.Sample.case))
        )
        db_sample = sample_result.scalar_one_or_none()
        if not db_sample:
            raise ValueError(f"Семпл с ID {db_cassette.sample_id} не найден")

        db_case_id = db_sample.case_id
        db_case = await repository_cases.get_single_case(db=db, case_id=db_case_id)
        db_sample = db_sample
        db_case = db_case
    response = GlassResponseForPrinting( 
    case_code=db_case.case_code,
    sample_number=db_sample.sample_number,
    cassette_number=db_cassette.cassette_number,
    glass_number=db_glass.glass_number,
    staining=db_glass.staining,
    patient_cor_id=db_case.patient_id)

    return response


async def print_glass_data(
    data: GlassPrinting, db: AsyncSession, request: Request
):
    db_glass = await get_full_glass_info(db, data.glass_id)
    if db_glass is None:
        raise HTTPException(status_code=404, detail=f"Стекло с ID {data.glass_id} не найдено в базе данных")

    clinic_name = data.clinic_name
    case_code = db_glass.case_code
    sample_number=db_glass.sample_number
    cassette_number=db_glass.cassette_number
    glass_number=db_glass.glass_number
    staining=db_glass.staining
    hooper=data.hooper
    patient_cor_id=db_glass.patient_cor_id
        
    content = f"{clinic_name}|{case_code}|{sample_number}|{cassette_number}|L{glass_number}|{staining}|{hooper}|{patient_cor_id}"

    label_to_print = PrintLabel(
        model_id=data.model_id, 
        content=content,
        uuid=data.glass_id
    )
 
    print_result = await print_labels(printer_ip=data.printer_ip, labels_to_print=[label_to_print], request=request)

    return print_result