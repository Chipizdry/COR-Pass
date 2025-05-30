import base64
from datetime import datetime, timedelta
from fastapi import HTTPException, UploadFile
from sqlalchemy import asc, desc, func, select
from typing import List, Optional, Tuple, List


from cor_pass.database.models import (
    Certificate,
    ClinicAffiliation,
    Diploma,
    Doctor,
    DoctorPatientStatus,
    Patient,
    PatientStatus,
    User,
    Doctor_Status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.schemas import DoctorCreate
from cor_pass.services.cipher import decrypt_data
from cor_pass.config.config import settings


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
        surname=doctor_data.surname,
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
