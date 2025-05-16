from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import StreamingResponse

from cor_pass.database.db import get_db

from cor_pass.database.models import (
    Doctor_Status,
)
from cor_pass.services.access import lawyer_access
from cor_pass.schemas import (
    CertificateResponse,
    ClinicAffiliationResponse,
    DiplomaResponse,
    DoctorResponse,
    DoctorWithRelationsResponse,
)
from cor_pass.repository import lawyer
import base64
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.services.logger import logger

router = APIRouter(prefix="/lawyer", tags=["Lawyer"])


@router.get(
    "/get_all_doctors",
    response_model=List[DoctorResponse],
    dependencies=[Depends(lawyer_access)],
)
async def get_all_doctors(
    skip: int = Query(0, description="Количество записей для пропуска"),
    limit: int = Query(10, description="Максимальное количество записей для возврата"),
    status: Optional[str] = Query(None, description="Фильтр по статусу врача"),
    sort_by: Optional[str] = Query(None, description="Сортировать по полю"),
    sort_order: Optional[str] = Query(
        "asc", description="Порядок сортировки ('asc' или 'desc')"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    **Получение списка всех врачей**\n
    Этот маршрут позволяет получить список всех врачей с возможностью пагинации,
    фильтрации по статусу и сортировки по дате регистрации.
    Уровень доступа:
    - Пользователи с ролью "lawyer"
    :param skip: int: Количество записей для пропуска.
    :param limit: int: Максимальное количество записей для возврата.
    :param status: Optional[str]: Фильтровать по статусу врача.
    :param sort_by: Optional[str]: Поле для сортировки.
    :param sort_order: Optional[str]: Порядок сортировки ('asc' или 'desc').
    :param db: AsyncSession: Сессия базы данных.
    :return: Список врачей.
    :rtype: List[DoctorResponse]
    """
    list_doctors = await lawyer.get_doctors(
        skip=skip,
        limit=limit,
        db=db,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    if not list_doctors:
        return []

    doctors_response = [
        DoctorResponse(
            id=doctor.id,
            doctor_id=doctor.doctor_id,
            work_email=doctor.work_email,
            phone_number=doctor.phone_number,
            first_name=doctor.first_name,
            surname=doctor.surname,
            last_name=doctor.last_name,
            scientific_degree=doctor.scientific_degree,
            date_of_last_attestation=doctor.date_of_last_attestation,
            status=doctor.status,
        )
        for doctor in list_doctors
    ]
    return doctors_response


# Функция для преобразования бинарных данных в base64


def bytes_to_base64(binary_data: bytes):
    if binary_data is None:
        return None
    return base64.b64encode(binary_data).decode("utf-8")



@router.patch("/asign_status/{doctor_id}", dependencies=[Depends(lawyer_access)])
async def assign_status(
    doctor_id: str,
    doctor_status: Doctor_Status,
    db: AsyncSession = Depends(get_db),
):
    """
    **Assign a doctor_status to a doctor by doctor_id. / Применение нового статуса доктора (подтвержден / на рассмотрении)**\n

    :param doctor_id: str: doctor_id of the user to whom you want to assign the status.

    :param doctor_status: DoctorStatus: The selected doctor_status for the assignment (pending, approved).

    :param db: AsyncSession: Database Session.

    :return: Message about successful status change.

    :rtype: dict
    """
    doctor = await lawyer.get_doctor(doctor_id=doctor_id, db=db)

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found"
        )

    if doctor_status == doctor.status:
        return {"message": "The account status has already been assigned"}
    else:
        await lawyer.approve_doctor(doctor=doctor, db=db, status=doctor_status)
        return {
            "message": f"{doctor.first_name} {doctor.last_name}'s status - {doctor_status.value}"
        }


@router.delete("/delete_doctor/{doctor_id}", dependencies=[Depends(lawyer_access)])
async def delete_user(doctor_id: str, db: AsyncSession = Depends(get_db)):
    """
    **Delete doctor by doctor_id. / Удаление врача по doctor_id**\n
    """
    doctor = await lawyer.get_doctor(doctor_id=doctor_id, db=db)
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found"
        )
    else:
        await lawyer.delete_doctor_by_doctor_id(db=db, doctor_id=doctor_id)
        return {
            "message": f" doctor - was deleted"
        }




@router.get("/doctors/{doctor_id}/photo", dependencies=[Depends(lawyer_access)])
async def get_doctor_photo(doctor_id: str, db: AsyncSession = Depends(get_db)):
    """Получает фотографию врача из базы данных."""
    doctor = await lawyer.get_doctor(doctor_id=doctor_id, db=db) # Assuming you have a function to get basic doctor info
    if not doctor or not doctor.doctors_photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor or photo not found")

    async def image_stream():
        yield doctor.doctors_photo

    return StreamingResponse(image_stream(), media_type="image/jpeg") # Adjust media type as needed

@router.get("/diplomas/{diploma_id}", dependencies=[Depends(lawyer_access)])
async def get_diploma_file(diploma_id: str, db: AsyncSession = Depends(get_db)):
    """Получает файл диплома (изображение или PDF) из базы данных."""
    document = await lawyer.get_diploma_by_id(diploma_id=diploma_id, db=db)
    if not document or not document.file_data or not document.file_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document or file not found")

    async def document_stream():
        yield document.file_data

    return StreamingResponse(document_stream(), media_type=document.file_type)

@router.get("/certificates/{certificate_id}", dependencies=[Depends(lawyer_access)])
async def get_certificate_file(certificate_id: str, db: AsyncSession = Depends(get_db)):
    """Получает файл сертификата (изображение или PDF) из базы данных."""
    document = await lawyer.get_certificate_by_id(certificate_id=certificate_id, db=db)
    if not document or not document.file_data or not document.file_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document or file not found")

    async def document_stream():
        yield document.file_data

    return StreamingResponse(document_stream(), media_type=document.file_type)

@router.get(
    "/get_doctor_info/{doctor_id}",
    response_model=DoctorWithRelationsResponse,
    dependencies=[Depends(lawyer_access)],
)
async def get_doctor_with_relations(
    doctor_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    **Получение информации о враче со всеми связями**\n
    Этот маршрут позволяет получить полную информацию о враче, включая дипломы, сертификаты и привязки к клиникам.\n
    Уровень доступа:\n
    - Пользователи с ролью "lawyer"\n
    :param doctor_id: str: ID врача.\n
    :param db: AsyncSession: Сессия базы данных.\n
    :return: Информация о враче со всеми связями.\n
    :rtype: DoctorWithRelationsResponse
    """
    doctor = await lawyer.get_all_doctor_info(doctor_id=doctor_id, db=db)

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found"
        )

    doctor_response = DoctorWithRelationsResponse(
        id=doctor.id,
        doctor_id=doctor.doctor_id,
        work_email=doctor.work_email,
        phone_number=doctor.phone_number,
        first_name=doctor.first_name,
        surname=doctor.surname,
        doctors_photo=f"/doctors/{doctor_id}/photo" if doctor.doctors_photo else None,
        last_name=doctor.last_name,
        scientific_degree=doctor.scientific_degree,
        date_of_last_attestation=doctor.date_of_last_attestation,
        status=doctor.status,
        diplomas=[
            DiplomaResponse(
                id=diploma.id,
                date=diploma.date,
                series=diploma.series,
                number=diploma.number,
                university=diploma.university,
                file_data=f"/diplomas/{diploma.id}" if diploma.file_data else None,
            )
            for diploma in doctor.diplomas
        ],
        certificates=[
            CertificateResponse(
                id=certificate.id,
                date=certificate.date,
                series=certificate.series,
                number=certificate.number,
                university=certificate.university,
                file_data=f"/certificates/{certificate.id}" if certificate.file_data else None, 
            )
            for certificate in doctor.certificates
        ],
        clinic_affiliations=[
            ClinicAffiliationResponse(
                id=affiliation.id,
                clinic_name=affiliation.clinic_name,
                department=affiliation.department,
                position=affiliation.position,
                specialty=affiliation.specialty,
            )
            for affiliation in doctor.clinic_affiliations
        ],
    )

    return doctor_response