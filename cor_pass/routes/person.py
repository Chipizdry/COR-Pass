from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from cor_pass.database.db import get_db
from cor_pass.services.auth import auth_service
from cor_pass.services.cipher import decrypt_data, decrypt_user_key
from cor_pass.services.qr_code import generate_qr_code
from cor_pass.services.recovery_file import generate_recovery_file
from cor_pass.services.email import send_email_code_with_qr
from cor_pass.database.models import User, Status
from cor_pass.services.access import user_access
from cor_pass.services.logger import logger
from cor_pass.schemas import (
    UserDb,
    PasswordStorageSettings,
    MedicalStorageSettings,
    EmailSchema,
    ChangePasswordModel,
    ResponseCorIdModel,
    ChangeMyPasswordModel,
    UserSessionResponseModel,
)
from cor_pass.repository import person
from cor_pass.repository import cor_id as repository_cor_id
from cor_pass.repository import user_session as repository_session
from pydantic import EmailStr
from fastapi.responses import StreamingResponse
from typing import List

router = APIRouter(prefix="/user", tags=["User"])


@router.get(
    "/my_core_id",
    # response_model=ResponseCorIdModel,
    dependencies=[Depends(user_access)],
)
async def read_cor_id(
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Просмотр своего COR-id** \n

    """

    cor_id = await repository_cor_id.get_cor_id(user, db)
    if cor_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="COR-Id not found"
        )
    return cor_id


@router.get("/account_status", dependencies=[Depends(user_access)])
async def get_status(email: EmailStr, db: Session = Depends(get_db)):
    """
    **Получение статуса/уровня аккаунта пользователя**\n
    """

    user = await person.get_user_by_email(email, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    else:
        account_status = await person.get_user_status(email, db)
        return {"message": f"{email} - {account_status.value}"}


@router.get("/get_settings")
async def get_user_settings(
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Получение настроек авторизированного пользователя**\n
    Level of Access:
    - Current authorized user
    """

    settings = await person.get_settings(user, db)
    return {
        "local_password_storage": settings.local_password_storage,
        "cloud_password_storage": settings.cloud_password_storage,
        "local_medical_storage": settings.local_medical_storage,
        "cloud_medical_storage": settings.cloud_medical_storage,
    }


@router.patch("/settings/password_storage", dependencies=[Depends(user_access)])
async def choose_password_storage(
    settings: PasswordStorageSettings,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Изменения настроек места хранения записей менеджера паролей**\n
    Level of Access:
    - Current authorized user
    """
    await person.change_password_storage_settings(user, settings, db)
    return {
        "message": "Password storage settings are changed",
        "local_password_storage": settings.local_password_storage,
        "cloud_password_storage": settings.cloud_password_storage,
    }


@router.patch("/settings/medical_storage", dependencies=[Depends(user_access)])
async def choose_medical_storage(
    settings: MedicalStorageSettings,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Изменение настроек места хранения мед. данных**\n
    Level of Access:
    - Current authorized user
    """
    await person.change_medical_storage_settings(user, settings, db)
    return {
        "message": "Medical storage settings are changed",
        "local_medical_storage": settings.local_medical_storage,
        "cloud_medical_storage": settings.cloud_medical_storage,
    }


@router.get("/get_email")
async def get_user_email(
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Получения имейла авторизированного пользователя**\n
    Level of Access:
    - Current authorized user
    """

    email = user.email
    return {"users email": email}


@router.patch("/change_email")
async def change_email(
    email: str,
    current_user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Смена имейла авторизированного пользователя** \n

    """
    user = await person.get_user_by_email(current_user.email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    else:
        if email:
            await person.change_user_email(email, user, db)
            logger.debug(f"{current_user.id} - changed his email to {email}")
            return {"message": f"User '{current_user.id}' changed his email to {email}"}
        else:
            print("Incorrect email input")
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                detail="Incorrect email input",
            )


@router.post("/add_backup_email")
async def add_backup_email(
    email: EmailSchema,
    current_user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
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
        if email:
            await person.add_user_backup_email(email.email, user, db)
            logger.debug(f"{current_user.id} - add his backup email")
            return {"message": f"{current_user.id} - add his backup email"}
        else:
            print("Incorrect email input")
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                detail="Incorrect email input",
            )


@router.patch("/change_password", dependencies=[Depends(user_access)])
async def change_password(
    body: ChangePasswordModel,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Смена пароля в сценарии "Забыли пароль"** \n

    """

    # user = await person.get_user_by_email(body.email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    else:
        if body.password:
            await person.change_user_password(user.email, body.password, db)
            logger.debug(f"{user.email} - changed his password")
            return {"message": f"User '{user.email}' changed his password"}
        else:
            print("Incorrect password input")
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                detail="Incorrect password input",
            )


@router.patch("/change_my_password", dependencies=[Depends(user_access)])
async def change_my_password(
    body: ChangeMyPasswordModel,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Смена пароля в сценарии "Изменить свой пароль"** \n
    """

    if not auth_service.verify_password(body.old_password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid old password"
        )
    else:
        if body.new_password:
            await person.change_user_password(user.email, body.new_password, db)
            logger.debug(f"{user.email} - changed his password")
            return {"message": f"User '{user.email}' changed his password"}
        else:
            print("Incorrect password input")
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                detail="Incorrect password input",
            )


@router.get("/get_recovery_code")
async def get_recovery_code(
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Получения кода восстановления авторизированного пользователя**\n
    Level of Access:
    - Current authorized user
    """
    recovery_code = await decrypt_data(
        encrypted_data=user.recovery_code,
        key=await decrypt_user_key(user.unique_cipher_key),
    )
    return {"users recovery code": recovery_code}


# @router.get("/get_recovery_qr_code")
# async def get_recovery_qr_code(
#     user: User = Depends(auth_service.get_current_user),
#     db: Session = Depends(get_db),
# ):
#     """
#     **Получения QR с кодом восстановления авторизированного пользователя**\n
#     Level of Access:
#     - Current authorized user
#     """

#     recovery_code = await decrypt_data(
#         encrypted_data=user.recovery_code,
#         key=await decrypt_user_key(user.unique_cipher_key),
#     )
#     recovery_qr_bytes = generate_qr_code(recovery_code)
#     recovery_qr = BytesIO(recovery_qr_bytes)
#     return StreamingResponse(recovery_qr, media_type="image/png")

import base64
from fastapi.responses import JSONResponse


@router.get("/get_recovery_qr_code")
async def get_recovery_qr_code(
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Получение QR с кодом восстановления авторизированного пользователя**\n
    Level of Access:
    - Current authorized user
    """

    recovery_code = await decrypt_data(
        encrypted_data=user.recovery_code,
        key=await decrypt_user_key(user.unique_cipher_key),
    )
    recovery_qr_bytes = generate_qr_code(recovery_code)

    # Конвертация QR-кода в Base64
    encoded_qr = base64.b64encode(recovery_qr_bytes).decode("utf-8")
    qr_code_data_url = f"data:image/png;base64,{encoded_qr}"

    return JSONResponse(content={"qr_code_url": qr_code_data_url})


@router.get("/get_recovery_file")
async def get_recovery_file(
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Получения файла восстановления авторизированного пользователя**\n
    Level of Access:
    - Current authorized user
    """

    recovery_code = await decrypt_data(
        encrypted_data=user.recovery_code,
        key=await decrypt_user_key(user.unique_cipher_key),
    )
    recovery_file = await generate_recovery_file(recovery_code)
    return StreamingResponse(
        recovery_file,
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=recovery_key.bin"},
    )


@router.delete("/delete_my_account")
async def delete_my_account(
    db: Session = Depends(get_db), user: User = Depends(auth_service.get_current_user)
):
    """
    **Delete user account and all data. / Удаление пользовательского аккаунта и всех его данных**\n

    """
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    else:
        await person.delete_user_by_email(db=db, email=user.email)
        logger.info("Account was deleted")
        return {"message": f" user {user.email} - was deleted"}


@router.get("/get_last_password_change")
async def get_last_password_change(
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Получение времени до требования смены пароля**\n
    Level of Access:
    - Current authorized user
    """

    last_password_change = await person.get_last_password_change(user.email, db)
    if last_password_change:
        change_period = timedelta(days=180)
        next_password_change = last_password_change + change_period
        days_remaining = (next_password_change - datetime.now()).days
        if days_remaining > 0:
            message = f"Your password was last changed on {last_password_change}. You need to change it in {days_remaining} days."
        else:
            message = "Your password has expired. You need to change it immediately."
    else:
        message = "Last password change date is not available."

    return {
        "message": message,
    }


@router.get("/send_recovery_keys_email")
async def send_recovery_keys_email(
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Отправка имейла с ключами восстановления**\n
    Level of Access:
    - Current authorized user
    """
    recovery_code = await decrypt_data(
        encrypted_data=user.recovery_code,
        key=await decrypt_user_key(user.unique_cipher_key),
    )
    await send_email_code_with_qr(user.email, host=None, recovery_code=recovery_code)
    return {f"sending keys to {user.email} done."}


@router.get(
    "/sessions/all",
    response_model=List[UserSessionResponseModel],
    dependencies=[Depends(user_access)],
)
async def read_sessions(
    skip: int = 0,
    limit: int = 150,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Get a list of user_sessions. / Получение всех сессий пользователя** \n

    :param skip: The number of sessions to skip (for pagination). Default is 0.
    :type skip: int
    :param limit: The maximum number of sessions to retrieve. Default is 50.
    :type limit: int
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: A list of UserSessionModel objects representing the sessions.
    :rtype: List[UserSessionModel]
    """
    try:
        sessions = await repository_session.get_all_user_sessions(
            db, user.cor_id, skip, limit
        )
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    return sessions


@router.get(
    "/sessions/{session_id}",
    response_model=UserSessionResponseModel,
    dependencies=[Depends(user_access)],
)
async def read_session_info(
    session_id: str,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Get a specific session by ID. / Получение данных одной конкретной сессии пользователя** \n

    :param session_id: The ID of the session.
    :type session_id: str
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: The UserSessionModel object representing the session.
    :rtype: UserSessionModel
    :raises HTTPException 404: If the session with the specified ID does not exist.
    """
    user_session = await repository_session.get_session_by_id(user, db, session_id)
    if user_session is None:
        logger.exception("Session not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return user_session


@router.delete("/sessions/{session_id}", response_model=UserSessionResponseModel)
async def remove_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
):
    """
    **Remove a session. / Удаление сессии** \n

    :param session_id: The ID of the session to remove.
    :type session_id: str
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: The removed UserSessionModel object representing the removed session.
    :rtype: UserSessionModel
    :raises HTTPException 404: If the session with the specified ID does not exist.
    """
    session = await repository_session.delete_session(user, db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return session
