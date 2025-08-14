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


@lru_cache(maxsize=16)
def load_volume(user_cor_id: str):
    logger.debug("[INFO] Загружаем том из DICOM-файлов...")

    # Чтение всех файлов
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
            # Пробуем разные методы чтения файла
            ds = None
            read_attempts = [
                lambda: pydicom.dcmread(path),  # Стандартное чтение
                lambda: pydicom.dcmread(path, force=True),  # Принудительное чтение
                lambda: pydicom.dcmread(
                    path, force=True, defer_size=1024
                ),  # Чтение с ограничением
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

            # Попытка декомпрессии если файл сжат
            if hasattr(ds, "file_meta") and hasattr(ds.file_meta, "TransferSyntaxUID"):
                if ds.file_meta.TransferSyntaxUID.is_compressed:
                    try:
                        ds.decompress()  # Автоматический выбор декомпрессора
                    except Exception as decompress_error:
                        print(
                            f"[WARN] Не удалось декомпрессировать {path}: {decompress_error}"
                        )
                        continue

            # Проверка необходимых атрибутов
            required_attrs = [
                "ImagePositionPatient",
                "ImageOrientationPatient",
                "pixel_array",
            ]
            if all(hasattr(ds, attr) for attr in required_attrs):
                datasets.append((ds, path))
            else:
                logger.debug(
                    f"[WARN] Файл {path} не содержит необходимых DICOM-тегов. Пропущен."
                )
                logger.debug(
                    f"       Найдены теги: {[attr for attr in required_attrs if hasattr(ds, attr)]}"
                )

        except Exception as e:
            logger.debug(f"[WARN] Пропущен файл {path} из-за ошибки чтения: {str(e)}")
            continue

    if not datasets:
        raise RuntimeError("Нет подходящих DICOM-файлов с ImagePositionPatient.")

    # Определение нормали к срезу из ориентации
    orientation = datasets[0][0].ImageOrientationPatient
    normal = np.cross(orientation[:3], orientation[3:])

    # Сортировка по проекции позиции на нормаль
    datasets.sort(key=lambda item: np.dot(item[0].ImagePositionPatient, normal))

    slices = []
    shapes = []
    example_ds = None

    for ds, path in datasets:
        try:
            # Получаем pixel_array с обработкой возможных ошибок
            if not hasattr(ds, "pixel_array"):
                logger.debug(
                    f"[WARN] Файл {path} не содержит pixel_array после декомпрессии"
                )
                continue

            arr = ds.pixel_array.astype(np.float32)

            # Применяем Rescale Slope/Intercept если они есть
            if hasattr(ds, "RescaleSlope") and hasattr(ds, "RescaleIntercept"):
                try:
                    slope = (
                        float(ds.RescaleSlope)
                        if isinstance(
                            ds.RescaleSlope, (str, pydicom.multival.MultiValue)
                        )
                        else ds.RescaleSlope
                    )
                    intercept = (
                        float(ds.RescaleIntercept)
                        if isinstance(
                            ds.RescaleIntercept, (str, pydicom.multival.MultiValue)
                        )
                        else ds.RescaleIntercept
                    )
                    arr = arr * slope + intercept
                except Exception as e:
                    print(
                        f"[WARN] Ошибка применения RescaleSlope/Intercept в {path}: {e}"
                    )

            slices.append(arr)
            shapes.append(arr.shape)

            if example_ds is None:
                example_ds = ds

        except Exception as e:
            logger.debug(f"[ERROR] Ошибка обработки {os.path.basename(path)}: {e}")
            continue

    if not slices:
        raise RuntimeError("Не удалось загрузить ни одного среза.")

    # Приведение всех к одной форме
    shape_counter = Counter(shapes)
    target_shape = shape_counter.most_common(1)[0][0]
    logger.debug(f"[INFO] Приведение всех срезов к форме {target_shape}")

    resized_slices = [
        (
            resize(slice_, target_shape, preserve_range=True).astype(np.float32)
            if slice_.shape != target_shape
            else slice_
        )
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
        volume, ds = load_volume(str(current_user.cor_id))

        # Получаем spacing
        ps = ds.PixelSpacing if hasattr(ds, "PixelSpacing") else [1, 1]
        st = float(ds.SliceThickness) if hasattr(ds, "SliceThickness") else 1.0

        if plane == "axial":
            img = volume[np.clip(index, 0, volume.shape[0] - 1), :, :]
            spacing_x, spacing_y = ps
        elif plane == "sagittal":
            img = np.flip(
                volume[:, :, np.clip(index, 0, volume.shape[2] - 1)], axis=(0, 1)
            )
            spacing_x, spacing_y = st, ps[0]
        elif plane == "coronal":
            img = np.flip(volume[:, np.clip(index, 0, volume.shape[1] - 1), :], axis=0)
            spacing_x, spacing_y = st, ps[1]
        else:
            raise HTTPException(status_code=400, detail="Invalid plane")

        # Windowing
        if mode == "auto":
            img = apply_window(img, ds)
        elif mode == "window":
            try:
                wc = (
                    window_center
                    if window_center is not None
                    else (
                        float(ds.WindowCenter[0])
                        if isinstance(ds.WindowCenter, pydicom.multival.MultiValue)
                        else float(ds.WindowCenter)
                    )
                )
                ww = (
                    window_width
                    if window_width is not None
                    else (
                        float(ds.WindowWidth[0])
                        if isinstance(ds.WindowWidth, pydicom.multival.MultiValue)
                        else float(ds.WindowWidth)
                    )
                )
                img_min = wc - ww / 2
                img_max = wc + ww / 2
                img = np.clip(img, img_min, img_max)
                img = ((img - img_min) / (img_max - img_min + 1e-5)) * 255
                img = img.astype(np.uint8)
            except Exception as e:
                print(f"Window level error, fallback to raw: {e}")
                img = ((img - img.min()) / (img.max() - img.min() + 1e-5)) * 255
                img = img.astype(np.uint8)
        elif mode == "raw":
            img = ((img - img.min()) / (img.max() - img.min() + 1e-5)) * 255
            img = img.astype(np.uint8)

        # Преобразуем в изображение и добавляем паддинг (512x512 канва)
        img_pil = Image.fromarray(img).convert("L")
        img_pil = ImageOps.pad(
            img_pil,
            (512, 512),
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
    try:
        print(f"Loading volume for user cor_id: {current_user.cor_id}")  # Логирование
        volume, ds = load_volume(str(current_user.cor_id))
        print(f"Volume shape: {volume.shape}")  # Логирование
        return {
            "slices": volume.shape[0],
            "width": volume.shape[1],
            "height": volume.shape[2],
        }
    except Exception as e:
        print(f"Error in volume_info: {str(e)}")  # Логирование
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metadata")
def get_metadata(current_user: User = Depends(auth_service.get_current_user)):
    try:
        volume, ds = load_volume(str(current_user.cor_id))
        depth, height, width = volume.shape

        spacing = ds.PixelSpacing if hasattr(ds, "PixelSpacing") else [1.0, 1.0]
        slice_thickness = (
            float(ds.SliceThickness) if hasattr(ds, "SliceThickness") else 1.0
        )

        metadata = {
            "shape": {"depth": depth, "height": height, "width": width},
            "spacing": {
                "x": float(spacing[1]),
                "y": float(spacing[0]),
                "z": slice_thickness,
            },
            "study_info": {
                "StudyInstanceUID": getattr(ds, "StudyInstanceUID", "N/A"),
                "SeriesInstanceUID": getattr(ds, "SeriesInstanceUID", "N/A"),
                "Modality": getattr(ds, "Modality", "N/A"),
                "StudyDate": getattr(ds, "StudyDate", "N/A"),
                "PatientName": str(getattr(ds, "PatientName", "N/A")),
                "PatientBirthDate": getattr(ds, "PatientBirthDate", "N/A"),
                "Manufacturer": getattr(ds, "Manufacturer", "N/A"),
                "DeviceModel": getattr(ds, "ManufacturerModelName", "N/A"),
                "KVP": getattr(ds, "KVP", "N/A"),
                "XRayTubeCurrent": getattr(ds, "XRayTubeCurrent", "N/A"),
                "Exposure": getattr(ds, "Exposure", "N/A"),
            },
        }

        return metadata
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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



