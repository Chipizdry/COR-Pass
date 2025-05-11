import logging
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from collections import Counter
import os
import numpy as np
import pydicom
from skimage.transform import resize
from PIL import Image
from io import BytesIO
from functools import lru_cache
from pathlib import Path
from fastapi import UploadFile, File
import zipfile
import shutil
from typing import List
import traceback

from pydicom.data import get_testdata_file
from pydicom.pixel_data_handlers.util import convert_color_space
import pydicom.config

# Настройка конфигурации pydicom
pydicom.config.enforce_valid_values = False
print(pydicom.config.pixel_data_handlers)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание роутера для API
router = APIRouter(prefix="/api/dicom", tags=["DICOM"])

# Путь к HTML-файлу для отображения DICOM-изображений
HTML_FILE = Path(__file__).parents[1] / "static" / "dicom_viewer.html"

# Директория для хранения загруженных DICOM файлов
DICOM_DIR = "dicom_files"
os.makedirs(DICOM_DIR, exist_ok=True)

# Попытка импорта дополнительных кодеков для декодирования DICOM
try:
    import pylibjpeg
    logger.info("pylibjpeg доступен для декодирования JPEG сжатых DICOM")
except ImportError:
    logger.warning("pylibjpeg не установлен, могут быть проблемы с JPEG сжатыми DICOM")

try:
    import gdcm
    logger.info("GDCM доступен для декодирования сжатых DICOM")
except ImportError:
    logger.warning("GDCM не установлен, могут быть проблемы с некоторыми сжатыми DICOM")

# Функция для проверки, является ли файл DICOM
def is_dicom_file(filepath: str) -> bool:
    """Проверяет, является ли файл DICOM файлом, независимо от расширения."""
    try:
        with open(filepath, 'rb') as f:
            f.seek(128)
            return f.read(4) == b'DICM'
    except:
        return False

