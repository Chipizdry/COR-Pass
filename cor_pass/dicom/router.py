

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import os
import pydicom
from pathlib import Path
from typing import List

router = APIRouter(prefix="/api/dicom", tags=["DICOM"])

DICOM_DIR = "dicom_files"
os.makedirs(DICOM_DIR, exist_ok=True)

@router.post("/upload")
async def upload_dicom_file(file: UploadFile = File(...)):
    """Загрузка DICOM файла на сервер"""
    try:
        file_path = os.path.join(DICOM_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        # Проверка, что файл действительно DICOM
        pydicom.dcmread(file_path)
        
        return {"filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid DICOM file: {str(e)}")

@router.get("/list")
async def list_dicom_files():
    """Список доступных DICOM файлов"""
    files = [f for f in os.listdir(DICOM_DIR) if f.endswith(('.dcm', '.DCM'))]
    return {"files": files}

@router.get("/{filename}/metadata")
async def get_dicom_metadata(filename: str):
    """Получение метаданных DICOM файла"""
    try:
        file_path = os.path.join(DICOM_DIR, filename)
        ds = pydicom.dcmread(file_path)
        
        metadata = {}
        for elem in ds:
            if elem.name != "Pixel Data":
                metadata[elem.name] = str(elem.value)
        
        return metadata
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"DICOM file not found or invalid: {str(e)}")

@router.get("/viewer", response_class=HTMLResponse)
async def dicom_viewer():
    """Встроенный DICOM просмотровщик"""
    return FileResponse("cor_pass/dicom/static/dicom_viewer.html")

@router.get("/{filename}")
async def get_dicom_file(filename: str):
    """Получение DICOM файла"""
    try:
        file_path = os.path.join(DICOM_DIR, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileResponse(file_path, media_type="application/dicom")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/series/{series_uid}")
async def get_dicom_series(series_uid: str):
    try:
        print(f"Looking for series: {series_uid}")  # Логирование
        series_files = []
        
        for filename in os.listdir(DICOM_DIR):
            # Пропускаем DICOMDIR (регистронезависимая проверка)
            if filename.upper() == 'DICOMDIR':
                print(f"Skipping DICOMDIR file: {filename}")
                continue
                
            file_path = os.path.join(DICOM_DIR, filename)
            try:
                ds = pydicom.dcmread(file_path)
                print(f"Checking file: {filename}, SeriesInstanceUID: {ds.SeriesInstanceUID}")  # Логирование
                
                if ds.SeriesInstanceUID == series_uid:
                    series_files.append(filename)
            except Exception as e:
                print(f"Error reading {filename}: {str(e)}")  # Логирование ошибок
                continue
        
        if not series_files:
            print("Series not found")  # Логирование
            raise HTTPException(status_code=404, detail="Series not found")
        
        print(f"Found {len(series_files)} files for series")  # Логирование
        return {"files": sorted(series_files)}
        
    except Exception as e:
        print(f"Server error: {str(e)}")  # Логирование
        raise HTTPException(status_code=500, detail=str(e))  

