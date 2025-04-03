from sqlalchemy.orm import Session
from typing import Optional
from fastapi import UploadFile, File

from cor_pass.database.models import (
    Certificate,
    ClinicAffiliation,
    Diploma,
    Doctor,
    User,
    DoctorStatus,
)
from cor_pass.schemas import DoctorCreate


async def create_doctor(
    doctor_data: dict,
    db: Session,
    user: User,
    doctors_photo_bytes: Optional[bytes] = None,
) -> Doctor:
    """
    Сервисная функция для создания врача.
    """
    # Создаем врача
    doctor = Doctor(
        doctor_id=user.cor_id,
        work_email=doctor_data.get("work_email"),
        first_name=doctor_data.get("first_name"),
        surname=doctor_data.get("surname"),
        last_name=doctor_data.get("last_name"),
        doctors_photo=doctors_photo_bytes,
        scientific_degree=doctor_data.get("scientific_degree"),
        date_of_last_attestation=doctor_data.get("date_of_last_attestation"),
        status=DoctorStatus.PENDING,
    )

    # Добавляем врача в сессию
    db.add(doctor)

    # Сохраняем изменения в базе данных
    db.commit()
    db.refresh(doctor)  # Обновляем объект врача после сохранения

    return doctor


async def create_certificates(
    doctor: Doctor,
    doctor_data: dict,
    db: Session,
    certificate_scan_bytes: Optional[bytes] = None,
) -> None:
    """
    Создает сертификаты для врача.
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

    db.commit()  # Сохраняем изменения


async def create_diploma(
    doctor: Doctor,
    doctor_data: dict,
    db: Session,
    diploma_scan_bytes: Optional[bytes] = None,
) -> None:
    """
    Создает дипломы для врача.
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

    db.commit()  # Сохраняем изменения


async def create_clinic_affiliation(
    doctor: Doctor, doctor_data: dict, db: Session
) -> None:
    """
    Создает привязки к клиникам для врача.
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

    db.commit()  # Сохраняем изменения


async def create_doctor_service(
    doctor_data: dict,
    db: Session,
    doctor: Doctor,
    diploma_scan_bytes: Optional[bytes] = None,
    certificate_scan_bytes: Optional[bytes] = None,
) -> Doctor:
    """
    Основная сервисная функция для создания врача и его сертификатов.
    """
    # doctor = await create_doctor(doctor_data, db, user, doctors_photo_bytes)

    # Проверяем, что врач был создан успешно
    if doctor:
        print("Врач создан успешно")

        # Создаем сертификаты
        await create_certificates(
            doctor, doctor_data, db, certificate_scan_bytes
        )

        # Создаем дипломы
        await create_diploma(doctor, doctor_data, db, diploma_scan_bytes)

        # Создаем привязки к клиникам
        await create_clinic_affiliation(doctor, doctor_data, db)

    return doctor
