from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from cor_pass.database.db import get_db
from cor_pass.services.auth import auth_service
from cor_pass.services.cipher import decrypt_data, decrypt_user_key
from cor_pass.services.qr_code import generate_qr_code
from cor_pass.services.recovery_file import generate_recovery_file
from cor_pass.database.models import User, Status
from cor_pass.services.access import user_access
from cor_pass.schemas import UserDb, PasswordStorageSettings, MedicalStorageSettings
from cor_pass.repository import users
from pydantic import EmailStr
from io import BytesIO
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/get_all", response_model=list[UserDb])
async def get_all_users(
    skip: int = 0,
    limit: int = 10,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Get a list of users. / Получение списка всех пользователей**\n
    This route allows to get a list of pagination-aware users.
    Level of Access:
    - Current authorized user
    :param skip: int: Number of users to skip.
    :param limit: int: Maximum number of users to return.
    :param current_user: User: Current authenticated user.
    :param db: Session: Database session.
    :return: List of users.
    :rtype: List[UserDb]
    """
    list_users = await users.get_users(skip, limit, db)
    return list_users


@router.patch("/asign_status/{account_status}", dependencies=[Depends(user_access)])
async def assign_status(
    email: EmailStr, account_status: Status, db: Session = Depends(get_db)
):
    """
    **Assign a account_status to a user by email. / Применение нового статуса аккаунта пользователя**\n

    This route allows to assign the selected account_status to a user by their email.

    :param email: EmailStr: Email of the user to whom you want to assign the status.

    :param account_status: Status: The selected account_status for the assignment (Premium, Basic).

    :param db: Session: Database Session.

    :return: Message about successful status change.

    :rtype: dict
    """
    user = await users.get_user_by_email(email, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    if account_status == user.account_status:
        return {"message": "The acount status has already been assigned"}
    else:
        await users.make_user_status(email, account_status, db)
        return {"message": f"{email} - {account_status.value}"}


@router.get("/account_status", dependencies=[Depends(user_access)])
async def get_status(email: EmailStr, db: Session = Depends(get_db)):
    """
    **Получение статуса/уровня аккаунта пользователя**\n
    """

    user = await users.get_user_by_email(email, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    else:
        account_status = await users.get_user_status(email, db)
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

    settings = await users.get_settings(user, db)
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
    await users.change_password_storage_settings(user, settings, db)
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
    await users.change_medical_storage_settings(user, settings, db)
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


@router.get("/get_recovery_qr_code")
async def get_recovery_qr_code(
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Получения QR с кодом восстановления авторизированного пользователя**\n
    Level of Access:
    - Current authorized user
    """

    recovery_code = await decrypt_data(
        encrypted_data=user.recovery_code,
        key=await decrypt_user_key(user.unique_cipher_key),
    )
    recovery_qr_bytes = generate_qr_code(recovery_code)
    recovery_qr = BytesIO(recovery_qr_bytes)
    return StreamingResponse(recovery_qr, media_type="image/png")


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
