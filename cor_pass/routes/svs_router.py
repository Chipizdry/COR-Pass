from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
import os
import logging
from openslide import OpenSlide
from io import BytesIO
from cor_pass.repository.glass import fetch_file_from_smb, get_glass_svs
from cor_pass.routes.dicom_router import load_volume
from cor_pass.services.auth import auth_service
from cor_pass.database.models import User
from PIL import Image
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.db import get_db
import shutil
from openslide import OpenSlide, OpenSlideUnsupportedFormatError

router = APIRouter(prefix="/svs", tags=["SVS"])

# SVS_ROOT_DIR = "svs_users_data"
# os.makedirs(SVS_ROOT_DIR, exist_ok=True)
DICOM_ROOT_DIR = "dicom_users_data"


@router.get("/svs_metadata")
def get_svs_metadata(current_user: User = Depends(auth_service.get_current_user)):
    user_slide_dir = os.path.join(DICOM_ROOT_DIR, str(current_user.cor_id), "slides")
    svs_files = [f for f in os.listdir(user_slide_dir) if f.lower().endswith(".svs")]

    if not svs_files:
        raise HTTPException(status_code=404, detail="No SVS files found.")

    svs_path = os.path.join(user_slide_dir, svs_files[0])

    try:
        slide = OpenSlide(svs_path)

        tile_size = 256  # размер тайла, подставь свой, если другой

        # Основные метаданные
        metadata = {
            "filename": svs_files[0],
            "dimensions": {
                "width": slide.dimensions[0],
                "height": slide.dimensions[1],
                "levels": slide.level_count,
            },
            "basic_info": {
                "mpp": float(slide.properties.get("aperio.MPP", 0)),
                "magnification": slide.properties.get("aperio.AppMag", "N/A"),
                "scan_date": slide.properties.get("aperio.Time", "N/A"),
                "scanner": slide.properties.get("aperio.User", "N/A"),
                "vendor": slide.properties.get("openslide.vendor", "N/A"),
            },
            "levels": [],
            "full_properties": {},
        }

        # Информация о уровнях + количество тайлов на уровне
        for level in range(slide.level_count):
            width, height = slide.level_dimensions[level]
            tiles_x = (width + tile_size - 1) // tile_size
            tiles_y = (height + tile_size - 1) // tile_size

            metadata["levels"].append(
                {
                    "downsample": float(
                        slide.properties.get(f"openslide.level[{level}].downsample", 0)
                    ),
                    # Размеры берём из slide.level_dimensions, а не из свойств, т.к. они надежнее
                    "width": width,
                    "height": height,
                    "tiles_x": tiles_x,
                    "tiles_y": tiles_y,
                    "total_tiles": tiles_x * tiles_y,
                }
            )

        # Все свойства для детального просмотра
        metadata["full_properties"] = dict(slide.properties)

        return metadata

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preview_svs")
def preview_svs(
    full: bool = Query(False),
    level: int = Query(0),  # Добавляем параметр уровня
    current_user: User = Depends(auth_service.get_current_user),
):
    user_slide_dir = os.path.join(DICOM_ROOT_DIR, str(current_user.cor_id), "slides")
    svs_files = [f for f in os.listdir(user_slide_dir) if f.lower().endswith(".svs")]

    if not svs_files:
        raise HTTPException(status_code=404, detail="No SVS found.")

    svs_path = os.path.join(user_slide_dir, svs_files[0])

    try:
        slide = OpenSlide(svs_path)

        if full:
            # Полное изображение в выбранном разрешении
            level = min(
                level, slide.level_count - 1
            )  # Проверяем, чтобы уровень был допустимым
            size = slide.level_dimensions[level]

            # Читаем регион целиком
            img = slide.read_region((0, 0), level, size)

            # Конвертируем в RGB, если нужно
            if img.mode == "RGBA":
                img = img.convert("RGB")
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


