import base64
from typing import List
from fastapi import APIRouter, Body, HTTPException, Depends, status
from cor_pass.database.db import get_db
from cor_pass.repository import lawyer
from cor_pass.repository.doctor import create_doctor, create_doctor_service
from cor_pass.repository.lawyer import get_doctor
from cor_pass.services.auth import auth_service
from cor_pass.database.models import Doctor_Status, User, Status
from cor_pass.services.access import admin_access
from cor_pass.schemas import (
    DoctorCreate,
    DoctorCreateResponse,
    DoctorResponse,
    DoctorWithRelationsResponse,
    FullUserInfoResponse,
    NewUserRegistration,
    ProfileResponse,
    UserDb,
)
from cor_pass.repository import person
from pydantic import EmailStr
from cor_pass.database.redis_db import redis_client
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from cor_pass.services.cipher import decrypt_data
from cor_pass.services.logger import logger
from cor_pass.config.config import settings

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/get_all", response_model=List[UserDb], dependencies=[Depends(admin_access)]
)
async def get_all_users(
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Get a list of users. / Получение списка всех пользователей**\n
    This route allows to get a list of pagination-aware users.
    Level of Access:
    - Admin
    :param skip: int: Number of users to skip.
    :param limit: int: Maximum number of users to return.
    :param current_user: User: Current authenticated user (for dependency injection).
    :param db: AsyncSession: Database session.
    :return: List of users with their last activity.
    :rtype: List[UserDb]
    """

    list_users = await person.get_users(skip, limit, db)
    users_list_with_activity = []

    for user in list_users:
        oid = str(user.id)  # Convert UUID to string for Redis
        last_active = None
        if await redis_client.exists(oid):
            users_last_activity = await redis_client.get(oid)
            user_response = UserDb(
                id=user.id,
                cor_id=user.cor_id,
                email=user.email,
                account_status=user.account_status,
                is_active=user.is_active,
                last_password_change=user.last_password_change,
                user_sex=user.user_sex,
                birth=user.birth,
                user_index=user.user_index,
                created_at=user.created_at,
                last_active=users_last_activity,
            )
        else:
            user_response = UserDb(
                id=user.id,
                cor_id=user.cor_id,
                email=user.email,
                account_status=user.account_status,
                is_active=user.is_active,
                last_password_change=user.last_password_change,
                user_sex=user.user_sex,
                birth=user.birth,
                user_index=user.user_index,
                created_at=user.created_at,
            )

        users_list_with_activity.append(user_response)

    return users_list_with_activity



async def _create_profile_response(db_profile, current_user, router_instance) -> ProfileResponse:
    """Формирует ProfileResponse, дешифруя поля и добавляя данные из User."""
    response_data = db_profile.__dict__.copy() # Копируем, чтобы не изменять исходный ORM объект
    decoded_key = base64.b64decode(settings.aes_key)

    # Дешифруем нужные поля для ответа
    for field_name in ["surname", "first_name", "middle_name"]:
        encrypted_field = f"encrypted_{field_name}"
        encrypted_value = response_data.get(encrypted_field)
        if encrypted_value:
            response_data[field_name] = await decrypt_data(encrypted_value, decoded_key)
        else:
            response_data[field_name] = None
        # Удаляем зашифрованное поле из ответа
        response_data.pop(encrypted_field, None)

    # Добавляем данные из User
    response_data["email"] = current_user.email
    response_data["sex"] = current_user.user_sex # Если sex есть в User

    # Добавляем URL для фото, если оно существует
    # if db_profile.photo_data:
    #     response_data["photo_url"] = router_instance.url_path_for("get_profile_photo_endpoint", user_id=current_user.id)
    # else:
    #     response_data["photo_url"] = None

    return ProfileResponse.model_validate(response_data)



@router.get(
    "/get_user_info/{user_cor_id}", 
    response_model=FullUserInfoResponse, 
    dependencies=[Depends(admin_access)]
)
async def get_all_user_info(
    user_cor_id: str,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Get a list of user's info. / Получение всей информации по пользователю**\n
    Level of Access:
    - Admin
    """
    full_user_data = {}

    user = await person.get_user_by_corid(db=db, cor_id=user_cor_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")

    last_active = None
    if await redis_client.exists(str(user.id)): 
        users_last_activity_str = await redis_client.get(str(user.id))
        try:
            last_active = users_last_activity_str
        except (ValueError, TypeError) as e:
            print(f"Error parsing last_active from Redis: {e}")
            last_active = None 

    full_user_data["user_info"] = UserDb(
        id=user.id,
        cor_id=user.cor_id,
        email=user.email,
        account_status=user.account_status,
        is_active=user.is_active,
        last_password_change=user.last_password_change,
        user_sex=user.user_sex, 
        birth=user.birth, 
        user_index=user.user_index,
        created_at=user.created_at,
        last_active=last_active, 
    )

    user_roles = await person.get_user_roles(email=user.email, db=db)
    if user_roles:
        full_user_data["user_roles"] = user_roles

    profile = await person.get_profile_by_user_id(db=db, user_id=user.id)
    if profile:
        profile_response = await _create_profile_response(profile, user, router) 
        full_user_data["profile"] = profile_response


    doctor = await lawyer.get_all_doctor_info(doctor_id=user.cor_id, db=db)
    if doctor:
        full_user_data["doctor_info"] = DoctorWithRelationsResponse.model_validate(doctor)

    return full_user_data





@router.patch("/asign_status/{account_status}", dependencies=[Depends(admin_access)])
async def assign_status(
    email: EmailStr, account_status: Status, db: AsyncSession = Depends(get_db)
):
    """
    **Assign a account_status to a user by email. / Применение нового статуса аккаунта пользователя**\n

    This route allows to assign the selected account_status to a user by their email.

    :param email: EmailStr: Email of the user to whom you want to assign the status.

    :param account_status: Status: The selected account_status for the assignment (Premium, Basic).

    :param db: AsyncSession: Database Session.

    :return: Message about successful status change.

    :rtype: dict
    """
    user = await person.get_user_by_email(email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if account_status == user.account_status:
        return {"message": "The account status has already been assigned"}
    else:
        await person.make_user_status(email, account_status, db)
        return {"message": f"{email} - {account_status.value}"}


@router.delete("/{email}", dependencies=[Depends(admin_access)])
async def delete_user(email: EmailStr, db: AsyncSession = Depends(get_db)):
    """
        **Delete user by email. / Удаление пользователя по имейлу**\n

    =
    """
    user = await person.get_user_by_email(email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    else:
        await person.delete_user_by_email(db=db, email=email)
        return {"message": f" user {email} - was deleted"}


@router.patch("/deactivate/{email}", dependencies=[Depends(admin_access)])
async def deactivate_user(email: EmailStr, db: AsyncSession = Depends(get_db)):
    """
    **Deactivate user by email. / Деактивация аккаунта пользователя**\n

    This route allows to deactivate a user account by their email.

    :param email: EmailStr: Email of the user to deactivate.

    :param db: AsyncSession: Database Session.

    :return: Message about successful deactivation.

    :rtype: dict
    """
    user = await person.get_user_by_email(email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if not user.is_active:
        return {"message": f"The {user.email} account is already deactivated"}
    else:
        await person.deactivate_user(email, db)
        return {"message": f"{user.email} - account is deactivated"}


@router.patch("/activate/{email}", dependencies=[Depends(admin_access)])
async def activate_user(email: EmailStr, db: AsyncSession = Depends(get_db)):
    """
    **Activate user by email. / Активация аккаунта пользователя**\n

    This route allows to activate a user account by their email.

    :param email: EmailStr: Email of the user to activate.

    :param db: AsyncSession: Database Session.

    :return: Message about successful activation.

    :rtype: dict
    """
    user = await person.get_user_by_email(email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if user.is_active:
        return {"message": f"The {user.email} account is already active"}
    else:
        await person.activate_user(email, db)
        return {"message": f"{user.email} - account is activated"}


@router.patch("/kickout/{email}", dependencies=[Depends(admin_access)])
async def kickout_user(email: EmailStr, db: AsyncSession = Depends(get_db)):
    """
    **Kickout user by email (delete refresh token). / Удаление рефреш токена пользователя**\n

    """
    user = await person.get_user_by_email(email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    else:
        new_token = None
        await person.update_token(user=user, token=new_token, db=db)
        return {"message": f"{email} - delete refresh token"}


@router.post(
    "/signup_as_doctor",
    response_model=DoctorCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(admin_access)],
)
async def signup_user_as_doctor(
    user_cor_id: str,
    doctor_data: DoctorCreate = Body(...),
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

    exist_doctor = await get_doctor(db=db, doctor_id=user_cor_id)
    if exist_doctor:
        logger.debug(f"{user_cor_id} doctor already exist")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Doctor account already exists"
        )
    user = await person.get_user_by_corid(db=db, cor_id=user_cor_id)
    if not user:
        logger.debug(f"User not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    try:
        doctor = await create_doctor(
            doctor_data=doctor_data,
            db=db,
            user=user,
        )
        cer, dip, clin = await create_doctor_service(
            doctor_data=doctor_data, db=db, doctor=doctor
        )
        
        await lawyer.approve_doctor(doctor=doctor, db=db, status=Doctor_Status.approved)
    except IntegrityError as e:
        logger.error(f"Database integrity error: {e}")
        await db.rollback()
        detail = "Database error occurred. Please check the data for duplicates or invalid entries."
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during doctor creation.",
        )
    # Сериализуем ответ
    doctor_response = DoctorCreateResponse(
        id=doctor.id,
        doctor_cor_id=doctor.doctor_id,
        work_email=doctor.work_email,
        phone_number=doctor.phone_number,
        first_name=doctor.first_name,
        surname=doctor.surname,
        last_name=doctor.last_name,
        scientific_degree=doctor.scientific_degree,
        date_of_last_attestation=doctor.date_of_last_attestation,
        status=doctor.status,
        diploma_id=dip,
        certificates_id=cer,
        clinic_affiliations_id=clin,
        place_of_registration=doctor.place_of_registration,
        passport_code=doctor.passport_code,
        taxpayer_identification_number=doctor.taxpayer_identification_number,
    )

    return doctor_response


@router.patch("/asign_doctor_status/{doctor_id}", dependencies=[Depends(admin_access)])
async def assign_status(
    doctor_id: str,
    doctor_status: Doctor_Status,
    db: AsyncSession = Depends(get_db),
):
    """
    **Assign a doctor_status to a doctor by doctor_id. / Применение нового статуса доктора (подтвержден / на рассмотрении)**\n

    :param doctor_id: str: doctor_id of the user to whom you want to assign the status.

    :param doctor_status: DoctorStatus: The selected doctor_status for the assignment.

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


@router.post(
    "/register_new_user",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(admin_access)],
)
async def register_new_user(
    body: NewUserRegistration, db: AsyncSession = Depends(get_db)
):
    """
    Создает нового пользователя с временным паролем
    """

    if body:
        new_user_info = body
        exist_user = await person.get_user_by_email(new_user_info.email, db)
        if exist_user:
            logger.debug(f"{new_user_info.email} user already exists")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Account already exists"
            )
        new_user = await person.register_new_user(db=db, body=new_user_info)
        return {"message": f"Новый пользователь {body.email} успешно зарегистрирован."}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректные данные регистрации пользователя.",
        )
