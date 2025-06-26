from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
import os
import logging
from openslide import OpenSlide
from io import BytesIO
from cor_pass.services.auth import auth_service
from cor_pass.database.models import User
from PIL import Image

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


@router.get("/tile")
def get_tile(
    level: int = Query(..., description="Zoom level"),
    x: int = Query(..., description="Tile X index"),
    y: int = Query(..., description="Tile Y index"),
    tile_size: int = Query(256, description="Tile size in pixels"),
    current_user: User = Depends(auth_service.get_current_user)
):
    try:
        user_slide_dir = os.path.join(DICOM_ROOT_DIR, str(current_user.cor_id), "slides")
        svs_files = [f for f in os.listdir(user_slide_dir) if f.lower().endswith('.svs')]

        if not svs_files:
            logger.warning(f"[NO SVS] User {current_user.cor_id} has no SVS files")
            raise HTTPException(status_code=404, detail="No SVS files found.")

        svs_path = os.path.join(user_slide_dir, svs_files[0])
        slide = OpenSlide(svs_path)

        if level < 0 or level >= slide.level_count:
            logger.warning(f"[INVALID LEVEL] level={level}, max={slide.level_count - 1}")
            return empty_tile()

        level_width, level_height = slide.level_dimensions[level]
        tiles_x = (level_width + tile_size - 1) // tile_size
        tiles_y = (level_height + tile_size - 1) // tile_size

        logger.info(f"[LEVEL INFO] level={level}, size={level_width}x{level_height}, tiles={tiles_x}x{tiles_y}")

        if x < 0 or x >= tiles_x or y < 0 or y >= tiles_y:
            logger.warning(f"[OUT OF BOUNDS] level={level}, x={x}, y={y}, tiles_x={tiles_x}, tiles_y={tiles_y}")
            return empty_tile()

        location = (x * tile_size, y * tile_size)
        region_width = min(tile_size, level_width - location[0])
        region_height = min(tile_size, level_height - location[1])

        # 💥 Ключевой момент: пересчёт координат в базовый уровень
        downsample = slide.level_downsamples[level]
        base_location = (int(location[0] * downsample), int(location[1] * downsample))
        base_size = (int(region_width * downsample), int(region_height * downsample))

        logger.debug(f"[TILE READ] level={level}, base_location={base_location}, base_size={base_size}")

        region = slide.read_region(base_location, 0, base_size).convert("RGB")
        region = region.resize((region_width, region_height), Image.LANCZOS)

        buf = BytesIO()
        region.save(buf, format="JPEG")
        buf.seek(0)

        return StreamingResponse(buf, media_type="image/jpeg")

    except Exception as e:
        import traceback
        logger.critical(f"[UNEXPECTED ERROR] {traceback.format_exc()}")
        return empty_tile()


def empty_tile(color=(255, 255, 255)) -> StreamingResponse:
    """Возвращает 1x1 JPEG-заглушку."""
    img = Image.new("RGB", (1, 1), color)
    buf = BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/jpeg")