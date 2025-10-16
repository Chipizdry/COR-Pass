import base64
from datetime import date, datetime, timedelta
import re
from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import asc, desc, func, select
from typing import List, Optional, Tuple, List

import sqlalchemy


from cor_pass.database.models import (
    Certificate,
    ClinicAffiliation,
    Diploma,
    Doctor,
    DoctorPatientStatus,
    DoctorSignatureSession,
    Patient,
    PatientClinicStatus,
    PatientClinicStatusModel,
    PatientStatus,
    User,
    Doctor_Status,
    DoctorSignature,
)
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.repository.case import get_patient_list_cases
from cor_pass.repository.patient import get_patient_by_corid
from cor_pass.repository.person import get_user_by_corid
from cor_pass.schemas import (
    DoctorCreate,
    DoctorSignatureResponse,
    DoctorSignatureResponseWithName,
    GetAllPatientsResponce,
    PatientDecryptedResponce,
    PatientResponseForGetPatients,
    StatusResponse,
)
from cor_pass.services.cipher import decrypt_data
from cor_pass.config.config import settings
from cor_pass.services.websocket import _is_expired


async def create_doctor(
    doctor_data: DoctorCreate,
    db: AsyncSession,
    user: User,
) -> Doctor:
    """
    Асинхронная сервисная функция по созданию врача.
    """
    doctor = Doctor(
        doctor_id=user.cor_id,
        work_email=doctor_data.work_email,
        phone_number=doctor_data.phone_number,
        first_name=doctor_data.first_name,
        middle_name=doctor_data.middle_name,
        last_name=doctor_data.last_name,
        scientific_degree=doctor_data.scientific_degree,
        date_of_last_attestation=doctor_data.date_of_last_attestation,
        passport_code=doctor_data.passport_code,
        taxpayer_identification_number=doctor_data.taxpayer_identification_number,
        place_of_registration=doctor_data.place_of_registration,
        date_of_next_review=datetime.now() + timedelta(days=180),
        status=Doctor_Status.pending,
    )

    db.add(doctor)

    await db.commit()
    await db.refresh(doctor)

    return doctor


async def create_certificates(
    doctor: Doctor,
    doctor_data: DoctorCreate,
    db: AsyncSession,
):
    """
    Асинхронно создает сертификаты врача.
    """
    list_of_certificates = []
    for cert in doctor_data.certificates:
        certificate = Certificate(
            doctor_id=doctor.doctor_id,
            date=cert.date,
            series=cert.series,
            number=cert.number,
            university=cert.university,
        )
        db.add(certificate)
        await db.flush()
        list_of_certificates.append(certificate.id)

    await db.commit()
    return list_of_certificates


async def create_diploma(
    doctor: Doctor,
    doctor_data: DoctorCreate,
    db: AsyncSession,
):
    """
    Асинхронно создает дипломы врача.
    """
    list_of_diplomas = []
    for dip in doctor_data.diplomas:
        diploma = Diploma(
            doctor_id=doctor.doctor_id,
            date=dip.date,
            series=dip.series,
            number=dip.number,
            university=dip.university,
        )
        db.add(diploma)
        await db.flush()
        list_of_diplomas.append(diploma.id)

    await db.commit()
    return list_of_diplomas


async def create_clinic_affiliation(
    doctor: Doctor, doctor_data: DoctorCreate, db: AsyncSession
):
    """
    Асинхронно создает привязки к клиникам для врача.
    """
    list_of_clinics = []
    for aff in doctor_data.clinic_affiliations:
        affiliation = ClinicAffiliation(
            doctor_id=doctor.doctor_id,
            clinic_name=aff.clinic_name,
            department=aff.department,
            position=aff.position,
            specialty=aff.specialty,
        )
        db.add(affiliation)
        await db.flush()
        list_of_clinics.append(affiliation.id)

    await db.commit()
    return list_of_clinics


async def create_doctor_service(
    doctor_data: DoctorCreate,
    db: AsyncSession,
    doctor: Doctor,
) -> Doctor:
    """
    Асинхронная основная сервисная функция по созданию врача и его сертификатов.
    """
    # doctor = await create_doctor(doctor_data, db, user, doctors_photo_bytes)

    if doctor:
        print("Врач создан успешно")

        certificates = await create_certificates(doctor, doctor_data, db)
        print(certificates)

        diploma = await create_diploma(doctor, doctor_data, db)
        print(diploma)

        clinic_aff = await create_clinic_affiliation(doctor, doctor_data, db)
        print(diploma)

    return certificates, diploma, clinic_aff


