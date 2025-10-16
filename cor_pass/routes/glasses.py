import asyncio
from datetime import datetime
from io import BytesIO
import os
import tempfile
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from openslide import OpenSlide
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.db import get_db
from cor_pass.database.models import Glass
from cor_pass.schemas import (
    ChangeGlassStaining,
    DeleteGlassesRequest,
    DeleteGlassesResponse,
    Glass as GlassModelScheema,
    GlassCreate,
    GlassPrinting,
    UploadGlassSVSResponse
)
from cor_pass.repository import glass as glass_service
from typing import List, Optional

from cor_pass.services.access import doctor_access
from loguru import logger
from cor_pass.config.config import settings
from scan_worker.smbprotocol_worker import save_file_to_smb, save_file_to_smb_manual

router = APIRouter(prefix="/glasses", tags=["Glass"])


@router.post(
    "/create",
    dependencies=[Depends(doctor_access)],
    response_model=List[GlassModelScheema],
)
async def create_glass_for_cassette(
    body: GlassCreate,
    printing: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Создаем указанное количество стёкол"""
    return await glass_service.create_glass(
        db=db,
        cassette_id=body.cassette_id,
        num_glasses=body.num_glasses,
        staining_type=body.staining_type,
        printing=printing,
    )


@router.get(
    "/{glass_id}",
    response_model=GlassModelScheema,
    dependencies=[Depends(doctor_access)],
)
async def read_glass_info(glass_id: str, db: AsyncSession = Depends(get_db)):
    """Получаем информацию о стекле по его ID."""
    db_glass = await glass_service.get_glass(db=db, glass_id=glass_id)
    if db_glass is None:
        raise HTTPException(status_code=404, detail="Glass not found")
    return db_glass


@router.delete(
    "/delete",
    response_model=DeleteGlassesResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
)
async def delete_glasses_endpoint(
    request_body: DeleteGlassesRequest, db: AsyncSession = Depends(get_db)
):
    """Удаляет несколько стекол по их ID."""
    result = await glass_service.delete_glasses(db=db, glass_ids=request_body.glass_ids)
    return result


@router.patch(
    "/{glass_id}/staining",
    response_model=GlassModelScheema,
    dependencies=[Depends(doctor_access)],
)
async def change_glass_staining(
    glass_id: str, body: ChangeGlassStaining, db: AsyncSession = Depends(get_db)
):
    """Получаем информацию о стекле по его ID."""
    db_glass = await glass_service.change_staining(db=db, glass_id=glass_id, body=body)
    if db_glass is None:
        raise HTTPException(status_code=404, detail="Glass not found")
    return db_glass


@router.patch(
    "/{glass_id}/printed",
    response_model=Optional[GlassModelScheema],
    dependencies=[Depends(doctor_access)],
)
async def change_glass_printing_status(
    data: GlassPrinting, request: Request, db: AsyncSession = Depends(get_db)
):
    """Меняем статус печати стекла"""

    print_result = await glass_service.print_glass_data(db=db, data=data, request=request)

    if print_result and print_result.get("success"):
        updated_glass = await glass_service.change_printing_status(
            db=db, glass_id=data.glass_id, printing=data.printing 
        )
        if updated_glass is None:
            logger.warning(f"Предупреждение: Стекло {data.glass_id} не найдено для обновления статуса после успешной печати.")
        
        return updated_glass


# Путь к заглушному PNG-файлу
PLACEHOLDER_PATH = "cor_pass/static/assets/dummy_glass.png"

@router.get(
    "/{glass_id}/preview",
    dependencies=[Depends(doctor_access)],
)
async def get_glass_preview(glass_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получает PNG-превью для стекла по его ID. Возвращает заглушный PNG при ошибке.
    """
    db_glass = await glass_service.get_glass_preview_png(db=db, glass_id=glass_id)
    if db_glass is None:
        logger.error(f"Стекло или preview_url не найдены для ID {glass_id}")
        raise HTTPException(status_code=404, detail="Glass or preview URL not found")
    
    if not settings.smb_enabled:
        logger.debug(f"SMB отключён, возвращаем заглушный PNG для стекла {glass_id}")
        try:
            with open(PLACEHOLDER_PATH, "rb") as f:
                placeholder_buf = BytesIO(f.read())
                placeholder_buf.seek(0)
                return StreamingResponse(placeholder_buf, media_type="image/png")
        except FileNotFoundError:
            logger.error(f"Заглушный файл {PLACEHOLDER_PATH} не найден")
            raise HTTPException(status_code=500, detail="Placeholder PNG not found")

    try:
        buf = await glass_service.fetch_png_from_smb(db_glass.preview_url)
        buf.seek(0)
        logger.debug(f"Успешно возвращено превью для стекла {glass_id}")
        return StreamingResponse(buf, media_type="image/png")
    except asyncio.TimeoutError as e:
        logger.error(f"Таймаут при получении превью для стекла {glass_id}: {str(e)}")
        with open(PLACEHOLDER_PATH, "rb") as f:
            placeholder_buf = BytesIO(f.read())
            placeholder_buf.seek(0)
            return StreamingResponse(placeholder_buf, media_type="image/png")
    except Exception as e:
        logger.error(f"Ошибка при получении превью для стекла {glass_id}: {str(e)}")
        with open(PLACEHOLDER_PATH, "rb") as f:
            placeholder_buf = BytesIO(f.read())
            placeholder_buf.seek(0)
            return StreamingResponse(placeholder_buf, media_type="image/png")
        


@router.post("/upload-glass/{glass_id}",
    dependencies=[Depends(doctor_access)],
    response_model=Optional[UploadGlassSVSResponse])
async def upload_glass_file(
    glass_id: str,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    if not file.filename.lower().endswith(".svs"):
        raise HTTPException(status_code=400, detail="Можно загрузить только .svs")
    
    if not settings.smb_enabled:
        logger.debug("Загрузка скана недоступна")
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="You are not connected to NAS / can not save svs scan",
        )
    try:
        data = BytesIO(await file.read())
        today = datetime.now().strftime("%Y-%m-%d")
        svs_path = f"{settings.base_path}/{today}/{file.filename}"
        smb_full_path = f"\\\\{settings.smb_server_ip}\\{settings.smb_share}\\{svs_path}"

        await save_file_to_smb_manual(data, smb_full_path)

        data.seek(0)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".svs") as tmp:
            tmp.write(data.read())
            tmp.flush()
            slide = OpenSlide(tmp.name)
            preview = slide.get_thumbnail((512, 512))

        buf = BytesIO()
        preview.save(buf, format="PNG")
        buf.seek(0)

        preview_path = smb_full_path.replace(".svs", ".png")
        await save_file_to_smb_manual(buf, preview_path)

        glass = await db.get(Glass, glass_id)
        if not glass:
            raise HTTPException(status_code=404, detail="Стекло не найдено")

        glass.scan_url = smb_full_path
        glass.preview_url = preview_path
        await db.commit()
        response = UploadGlassSVSResponse(
            preview_url=preview_path,
            scan_url=smb_full_path
        )

        return response

    except Exception as e:
        logger.exception(f"Ошибка при загрузке SVS: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при обработке файла")
    finally:
        if 'tmp' in locals() and os.path.exists(tmp.name):
            os.unlink(tmp.name)