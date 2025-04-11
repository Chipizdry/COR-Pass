

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from skimage.transform import resize
from skimage import filters
import numpy as np
import os
import pydicom
from PIL import Image
from io import BytesIO
from pathlib import Path
from typing import List

router = APIRouter(prefix="/api/dicom", tags=["DICOM"])

DICOM_DIR = "dicom_files"
os.makedirs(DICOM_DIR, exist_ok=True)


def normalize_image(img):
    """Нормализация изображения к диапазону 0-255"""
    img_min = img.min()
    img_max = img.max()
    
    if img_max == img_min:
        return np.zeros_like(img, dtype=np.uint8)
    
    normalized = ((img - img_min) / (img_max - img_min)) * 255
    return normalized.astype(np.uint8)

def apply_window(img, window_center, window_width):
    """Применение оконных настроек к изображению"""
    img_min = window_center - window_width // 2
    img_max = window_center + window_width // 2
    img = np.clip(img, img_min, img_max)
    img = ((img - img_min) / (img_max - img_min)) * 255
    return img.astype(np.uint8)


@router.post("/upload")
async def upload_dicom_file(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(DICOM_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        pydicom.dcmread(file_path)  # Проверка, что файл корректный
        return {"filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid DICOM file: {str(e)}")


@router.get("/list")
async def list_dicom_files():
    files = [f for f in os.listdir(DICOM_DIR) if f.endswith(('.dcm', '.DCM'))]
    return {"files": files}


@router.get("/{filename}/metadata")
async def get_dicom_metadata(filename: str):
    try:
        file_path = os.path.join(DICOM_DIR, filename)
        ds = pydicom.dcmread(file_path)
        metadata = {elem.name: str(elem.value) for elem in ds if elem.name != "Pixel Data"}
        return metadata
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"DICOM file not found or invalid: {str(e)}")


@router.get("/viewer", response_class=HTMLResponse)
async def dicom_viewer():
    return FileResponse("cor_pass/dicom/static/dicom_viewer.html")


@router.get("/{filename}")
async def get_dicom_file(filename: str):
    file_path = os.path.join(DICOM_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="application/dicom")


@router.get("/series/{series_uid}")
async def get_dicom_series(series_uid: str):
    try:
        print(f"Looking for series: {series_uid}")
        series_files = []

        for filename in os.listdir(DICOM_DIR):
            if filename.upper() == 'DICOMDIR':
                continue

            try:
                ds = pydicom.dcmread(os.path.join(DICOM_DIR, filename))
                if ds.SeriesInstanceUID == series_uid:
                    series_files.append(filename)
            except Exception as e:
                print(f"Error reading {filename}: {e}")

        if not series_files:
            raise HTTPException(status_code=404, detail="Series not found")

        return {"files": sorted(series_files)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reconstruct/{plane}")
def reconstruct_plane(
    plane: str,
    index: int = Query(None),
    size: int = Query(512, gt=0, le=1024)
):
    try:
        print(f"\n=== Reconstruction Start: {plane.upper()} ===")

        files = sorted(
            [os.path.join(DICOM_DIR, f) for f in os.listdir(DICOM_DIR) if f.lower().endswith('.dcm')],
            key=lambda x: int(pydicom.dcmread(x).InstanceNumber)
        )

        slices = []
        for f in files:
            try:
                ds = pydicom.dcmread(f)
                if 'PixelData' not in ds:
                    continue

                pixel_array = ds.pixel_array.astype(np.float32)

                if hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
                    pixel_array = pixel_array * ds.RescaleSlope + ds.RescaleIntercept

                slices.append(pixel_array)
            except Exception as e:
                print(f"Skip file {f}: {e}")

        if not slices:
            raise HTTPException(status_code=404, detail="No valid slices found")

        try:
            volume = np.stack(slices)
        except ValueError:
            from collections import Counter
            target_shape = Counter([s.shape for s in slices]).most_common(1)[0][0]
            resized = [resize(s, target_shape, preserve_range=True) for s in slices]
            volume = np.stack(resized)

        # Выбор среза
        if plane.lower() == "axial":
            z = index if index is not None else volume.shape[0] // 2
            img = volume[np.clip(z, 0, volume.shape[0] - 1), :, :]
        elif plane.lower() == "sagittal":
            x = index if index is not None else volume.shape[2] // 2
            img = volume[:, :, np.clip(x, 0, volume.shape[2] - 1)]
        elif plane.lower() == "coronal":
            y = index if index is not None else volume.shape[1] // 2
            img = volume[:, np.clip(y, 0, volume.shape[1] - 1), :]
        else:
            raise HTTPException(status_code=400, detail="Invalid plane")

        print(f"Selected slice shape: {img.shape}, dtype: {img.dtype}, min={img.min()}, max={img.max()}")

        # Применение оконной настройки
        try:
            ds = pydicom.dcmread(files[0])
            wc = ds.WindowCenter
            ww = ds.WindowWidth

            # Обработка MultiValue
            wc = float(wc[0]) if isinstance(wc, pydicom.multival.MultiValue) else float(wc)
            ww = float(ww[0]) if isinstance(ww, pydicom.multival.MultiValue) else float(ww)

            print(f"Windowing: center={wc}, width={ww}")
            img = apply_window(img, wc, ww)
        except Exception as e:
            print(f"Windowing failed: {e} — applying normalization")
            img = normalize_image(img)

        print(f"After window/normalize: dtype={img.dtype}, min={img.min()}, max={img.max()}")

        # Sharpen
        img = filters.unsharp_mask(img, radius=1, amount=1)
        img = (img * 255).clip(0, 255).astype(np.uint8)
        print(f"After sharpening: shape={img.shape}, dtype={img.dtype}")

        pil_img = Image.fromarray(img)
        pil_img = pil_img.resize((size, size), Image.LANCZOS)

        buf = BytesIO()
        pil_img.save(buf, format="PNG")
        buf.seek(0)
        print("=== Reconstruction done ===")
        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:
        print(f"Reconstruction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