async def get_doctor_patients_with_status(
    db: AsyncSession,
    doctor: Doctor,
    status_filters: Optional[List[PatientStatus]] = None,
    sex_filters: Optional[List[str]] = None,
    sort_by: Optional[str] = "change_date",
    sort_order: Optional[str] = "desc",
    skip: int = 1,
    limit: int = 10,
) -> Tuple[List, int]:
    """
    Асинхронно получает список пациентов конкретного врача вместе с их статусами с учетом
    фильтрации, сортировки и пагинации.
    """
    query = (
        select(DoctorPatientStatus, Patient)
        .join(Patient, DoctorPatientStatus.patient_id == Patient.id)
        .where(DoctorPatientStatus.doctor_id == doctor.id)
    )

    # Фильтрация по статусу
    if status_filters:
        query = query.where(
            DoctorPatientStatus.status.in_([s.value for s in status_filters])
        )

    # Фильтрация по полу пациента
    if sex_filters:
        query = query.where(Patient.sex.in_(sex_filters))

    # Сортировка
    order_by_clause = None
    if sort_by == "change_date":
        order_by_clause = (
            desc(Patient.change_date)
            if sort_order == "desc"
            else asc(Patient.change_date)
        )
    elif sort_by == "birth_date":
        order_by_clause = (
            desc(Patient.birth_date)
            if sort_order == "desc"
            else asc(Patient.birth_date)
        )

    if order_by_clause is not None:
        query = query.order_by(order_by_clause)

    # Пагинация
    offset = (skip - 1) * limit
    patients_with_status_result = await db.execute(query.offset(offset).limit(limit))
    patients_with_status = patients_with_status_result.all()

    # Получаем общее количество результатов для пагинации
    count_query = (
        select(func.count())
        .select_from(DoctorPatientStatus)
        .join(Patient, DoctorPatientStatus.patient_id == Patient.id)
        .where(DoctorPatientStatus.doctor_id == doctor.id)
    )
    if status_filters:
        count_query = count_query.where(
            DoctorPatientStatus.status.in_([s.value for s in status_filters])
        )
    if sex_filters:
        count_query = count_query.where(Patient.sex.in_(sex_filters))

    total_count_result = await db.execute(count_query)
    total_count = total_count_result.scalar_one()

    result = []
    decoded_key = base64.b64decode(settings.aes_key)
    for dps, patient in patients_with_status:
        decrypted_surname = (
            await decrypt_data(patient.encrypted_surname, decoded_key)
            if patient.encrypted_surname
            else None
        )
        decrypted_first_name = (
            await decrypt_data(patient.encrypted_first_name, decoded_key)
            if patient.encrypted_first_name
            else None
        )
        decrypted_middle_name = (
            await decrypt_data(patient.encrypted_middle_name, decoded_key)
            if patient.encrypted_middle_name
            else None
        )

        result.append(
            {
                "patient": {
                    "id": patient.id,
                    "patient_cor_id": patient.patient_cor_id,
                    "surname": decrypted_surname,
                    "first_name": decrypted_first_name,
                    "middle_name": decrypted_middle_name,
                    "birth_date": patient.birth_date,
                    "sex": patient.sex,
                    "email": patient.email,
                    "phone_number": patient.phone_number,
                    "address": patient.address,
                    "change_date": patient.change_date,
                },
                "status": dps.status.value,
            }
        )

    return result, total_count


