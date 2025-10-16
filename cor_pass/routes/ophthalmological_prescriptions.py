from datetime import datetime, timedelta, timezone
import uuid
from fastapi import APIRouter, Depends, status, HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from cor_pass.repository.case import get_pending_signings_for_ophtalmological, get_pending_signings_for_report
from cor_pass.repository.doctor import get_doctor_signature_by_id
from cor_pass.repository.lawyer import get_doctor
from cor_pass.schemas import (
    InitiateSignatureResponse,
    OphthalmologicalPrescriptionCreate,
    OphthalmologicalPrescriptionReadWithSigning,
    OphthalmologicalPrescriptionUpdate,
    OphthalmologicalPrescriptionRead,
)
from cor_pass.routes.doctor import router as doctor_router
from cor_pass.database.models import DoctorSignatureSession, User
from cor_pass.services.access import user_access, doctor_access
from cor_pass.services.auth import auth_service
from cor_pass.database.db import get_db
from cor_pass.repository.ophthalmological_prescription import (
    create_ophthalmological_prescription,
    get_prescription_by_patient_new,
    get_prescriptions_by_patient,
    get_prescription_by_id,
    update_prescription,
    delete_prescription,
)
from cor_pass.services.websocket import DEEP_LINK_SCHEME, SESSION_TTL_MINUTES

router = APIRouter(
    prefix="/ophthalmology/prescriptions",
    tags=["Ophthalmological Prescriptions"],
)


@router.post(
    "/sign",
    response_model=InitiateSignatureResponse,
    dependencies=[Depends(doctor_access)],
    summary="Инициация создания и подписания рецепта",
)
async def initiate_prescription_signing(
    body: OphthalmologicalPrescriptionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
):
    """
    Создает рецепт и инициирует подписание
    """

    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    prescription = await create_ophthalmological_prescription(db=db, body=body, user=user)


    session_token = uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=SESSION_TTL_MINUTES)

    sess = DoctorSignatureSession(
        session_token=session_token,
        doctor_cor_id=doctor.doctor_id,
        ophthalmological_prescription_id=prescription.id,
        doctor_signature_id=body.doctor_signature_id,
        status="pending",
        expires_at=expires_at,
    )
    db.add(sess)
    await db.commit()

    deep_link = f"{DEEP_LINK_SCHEME}?session_token={session_token}"

    return InitiateSignatureResponse(
        session_token=session_token,
        deep_link=deep_link,
        expires_at=expires_at,
        status="pending",
    )



# @router.post(
#     "/create",
#     response_model=OphthalmologicalPrescriptionRead,
#     status_code=status.HTTP_201_CREATED,
#     dependencies=[Depends(user_access)],
#     summary="Создать новый рецепт",
# )
# async def create_ophthalmological_prescription_route(
#     body: OphthalmologicalPrescriptionCreate,
#     current_user: User = Depends(auth_service.get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     Создает новый рецепт для очков
#     """
#     new_prescription = await create_ophthalmological_prescription(
#         db=db,
#         body=body,
#         user=current_user,
#     )
#     return new_prescription




@router.get(
    "/patient/{patient_id}",
    response_model=List[OphthalmologicalPrescriptionReadWithSigning],
    dependencies=[Depends(user_access)],
    summary="Получить рецепты пациента (с информацией о враче и подписи)",
)
async def get_patient_prescriptions_route(
    patient_id: str,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает все офтальмологические рецепты пациента вместе с информацией
    о подписи и враче (если подпись есть).
    """
    prescriptions = await get_prescription_by_patient_new(db=db, patient_id=patient_id)
    response_list: list[OphthalmologicalPrescriptionReadWithSigning] = []

    for presc in prescriptions:
        doctor_signature_info = None
        signing_session = None
        if presc.doctor_signature_id:
            try:
                doctor_signature_info = await get_doctor_signature_by_id(
                    db=db, signature_id=presc.doctor_signature_id, router=doctor_router
                )
                sign_session = await get_pending_signings_for_ophtalmological(db=db, ophthalmological_prescription_id=presc.id, doctor_id=doctor_signature_info.doctor_id)
                signing_session = sign_session
            except HTTPException:
                doctor_signature_info = None

        response_list.append(
            OphthalmologicalPrescriptionReadWithSigning(
                ophthalmological_prescription=presc,
                doctor_signing_info=doctor_signature_info,
                current_signings=signing_session if signing_session else None
            )
        )

    return response_list


# @router.get(
#     "/{prescription_id}",
#     response_model=OphthalmologicalPrescriptionRead,
#     dependencies=[Depends(user_access)],
#     summary="Получить рецепт по ID",
# )
# async def get_prescription_by_id_route(
#     prescription_id: str,
#     current_user: User = Depends(auth_service.get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     Возвращает рецепт по ID.
#     """
#     prescription = await get_prescription_by_id(db=db, prescription_id=prescription_id)
#     if not prescription:
#         raise HTTPException(status_code=404, detail="Рецепт не найден")
#     return prescription


# @router.put(
#     "/{prescription_id}",
#     response_model=OphthalmologicalPrescriptionRead,
#     dependencies=[Depends(user_access)],
#     summary="Обновить рецепт на очки",
# )
# async def update_prescription_route(
#     prescription_id: str,
#     body: OphthalmologicalPrescriptionUpdate,
#     current_user: User = Depends(auth_service.get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     Обновляет рецепт на очки
#     """
#     updated_prescription = await update_prescription(db=db, prescription_id=prescription_id, body=body)
#     if not updated_prescription:
#         raise HTTPException(status_code=404, detail="Рецепт не найден")
#     return updated_prescription



# @router.delete(
#     "/{prescription_id}",
#     status_code=status.HTTP_204_NO_CONTENT,
#     dependencies=[Depends(user_access)],
#     summary="Удаляет рецепт очков",
# )
# async def delete_prescription_route(
#     prescription_id: str,
#     current_user: User = Depends(auth_service.get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     Удалет рецепт по id
#     """
#     deleted = await delete_prescription(db=db, prescription_id=prescription_id)
#     if not deleted:
#         raise HTTPException(status_code=404, detail="Рецепт не найден")
#     return None