@router.get("/tile")
def get_tile(
    level: int = Query(..., description="Zoom level"),
    x: int = Query(..., description="Tile X index"),
    y: int = Query(..., description="Tile Y index"),
    tile_size: int = Query(256, description="Tile size in pixels"),
    current_user: User = Depends(auth_service.get_current_user),
):
    try:
        user_slide_dir = os.path.join(
            DICOM_ROOT_DIR, str(current_user.cor_id), "slides"
        )
        svs_files = [
            f for f in os.listdir(user_slide_dir) if f.lower().endswith(".svs")
        ]

        if not svs_files:
            logger.warning(f"[NO SVS] User {current_user.cor_id} has no SVS files")
            raise HTTPException(status_code=404, detail="No SVS files found.")

        svs_path = os.path.join(user_slide_dir, svs_files[0])
        slide = OpenSlide(svs_path)

        if level < 0 or level >= slide.level_count:
            logger.warning(
                f"[INVALID LEVEL] level={level}, max={slide.level_count - 1}"
            )
            return empty_tile()

        level_width, level_height = slide.level_dimensions[level]
        tiles_x = (level_width + tile_size - 1) // tile_size
        tiles_y = (level_height + tile_size - 1) // tile_size

        if x < 0 or x >= tiles_x or y < 0 or y >= tiles_y:
            logger.warning(
                f"[OUT OF BOUNDS] level={level}, x={x}, y={y}, tiles_x={tiles_x}, tiles_y={tiles_y}"
            )
            return empty_tile()

        # Пересчёт координат тайла из текущего уровня в координаты уровня 0
        scale = slide.level_downsamples[level]
        location = (int(x * tile_size * scale), int(y * tile_size * scale))

        # Фактический размер региона (в пикселях уровня level)
        region_width = min(tile_size, level_width - x * tile_size)
        region_height = min(tile_size, level_height - y * tile_size)

        region = slide.read_region(
            location, level, (region_width, region_height)
        ).convert("RGB")
        region = region.resize((tile_size, tile_size), Image.LANCZOS)

        buf = BytesIO()
        region.save(buf, format="JPEG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/jpeg")

    except Exception as e:
        import traceback

        logger.error(f"[ERROR GET TILE] {traceback.format_exc()}")
        return empty_tile()


def empty_tile(color=(255, 255, 255)) -> StreamingResponse:
    """Возвращает 1x1 JPEG-заглушку."""
    img = Image.new("RGB", (1, 1), color)
    buf = BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/jpeg")



@router.get(
    "/{glass_id}/svs",
    dependencies=[Depends(auth_service.get_current_user)],
)
async def upload_svs_from_storage(
    glass_id: str,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Обрабатывает SVS-файл из хранилища по glass_id, сохраняет его в user_slide_dir.
    """
    try:
        db_glass = await get_glass_svs(db=db, glass_id=glass_id)
        if db_glass is None:
            logger.error(f"Стекло или scan_url не найдены для ID {glass_id}")
            raise HTTPException(status_code=404, detail="Glass or scan URL not found")

        user_dir = os.path.join(DICOM_ROOT_DIR, str(current_user.cor_id))
        user_dicom_dir = user_dir
        user_slide_dir = os.path.join(user_dir, "slides")

        if os.path.exists(user_dicom_dir):
            logger.debug(f"Удаление старой директории: {user_dicom_dir}")
            shutil.rmtree(user_dicom_dir)
        os.makedirs(user_dicom_dir, exist_ok=True)
        os.makedirs(user_slide_dir, exist_ok=True)
        logger.debug(f"Созданы директории: {user_dicom_dir}, {user_slide_dir}")


        filename = os.path.basename(db_glass.scan_url)
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext != ".svs":
            logger.error(f"Файл {filename} не является SVS-файлом")
            raise HTTPException(status_code=400, detail="File is not an SVS file")

        temp_path = await fetch_file_from_smb(db_glass.scan_url)
        logger.debug(f"SVS-файл загружен во временный файл: {temp_path}")

        valid_svs = 0
        try:
            OpenSlide(temp_path)
            target_path = os.path.join(user_slide_dir, filename)
            shutil.move(temp_path, target_path)
            logger.info(f"SVS-файл перемещён в: {target_path}")
            valid_svs += 1
        except OpenSlideUnsupportedFormatError:
            logger.error(f"Файл {filename} не является допустимым SVS-форматом")
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                logger.debug(f"Временный файл {temp_path} удалён")
            raise HTTPException(status_code=400, detail=f"File {filename} is not a valid SVS format")
        except Exception as e:
            logger.error(f"Ошибка при обработке файла {filename}: {str(e)}")
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                logger.debug(f"Временный файл {temp_path} удалён")
            raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

        try:
            load_volume.cache_clear()
        except NameError:
            logger.debug("load_volume не определён, кэш не очищается")

        if valid_svs > 0:
            message = f"Загружен файл SVS (1 шт.)"
        else:
            if os.path.exists(user_dicom_dir):
                shutil.rmtree(user_dicom_dir)
                logger.debug(f"Директория {user_dicom_dir} удалена из-за отсутствия валидных файлов")
            raise HTTPException(status_code=400, detail="No valid SVS files processed")

        return {"message": message}

    except Exception as e:
        logger.error(f"Ошибка в маршруте /upload/{glass_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))