async def get_patients_with_optional_status(
    db: AsyncSession,
    doctor: Optional[Doctor] = None,
    doctor_status_filters: Optional[List[PatientStatus]] = None,
    clinic_status_filters: Optional[List[PatientClinicStatus]] = None,
    sex_filters: Optional[List[str]] = None,
    sort_by: Optional[str] = "change_date",
    sort_order: Optional[str] = "desc",
    skip: int = 1,
    limit: int = 30
) -> Tuple[List, int]:
    query = (
        select(DoctorPatientStatus, Patient, PatientClinicStatusModel)
        .join(Patient, DoctorPatientStatus.patient_id == Patient.id)
        .join(
            PatientClinicStatusModel,
            PatientClinicStatusModel.patient_id == Patient.id,
            isouter=True,
        )
    )

    if doctor:
        query = query.where(DoctorPatientStatus.doctor_id == doctor.id)

    if doctor_status_filters:
        query = query.where(
            DoctorPatientStatus.status.in_([s.value for s in doctor_status_filters])
        )

    if clinic_status_filters:
        query = query.where(
            PatientClinicStatusModel.patient_status_for_clinic.in_(
                [s.value for s in clinic_status_filters]
            )
        )

    if sex_filters:
        query = query.where(Patient.sex.in_(sex_filters))

    order_by_clause = None
    if sort_by == "change_date":
        order_by_clause = (
            desc(Patient.change_date)
            if sort_order == "desc"
            else asc(Patient.change_date)
        )
    elif sort_by == "birth_date":
        order_by_clause = (
            desc(Patient.birth_date)
            if sort_order == "desc"
            else asc(Patient.birth_date)
        )

    if order_by_clause is not None:
        query = query.order_by(order_by_clause)

    offset = (skip - 1) * limit
    patients_data_result = await db.execute(query.offset(offset).limit(limit))

    patients_data = patients_data_result.all()

    count_query = (
        select(func.count(Patient.id.distinct()))
        .select_from(Patient)
        .join(
            DoctorPatientStatus,
            DoctorPatientStatus.patient_id == Patient.id,
            isouter=True,
        )
        .join(
            PatientClinicStatusModel,
            PatientClinicStatusModel.patient_id == Patient.id,
            isouter=True,
        )
    )

    if doctor:
        count_query = count_query.where(DoctorPatientStatus.doctor_id == doctor.id)

    if doctor_status_filters:
        count_query = count_query.where(
            DoctorPatientStatus.status.in_([s.value for s in doctor_status_filters])
        )

    if clinic_status_filters:
        count_query = count_query.where(
            PatientClinicStatusModel.patient_status_for_clinic.in_(
                [s.value for s in clinic_status_filters]
            )
        )

    if sex_filters:
        count_query = count_query.where(Patient.sex.in_(sex_filters))

    total_count_result = await db.execute(count_query)
    total_count = total_count_result.scalar_one()

    result = []
    decoded_key = base64.b64decode(settings.aes_key)

    for doctor_patient_status, patient, clinic_patient_status in patients_data:
        decrypted_surname = (
            await decrypt_data(patient.encrypted_surname, decoded_key)
            if patient.encrypted_surname
            else None
        )
        decrypted_first_name = (
            await decrypt_data(patient.encrypted_first_name, decoded_key)
            if patient.encrypted_first_name
            else None
        )
        decrypted_middle_name = (
            await decrypt_data(patient.encrypted_middle_name, decoded_key)
            if patient.encrypted_middle_name
            else None
        )
        status_for_doctor = (
            doctor_patient_status.status if doctor_patient_status else None
        )
        status_for_clinic = (
            clinic_patient_status.patient_status_for_clinic
            if clinic_patient_status
            else None
        )

        list_cases = await get_patient_list_cases(db=db, patient_id=patient.patient_cor_id)
        patient_response = PatientResponseForGetPatients(
            id=patient.id,
            patient_cor_id=patient.patient_cor_id,
            surname=decrypted_surname,
            first_name=decrypted_first_name,
            middle_name=decrypted_middle_name,
            birth_date=patient.birth_date if patient else None,
            sex=patient.sex if patient else None,
            email=patient.email if patient else None,
            phone_number=patient.phone_number if patient else None,
            address=patient.address if patient else None,
            change_date=patient.change_date if patient else None,
            doctor_status=status_for_doctor,
            clinic_status=status_for_clinic,
            cases = list_cases
        )
        result.append(patient_response)
 
    response = GetAllPatientsResponce(patients=result, total_count=total_count)
    return response

 
