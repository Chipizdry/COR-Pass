from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse, HTMLResponse
import os
import numpy as np
import pydicom
import pydicom.config
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
from pydicom import config
from loguru import logger

pydicom.config.settings.reading_validation_mode = pydicom.config.RAISE


SUPPORTED_TRANSFER_SYNTAXES = {
    "1.2.840.10008.1.2": "Implicit VR Little Endian",
    "1.2.840.10008.1.2.1": "Explicit VR Little Endian",
    "1.2.840.10008.1.2.2": "Explicit VR Big Endian",
    "1.2.840.10008.1.2.4.70": "JPEG Lossless, Non-Hierarchical, First-Order Prediction",
    "1.2.840.10008.1.2.4.57": "JPEG Lossless, Non-Hierarchical",
    "1.2.840.10008.1.2.4.50": "JPEG Baseline",
}


router = APIRouter(prefix="/dicom", tags=["DICOM"])
HTML_FILE = Path(__file__).parents[1] / "static" / "dicom_viewer.html"
DICOM_ROOT_DIR = "dicom_users_data"
os.makedirs(DICOM_ROOT_DIR, exist_ok=True)


# Проверка доступных декомпрессоров
def check_dicom_support():
    logger.debug("\n[INFO] Проверка поддержки DICOM:")
    logger.debug(f"GDCM доступен: {'gdcm' in pydicom.config.pixel_data_handlers}")
    logger.debug(
        f"Pylibjpeg доступен: {'pylibjpeg' in pydicom.config.pixel_data_handlers}"
    )
    logger.debug(
        f"OpenJPEG доступен: {'openjpeg' in pydicom.config.pixel_data_handlers}"
    )

    # Вывод информации о Transfer Syntax
    logger.debug("\nПоддерживаемые Transfer Syntax:")
    for uid, name in SUPPORTED_TRANSFER_SYNTAXES.items():
        handler = pydicom.uid.UID(uid).is_supported
        logger.debug(f"{name} ({uid}): {'✓' if handler else '✗'}")




def sort_by_image_position(datasets):
    """
    Универсальная сортировка срезов по нормали к ImageOrientationPatient.
    Работает для всех производителей.
    """
    orientation = datasets[0][0].ImageOrientationPatient
    normal = np.cross(orientation[:3], orientation[3:])
    datasets.sort(key=lambda item: np.dot(item[0].ImagePositionPatient, normal))
    return datasets


def process_siemens_dicom(datasets):
    """
    Обработка Siemens DICOM:
    - Разбиваем на группы по ImageOrientationPatient
    - Сортируем каждую группу отдельно
    - Возвращаем словарь {orientation: slices}
    """
    logger.debug("[INFO] Обработка Siemens DICOM...")

    groups = {}
    for ds, path in datasets:
        try:
            orient = tuple(round(float(x), 4) for x in ds.ImageOrientationPatient)
        except Exception:
            continue

        if orient not in groups:
            groups[orient] = []
        groups[orient].append((ds, path))

    logger.debug(f"[INFO] Siemens: найдено групп ориентаций: {len(groups)}")

    result = {}
    for orient, slices in groups.items():
        # вычисляем нормаль
        row, col = np.array(orient[:3]), np.array(orient[3:])
        normal = np.cross(row, col)

        slices.sort(key=lambda item: np.dot(item[0].ImagePositionPatient, normal))
        result[orient] = slices

        logger.debug(f"[INFO] Группа {orient}: {len(slices)} срезов")

    return result


def process_default_dicom(datasets):
    """
    Универсальная обработка для всех остальных вендоров.
    """
    logger.debug("[INFO] Обработка DICOM по умолчанию...")
    return sort_by_image_position(datasets)




