import base64
from fastapi import HTTPException
from sqlalchemy import select
from cor_pass.database.models import (
    Patient,
    DoctorPatientStatus,
    PatientStatus,
    Doctor,
)

from cor_pass.schemas import (
    NewPatientRegistration,
    PasswordGeneratorSettings,
    UserModel,
)
from cor_pass.repository import person as repository_person

from cor_pass.repository.password_generator import generate_password
from cor_pass.repository import cor_id as repository_cor_id
from cor_pass.services.cipher import encrypt_data
from cor_pass.services.email import (
    send_email_code_with_temp_pass,
)
from cor_pass.config.config import settings
from cor_pass.services.auth import auth_service
from cor_pass.services.logger import logger
from sqlalchemy.ext.asyncio import AsyncSession


async def register_new_patient(
    db: AsyncSession, body: NewPatientRegistration, doctor: Doctor
):
    """
    Асинхронно регистрирует нового пользователя как пациента и связывает его с врачом.
    """
    # Генерируем временный пароль
    password_settings = PasswordGeneratorSettings()
    temp_password = generate_password(password_settings)
    hashed_password = auth_service.get_password_hash(temp_password)

    user_signup_data = UserModel(
        email=body.email,
        password=temp_password,
        birth=body.birth_date.year,
        user_sex=body.sex,
    )
    hashed_password = auth_service.get_password_hash(temp_password)
    user_signup_data.password = hashed_password

    new_user = await repository_person.create_user(user_signup_data, db)

    await db.flush()

    await repository_cor_id.create_new_corid(new_user, db)
    decoded_key = base64.b64decode(settings.aes_key)

    new_patient = Patient(
        patient_cor_id=new_user.cor_id,
        encrypted_surname=await encrypt_data(body.surname.encode("utf-8"), decoded_key),
        encrypted_first_name=await encrypt_data(
            body.first_name.encode("utf-8"), decoded_key
        ),
        encrypted_middle_name=(
            await encrypt_data(body.middle_name.encode("utf-8"), decoded_key)
            if body.middle_name
            else None
        ),
        birth_date=body.birth_date,
        sex=body.sex,
        email=body.email,
        phone_number=body.phone_number,
        address=body.address,
    )
    db.add(new_patient)
    await db.commit()

    doctor_patient_status = DoctorPatientStatus(
        patient_id=new_patient.id,
        doctor_id=doctor.id,
        status=PatientStatus.registered,
    )
    db.add(doctor_patient_status)

    await db.commit()

    await send_email_code_with_temp_pass(
        email=new_patient.email, temp_pass=temp_password
    )


async def add_existing_patient(
    db: AsyncSession, cor_id: str, doctor: Doctor, status: str = "registered"
):
    """
    Асинхронно добавляет существующего пользователя как пациента к врачу.
    """

    existing_user = await repository_person.get_user_by_corid(cor_id, db)
    if not existing_user:
        raise HTTPException(
            status_code=404, detail=f"Пользователь с Cor ID {cor_id} не найден."
        )

    stmt_patient = select(Patient).where(Patient.patient_cor_id == cor_id)
    result_patient = await db.execute(stmt_patient)
    existing_patient = result_patient.scalar_one_or_none()
    if existing_patient:
        raise HTTPException(
            status_code=400,
            detail=f"Пользователь с Cor ID {cor_id} уже является пациентом.",
        )

    new_patient = Patient(
        patient_cor_id=existing_user.cor_id,
        sex=existing_user.user_sex,
        email=existing_user.email,
    )
    db.add(new_patient)
    await db.flush()
    doctor_id_str = doctor.id

    doctor_patient_status = DoctorPatientStatus(
        patient_id=new_patient.id, doctor_id=doctor_id_str, status=PatientStatus(status)
    )
    db.add(doctor_patient_status)

    await db.commit()
    return new_patient


async def get_patient_by_corid(db: AsyncSession, cor_id: str):
    
    existing_user = await repository_person.get_user_by_corid(cor_id, db)
    if not existing_user:
        raise HTTPException(
            status_code=404, detail=f"Пользователь с Cor ID {cor_id} не найден."
        )

    stmt_patient = select(Patient).where(Patient.patient_cor_id == cor_id)
    result_patient = await db.execute(stmt_patient)
    existing_patient = result_patient.scalar_one_or_none()
    if not existing_patient:
                raise HTTPException(
            status_code=404, detail=f"Пациент с Cor ID {cor_id} не найден."
        )
    return existing_patient