async def get_doctor_single_patient_with_status(
    patient_cor_id: str,
    db: AsyncSession,
    doctor: Doctor,
) -> PatientDecryptedResponce:
    """
    Получает информацию о конкретном пациенте для доктора, включая его статус и расшифрованные данные.
    """
    existing_patient = await get_patient_by_corid(cor_id=patient_cor_id, db=db)
    if not existing_patient:
        raise HTTPException(status_code=404, detail=f"Пациент не найден")
    stmt_status = (
        select(DoctorPatientStatus)
        .where(DoctorPatientStatus.patient_id == existing_patient.id)
        .where(DoctorPatientStatus.doctor_id == doctor.id)
    )
    result_status = await db.execute(stmt_status)
    result_status = result_status.scalar_one_or_none()

    decoded_key = base64.b64decode(settings.aes_key)
    existing_patient.encrypted_surname = (
        await decrypt_data(existing_patient.encrypted_surname, decoded_key)
        if existing_patient.encrypted_surname
        else None
    )

    existing_patient.encrypted_first_name = (
        await decrypt_data(existing_patient.encrypted_first_name, decoded_key)
        if existing_patient.encrypted_first_name
        else None
    )
    existing_patient.encrypted_middle_name = (
        await decrypt_data(existing_patient.encrypted_middle_name, decoded_key)
        if existing_patient.encrypted_middle_name
        else None
    )

    user_birth_year = existing_patient.birth_date
    if user_birth_year is None and existing_patient.patient_cor_id:
        cor_id_parts = existing_patient.patient_cor_id.split("-")
        if len(cor_id_parts) > 1:
            year_part = cor_id_parts[1]
            numbers = re.findall(r"\d+", year_part)
            if numbers:
                try:
                    user_birth_year = numbers[0]
                except ValueError:
                    user_birth_year = None

    patient_age: Optional[int] = None
    if existing_patient.birth_date:
        today = date.today()
        patient_age = (
            today.year
            - existing_patient.birth_date.year
            - (
                (today.month, today.day)
                < (existing_patient.birth_date.month, existing_patient.birth_date.day)
            )
        )
    response = PatientDecryptedResponce(
        patient_cor_id=existing_patient.patient_cor_id,
        surname=existing_patient.encrypted_surname,
        first_name=existing_patient.encrypted_first_name,
        middle_name=existing_patient.encrypted_middle_name,
        sex=existing_patient.sex,
        birth_date=user_birth_year,
        status=result_status.status,
        age=patient_age,
    )
    return response


async def get_doctor_single_patient_without_doctor_status(
    patient_cor_id: str,
    db: AsyncSession,
    doctor: Doctor,
) -> PatientDecryptedResponce:
    """
    Получает информацию о конкретном пациенте для доктора, включая его статус и расшифрованные данные.
    """
    existing_patient = await get_patient_by_corid(cor_id=patient_cor_id, db=db)
    if not existing_patient:
        raise HTTPException(status_code=404, detail=f"Пациент не найден")
    stmt_status = select(DoctorPatientStatus).where(
        DoctorPatientStatus.patient_id == existing_patient.id
    )
    result_status = await db.execute(stmt_status)
    result_status = result_status.scalar_one_or_none()

    decoded_key = base64.b64decode(settings.aes_key)
    existing_patient.encrypted_surname = (
        await decrypt_data(existing_patient.encrypted_surname, decoded_key)
        if existing_patient.encrypted_surname
        else None
    )

    existing_patient.encrypted_first_name = (
        await decrypt_data(existing_patient.encrypted_first_name, decoded_key)
        if existing_patient.encrypted_first_name
        else None
    )
    existing_patient.encrypted_middle_name = (
        await decrypt_data(existing_patient.encrypted_middle_name, decoded_key)
        if existing_patient.encrypted_middle_name
        else None
    )

    user_birth_year = existing_patient.birth_date
    if user_birth_year is None and existing_patient.patient_cor_id:
        cor_id_parts = existing_patient.patient_cor_id.split("-")
        if len(cor_id_parts) > 1:
            year_part = cor_id_parts[1]
            numbers = re.findall(r"\d+", year_part)
            if numbers:
                try:
                    user_birth_year = numbers[0]
                except ValueError:
                    user_birth_year = None

    patient_age: Optional[int] = None
    if existing_patient.birth_date:
        today = date.today()
        patient_age = (
            today.year
            - existing_patient.birth_date.year
            - (
                (today.month, today.day)
                < (existing_patient.birth_date.month, existing_patient.birth_date.day)
            )
        )
    response = PatientDecryptedResponce(
        patient_cor_id=existing_patient.patient_cor_id,
        surname=existing_patient.encrypted_surname,
        first_name=existing_patient.encrypted_first_name,
        middle_name=existing_patient.encrypted_middle_name,
        sex=existing_patient.sex,
        birth_date=user_birth_year,
        status=result_status.status,
        age=patient_age,
    )
    return response


