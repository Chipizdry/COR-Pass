from datetime import date
import json
from fastapi import (
    APIRouter,
    Body,
    Depends,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    File,
    responses,
    status,
)
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Annotated, List, Optional

from cor_pass.database.db import get_db
from cor_pass.database.models import Patient, PatientStatus, User
from cor_pass.repository.doctor import (
    create_doctor,
    create_doctor_service,
    get_doctor_patients_with_status,
)
from cor_pass.repository.lawyer import get_doctor
from cor_pass.repository.patient import add_existing_patient, register_new_patient
from cor_pass.schemas import (
    CertificateResponse,
    ClinicAffiliationResponse,
    DiplomaResponse,
    DoctorCreate,
    DoctorResponse,
    ExistingPatientAdd,
    NewPatientRegistration,
    PaginatedPatientsResponse,
    PatientResponce,
)
from cor_pass.repository import person as repository_person
from cor_pass.repository import user_session as repository_session
from cor_pass.repository import cor_id as repository_cor_id
from cor_pass.services.auth import auth_service
from cor_pass.services.access import user_access, doctor_access
from cor_pass.services.auth import auth_service
from cor_pass.services.image_validation import validate_image_file
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/doctor", tags=["Doctor"])


@router.post(
    "/signup",
    # response_model=DoctorResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_access)],
)
async def signup_doctor(
    doctor_data: str = Form(
        ...,
        example='{"work_email": "doctor@example.com","phone_number": "+380636666541", "first_name": "John", "surname": "Doe", "last_name": "Smith", "scientific_degree": "PhD", "date_of_last_attestation": "2022-12-31", "diplomas": [{"date": "2023-01-01", "series": "AB", "number": "123456", "university": "Medical University"}], "certificates": [{"date": "2023-01-01", "series": "CD", "number": "654321", "university": "Another University"}], "clinic_affiliations": [{"clinic_name": "City Hospital", "department": "Cardiology", "position": "Senior Doctor", "specialty": "Cardiologist"}]}',
        description="Данные врача в формате JSON. Пример: см. значение по умолчанию.",
    ),
    # doctor_data: DoctorCreate = Body(...),
    doctors_photo: UploadFile = File(None),
    diploma_scan: UploadFile = File(None),
    certificate_scan: UploadFile = File(None),
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Создание врача со всеми связанными данными**\n
    Этот маршрут позволяет создать врача вместе с дипломами, сертификатами и привязками к клиникам.
    Уровень доступа:
    - Текущий авторизованный пользователь
    :param doctor_data: str: Данные для создания врача в формате JSON.
    :param db: AsyncSession: Сессия базы данных.
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
    except HTTPException as exception:
        logger.error(f"Error validating image: {str(exception)}")
        raise exception

    # Парсим JSON-строку в словарь
    try:
        doctor_data_dict = json.loads(doctor_data)
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid JSON format",
        )
    

    exist_doctor = await get_doctor(db=db, doctor_id=current_user.cor_id)
    if exist_doctor:
        logger.debug(f"{current_user.cor_id} doctor already exist")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Doctor account already exists"
        )

    doctors_photo_bytes = await doctors_photo.read() if doctors_photo else None
    diploma_scan_bytes = await diploma_scan.read() if diploma_scan else None
    certificate_scan_bytes = await certificate_scan.read() if certificate_scan else None

    try:
        if "date_of_last_attestation" in doctor_data_dict and doctor_data_dict["date_of_last_attestation"]:
            doctor_data_dict["date_of_last_attestation"] = date.fromisoformat(doctor_data_dict["date_of_last_attestation"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid date format for date_of_last_attestation. Expected YYYY-MM-DD.",
        )

    if "diplomas" in doctor_data_dict and isinstance(doctor_data_dict["diplomas"], list):
        for diploma in doctor_data_dict["diplomas"]:
            if "date" in diploma and diploma["date"]:
                try:
                    diploma["date"] = date.fromisoformat(diploma["date"])
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Invalid date format in diplomas. Expected YYYY-MM-DD.",
                    )

    if "certificates" in doctor_data_dict and isinstance(doctor_data_dict["certificates"], list):
        for certificate in doctor_data_dict["certificates"]:
            if "date" in certificate and certificate["date"]:
                try:
                    certificate["date"] = date.fromisoformat(certificate["date"])
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Invalid date format in certificates. Expected YYYY-MM-DD.",
                    )
    try:
        doctor = await create_doctor(
            doctor_data=doctor_data_dict,
            db=db,
            doctors_photo_bytes=doctors_photo_bytes,
            user=current_user,
        )
        doctors_data = await create_doctor_service(
            doctor_data=doctor_data_dict,
            db=db,
            doctor=doctor,
            diploma_scan_bytes=diploma_scan_bytes,
            certificate_scan_bytes=certificate_scan_bytes,
        )
    except IntegrityError as e:
            logger.error(f"Database integrity error: {e}")
            await db.rollback()  
            detail = "Database error occurred. Please check the data for duplicates or invalid entries."
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=detail
            )
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during doctor creation.",
        )
    # Сериализуем ответ
    doctor_response = DoctorResponse(
        id=doctor.id,
        doctor_id=doctor.doctor_id,
        work_email=doctor.work_email,
        phone_number=doctor.phone_number,
        first_name=doctor.first_name,
        surname=doctor.surname,
        last_name=doctor.last_name,
        # doctors_photo=doctor.doctors_photo, 
        scientific_degree=doctor.scientific_degree,
        date_of_last_attestation=doctor.date_of_last_attestation,
        status=doctor.status,
    )

    return doctor_response