@lru_cache(maxsize=16)
def load_volume(user_cor_id: str):
    logger.debug("[INFO] Загружаем том из DICOM-файлов...")

    user_dicom_dir = os.path.join(DICOM_ROOT_DIR, user_cor_id)
    if not os.path.exists(user_dicom_dir):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DICOM данные для этого пользователя не найдены.",
        )

    dicom_paths = [
        os.path.join(user_dicom_dir, f)
        for f in os.listdir(user_dicom_dir)
        if not f.startswith(".") and os.path.isfile(os.path.join(user_dicom_dir, f))
    ]

    datasets = []
    for path in dicom_paths:
        try:
            ds = None
            read_attempts = [
                lambda: pydicom.dcmread(path),
                lambda: pydicom.dcmread(path, force=True),
                lambda: pydicom.dcmread(path, force=True, defer_size=1024),
            ]
            for attempt in read_attempts:
                try:
                    ds = attempt()
                    break
                except:
                    continue

            if ds is None:
                logger.debug(f"[WARN] Не удалось прочитать файл {path}")
                continue

            if hasattr(ds, "file_meta") and hasattr(ds.file_meta, "TransferSyntaxUID"):
                if ds.file_meta.TransferSyntaxUID.is_compressed:
                    try:
                        ds.decompress()
                    except Exception as decompress_error:
                        logger.warning(
                            f"[WARN] Не удалось декомпрессировать {path}: {decompress_error}"
                        )
                        continue

            required_attrs = [
                "ImagePositionPatient",
                "ImageOrientationPatient",
                "pixel_array",
            ]
            if all(hasattr(ds, attr) for attr in required_attrs):
                datasets.append((ds, path))
        except Exception as e:
            logger.warning(f"[WARN] Пропущен файл {path}: {str(e)}")
            continue

    if not datasets:
        raise RuntimeError("Нет подходящих DICOM-файлов с ImagePositionPatient.")

    # === Выбор обработчика по вендору ===
    manufacturer = getattr(datasets[0][0], "Manufacturer", "").upper()
    logger.debug(f"[INFO] Производитель: {manufacturer}")

    if "SIEMENS" in manufacturer:
        grouped = process_siemens_dicom(datasets)
        volumes = {}
        example_ds = None
        for orient, slices in grouped.items():
            arrs, shapes = [], []
            for ds, path in slices:
                arr = ds.pixel_array.astype(np.float32)
                if hasattr(ds, "RescaleSlope") and hasattr(ds, "RescaleIntercept"):
                    try:
                        arr = arr * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
                    except:
                        pass
                arrs.append(arr)
                shapes.append(arr.shape)
                if example_ds is None:
                    example_ds = ds

            # Выравниваем размеры
            target_shape = Counter(shapes).most_common(1)[0][0]
            resized = [
                resize(a, target_shape, preserve_range=True).astype(np.float32)
                if a.shape != target_shape else a
                for a in arrs
            ]
            volumes[orient] = np.stack(resized)

        logger.debug(f"[INFO] Siemens: собрали {len(volumes)} групп")
        return volumes, example_ds

    else:
        # === Default path для остальных производителей ===
        datasets = process_default_dicom(datasets)
        slices, shapes = [], []
        example_ds = None

        for ds, path in datasets:
            try:
                arr = ds.pixel_array.astype(np.float32)
                if hasattr(ds, "RescaleSlope") and hasattr(ds, "RescaleIntercept"):
                    try:
                        slope, intercept = float(ds.RescaleSlope), float(ds.RescaleIntercept)
                        arr = arr * slope + intercept
                    except Exception as e:
                        logger.warning(f"[WARN] Ошибка RescaleSlope/Intercept: {e}")
                slices.append(arr)
                shapes.append(arr.shape)
                if example_ds is None:
                    example_ds = ds
            except Exception as e:
                logger.error(f"[ERROR] Ошибка обработки {path}: {e}")
                continue

        if not slices:
            raise RuntimeError("Не удалось загрузить ни одного среза.")

        target_shape = Counter(shapes).most_common(1)[0][0]
        resized_slices = [
            resize(slice_, target_shape, preserve_range=True).astype(np.float32)
            if slice_.shape != target_shape else slice_
            for slice_ in slices
        ]
        volume = np.stack(resized_slices)
        logger.debug(f"[INFO] Загружено срезов: {len(volume)}")
        return volume, example_ds






