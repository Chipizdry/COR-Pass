from fastapi import APIRouter, File, HTTPException, Depends, UploadFile, status, BackgroundTasks
from datetime import datetime, timedelta, timezone
from cor_pass.database.db import get_db
from cor_pass.services import redis_service
from cor_pass.services.websocket_events_manager import websocket_events_manager
from cor_pass.services.auth import auth_service
from cor_pass.services.cipher import decrypt_data, decrypt_user_key
from cor_pass.services.image_validation import validate_image_file
from cor_pass.services.ip2_location import get_ip_geolocation
from cor_pass.services.qr_code import generate_qr_code
from cor_pass.services.recovery_file import generate_recovery_file
from cor_pass.services.email import send_email_code_with_qr, send_feedback_email, send_proposal_email
from cor_pass.database.models import User
from cor_pass.services.access import user_access
from loguru import logger
from cor_pass.schemas import (
    DeleteMyAccount,
    FeedbackProposalsScheema,
    FeedbackRatingScheema,
    PasswordStorageSettings,
    MedicalStorageSettings,
    EmailSchema,
    ChangePasswordModel,
    ChangeMyPasswordModel,
    ProfileCreate,
    ProfileResponse,
    UserSessionResponseModel,
)
from cor_pass.repository import person
from cor_pass.repository import cor_id as repository_cor_id
from cor_pass.repository import user_session as repository_session
from cor_pass.config.config import settings
from pydantic import EmailStr
from fastapi.responses import StreamingResponse
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

import base64
from fastapi.responses import JSONResponse
from fastapi_limiter.depends import RateLimiter

router = APIRouter(prefix="/user", tags=["User"])


@router.get(
    "/my_core_id",
    dependencies=[Depends(user_access)],
)
async def read_cor_id(
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Просмотр своего COR-id** \n

    """

    cor_id = await repository_cor_id.get_cor_id(current_user, db)
    if cor_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="COR-Id not found"
        )
    return cor_id


@router.get(
    "/my_core_id_qr",
    dependencies=[Depends(user_access)],
)
async def get_cor_id_qr(
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Просмотр своего QR COR-id** \n
    """
    cor_id = await repository_cor_id.get_cor_id(current_user, db)
    if cor_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="COR-Id not found"
        )
    cor_id_qr_bytes = generate_qr_code(cor_id)

    # Конвертация QR-кода в Base64
    encoded_qr = base64.b64encode(cor_id_qr_bytes).decode("utf-8")
    qr_code_data_url = f"data:image/png;base64,{encoded_qr}"

    return JSONResponse(content={"qr_code_url": qr_code_data_url})