@router.get(
    "/patients",
    dependencies=[Depends(doctor_access)], 
    # response_model=PatientResponce
)
async def get_doctor_patients(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
    patient_status: Optional[str] = Query(None),  # Принимаем статус как строку
    sex: Optional[List[str]] = Query(None),
    sort_by: Optional[str] = Query("change_date"),
    sort_order: Optional[str] = Query("desc"),
    skip: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    doctor = await get_doctor(db=db, doctor_id=current_user.cor_id)
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    status_filters = None
    if patient_status:
        try:
            status_filters = [PatientStatus(patient_status)]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status value: {status}. Allowed values are: {[e.value for e in PatientStatus]}",
            )

    patients_with_status, total_count = await get_doctor_patients_with_status(
        db=db,
        doctor=doctor,
        status_filters=status_filters,
        sex_filters=sex,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=limit,
    )
    return {"items": patients_with_status, "total": total_count}


@router.post(
    "/patients/register-new",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(doctor_access)],
)
async def add_new_patient_to_doctor(
    body: NewPatientRegistration,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    """
    Добавить нового пациента к врачу.
    """
    doctor = await get_doctor(current_user.cor_id, db)
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found"
        )

    if current_user.cor_id != doctor.doctor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to add patients to this doctor",
        )

    if body:
        new_patient_info = body
        exist_user = await repository_person.get_user_by_email(
            new_patient_info.email, db
        )
        if exist_user:
            logger.debug(f"{new_patient_info.email} user already exists")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Account already exists"
            )
        new_patient = await register_new_patient(db, new_patient_info, doctor)
        return {
            "message": f"Новый пациент {new_patient_info.first_name} {new_patient_info.surname} успешно зарегистрирован и добавлен к врачу."
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректные данные для добавления пациента.",
        )


@router.post("/patients/add-existing", dependencies=[Depends(doctor_access)])
async def add_existing_patient_to_doctor(
    patient_data: ExistingPatientAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    """
    Добавить существующего пациента к врачу.
    """
    doctor = await get_doctor(doctor_id=current_user.cor_id, db=db)
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found"
        )

    existing_patient = await add_existing_patient(
        db=db, doctor=doctor, cor_id=patient_data.cor_id
    )
    if not existing_patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )

    return existing_patient
