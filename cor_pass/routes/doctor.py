import json
from fastapi import APIRouter, Body, Depends, Form, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional

from cor_pass.database.db import get_db
from cor_pass.database.models import User
from cor_pass.repository.doctor import create_doctor, create_doctor_service
from cor_pass.schemas import (
    CertificateResponse,
    ClinicAffiliationResponse,
    DiplomaResponse,
    DoctorCreate,
    DoctorResponse,
)

from cor_pass.services.access import user_access
from cor_pass.services.auth import auth_service
from cor_pass.services.image_validation import validate_image_file
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/doctor", tags=["Doctor"])


@router.post(
    "/signup",
    # response_model=DoctorResponse,
    status_code=201,
    dependencies=[Depends(user_access)],
)
async def signup_doctor(
    doctor_data: str = Form(
        ...,
        example='{"work_email": "doctor@example.com", "first_name": "John", "surname": "Doe", "last_name": "Smith", "scientific_degree": "PhD", "date_of_last_attestation": "2022-12-31", "diplomas": [{"date": "2023-01-01", "series": "AB", "number": "123456", "university": "Medical University"}], "certificates": [{"date": "2023-01-01", "series": "CD", "number": "654321", "university": "Another University"}], "clinic_affiliations": [{"clinic_name": "City Hospital", "department": "Cardiology", "position": "Senior Doctor", "specialty": "Cardiologist"}]}',
        description="Данные врача в формате JSON. Пример: см. значение по умолчанию.",
    ),
    # doctor_data: DoctorCreate = Body(...),
    doctors_photo: UploadFile = File(None),
    diploma_scan: UploadFile = File(None),
    certificate_scan: UploadFile = File(None),
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Создание врача со всеми связанными данными**\n
    Этот маршрут позволяет создать врача вместе с дипломами, сертификатами и привязками к клиникам.
    Уровень доступа:
    - Текущий авторизованный пользователь
    :param doctor_data: DoctorCreate: Данные для создания врача.
    :param db: Session: Сессия базы данных.
    :return: Созданный врач.
    :rtype: DoctorResponse
    """
    try:
        # Валидация изображений
        if doctors_photo:
            doctors_photo = await validate_image_file(doctors_photo)
        if diploma_scan:
            diploma_scan = await validate_image_file(diploma_scan)
        if certificate_scan:
            certificate_scan = await validate_image_file(certificate_scan)
    except HTTPException as exeption:
        logger.error(f"Error validating image: {str(exeption)}")
        raise exeption

    # Парсим JSON-строку в объект DoctorCreate
    doctor_data_dict = json.loads(doctor_data)
    doctors_photo_bytes = await doctors_photo.read() if doctors_photo else None
    diploma_scan_bytes = await diploma_scan.read() if diploma_scan else None
    certificate_scan_bytes = await certificate_scan.read() if certificate_scan else None
    # doctor_data_obj = DoctorCreate(**doctor_data_dict)
    doctor = await create_doctor(
        doctor_data=doctor_data_dict,
        db=db,
        doctors_photo_bytes=doctors_photo_bytes,
        user=user,
    )
    doctors_data = await create_doctor_service(
        doctor_data=doctor_data_dict,
        db=db,
        doctor=doctor,
        diploma_scan_bytes=diploma_scan_bytes,
        certificate_scan_bytes=certificate_scan_bytes,
    )

    # Сериализуем ответ
    doctor_response = DoctorResponse(
        id=doctor.id,
        doctor_id=doctor.doctor_id,
        work_email=doctor.work_email,
        first_name=doctor.first_name,
        surname=doctor.surname,
        last_name=doctor.last_name,
        doctors_photo=doctor.doctors_photo,
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
