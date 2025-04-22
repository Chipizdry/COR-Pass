import base64
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session, joinedload
from typing import Dict, List, Optional, Tuple, List
from fastapi import UploadFile, File

from cor_pass.database.models import (
    Certificate,
    ClinicAffiliation,
    Diploma,
    Doctor,
    DoctorPatientStatus,
    Patient,
    PatientStatus,
    User,
    DoctorStatus,
)
from cor_pass.schemas import DoctorCreate
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.services.cipher import decrypt_data
from cor_pass.config.config import settings

async def create_doctor(
    doctor_data: dict,
    db: AsyncSession,
    user: User,
    doctors_photo_bytes: Optional[bytes] = None,
) -> Doctor:
    """
    Асинхронная сервисная функция по созданию врача.
    """
    doctor = Doctor(
        doctor_id=user.cor_id,
        work_email=doctor_data.get("work_email"),
        phone_number=doctor_data.get("phone_number"),
        first_name=doctor_data.get("first_name"),
        surname=doctor_data.get("surname"),
        last_name=doctor_data.get("last_name"),
        doctors_photo=doctors_photo_bytes,
        scientific_degree=doctor_data.get("scientific_degree"),
        date_of_last_attestation=doctor_data.get("date_of_last_attestation"),
        status=DoctorStatus.PENDING,
    )

    db.add(doctor)

    await db.commit()
    await db.refresh(doctor) 

    return doctor


async def create_certificates(
    doctor: Doctor,
    doctor_data: dict,
    db: AsyncSession,
    certificate_scan_bytes: Optional[bytes] = None,
) -> None:
    """
    Асинхронно создает сертификаты врача.
    """
    for cert in doctor_data.get("certificates", []):
        certificate = Certificate(
            doctor_id=doctor.doctor_id,
            date=cert.get("date"),
            series=cert.get("series"),
            number=cert.get("number"),
            university=cert.get("university"),
            scan=certificate_scan_bytes,
        )
        db.add(certificate)

    await db.commit() 


async def create_diploma(
    doctor: Doctor,
    doctor_data: dict,
    db: AsyncSession,
    diploma_scan_bytes: Optional[bytes] = None,
) -> None:
    """
    Асинхронно создает дипломы врача.
    """
    for dip in doctor_data.get("diplomas", []):
        diploma = Diploma(
            doctor_id=doctor.doctor_id,
            date=dip.get("date"),
            series=dip.get("series"),
            number=dip.get("number"),
            university=dip.get("university"),
            scan=diploma_scan_bytes,
        )
        db.add(diploma)

    await db.commit() 


async def create_clinic_affiliation(
    doctor: Doctor, doctor_data: dict, db: AsyncSession
) -> None:
    """
    Асинхронно создает привязки к клиникам для врача.
    """
    for aff in doctor_data.get("clinic_affiliations", []):
        affiliation = ClinicAffiliation(
            doctor_id=doctor.doctor_id,
            clinic_name=aff.get("clinic_name"),
            department=aff.get("department"),
            position=aff.get("position"),
            specialty=aff.get("specialty"),
        )
        db.add(affiliation)

    await db.commit()


async def create_doctor_service(
    doctor_data: dict,
    db: AsyncSession,
    doctor: Doctor,
    doctors_photo_bytes: Optional[bytes] = None,
    diploma_scan_bytes: Optional[bytes] = None,
    certificate_scan_bytes: Optional[bytes] = None,
) -> Doctor:
    """
    Асинхронная основная сервисная функция по созданию врача и его сертификатов.
    """
    # doctor = await create_doctor(doctor_data, db, user, doctors_photo_bytes)


    if doctor:
        print("Врач создан успешно")


        await create_certificates(doctor, doctor_data, db, certificate_scan_bytes)


        await create_diploma(doctor, doctor_data, db, diploma_scan_bytes)


        await create_clinic_affiliation(doctor, doctor_data, db)

    return doctor



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
        query = query.where(DoctorPatientStatus.status.in_([s.value for s in status_filters]))

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
        count_query = count_query.where(DoctorPatientStatus.status.in_([s.value for s in status_filters]))
    if sex_filters:
        count_query = count_query.where(Patient.sex.in_(sex_filters))

    total_count_result = await db.execute(count_query)
    total_count = total_count_result.scalar_one()

    result = []
    decoded_key = base64.b64decode(settings.aes_key)
    for dps, patient in patients_with_status:
        decrypted_surname = await decrypt_data(patient.encrypted_surname, decoded_key) if patient.encrypted_surname else None
        decrypted_first_name = await decrypt_data(patient.encrypted_first_name, decoded_key) if patient.encrypted_first_name else None
        decrypted_middle_name = await decrypt_data(patient.encrypted_middle_name, decoded_key) if patient.encrypted_middle_name else None

        result.append({
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
        })

    return result, total_count
