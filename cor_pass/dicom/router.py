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
from fastapi import UploadFile, File




router = APIRouter(prefix="/api/dicom", tags=["DICOM"])
HTML_FILE = Path(__file__).parents[1] / "static" / "dicom_viewer.html"
DICOM_DIR = "dicom_files"
os.makedirs(DICOM_DIR, exist_ok=True)

from skimage.transform import resize
from collections import Counter

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
        ds = pydicom.dcmread(f)
        arr = ds.pixel_array.astype(np.float32)
        if hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
            arr = arr * ds.RescaleSlope + ds.RescaleIntercept
        slices.append(arr)
        shapes.append(arr.shape)
        if example_ds is None:
            example_ds = ds

    # Определяем наиболее частую форму (размер срезов)
    shape_counter = Counter(shapes)
    target_shape = shape_counter.most_common(1)[0][0]
    print(f"[INFO] Приводим к форме: {target_shape}")

    resized_slices = [
        resize(slice_, target_shape, preserve_range=True).astype(np.float32)
        if slice_.shape != target_shape else slice_
        for slice_ in slices
    ]

    volume = np.stack(resized_slices)
    return volume, example_ds

@router.get("/viewer", response_class=HTMLResponse)
def get_viewer():
    return HTMLResponse(HTML_FILE.read_text(encoding="utf-8"))


def apply_window(img, center, width):
    img_min = center - width / 2
    img_max = center + width / 2
    img = np.clip(img, img_min, img_max)
    img = ((img - img_min) / (img_max - img_min)) * 255
    return img.astype(np.uint8)

@router.get("/reconstruct/{plane}")
def reconstruct(plane: str, index: int = Query(...), size: int = 512):
    try:
        volume, ds = load_volume()

        if plane == "axial":
            img = volume[np.clip(index, 0, volume.shape[0] - 1), :, :]
        elif plane == "sagittal":
            img = volume[:, :, np.clip(index, 0, volume.shape[2] - 1)]
             # Поворот сагиттального среза на 180 градусов относительно горизонта
            img = np.flip(img, axis=(0, 1))  # или img = np.rot90(img, 2)
        elif plane == "coronal":
            img = volume[:, np.clip(index, 0, volume.shape[1] - 1), :]
            # Разворот коронального среза на 180 градусов
            img = np.flip(img, axis=0)
        else:
            raise HTTPException(status_code=400, detail="Invalid plane")

        wc = float(ds.WindowCenter[0]) if isinstance(ds.WindowCenter, pydicom.multival.MultiValue) else float(ds.WindowCenter)
        ww = float(ds.WindowWidth[0]) if isinstance(ds.WindowWidth, pydicom.multival.MultiValue) else float(ds.WindowWidth)
        img = apply_window(img, wc, ww)

        # Получаем spacing
        ps = ds.PixelSpacing if hasattr(ds, 'PixelSpacing') else [1, 1]
        st = float(ds.SliceThickness) if hasattr(ds, 'SliceThickness') else 1.0

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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/upload")
async def upload_dicom_files(files: List[UploadFile] = File(...)):
    try:
        # Очищаем директорию перед загрузкой новых файлов
        shutil.rmtree(DICOM_DIR)
        os.makedirs(DICOM_DIR, exist_ok=True)
        
        processed_files = 0
        valid_files = 0
        
        for file in files:
            file_ext = os.path.splitext(file.filename)[1].lower()
            
            # Пропускаем файлы с недопустимыми расширениями
            if file_ext not in {'.dcm', '.zip'}:
                continue
                
            temp_path = os.path.join(DICOM_DIR, file.filename)
            
            # Сохраняем файл
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Обрабатываем ZIP архив
            if file_ext == '.zip':
                try:
                    with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                        zip_ref.extractall(DICOM_DIR)
                    os.remove(temp_path)
                    
                    # Валидация DICOM файлов после распаковки
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
                # Валидация одиночного DICOM файла
                try:
                    pydicom.dcmread(temp_path, stop_before_pixels=True)
                    valid_files += 1
                except:
                    os.remove(temp_path)
                    continue
                    
            processed_files += 1
        
        if valid_files == 0:
            raise HTTPException(
                status_code=400, 
                detail="No valid DICOM files found in the uploaded files"
            )
        
        # Очищаем кэш загруженного объема
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