@router.get("/account_status", dependencies=[Depends(user_access)])
async def get_status(email: EmailStr, db: AsyncSession = Depends(get_db)):
    """
    **Получение статуса/уровня аккаунта пользователя**\n
    """

    user = await person.get_user_by_email(email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    else:
        account_status = await person.get_user_status(email, db)
        return {"message": f"{email} - {account_status.value}"}


@router.get("/get_settings")
async def get_user_settings(
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Получение настроек авторизированного пользователя**\n
    Level of Access:
    - Current authorized user
    """

    settings = await person.get_settings(current_user, db)
    return {
        "local_password_storage": settings.local_password_storage,
        "cloud_password_storage": settings.cloud_password_storage,
        "local_medical_storage": settings.local_medical_storage,
        "cloud_medical_storage": settings.cloud_medical_storage,
    }


@router.patch("/settings/password_storage", dependencies=[Depends(user_access)])
async def choose_password_storage(
    settings: PasswordStorageSettings,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Изменения настроек места хранения записей менеджера паролей**\n
    Level of Access:
    - Current authorized user
    """
    await person.change_password_storage_settings(current_user, settings, db)
    return {
        "message": "Password storage settings are changed",
        "local_password_storage": settings.local_password_storage,
        "cloud_password_storage": settings.cloud_password_storage,
    }


@router.patch("/settings/medical_storage", dependencies=[Depends(user_access)])
async def choose_medical_storage(
    settings: MedicalStorageSettings,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Изменение настроек места хранения мед. данных**\n
    Level of Access:
    - Current authorized user
    """
    await person.change_medical_storage_settings(current_user, settings, db)
    return {
        "message": "Medical storage settings are changed",
        "local_medical_storage": settings.local_medical_storage,
        "cloud_medical_storage": settings.cloud_medical_storage,
    }


@router.get("/get_email")
async def get_user_email(
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Получения имейла авторизированного пользователя**\n
    Level of Access:
    - Current authorized user
    """

    email = current_user.email
    return {"users email": email}


@router.patch("/change_email")
async def change_email(
    body: EmailSchema,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Смена имейла авторизированного пользователя** \n
    """
    existing_email = await person.get_user_by_email(body.email, db)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Account already exist"
        )
    user = await person.get_user_by_email(current_user.email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    else:
        if body.email:
            await person.change_user_email(body.email, user, db)
            logger.debug(f"{current_user.id} - changed his email to {body.email}")
            return {
                "message": f"User '{current_user.id}' changed his email to {body.email}"
            }
        else:
            logger.warning("Incorrect email input provided for user email change.")
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                detail="Incorrect email input",
            )


@router.post("/add_backup_email")
async def add_backup_email(
    email: EmailSchema,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Добавление резервного имейла** \n
    """
    user = await person.get_user_by_email(current_user.email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    else:
        if email and email.email:  # Check if email object and its email attribute exist
            await person.add_user_backup_email(email.email, user, db)
            logger.debug(f"{current_user.id} - added his backup email")
            return {"message": f"{current_user.id} - added his backup email"}
        else:
            logger.warning("Incorrect email input provided for adding backup email.")
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                detail="Incorrect email input",
            )


@router.patch("/change_password", dependencies=[Depends(user_access)])
async def change_password(
    body: ChangePasswordModel,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Смена пароля в сценарии "Забыли пароль"** \n
    """

    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    else:
        if body.password:
            await person.change_user_password(current_user.email, body.password, db)
            logger.debug(f"{current_user.email} - changed his password")
            return {"message": f"User '{current_user.email}' changed his password"}
        else:
            logger.warning(
                "Incorrect password input provided for user password change."
            )
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                detail="Incorrect password input",
            )


@router.patch("/change_my_password", dependencies=[Depends(user_access)])
async def change_my_password(
    body: ChangeMyPasswordModel,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Смена пароля в сценарии "Изменить свой пароль"** \n
    """

    if not auth_service.verify_password(body.old_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid old password"
        )
    else:
        if body.new_password:
            await person.change_user_password(current_user.email, body.new_password, db)
            logger.debug(f"{current_user.email} - changed his password")
            return {"message": f"User '{current_user.email}' changed his password"}
        else:
            logger.warning(
                "Incorrect new password input provided for user password change."
            )
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                detail="Incorrect new password input",
            )


@router.get("/get_recovery_code")
async def get_recovery_code(
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Получения кода восстановления авторизированного пользователя**\n
    Level of Access:
    - Current authorized user
    """
    decrypted_key = await decrypt_user_key(current_user.unique_cipher_key)
    recovery_code = await decrypt_data(
        encrypted_data=current_user.recovery_code,
        key=decrypted_key,
    )
    return {"users recovery code": recovery_code}


@router.get("/get_recovery_qr_code")
async def get_recovery_qr_code(
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Получение QR с кодом восстановления авторизированного пользователя**\n
    Level of Access:
    - Current authorized user
    """
    decrypted_key = await decrypt_user_key(current_user.unique_cipher_key)
    recovery_code = await decrypt_data(
        encrypted_data=current_user.recovery_code,
        key=decrypted_key,
    )
    recovery_qr_bytes = generate_qr_code(recovery_code)

    # Конвертация QR-кода в Base64
    encoded_qr = base64.b64encode(recovery_qr_bytes).decode("utf-8")
    qr_code_data_url = f"data:image/png;base64,{encoded_qr}"

    return JSONResponse(content={"qr_code_url": qr_code_data_url})


@router.get("/get_recovery_file")
async def get_recovery_file(
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Получения файла восстановления авторизированного пользователя**\n
    Level of Access:
    - Current authorized user
    """
    decrypted_key = await decrypt_user_key(current_user.unique_cipher_key)
    recovery_code = await decrypt_data(
        encrypted_data=current_user.recovery_code,
        key=decrypted_key,
    )
    recovery_file = await generate_recovery_file(recovery_code)
    return StreamingResponse(
        content=recovery_file,
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=recovery_key.bin"},
    )


@router.delete("/delete_my_account")
async def delete_my_account(
    body: DeleteMyAccount,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    """
    **Delete user account and all data. / Удаление пользовательского аккаунта и всех его данных**\n
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    else:
        if auth_service.verify_password(body.password, current_user.password):
            await person.delete_user_by_email(db=db, email=current_user.email)
            logger.info(f"Account for user {current_user.email} was deleted")
            return {"message": f" user {current_user.email} - was deleted"}
        else:
            raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password incorrect",
        )


@router.get("/get_last_password_change")
async def get_last_password_change(
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Получение времени до требования смены пароля**\n
    Level of Access:
    - Current authorized user
    """

    last_password_change = await person.get_last_password_change(current_user.email, db)
    if last_password_change:
        change_period = timedelta(days=180)
        next_password_change = last_password_change + change_period
        days_remaining = (next_password_change - datetime.now()).days
        if days_remaining > 0:
            message = f"Your password was last changed on {last_password_change.strftime('%Y-%m-%d %H:%M:%S')}. You need to change it in {days_remaining} days."
        else:
            message = "Your password has expired. You need to change it immediately."
    else:
        message = "Last password change date is not available."

    return {
        "message": message,
    }


@router.get(
    "/send_recovery_keys_email",
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
)
async def send_recovery_keys_email(
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Отправка имейла с ключами восстановления**\n
    Level of Access:
    - Current authorized user
    """
    decrypted_key = await decrypt_user_key(current_user.unique_cipher_key)
    recovery_code = await decrypt_data(
        encrypted_data=current_user.recovery_code,
        key=decrypted_key,
    )
    await send_email_code_with_qr(
        current_user.email, host=None, recovery_code=recovery_code
    )
    return {"message": f"Sending keys to {current_user.email} done."}


@router.get(
    "/sessions/all",
    response_model=List[UserSessionResponseModel],
    dependencies=[Depends(user_access)],
)
async def read_sessions(
    skip: int = 0,
    limit: int = 150,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Get a list of user_sessions. / Получение всех сессий пользователя** \n

    :param skip: The number of sessions to skip (for pagination). Default is 0.
    :type skip: int
    :param limit: The maximum number of sessions to retrieve. Default is 50.
    :type limit: int
    :param db: The database session. Dependency on get_db.
    :type db: AsyncSession, optional
    :return: A list of UserSessionModel objects representing the sessions.
    :rtype: List[UserSessionResponseModel]
    """
    try:
        sessions_from_db = await repository_session.get_all_user_sessions(
            db, current_user.cor_id, skip, limit
        )
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    response_sessions = []
    for session in sessions_from_db:
        geolocation_data = get_ip_geolocation(session.ip_address)

        session_response = UserSessionResponseModel(
            id=session.id,
            user_id=session.user_id,
            device_type=session.device_type,
            device_info=session.device_info,
            ip_address=session.ip_address,
            device_os=session.device_os,
            created_at=session.created_at,
            updated_at=session.updated_at,
            jti=session.jti,
            **geolocation_data,
        )
        response_sessions.append(session_response)

    return response_sessions


@router.get(
    "/sessions/{session_id}",
    response_model=UserSessionResponseModel,
    dependencies=[Depends(user_access)],
)
async def read_session_info(
    session_id: str,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Get a specific session by ID. / Получение данных одной конкретной сессии пользователя** \n

    :param session_id: The ID of the session.
    :type session_id: str
    :param db: The database session. Dependency on get_db.
    :type db: AsyncSession, optional
    :return: The UserSessionModel object representing the session.
    :rtype: UserSessionResponseModel
    :raises HTTPException 404: If the session with the specified ID does not exist.
    """
    user_session = await repository_session.get_session_by_id(
        current_user, db, session_id
    )
    if user_session is None:
        logger.exception(
            f"Session with ID '{session_id}' not found for user '{current_user.id}'"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    geolocation_data = get_ip_geolocation(user_session.ip_address)
    response_data = {
        "id": user_session.id,
        "user_id": user_session.user_id,
        "device_type": user_session.device_type,
        "device_info": user_session.device_info,
        "ip_address": user_session.ip_address,
        "device_os": user_session.device_os,
        "created_at": user_session.created_at,
        "updated_at": user_session.updated_at,
        "jti": user_session.jti,
        **geolocation_data,
    }

    return UserSessionResponseModel(**response_data)


@router.delete("/sessions/{session_id}", response_model=UserSessionResponseModel)
async def remove_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    """
    **Remove a session. / Удаление сессии** \n
    :param session_id: The ID of the session to remove.
    :type session_id: str
    :param db: The database session. Dependency on get_db.
    :type db: AsyncSession, optional
    :return: The removed UserSessionModel object representing the removed session.
    :rtype: UserSessionResponseModel
    :raises HTTPException 404: If the session with the specified ID does not exist.
    """
    session_to_revoke = await repository_session.get_session_by_id(
        db=db, session_id=session_id, user=current_user
    )
    if not session_to_revoke:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена."
        )

    if session_to_revoke.user_id != current_user.cor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы не можете отозвать чужую сессию.",
        )
    if session_to_revoke.jti:
        blacklist_expires = timedelta(seconds=settings.access_token_expiration)
    await redis_service.add_jti_to_blacklist(session_to_revoke.jti, blacklist_expires)
    token = session_to_revoke.access_token
    session_token = await decrypt_data(
        encrypted_data=token,
        key=await decrypt_user_key(current_user.unique_cipher_key),
    )
    event_data = {
        "channel": "cor-erp-prod",
        "event_type": "token_blacklisted",
        "token": session_token,
        "reason": "Token explicitly revoked or logged out.",
        "timestamp": datetime.now(timezone.utc).timestamp(),
    }
    await websocket_events_manager.broadcast_event(event_data)

    session = await repository_session.delete_session(current_user, db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    return session


async def _create_profile_response(
    db_profile, current_user, router_instance
) -> ProfileResponse:
    """Формирует ProfileResponse, дешифруя поля и добавляя данные из User."""
    response_data = (
        db_profile.__dict__.copy()
    )  # Копируем, чтобы не изменять исходный ORM объект
    decoded_key = base64.b64decode(settings.aes_key)

    for field_name in ["surname", "first_name", "middle_name"]:
        encrypted_field = f"encrypted_{field_name}"
        encrypted_value = response_data.get(encrypted_field)
        if encrypted_value:
            response_data[field_name] = await decrypt_data(encrypted_value, decoded_key)
        else:
            response_data[field_name] = None

        response_data.pop(encrypted_field, None)

    response_data["email"] = current_user.email
    response_data["sex"] = current_user.user_sex

    # URL для фото
    # if db_profile.photo_data:
    #     response_data["photo_url"] = router_instance.url_path_for("get_profile_photo_endpoint", user_id=current_user.id)
    # else:
    #     response_data["photo_url"] = None

    return ProfileResponse.model_validate(response_data)


@router.put(
    "/profile/upsert", response_model=ProfileResponse, status_code=status.HTTP_200_OK
)
async def upsert_user_profile_endpoint(
    profile_data: ProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    """
    **Создание или обновление профиля пользователя**\n
    Создает новый профиль для текущего авторизованного пользователя, если его нет,
    или обновляет существующий.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    if profile_data.birth_date and profile_data.birth_date.year != current_user.birth:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Пользователь указал не верный год рождения (год рождения должен совпадать с указанным ранее в cor-id)",
        )
    db_profile = await person.upsert_user_profile(db, current_user.id, profile_data)

    return await _create_profile_response(db_profile, current_user, router)


@router.get("/profile", response_model=ProfileResponse, status_code=status.HTTP_200_OK)
async def get_user_profile_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    """
    **Получение профиля текущего пользователя**\n
    Возвращает данные профиля для текущего авторизованного пользователя.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    db_profile = await person.get_profile_by_user_id(db, current_user.id)

    if not db_profile:
        profile_data = ProfileCreate()
        db_profile = await person.upsert_user_profile(db, current_user.id, profile_data)

    return await _create_profile_response(db_profile, current_user, router)


@router.put("/photo", status_code=status.HTTP_200_OK)
async def upload_profile_photo_endpoint(
    file: UploadFile = Depends(validate_image_file),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    """
    **Загрузка или обновление фотографии профиля.**\n
    Принимает изображение (JPEG/PNG) и сохраняет его для профиля текущего пользователя.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    db_profile = await person.get_profile_by_user_id(db, current_user.id)
    if not db_profile:
        profile_data = ProfileCreate()
        db_profile = await person.upsert_user_profile(db, current_user.id, profile_data)

    await person.upload_profile_photo(db, current_user.id, file)
    return {"message": "Profile photo uploaded successfully."}


@router.get("/photo", status_code=status.HTTP_200_OK)
async def get_profile_photo_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    """
    **Получение фотографии профиля.**\n
    Возвращает фотографию профиля текущего авторизованного пользователя.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    user_id_to_fetch = current_user.id

    photo_data = await person.get_profile_photo(db=db, user_id=user_id_to_fetch)

    if not photo_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profile photo not found."
        )

    async def image_stream():
        yield photo_data[0]

    return StreamingResponse(image_stream(), media_type=photo_data[1])


@router.get("/photo/base64", status_code=status.HTTP_200_OK)
async def get_profile_photo_base64_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    """
    **Получение фотографии профиля в формате Base64.**\n
    Возвращает фотографию профиля текущего авторизованного пользователя
    в виде Base64-строки, встраиваемой в Data URL.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    user_id_to_fetch = current_user.id

    photo_data = await person.get_profile_photo(db=db, user_id=user_id_to_fetch)

    if not photo_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profile photo not found."
        )

    encoded_photo = base64.b64encode(photo_data[0]).decode("utf-8")

    photo_data_url = f"data:{photo_data[1]};base64,{encoded_photo}"

    return JSONResponse(content={"photo_data_url": photo_data_url})


@router.post("/feedback/rate", 
             dependencies=[Depends(RateLimiter(times=5, seconds=60))],
             status_code=status.HTTP_200_OK)
async def submit_feedback(
    feedback: FeedbackRatingScheema,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Принимает обратную связь от пользователя и отправляет её на почту отдела маркетинга.
    """
    background_tasks.add_task(
        send_feedback_email,
        feedback=feedback,
        user_cor_id=current_user.cor_id,
        user_email=current_user.email
    )
    
    return {"message": "Спасибо за ваш отзыв! Он был успешно отправлен."}

@router.post("/feedback/proposal", 
             dependencies=[Depends(RateLimiter(times=5, seconds=60))],
             status_code=status.HTTP_200_OK)
async def submit_proposal(
    feedback: FeedbackProposalsScheema,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Принимает предложение от пользователя и отправляет её на почту отдела маркетинга.
    """
    background_tasks.add_task(
        send_proposal_email,
        feedback=feedback,
        user_cor_id=current_user.cor_id,
        user_email=current_user.email
    )
    
    return {"message": "Спасибо за ваше предложение! Мы рассмотрим его и свяжемся с Вами при необходимости"}