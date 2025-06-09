


from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse, HTMLResponse,Response
import os
import numpy as np
import pydicom
import openslide
import logging
import xml.etree.ElementTree as ET
from openslide import OpenSlide, OpenSlideUnsupportedFormatError
from skimage.transform import resize
from PIL import Image
from PIL import ImageOps
from io import BytesIO
from functools import lru_cache
from pathlib import Path
import zipfile
import shutil
from typing import List
from collections import Counter
from skimage.transform import resize
from collections import Counter
from cor_pass.services.auth import auth_service
from cor_pass.database.models import User

logger = logging.getLogger("svs_logger")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/svs", tags=["SVS"])

#SVS_ROOT_DIR = "svs_users_data"
#os.makedirs(SVS_ROOT_DIR, exist_ok=True)
DICOM_ROOT_DIR = "dicom_users_data"


@router.get("/svs_metadata")
def get_svs_metadata(current_user: User = Depends(auth_service.get_current_user)):
    user_slide_dir = os.path.join(DICOM_ROOT_DIR, str(current_user.cor_id), "slides")
    svs_files = [f for f in os.listdir(user_slide_dir) if f.lower().endswith('.svs')]

    if not svs_files:
        raise HTTPException(status_code=404, detail="No SVS files found.")

    svs_path = os.path.join(user_slide_dir, svs_files[0])

    try:
        slide = OpenSlide(svs_path)
        
        # Основные метаданные
        metadata = {
            "filename": svs_files[0],
            "dimensions": {
                "width": slide.dimensions[0],
                "height": slide.dimensions[1],
                "levels": slide.level_count
            },
            "basic_info": {
                "mpp": float(slide.properties.get('aperio.MPP', 0)),
                "magnification": slide.properties.get('aperio.AppMag', 'N/A'),
                "scan_date": slide.properties.get('aperio.Time', 'N/A'),
                "scanner": slide.properties.get('aperio.User', 'N/A'),
                "vendor": slide.properties.get('openslide.vendor', 'N/A')
            },
            "levels": [],
            "full_properties": {}
        }

        # Информация о уровнях
        for level in range(slide.level_count):
            metadata["levels"].append({
                "downsample": float(slide.properties.get(f'openslide.level[{level}].downsample', 0)),
                "width": int(slide.properties.get(f'openslide.level[{level}].width', 0)),
                "height": int(slide.properties.get(f'openslide.level[{level}].height', 0))
            })

        # Все свойства для детального просмотра
        metadata["full_properties"] = dict(slide.properties)

        return metadata

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preview_svs")
def preview_svs(
    full: bool = Query(False),
    level: int = Query(0),  # Добавляем параметр уровня
    current_user: User = Depends(auth_service.get_current_user)
):
    user_slide_dir = os.path.join(DICOM_ROOT_DIR, str(current_user.cor_id), "slides")
    svs_files = [f for f in os.listdir(user_slide_dir) if f.lower().endswith('.svs')]

    if not svs_files:
        raise HTTPException(status_code=404, detail="No SVS found.")

    svs_path = os.path.join(user_slide_dir, svs_files[0])

    try:
        slide = OpenSlide(svs_path)
        
        if full:
            # Полное изображение в выбранном разрешении
            level = min(level, slide.level_count - 1)  # Проверяем, чтобы уровень был допустимым
            size = slide.level_dimensions[level]
            
            # Читаем регион целиком
            img = slide.read_region((0, 0), level, size)
            
            # Конвертируем в RGB, если нужно
            if img.mode == 'RGBA':
                img = img.convert('RGB')
        else:
            # Миниатюра
            size = (300, 300)
            img = slide.get_thumbnail(size)
        
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# @router.get("/tile")
# def get_tile(
#     level: int = Query(...),
#     x: int = Query(...),
#     y: int = Query(...),
#     tile_size: int = Query(256),
#     current_user: User = Depends(auth_service.get_current_user)
# ):
#     user_slide_dir = os.path.join(DICOM_ROOT_DIR, str(current_user.cor_id), "slides")
#     svs_files = [f for f in os.listdir(user_slide_dir) if f.lower().endswith('.svs')]