# Функция для загрузки DICOM тома
@lru_cache(maxsize=1)
def load_volume():
    logger.info("Загрузка тома из DICOM файлов...")
    
    # Ищем все файлы, включая без расширения .dcm
    all_files = [os.path.join(DICOM_DIR, f) for f in os.listdir(DICOM_DIR)]
    dicom_files = [f for f in all_files if f.lower().endswith(".dcm") or is_dicom_file(f)]
    
    if not dicom_files:
        raise ValueError("Не найдено ни одного DICOM файла в директории")
    
    logger.info(f"Найдено {len(dicom_files)} DICOM файлов для обработки")

    # Сортируем файлы по номеру инстанса
    files = sorted(
        dicom_files,
        key=lambda x: int(pydicom.dcmread(x, stop_before_pixels=True).get('InstanceNumber', 0))
    )

    slices = []
    shapes = []
    example_ds = None
    errors = []

    for i, f in enumerate(files):
        try:
            logger.debug(f"Обработка файла {i+1}/{len(files)}: {os.path.basename(f)}")
            ds = pydicom.dcmread(f)
            
            if not hasattr(ds, 'pixel_array'):
                logger.warning(f"Файл {f} не содержит данных пикселей, пропускаем")
                continue

            try:
                arr = ds.pixel_array.astype(np.float32)
            except Exception as e:
                logger.error(f"Ошибка декодирования пикселей в файле {f}: {str(e)}")
                raise

            if hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
                arr = arr * ds.RescaleSlope + ds.RescaleIntercept
            
            slices.append(arr)
            shapes.append(arr.shape)
            
            if example_ds is None:
                example_ds = ds
                logger.info(f"Пример DICOM метаданных: Modality={ds.get('Modality', 'N/A')}, "
                            f"Rows={ds.get('Rows', 'N/A')}, Columns={ds.get('Columns', 'N/A')}, "
                            f"WindowCenter={ds.get('WindowCenter', 'N/A')}, "
                            f"WindowWidth={ds.get('WindowWidth', 'N/A')}")

        except Exception as e:
            errors.append(f"Ошибка в файле {f}: {str(e)}")
            continue

    if not slices:
        error_msg = "Не удалось загрузить ни один DICOM файл. Ошибки:\n" + "\n".join(errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Определяем наиболее частую форму (размер срезов)
    shape_counter = Counter(shapes)
    target_shape = shape_counter.most_common(1)[0][0]
    logger.info(f"Приведение к форме: {target_shape}")

    resized_slices = [
        resize(slice_, target_shape, preserve_range=True).astype(np.float32)
        if slice_.shape != target_shape else slice_
        for slice_ in slices
    ]

    volume = np.stack(resized_slices)
    logger.info(f"Успешно загружен том с размерами: {volume.shape}")
    return volume, example_ds

# Роут для отображения HTML представления DICOM просмотра
@router.get("/viewer", response_class=HTMLResponse)
def get_viewer():
    try:
        return HTMLResponse(HTML_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Ошибка загрузки HTML файла: {str(e)}")
        raise HTTPException(status_code=500, detail="Не удалось загрузить DICOM viewer")

# Функция для применения окна (window) к изображению
def apply_window(img, center, width):
    img_min = center - width / 2
    img_max = center + width / 2
    img = np.clip(img, img_min, img_max)
    img = ((img - img_min) / (img_max - img_min)) * 255
    return img.astype(np.uint8)

# Роут для реконструкции изображений по плоскости
@router.get("/reconstruct/{plane}")
def reconstruct(plane: str, index: int = Query(...), size: int = 512):
    try:
        logger.info(f"Реконструкция {plane} среза с индексом {index}")
        volume, ds = load_volume()

        if plane == "axial":
            img = volume[np.clip(index, 0, volume.shape[0] - 1), :, :]
        elif plane == "sagittal":
            img = volume[:, :, np.clip(index, 0, volume.shape[2] - 1)]
            img = np.flip(img, axis=(0, 1))
        elif plane == "coronal":
            img = volume[:, np.clip(index, 0, volume.shape[1] - 1), :]
            img = np.flip(img, axis=0)
        else:
            raise HTTPException(status_code=400, detail="Недопустимая плоскость реконструкции")

        # Обработка параметров окна
        try:
            wc = ds.get('WindowCenter', 0)
            ww = ds.get('WindowWidth', 0)
            
            if isinstance(wc, pydicom.multival.MultiValue):
                wc = float(wc[0])
            else:
                wc = float(wc)
                
            if isinstance(ww, pydicom.multival.MultiValue):
                ww = float(ww[0])
            else:
                ww = float(ww)
        except Exception as e:
            logger.warning(f"Ошибка получения параметров окна, используются значения по умолчанию: {str(e)}")
            wc, ww = 0, 0

        img = apply_window(img, wc, ww)

        # Получаем spacing
        ps = ds.get('PixelSpacing', [1, 1])
        st = float(ds.get('SliceThickness', 1.0))

        # Определяем реальный масштаб по плоскости
        if plane == "axial":
            spacing_x, spacing_y = ps
        elif plane == "sagittal":
            spacing_x, spacing_y = st, ps[0]
        elif plane == "coronal":
            spacing_x, spacing_y = st, ps[1]

        # Размер в пикселях (с сохранением пропорций)
        aspect_ratio = spacing_y / spacing_x
        height = size
        width = int(size * aspect_ratio)

        # Масштабируем с учётом реальных размеров
        img = Image.fromarray(img).resize((width, height))
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        logger.error(f"Ошибка реконструкции: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# Роут для загрузки DICOM файлов
@router.post("/upload")
async def upload_dicom_files(files: List[UploadFile] = File(...)):
    try:
        logger.info(f"Получено {len(files)} файлов для загрузки")
        
        # Очищаем директорию перед загрузкой новых файлов
        shutil.rmtree(DICOM_DIR)
        os.makedirs(DICOM_DIR, exist_ok=True)
        
        processed_files = 0
        valid_files = 0
        invalid_files = []

        for file in files:
            file_ext = os.path.splitext(file.filename)[1].lower()
            temp_path = os.path.join(DICOM_DIR, file.filename)

            try:
                logger.debug(f"Сохраняется файл: {file.filename}")
                with open(temp_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                if file_ext == ".zip":
                    logger.info(f"Распаковка ZIP архива: {file.filename}")
                    with zipfile.ZipFile(temp_path, "r") as zip_ref:
                        zip_ref.extractall(DICOM_DIR)
                    os.remove(temp_path)
                
                processed_files += 1

            except Exception as e:
                logger.error(f"Ошибка при сохранении файла {file.filename}: {e}")
                invalid_files.append((file.filename, str(e)))

        # Проверка всех файлов в директории
        final_files = [os.path.join(DICOM_DIR, f) for f in os.listdir(DICOM_DIR)]
        for f in final_files:
            try:
                if is_dicom_file(f):
                    # Попробуем прочитать файл как DICOM
                    ds = pydicom.dcmread(f, stop_before_pixels=True)
                    valid_files += 1
                    logger.info(f"Файл подтверждён как DICOM: {os.path.basename(f)}")
                else:
                    raise ValueError("Файл не содержит сигнатуру DICM")
            except Exception as e:
                logger.warning(f"Невалидный DICOM файл: {os.path.basename(f)} — {e}")
                invalid_files.append((os.path.basename(f), str(e)))
                os.remove(f)  # Удалим невалидный файл

        return {
            "status": "ok",
            "processed": processed_files,
            "valid_dicom": valid_files,
            "invalid_files": invalid_files
        }

    except Exception as e:
        logger.error(f"Ошибка при загрузке DICOM файлов: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка загрузки DICOM файлов")

@router.get("/volume_shape")
def get_volume_shape():
    try:
        volume, _ = load_volume()
        shape = {
            "axial": volume.shape[0],
            "coronal": volume.shape[1],
            "sagittal": volume.shape[2]
        }
        return shape
    except Exception as e:
        logger.error(f"Ошибка получения формы тома: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка получения формы тома")


@router.get("/metadata")
def get_metadata():
    try:
        volume, ds = load_volume()
        depth, height, width = volume.shape

        spacing = ds.get("PixelSpacing", [1.0, 1.0])
        slice_thickness = float(ds.get("SliceThickness", 1.0))
        
        return {
            "shape": {
                "depth": depth,       # количество аксиальных срезов
                "height": height,
                "width": width
            },
            "spacing": {
                "x": float(spacing[1]),
                "y": float(spacing[0]),
                "z": slice_thickness
            }
        }
    except Exception as e:
        logger.error(f"Ошибка получения метаданных: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Не удалось получить метаданные")        