@router.get("/viewer", response_class=HTMLResponse)
def get_viewer(current_user: User = Depends(auth_service.get_current_user)):
    return HTMLResponse(HTML_FILE.read_text(encoding="utf-8"))


def apply_window(img, ds):
    try:
        wc = (
            float(ds.WindowCenter[0])
            if isinstance(ds.WindowCenter, pydicom.multival.MultiValue)
            else float(ds.WindowCenter)
        )
        ww = (
            float(ds.WindowWidth[0])
            if isinstance(ds.WindowWidth, pydicom.multival.MultiValue)
            else float(ds.WindowWidth)
        )
        img_min = wc - ww / 2
        img_max = wc + ww / 2
        img = np.clip(img, img_min, img_max)
        img = ((img - img_min) / (img_max - img_min + 1e-5)) * 255
        return img.astype(np.uint8)
    except Exception as e:
        logger.debug(f"[WARN] Ошибка применения Window Center/Width: {e}")
        return img.astype(np.uint8)


@router.get("/reconstruct/{plane}")
def reconstruct(
    plane: str,
    index: int = Query(...),
    size: int = 512,
    mode: str = Query("auto", enum=["auto", "window", "raw"]),
    window_center: float = Query(None),
    window_width: float = Query(None),
    current_user: User = Depends(auth_service.get_current_user),
):
    try:
        volume_data, ds = load_volume(str(current_user.cor_id))

        # Siemens: если volume_data — словарь, выбираем ориентацию с максимальным числом срезов
        if isinstance(volume_data, dict):
            orient, volume = max(volume_data.items(), key=lambda x: x[1].shape[0])
            logger.debug(f"Siemens: выбрана ориентация {orient}, срезов: {volume.shape[0]}")
        else:
            volume = volume_data

        # Безопасное чтение PixelSpacing и SliceThickness
        ps = getattr(ds, "PixelSpacing", [1.0, 1.0])
        ps = [float(x) if x not in (None, "") else 1.0 for x in ps]
        st = float(getattr(ds, "SliceThickness", 1.0) or 1.0)

        # Выбор среза в зависимости от плоскости
        if plane == "axial":
            img = volume[np.clip(index, 0, volume.shape[0] - 1), :, :]
            spacing_x, spacing_y = ps
        elif plane == "sagittal":
            img = np.flip(volume[:, :, np.clip(index, 0, volume.shape[2] - 1)], axis=(0, 1))
            spacing_x, spacing_y = st, ps[0]
        elif plane == "coronal":
            img = np.flip(volume[:, np.clip(index, 0, volume.shape[1] - 1), :], axis=0)
            spacing_x, spacing_y = st, ps[1]
        else:
            raise HTTPException(status_code=400, detail="Invalid plane")

        # === Применение оконного преобразования ===
        if mode == "auto":
            img = apply_window(img, ds)
        elif mode == "window":
            try:
                wc = window_center if window_center is not None else (
                    float(ds.WindowCenter[0])
                    if isinstance(ds.WindowCenter, pydicom.multival.MultiValue)
                    else float(ds.WindowCenter)
                )
                ww = window_width if window_width is not None else (
                    float(ds.WindowWidth[0])
                    if isinstance(ds.WindowWidth, pydicom.multival.MultiValue)
                    else float(ds.WindowWidth)
                )
                img_min, img_max = wc - ww / 2, wc + ww / 2
                img = np.clip(img, img_min, img_max)
                img = ((img - img_min) / (img_max - img_min + 1e-5)) * 255
                img = img.astype(np.uint8)
            except Exception as e:
                logger.warning(f"Ошибка window mode, fallback на raw: {e}")
                img = ((img - img.min()) / (img.max() - img.min() + 1e-5)) * 255
                img = img.astype(np.uint8)
        elif mode == "raw":
            img = ((img - img.min()) / (img.max() - img.min() + 1e-5)) * 255
            img = img.astype(np.uint8)

        # === Преобразование в PNG с подгонкой размера ===
        img_pil = Image.fromarray(img).convert("L")
        img_pil = ImageOps.pad(
            img_pil,
            (size, size),
            method=Image.Resampling.BICUBIC,
            color=0,
            centering=(0.5, 0.5),
        )

        buf = BytesIO()
        img_pil.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    