async def upload_doctor_photo_service(
    doctor_id: str, file: UploadFile, db: AsyncSession
):
    stmt = select(Doctor).where(Doctor.doctor_id == doctor_id)
    result = await db.execute(stmt)
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=404, detail="Врач не найден")
    doctor.doctors_photo = file.file.read()
    await db.commit()
    await db.refresh(doctor)
    return {"doctor_id": doctor_id, "message": "Фотография врача успешно загружена"}


async def upload_reserv_data_service(
    doctor_id: str, file: UploadFile, db: AsyncSession
):
    allowed_types = ["image/jpeg", "image/png", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Недопустимый тип файла. Разрешены только JPEG, PNG и PDF.",
        )
    stmt = select(Doctor).where(Doctor.doctor_id == doctor_id)
    result = await db.execute(stmt)
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=404, detail="Врач не найден")
    contents = await file.read()
    doctor.reserv_scan_data = contents
    doctor.reserv_scan_file_type = file.content_type
    await db.commit()
    return {"doctor_id": doctor_id, "message": "Выписка из резерва успешно загружена"}


async def upload_diploma_service(diploma_id: str, file: UploadFile, db: AsyncSession):
    allowed_types = ["image/jpeg", "image/png", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Недопустимый тип файла. Разрешены только JPEG, PNG и PDF.",
        )
    stmt = select(Diploma).where(Diploma.id == diploma_id)
    result = await db.execute(stmt)
    diploma = result.scalar_one()
    if not diploma:
        raise HTTPException(status_code=404, detail="Документ не найден")
    contents = await file.read()
    diploma.file_data = contents
    diploma.file_type = file.content_type
    await db.commit()
    return {"document_id": diploma_id, "message": "Диплом успешно загружен"}


async def upload_certificate_service(
    certificate_id: str, file: UploadFile, db: AsyncSession
):
    allowed_types = ["image/jpeg", "image/png", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Недопустимый тип файла. Разрешены только JPEG, PNG и PDF.",
        )
    stmt = select(Certificate).where(Certificate.id == certificate_id)
    result = await db.execute(stmt)
    certificate = result.scalar_one()
    if not certificate:
        raise HTTPException(status_code=404, detail="Документ не найден")
    contents = await file.read()
    certificate.file_data = contents
    certificate.file_type = file.content_type
    await db.commit()
    return {"document_id": certificate_id, "message": "Сертификат успешно загружен"}


async def create_doctor_signature(
    db: AsyncSession,
    doctor_id: str,  # uuid
    signature_name: Optional[str],
    router: APIRouter,
    signature_scan_file: UploadFile,
    is_default: bool = False,
) -> DoctorSignatureResponse:
    """
    Загружает новую подпись доктора и сохраняет её в базе данных.
    """
    signature_bytes = await signature_scan_file.read()
    signature_mime_type = signature_scan_file.content_type

    if not signature_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Файл подписи пустой."
        )
    if not signature_mime_type or not signature_mime_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пожалуйста, загрузите файл изображения для подписи.",
        )

    if is_default:
        await db.execute(
            DoctorSignature.__table__.update()
            .where(DoctorSignature.doctor_id == doctor_id)
            .values(is_default=False)
        )

    db_signature = DoctorSignature(
        doctor_id=doctor_id,
        signature_name=signature_name,
        signature_scan_data=signature_bytes,
        signature_scan_type=signature_mime_type,
        is_default=is_default,
        created_at=func.now(),
    )
    db.add(db_signature)
    await db.commit()
    await db.refresh(db_signature)

    signature_data = (
        router.url_path_for("get_signature_attachment", signature_id=db_signature.id)
        if db_signature.signature_scan_data
        else None
    )

    return DoctorSignatureResponse(
        id=db_signature.id,
        doctor_id=db_signature.doctor_id,
        signature_name=db_signature.signature_name,
        signature_scan_data=signature_data,
        signature_scan_type=db_signature.signature_scan_type,
        is_default=db_signature.is_default,
        created_at=db_signature.created_at,
    )


