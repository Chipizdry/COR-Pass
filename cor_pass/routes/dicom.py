from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import os
import pydicom
from cor_pass.services.access import user_access

router = APIRouter(prefix="/dicom", tags=["DICOM"])

DICOM_DIR = "dicom_files"
os.makedirs(DICOM_DIR, exist_ok=True)


@router.post("/upload", dependencies=[Depends(user_access)])
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


@router.get("/list", dependencies=[Depends(user_access)])
async def list_dicom_files():
    """Список доступных DICOM файлов"""
    files = [f for f in os.listdir(DICOM_DIR) if f.endswith((".dcm", ".DCM"))]
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
        raise HTTPException(
            status_code=404, detail=f"DICOM file not found or invalid: {str(e)}"
        )


@router.get("/viewer", response_class=HTMLResponse, dependencies=[Depends(user_access)])
async def dicom_viewer():
    """Встроенный DICOM просмотровщик"""
    return FileResponse("cor_pass/static/dicom_viewer.html")


@router.get("/{filename}", dependencies=[Depends(user_access)])
async def get_dicom_file(filename: str):
    """Получение DICOM файла"""
    try:
        file_path = os.path.join(DICOM_DIR, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(file_path, media_type="application/dicom")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