@router.post("/upload")
async def upload_dicom_files(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(auth_service.get_current_user),
):
    try:
        user_dir = os.path.join(DICOM_ROOT_DIR, str(current_user.cor_id))
        user_dicom_dir = user_dir
        user_slide_dir = os.path.join(user_dir, "slides")

        # Чистим старые данные
        if os.path.exists(user_dicom_dir):
            shutil.rmtree(user_dicom_dir)
        os.makedirs(user_dicom_dir, exist_ok=True)
        os.makedirs(user_slide_dir, exist_ok=True)

        processed_files = 0
        valid_dicom = 0
        valid_svs = 0

        for file in files:
            file_ext = os.path.splitext(file.filename)[1].lower()

            temp_path = os.path.join(user_dicom_dir, file.filename)
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            processed_files += 1

            if file_ext == ".svs":
                try:
                    # Проверяем что .svs файл действительно читается как OpenSlide
                    OpenSlide(temp_path)
                    shutil.move(temp_path, os.path.join(user_slide_dir, file.filename))
                    logger.info(f"SVS-файл перемещён в: {user_slide_dir}")
                    valid_svs += 1
                except OpenSlideUnsupportedFormatError:
                    os.remove(temp_path)
                    print(
                        f"[ERROR] Файл {file.filename} не является допустимым SVS-форматом."
                    )
                continue

            if file_ext == ".zip":
                try:
                    with zipfile.ZipFile(temp_path, "r") as zip_ref:
                        for member in zip_ref.namelist():
                            member_path = os.path.join(user_dicom_dir, member)
                            if not member_path.startswith(user_dicom_dir):
                                raise ValueError("Zip Slip атака предотвращена!")
                            zip_ref.extract(member, user_dicom_dir)
                    os.remove(temp_path)
                except Exception as e:
                    print(f"[ERROR] Ошибка распаковки {file.filename}: {e}")
                    os.remove(temp_path)
                    continue

        # Проверка DICOM-файлов
        dicom_paths = [
            os.path.join(user_dicom_dir, f)
            for f in os.listdir(user_dicom_dir)
            if not f.startswith(".")
            and os.path.isfile(os.path.join(user_dicom_dir, f))
            and f.lower().endswith((".dcm", ""))
            and not f.lower().endswith(".svs")
        ]

        for file_path in dicom_paths:
            try:
                pydicom.dcmread(file_path, stop_before_pixels=True)
                valid_dicom += 1
            except:
                os.remove(file_path)

        if valid_dicom == 0 and valid_svs == 0:
            shutil.rmtree(user_dicom_dir)
            raise HTTPException(
                status_code=400, detail="No valid DICOM or SVS files found."
            )

        load_volume.cache_clear()

        if valid_svs > 0 and valid_dicom == 0:
            message = f"Загружен файл SVS ({valid_svs} шт.)"
        elif valid_dicom > 0 and valid_svs == 0:
            message = f"Загружено {valid_dicom} срезов DICOM"
        elif valid_dicom > 0 and valid_svs > 0:
            message = f"Загружено {valid_dicom} срезов DICOM и {valid_svs} файл(ов) SVS"
        else:
            message = (
                "Файлы загружены, но не удалось распознать ни одного DICOM или SVS."
            )

        return {"message": message}

    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/volume_info")
