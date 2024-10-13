from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from cor_pass.database.db import get_db
from cor_pass.services.auth import auth_service
from cor_pass.services.cipher import decrypt_data, decrypt_user_key
from cor_pass.services.qr_code import generate_qr_code
from cor_pass.services.recovery_file import generate_recovery_file
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
)
from cor_pass.repository import person
from cor_pass.repository import cor_id as repository_cor_id
from pydantic import EmailStr
from io import BytesIO
from fastapi.responses import StreamingResponse

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


@router.patch("/change_password")
async def change_password(body: ChangePasswordModel, db: Session = Depends(get_db)):
    """
    **Смена пароля** \n

    """

    user = await person.get_user_by_email(body.email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    else:
        if body.password:
            await person.change_user_password(body.email, body.password, db)
            logger.debug(f"{body.email} - changed his password")
            return {"message": f"User '{body.email}' changed his password"}
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