#     if not svs_files:
#         raise HTTPException(status_code=404, detail="No SVS found.")

#     svs_path = os.path.join(user_slide_dir, svs_files[0])

#     try:
#         slide = OpenSlide(svs_path)

#         if level >= slide.level_count:
#             raise HTTPException(status_code=400, detail="Invalid level")

#         # Размер изображения на этом уровне
#         level_width, level_height = slide.level_dimensions[level]

#         # Проверка выхода за границы
#         if x * tile_size >= level_width or y * tile_size >= level_height:
#             raise HTTPException(status_code=404, detail="Tile out of bounds")

#         # Позиция в пикселях на этом уровне
#         location = (x * tile_size, y * tile_size)
#         size = (
#             min(tile_size, level_width - location[0]),
#             min(tile_size, level_height - location[1])
#         )

#         tile = slide.read_region(location, level, size).convert("RGB")
#         buf = BytesIO()
#         tile.save(buf, format="JPEG")
#         buf.seek(0)
#         return StreamingResponse(buf, media_type="image/jpeg")

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))




@router.get("/tile")
def get_tile(
    level: int = Query(...),
    x: int = Query(...),
    y: int = Query(...),
    tile_size: int = Query(256),
    current_user: User = Depends(auth_service.get_current_user)
):
    # Логирование начала запроса
    logger.info(f"Starting tile request - level: {level}, x: {x}, y: {y}, tile_size: {tile_size}")
    
    user_slide_dir = os.path.join(DICOM_ROOT_DIR, str(current_user.cor_id), "slides")
    logger.info(f"User slide directory: {user_slide_dir}")
    
    svs_files = [f for f in os.listdir(user_slide_dir) if f.lower().endswith('.svs')]
    logger.info(f"Found SVS files: {svs_files}")

    if not svs_files:
        logger.error("No SVS files found in directory")
        raise HTTPException(status_code=404, detail="No SVS found.")

    svs_path = os.path.join(user_slide_dir, svs_files[0])
    logger.info(f"Processing SVS file: {svs_path}")

    try:
        # Логирование перед открытием слайда
        logger.info("Attempting to open SVS file with OpenSlide")
        slide = OpenSlide(svs_path)
        logger.info(f"Successfully opened slide. Total levels: {slide.level_count}, Dimensions: {slide.dimensions}")

        # Проверка уровня
        logger.info(f"Checking if requested level {level} is valid")
        if level >= slide.level_count:
            logger.error(f"Invalid level requested: {level}. Max available: {slide.level_count - 1}")
            raise HTTPException(status_code=400, detail="Invalid level")

        # Получение размеров уровня
        level_width, level_height = slide.level_dimensions[level]
        logger.info(f"Level {level} dimensions: width={level_width}, height={level_height}")

        # Проверка границ
        logger.info(f"Checking tile boundaries - x: {x}, y: {y}, tile_size: {tile_size}")
        if x * tile_size >= level_width or y * tile_size >= level_height:
            logger.error(f"Tile out of bounds - x: {x}, y: {y} at level {level}")
            raise HTTPException(status_code=404, detail="Tile out of bounds")

        # Расчет позиции и размера
        location = (x * tile_size, y * tile_size)
        size = (
            min(tile_size, level_width - location[0]),
            min(tile_size, level_height - location[1])
        )
        logger.info(f"Tile location: {location}, size: {size}")

        # Чтение региона
        logger.info("Reading region from slide")
        tile = slide.read_region(location, level, size).convert("RGB")
        logger.info("Successfully read and converted region")

        # Подготовка ответа
        logger.info("Preparing response buffer")
        buf = BytesIO()
        tile.save(buf, format="JPEG")
        buf.seek(0)
        logger.info("Tile successfully prepared for streaming")

        return StreamingResponse(buf, media_type="image/jpeg")

    except HTTPException as he:
        logger.error(f"HTTPException during tile processing: {he.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during tile processing: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Закрытие слайда, если он был открыт
        if 'slide' in locals():
            logger.info("Closing slide")
            slide.close()
            logger.info("Slide closed")