async def get_doctor_signatures(
    db: AsyncSession, doctor_id: str, router: APIRouter
) -> List[DoctorSignatureResponse]:
    """
    Получает все подписи для указанного доктора.
    """
    signatures_result = await db.execute(
        select(DoctorSignature)
        .where(DoctorSignature.doctor_id == doctor_id)
        .order_by(DoctorSignature.created_at.desc())
    )
    db_signatures = signatures_result.scalars().all()

    response_signatures = []
    for sig in db_signatures:
        signature_data = router.url_path_for(
            "get_signature_attachment", signature_id=sig.id
        )
        response_signatures.append(
            DoctorSignatureResponse(
                id=sig.id,
                doctor_id=sig.doctor_id,
                signature_name=sig.signature_name,
                signature_scan_data=signature_data,
                signature_scan_type=sig.signature_scan_type,
                is_default=sig.is_default,
                created_at=sig.created_at,
            )
        )
    return response_signatures



async def get_doctor_signature_by_id(
    db: AsyncSession,
    signature_id: str,
    router: APIRouter,
) -> DoctorSignatureResponseWithName:
    """
    Получает одну подпись врача по ID и возвращает вместе с ФИО врача.
    """
    result = await db.execute(
        select(DoctorSignature, Doctor.first_name, Doctor.last_name)
        .join(Doctor, Doctor.id == DoctorSignature.doctor_id)
        .where(DoctorSignature.id == signature_id)
    )
    record = result.first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor signature not found",
        )

    sig, first_name, last_name = record

    return DoctorSignatureResponseWithName(
        # id=sig.id,
        doctor_id=sig.doctor_id,
        # signature_name=sig.signature_name,
        signature_scan_data=router.url_path_for(
            "get_signature_attachment", signature_id=sig.id
        ),
        signature_scan_type=sig.signature_scan_type,
        # is_default=sig.is_default,
        # created_at=sig.created_at,
        doctor_first_name=first_name,
        doctor_last_name=last_name,
    )

async def set_default_doctor_signature(
    db: AsyncSession, doctor_id: str, signature_id: str, router: APIRouter
) -> List[DoctorSignatureResponse]:
    """
    Устанавливает указанную подпись как подпись по умолчанию для доктора.
    Возвращает все подписи доктора с обновленным статусом.
    """

    await db.execute(
        DoctorSignature.__table__.update()
        .where(DoctorSignature.doctor_id == doctor_id)
        .values(is_default=False)
    )

    signature_to_update = await db.scalar(
        select(DoctorSignature).where(
            DoctorSignature.id == signature_id, DoctorSignature.doctor_id == doctor_id
        )
    )
    if not signature_to_update:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Подпись не найдена или принадлежит другому врачу.",
        )

    signature_to_update.is_default = True
    await db.commit()
    await db.refresh(signature_to_update)

    return await get_doctor_signatures(db, doctor_id, router=router)


async def delete_doctor_signature(db: AsyncSession, doctor_id: str, signature_id: str):
    """
    Удаляет указанную подпись доктора.
    """
    signature_to_delete = await db.scalar(
        select(DoctorSignature).where(
            DoctorSignature.id == signature_id, DoctorSignature.doctor_id == doctor_id
        )
    )
    if not signature_to_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Подпись не найдена или принадлежит другому врачу.",
        )

    await db.delete(signature_to_delete)
    await db.commit()
    return {"message": "Подпись удалена."}


async def get_signature_data(
    db: AsyncSession, signature_id: str
) -> Optional[DoctorSignature]:
    result = await db.execute(
        select(DoctorSignature).where(DoctorSignature.id == signature_id)
    )
    return result.scalar_one_or_none()


async def get_pending_signings(db: AsyncSession, diagnosis_id: str)-> Optional[DoctorSignatureSession]:
    q = sqlalchemy.select(DoctorSignatureSession).where(DoctorSignatureSession.diagnosis_id == diagnosis_id)
    res = await db.execute(q)
    singning_record = res.scalars().all()
    return singning_record
