from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
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
from collections import Counter

router = APIRouter(prefix="/dicom", tags=["DICOM"])
HTML_FILE = Path(__file__).parents[1] / "static" / "dicom_viewer.html"
DICOM_DIR = "dicom_files"
os.makedirs(DICOM_DIR, exist_ok=True)

@lru_cache(maxsize=1)
def load_volume():
    print("[INFO] Загружаем том из DICOM-файлов...")

    files = sorted(
        [os.path.join(DICOM_DIR, f) for f in os.listdir(DICOM_DIR) if f.lower().endswith(".dcm")],
        key=lambda x: int(pydicom.dcmread(x, stop_before_pixels=True).InstanceNumber)
    )

    slices = []
    shapes = []
    example_ds = None

    for f in files:
        try:
            ds = pydicom.dcmread(f)
            print(f"[INFO] Обработка файла: {os.path.basename(f)}")
            print(f"        → Transfer Syntax: {ds.file_meta.TransferSyntaxUID}")

            arr = ds.pixel_array.astype(np.float32)

            if hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
                arr = arr * ds.RescaleSlope + ds.RescaleIntercept

            slices.append(arr)
            shapes.append(arr.shape)

            if example_ds is None:
                example_ds = ds

        except Exception as e:
            print(f"[ERROR] Не удалось прочитать {os.path.basename(f)}: {e}")
            continue

    if not slices:
        raise RuntimeError("Не удалось загрузить ни одного DICOM-среза.")

    shape_counter = Counter(shapes)
    target_shape = shape_counter.most_common(1)[0][0]
    print(f"[INFO] Приводим срезы к форме: {target_shape}")

    resized_slices = [
        resize(slice_, target_shape, preserve_range=True).astype(np.float32)
        if slice_.shape != target_shape else slice_
        for slice_ in slices
    ]

    volume = np.stack(resized_slices)
    print(f"[INFO] Загружено срезов: {len(resized_slices)}")

    return volume, example_ds

@router.get("/viewer", response_class=HTMLResponse)
def get_viewer():
    return HTMLResponse(HTML_FILE.read_text(encoding="utf-8"))

def apply_window(img, ds):
    try:
        wc = float(ds.WindowCenter[0]) if isinstance(ds.WindowCenter, pydicom.multival.MultiValue) else float(ds.WindowCenter)
        ww = float(ds.WindowWidth[0]) if isinstance(ds.WindowWidth, pydicom.multival.MultiValue) else float(ds.WindowWidth)
        img_min = wc - ww / 2
        img_max = wc + ww / 2
        img = np.clip(img, img_min, img_max)
        img = ((img - img_min) / (img_max - img_min + 1e-5)) * 255
        return img.astype(np.uint8)
    except Exception as e:
        print(f"[WARN] Ошибка применения Window Center/Width: {e}")
        return img.astype(np.uint8)

@router.get("/reconstruct/{plane}")
def reconstruct(
    plane: str,
    index: int = Query(...),
    size: int = 512,
    mode: str = Query("auto", enum=["auto", "window", "raw"]),
    window_center: float = Query(None),
    window_width: float = Query(None)
):
    try:
        volume, ds = load_volume()

        if plane == "axial":
            img = volume[np.clip(index, 0, volume.shape[0] - 1), :, :]
        elif plane == "sagittal":
            img = np.flip(volume[:, :, np.clip(index, 0, volume.shape[2] - 1)], axis=(0, 1))
        elif plane == "coronal":
            img = np.flip(volume[:, np.clip(index, 0, volume.shape[1] - 1), :], axis=0)
        else:
            raise HTTPException(status_code=400, detail="Invalid plane")

        if mode == "auto":
            img = apply_window(img, ds)
        elif mode == "window":
            try:
                # Используем переданные значения или значения из DICOM
                wc = window_center if window_center is not None else (
                    float(ds.WindowCenter[0]) if isinstance(ds.WindowCenter, pydicom.multival.MultiValue) 
                    else float(ds.WindowCenter))
                ww = window_width if window_width is not None else (
                    float(ds.WindowWidth[0]) if isinstance(ds.WindowWidth, pydicom.multival.MultiValue) 
                    else float(ds.WindowWidth))
                
                img_min = wc - ww / 2
                img_max = wc + ww / 2
                img = np.clip(img, img_min, img_max)
                img = ((img - img_min) / (img_max - img_min + 1e-5)) * 255
                img = img.astype(np.uint8)
            except Exception as e:
                print(f"Window level error, using raw: {e}")
                img = ((img - img.min()) / (img.max() - img.min() + 1e-5)) * 255
                img = img.astype(np.uint8)
        elif mode == "raw":
            img = ((img - img.min()) / (img.max() - img.min() + 1e-5)) * 255
            img = img.astype(np.uint8)

        ps = ds.PixelSpacing if hasattr(ds, 'PixelSpacing') else [1, 1]
        st = float(ds.SliceThickness) if hasattr(ds, 'SliceThickness') else 1.0

        if plane == "axial":
            spacing_x, spacing_y = ps
        elif plane == "sagittal":
            spacing_x, spacing_y = st, ps[0]
        elif plane == "coronal":
            spacing_x, spacing_y = st, ps[1]

        aspect_ratio = spacing_y / spacing_x
        height = size
        width = int(size * aspect_ratio)

        img = Image.fromarray(img).resize((width, height))
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload")
async def upload_dicom_files(files: List[UploadFile] = File(...)):
    try:
        shutil.rmtree(DICOM_DIR)
        os.makedirs(DICOM_DIR, exist_ok=True)

        processed_files = 0
        valid_files = 0

        for file in files:
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in {'.dcm', '.zip'}:
                continue

            temp_path = os.path.join(DICOM_DIR, file.filename)
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            if file_ext == '.zip':
                try:
                    with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                        zip_ref.extractall(DICOM_DIR)
                    os.remove(temp_path)
                    for extracted_file in os.listdir(DICOM_DIR):
                        if extracted_file.lower().endswith('.dcm'):
                            try:
                                pydicom.dcmread(os.path.join(DICOM_DIR, extracted_file), stop_before_pixels=True)
                                valid_files += 1
                            except:
                                os.remove(os.path.join(DICOM_DIR, extracted_file))
                except zipfile.BadZipFile:
                    os.remove(temp_path)
                    continue
            else:
                try:
                    pydicom.dcmread(temp_path, stop_before_pixels=True)
                    valid_files += 1
                except:
                    os.remove(temp_path)
                    continue

            processed_files += 1

        if valid_files == 0:
            raise HTTPException(status_code=400, detail="No valid DICOM files found in the uploaded files")

        load_volume.cache_clear()

        return {
            "message": f"Successfully processed {processed_files} files, {valid_files} DICOM files validated"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/volume_info")
def get_volume_info():
    try:
        volume, ds = load_volume()
        return {
            "slices": volume.shape[0],
            "width": volume.shape[1],
            "height": volume.shape[2]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metadata")
def get_metadata():
    try:
        volume, ds = load_volume()
        depth, height, width = volume.shape

        spacing = ds.PixelSpacing if hasattr(ds, 'PixelSpacing') else [1.0, 1.0]
        slice_thickness = float(ds.SliceThickness) if hasattr(ds, 'SliceThickness') else 1.0

        return {
            "shape": {
                "depth": depth,
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
        raise HTTPException(status_code=500, detail=str(e))
