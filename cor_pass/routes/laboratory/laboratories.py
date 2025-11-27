from fastapi import APIRouter, UploadFile, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.db import get_db
from cor_pass.schemas import LaboratoryCreate, LaboratoryUpdate, LaboratoryRead
from cor_pass.repository.laboratory.laboratory import (
    get_laboratory, create_laboratory, update_laboratory, upload_lab_logo
)
from cor_pass.services.shared.document_validation import validate_prescription_file
from cor_pass.services.shared.image_validation import validate_image_file
from cor_pass.services.shared.access import admin_access, lab_assistant_or_doctor_access

router = APIRouter(prefix="/laboratory", tags=["Laboratory"])


@router.post("/create", response_model=LaboratoryRead, status_code=201, dependencies=[Depends(admin_access)])
async def create_lab(data: LaboratoryCreate, db: AsyncSession = Depends(get_db)):
    return await create_laboratory(db, data)


@router.get("/info", response_model=LaboratoryRead, dependencies=[Depends(lab_assistant_or_doctor_access)])
async def get_lab(db: AsyncSession = Depends(get_db)):
    lab = await get_laboratory(db)
    if not lab:
        raise HTTPException(status_code=404, detail="Запись лаборатории не найдена")
    return lab


@router.put("/update", response_model=LaboratoryRead, dependencies=[Depends(admin_access)])
async def update_lab(data: LaboratoryUpdate, db: AsyncSession = Depends(get_db)):
    return await update_laboratory(db, data)


@router.post("/logo", response_model=LaboratoryRead, dependencies=[Depends(admin_access)])
async def upload_logo(file: UploadFile, db: AsyncSession = Depends(get_db)):
    content = await validate_prescription_file(file)
    return await upload_lab_logo(db=db, file_data=content, mime_type=file.content_type)


@router.get("/logo", dependencies=[Depends(lab_assistant_or_doctor_access)])
async def get_logo(db: AsyncSession = Depends(get_db)):
    lab = await get_laboratory(db)
    if not lab or not lab.lab_logo_data:
        raise HTTPException(status_code=404, detail="Логотип не найден")
    return Response(content=lab.lab_logo_data, media_type=lab.lab_logo_type)