def get_volume_info(current_user: User = Depends(auth_service.get_current_user)):
    """
    Возвращает информацию о загруженном томе: количество срезов, ширину и высоту.
    Работает для Siemens (где volume_data — словарь ориентаций) и других производителей.
    """
    try:
        volume_data, ds = load_volume(str(current_user.cor_id))

        if isinstance(volume_data, dict):
            # Для Siemens: выбираем ориентацию с максимальным числом срезов
            orient, volume = max(volume_data.items(), key=lambda x: x[1].shape[0])
        else:
            volume = volume_data

        return {
            "slices": volume.shape[0],
            "width": volume.shape[2],   # np.stack формат: (slices, height, width)
            "height": volume.shape[1],
        }

    except Exception as e:
        logger.error(f"Ошибка get_volume_info: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения информации о томе: {e}")


@router.get("/metadata")
def get_metadata(current_user: User = Depends(auth_service.get_current_user)):
    """
    Возвращает метаданные DICOM тома, включая размеры, spacing, толщину среза и Study/Patient info.
    Работает для Siemens и других производителей.
    """
    try:
        volume_data, ds = load_volume(str(current_user.cor_id))

        if isinstance(volume_data, dict):
            orient, volume = max(volume_data.items(), key=lambda x: x[1].shape[0])
        else:
            volume = volume_data

        depth, height, width = volume.shape

        # Безопасное получение spacing и slice_thickness
        spacing = getattr(ds, "PixelSpacing", [1.0, 1.0])
        if isinstance(spacing, (list, tuple)) and len(spacing) >= 2:
            spacing_x, spacing_y = float(spacing[0]), float(spacing[1])
        else:
            spacing_x, spacing_y = 1.0, 1.0

        try:
            slice_thickness = float(getattr(ds, "SliceThickness", 1.0))
        except Exception:
            slice_thickness = 1.0

        # Удобная функция безопасного получения атрибута
        def safe_get(attr, default="N/A"):
            try:
                value = getattr(ds, attr, default)
                if value is None or value == "":
                    return default
                if isinstance(value, pydicom.valuerep.PersonName):
                    return str(value)
                return value
            except Exception:
                return default

        metadata = {
            "shape": {"depth": depth, "height": height, "width": width},
            "spacing": {"x": spacing_x, "y": spacing_y, "z": slice_thickness},
            "study_info": {
                "StudyInstanceUID": safe_get("StudyInstanceUID"),
                "SeriesInstanceUID": safe_get("SeriesInstanceUID"),
                "Modality": safe_get("Modality"),
                "StudyDate": safe_get("StudyDate"),
                "PatientName": safe_get("PatientName"),
                "PatientBirthDate": safe_get("PatientBirthDate"),
                "Manufacturer": safe_get("Manufacturer"),
                "DeviceModel": safe_get("ManufacturerModelName"),
                "KVP": safe_get("KVP"),
                "XRayTubeCurrent": safe_get("XRayTubeCurrent"),
                "Exposure": safe_get("Exposure"),
            },
        }

        return metadata

    except Exception as e:
        logger.error(f"Ошибка get_metadata: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при получении метаданных: {e}")


def handle_compressed_dicom(file_path):
    try:
        ds = pydicom.dcmread(file_path, force=True)

        if hasattr(ds, "file_meta") and ds.file_meta.TransferSyntaxUID.is_compressed:
            try:
                ds.decompress("gdcm")  # Сначала пробуем GDCM
            except:
                try:
                    ds.decompress("pylibjpeg")  # Затем pylibjpeg
                except:
                    print(
                        f"[WARN] Все методы декомпрессии не сработали для {file_path}"
                    )
                    return None

        return ds
    except Exception as e:
        print(f"[ERROR] Ошибка обработки сжатого DICOM: {e}")
        return None


