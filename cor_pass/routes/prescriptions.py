from datetime import datetime
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Depends, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.db import get_db
from cor_pass.database.models import User
from cor_pass.services.auth import auth_service
from cor_pass.repository import prescription
from cor_pass.schemas import PrescriptionFileRead
from cor_pass.services.document_validation import validate_prescription_file

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])


@router.post("/upload", response_model=PrescriptionFileRead, status_code=status.HTTP_201_CREATED)
async def upload_prescription(
    file: UploadFile = File(...),
    issue_date: Optional[datetime] = None,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await validate_prescription_file(file)

    new_file = await prescription.create_prescription_file(
        db=db,
        user_cor_id=current_user.cor_id,
        file_name=file.filename,
        file_type=file.content_type,
        file_size_kb=round(len(content) / 1024, 2),
        file_data=content,
        issue_date=issue_date,
    )
    return new_file


@router.get("/list", response_model=list[PrescriptionFileRead])
async def list_prescriptions(
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await prescription.get_user_prescriptions(db, current_user.cor_id)


@router.get("/{file_id}")
async def download_prescription(
    file_id: str,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    file_obj = await prescription.get_prescription_file(db, file_id, current_user.cor_id)
    return Response(
        content=file_obj.file_data,
        media_type=file_obj.file_type,
        headers={"Content-Disposition": f"attachment; filename={file_obj.file_name}"},
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prescription(
    file_id: str,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await prescription.delete_prescription_file(db, file_id, current_user.cor_id)