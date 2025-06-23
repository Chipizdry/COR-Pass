import base64
from http.client import HTTPException
from typing import List, Optional
from fastapi import UploadFile, status
from sqlalchemy.future import select
from sqlalchemy import func
import uuid
from datetime import datetime
from cor_pass.database.models import (
    User,
    Status,
    Verification,
    UserSettings,
    Profile
)
from cor_pass.repository.password_generator import generate_password
from cor_pass.repository import cor_id as repository_cor_id
from cor_pass.schemas import (
    NewUserRegistration,
    PasswordGeneratorSettings,
    ProfileCreate,
    UserModel,
    PasswordStorageSettings,
    MedicalStorageSettings,
)
from cor_pass.services.auth import auth_service
from cor_pass.services import roles as role_check
from cor_pass.services.logger import logger
from cor_pass.services.cipher import (
    generate_aes_key,
    encrypt_user_key,
    generate_recovery_code,
    encrypt_data,
)
from cor_pass.services.email import (
    send_email_code_with_qr,
    send_email_code_with_temp_pass,
)
from sqlalchemy.exc import NoResultFound

from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.config.config import settings

async def get_user_by_email(email: str, db: AsyncSession) -> User | None:
    """
    Асинхронно получает пользователя по его email.

    """
    email_lower = email.lower()
    stmt = select(User).where(User.email.ilike(email_lower))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    return user


async def get_user_by_uuid(uuid: str, db: AsyncSession) -> User | None:
    """
    Асинхронно получает пользователя по его UUID.

    """
    stmt = select(User).where(User.id == uuid)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    return user


async def get_user_by_corid(cor_id: str, db: AsyncSession) -> User | None:
    """
    Асинхронно получает пользователя по его Cor ID.

    """
    stmt = select(User).where(User.cor_id == cor_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    return user


async def get_max_user_index(db: AsyncSession) -> int | None:
    """Асинхронно получает максимальный user_index из базы данных."""
    result = await db.execute(select(func.max(User.user_index)))
    return result.scalar_one_or_none()


async def create_user(body: UserModel, db: AsyncSession) -> User:
    """
    Асинхронно создает нового юзера в базе данных.

    """

    new_user = User(**body.model_dump())
    new_user.id = str(uuid.uuid4())

    user_settings = UserSettings(user_id=new_user.id)
    max_index = await get_max_user_index(db)
    new_user.user_index = (max_index + 1) if max_index is not None else 1
    new_user.account_status = Status.basic
    new_user.unique_cipher_key = await generate_aes_key()  # ->bytes
    new_user.recovery_code = await generate_recovery_code()
    await send_email_code_with_qr(
        new_user.email, host=None, recovery_code=new_user.recovery_code
    )
    encrypted_recovery_code = await encrypt_data(
        data=new_user.recovery_code, key=new_user.unique_cipher_key
    )

    new_user.unique_cipher_key = await encrypt_user_key(new_user.unique_cipher_key)
    new_user.recovery_code = encrypted_recovery_code

    try:
        db.add(new_user)
        db.add(user_settings)
        await db.commit()
        await db.refresh(new_user)
        await db.refresh(user_settings)
        return new_user
    except Exception as e:
        await db.rollback()
        raise e


async def update_token(user: User, token: str | None, db: AsyncSession) -> None:
    """
    Асинхронно обновляет refresh token пользователя.

    """
    user.refresh_token = token
    await db.commit()
    await db.refresh(user)


async def get_users(skip: int, limit: int, db: AsyncSession) -> list[User]:
    """
    Асинхронно возвращает список всех пользователей базы данных.

    """
    stmt = select(User).offset(skip).limit(limit)
    result = await db.execute(stmt)
    users = result.scalars().all()
    return list(users)


# переписать
async def make_user_status(
    email: str, account_status: Status, db: AsyncSession
) -> None:
    """
    Асинхронно обновляет статус пользователя на указанный.

    """

    user = await get_user_by_email(email, db)
    if user:
        user.account_status = account_status
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise e


async def get_user_status(email: str, db: AsyncSession) -> Status | None:
    """
    Асинхронно получает статус пользователя по его email.
    """
    user = await get_user_by_email(email, db)
    if user:
        return user.account_status
    return None


async def write_verification_code(
    email: str, db: AsyncSession, verification_code: int
) -> None:
    """
    Асинхронно записывает или обновляет верификационный код для указанного email.

    """
    stmt = select(Verification).where(Verification.email == email)
    result = await db.execute(stmt)
    verification_record = result.scalar_one_or_none()

    if verification_record:
        verification_record.verification_code = verification_code
        try:
            await db.commit()
            logger.debug("Обновлен код верификации в существующей записи")
        except Exception as e:
            await db.rollback()
            raise e
    else:
        verification_record = Verification(
            email=email, verification_code=verification_code
        )
        try:
            db.add(verification_record)
            await db.commit()
            await db.refresh(verification_record)
            logger.debug("Создана новая запись верификации")
        except Exception as e:
            await db.rollback()
            raise e


async def verify_verification_code(
    email: str, db: AsyncSession, verification_code: int
) -> bool:
    """
    Асинхронно проверяет код верификации для указанного e-mail.

    """
    try:
        stmt = select(Verification).where(Verification.email == email)
        result = await db.execute(stmt)
        verification_record = result.scalar_one_or_none()

        if (
            verification_record
            and verification_record.verification_code == verification_code
        ):
            verification_record.email_confirmation = True
            await db.commit()
            return True
        else:
            return False
    except Exception as e:
        raise e


async def change_user_password(email: str, password: str, db: AsyncSession) -> None:
    """
    Асинхронно изменяет пользовательский пароль.
    """
    user = await get_user_by_email(email, db)
    if user:
        hashed_password = auth_service.get_password_hash(password)
        user.password = hashed_password
        user.last_password_change = datetime.now()
        try:
            await db.commit()
            logger.debug("Password has changed")
        except Exception as e:
            await db.rollback()
            raise e
    else:
        logger.warning(f"User with email {email} not found during password change.")


async def change_user_email(email: str, current_user, db: AsyncSession) -> None:
    """
    Асинхронно изменяет email пользователя.
    """
    current_user.email = email
    try:
        await db.commit()
        logger.debug("Email has changed")
    except Exception as e:
        await db.rollback()
        raise e


async def add_user_backup_email(
    email: str, current_user: User, db: AsyncSession
) -> None:
    """
    Асинхронно добавляет резервный email пользователю.
    """
    current_user.backup_email = email
    try:
        await db.commit()
        logger.debug("Backup email has added")
    except Exception as e:
        await db.rollback()
        raise e


async def delete_user_by_email(db: AsyncSession, email: str):
    """
    Асинхронно удаляет пользователя по его email.
    """
    try:
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalar_one()

        await db.delete(user)
        await db.commit()
    except NoResultFound:
        print("Пользователя не найдено.")
    except Exception as e:
        await db.rollback()
        print(f"Произошла ошибка при удалении пользователя: {e}")


async def get_settings(user: User, db: AsyncSession):
    """
    Асинхронно получает пользовательские настройки. Если настройки отсутствуют, создаются новые.
    """
    stmt = (
        select(UserSettings)
        .join(User, UserSettings.user_id == User.id)
        .where(UserSettings.user_id == user.id)
    )
    result = await db.execute(stmt)
    user_settings = result.scalar_one_or_none()

    if user_settings:
        return user_settings
    else:
        user_settings = UserSettings(user_id=user.id)
        try:
            db.add(user_settings)
            await db.commit()
            await db.refresh(user_settings)
            logger.debug("Created new user_settings")
        except Exception as e:
            await db.rollback()
            raise e
        return user_settings


async def get_max_user_index(db: AsyncSession):
    """
    Асинхронно получает максимальное значение user_index из таблицы User.
    """
    try:
        result = await db.execute(select(func.max(User.user_index)))
        max_index = result.scalar_one_or_none()
        if max_index is None:
            logger.debug("No users found in the database.")
            return None
        return max_index
    except Exception as e:
        logger.error(f"Failed to get max user_index: {e}")
        await db.rollback()
        raise e


async def change_password_storage_settings(
    current_user: User, settings: PasswordStorageSettings, db: AsyncSession
) -> UserSettings:
    """
    Асинхронно изменяет настройки хранения пользовательских паролей.
    Если настройки отсутствуют, создаются новые.
    """
    stmt = (
        select(UserSettings)
        .join(User, UserSettings.user_id == User.id)
        .where(UserSettings.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    user_settings = result.scalar_one_or_none()

    if user_settings:
        user_settings.local_password_storage = settings.local_password_storage
        user_settings.cloud_password_storage = settings.cloud_password_storage
        await db.commit()
        await db.refresh(user_settings)
    else:
        user_settings = UserSettings(
            user_id=current_user.id,
            local_password_storage=settings.local_password_storage,
            cloud_password_storage=settings.cloud_password_storage,
        )
        try:
            db.add(user_settings)
            await db.commit()
            await db.refresh(user_settings)
            logger.debug("Created new user_settings")
        except Exception as e:
            await db.rollback()
            raise e
    return user_settings


async def change_medical_storage_settings(
    current_user: User, settings: MedicalStorageSettings, db: AsyncSession
) -> UserSettings:
    """
    Асинхронно изменяет настройку хранения медицинских данных пользователя.
    Если настройки отсутствуют, создаются новые.
    """
    stmt = (
        select(UserSettings)
        .join(User, UserSettings.user_id == User.id)
        .where(UserSettings.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    user_settings = result.scalar_one_or_none()

    if user_settings:
        user_settings.local_medical_storage = settings.local_medical_storage
        user_settings.cloud_medical_storage = settings.cloud_medical_storage
        await db.commit()
        await db.refresh(user_settings)
    else:
        user_settings = UserSettings(
            user_id=current_user.id,
            local_medical_storage=settings.local_medical_storage,
            cloud_medical_storage=settings.cloud_medical_storage,
        )
        try:
            db.add(user_settings)
            await db.commit()
            await db.refresh(user_settings)
            logger.debug("Created new user_settings")
        except Exception as e:
            await db.rollback()
            raise e
    return user_settings


async def deactivate_user(email: str, db: AsyncSession) -> None:
    """
    Асинхронно деактивирует аккаунт пользователя по указанному email-адресу.

    """
    user = await get_user_by_email(email, db)
    if user:
        user.is_active = False
        try:
            await db.commit()
            await db.refresh(user)
        except Exception as e:
            await db.rollback()
            raise e


async def activate_user(email: str, db: AsyncSession) -> None:
    """
    Асинхронно активирует аккаунт пользователя по указанному email-адресу.

    """
    user = await get_user_by_email(email, db)
    if user:
        user.is_active = True
        try:
            await db.commit()
            await db.refresh(user)
        except Exception as e:
            await db.rollback()
            raise e


async def get_last_password_change(email: str, db: AsyncSession) -> Optional[datetime]:
    """
    Асинхронно получает дату последнего изменения пароля пользователя по его email.
    Возвращает None, если пользователь не найден.
    """
    user = await get_user_by_email(email, db)
    if user:
        return user.last_password_change
    return None


async def get_user_roles(email: str, db: AsyncSession) -> List[str]:
    roles = []
    user = await get_user_by_email(email, db)

    if await role_check.admin_role_checker.is_admin(user=user):
        roles.append("admin")
    if await role_check.lawyer_role_checker.is_lawyer(user=user, db=db):
        roles.append("lawyer")
    if await role_check.cor_int_role_checker.is_cor_int(user=user):
        roles.append("cor-int")
    doctor = await role_check.doctor_role_checker.is_doctor(user=user, db=db)
    if doctor:
        roles.append("doctor")
    lab_assistant = await role_check.lab_assistant_role_checker.is_lab_assistant(user=user, db=db)
    if lab_assistant:
        roles.append("lab_assistant")
    energy_manager = await role_check.energy_manager_role_checker.is_energy_manager(user=user, db=db)
    if energy_manager:
        roles.append("energy_manager")
    if user.is_active:
        roles.append("active_user")
    return roles


async def register_new_user(db: AsyncSession, body: NewUserRegistration):
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

    new_user = await create_user(user_signup_data, db)

    await db.flush()

    await repository_cor_id.create_new_corid(new_user, db)
    await db.commit()

    await send_email_code_with_temp_pass(email=body.email, temp_pass=temp_password)


async def get_profile_by_user_id(db: AsyncSession, user_id: str) -> Optional[Profile]:
    """
    Получает профиль пользователя по user_id.
    """

    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Profile)
        .where(Profile.user_id == user_id)
        .options(selectinload(Profile.user))
    )
    return result.scalars().first()

async def upsert_user_profile(db: AsyncSession, user_id: str, profile_data: ProfileCreate) -> Profile:
    """
    Создает или обновляет профиль пользователя, обрабатывая шифрование.
    """
    db_profile = await get_profile_by_user_id(db, user_id)

    update_data = profile_data.model_dump(exclude_unset=True) # Получаем только переданные поля
    decoded_key = base64.b64decode(settings.aes_key)

    if db_profile:
        print(f"Updating existing profile for user_id: {user_id}")
        for field, value in update_data.items():
            if field in ["surname", "first_name", "middle_name"]:
                setattr(db_profile, f"encrypted_{field}", await encrypt_data(value.encode("utf-8"), decoded_key) if value is not None else None)
            elif field == "photo": 
                pass 
            else:
                setattr(db_profile, field, value)
        
        await db.commit()
        await db.refresh(db_profile)
    else:
        print(f"Creating new profile for user_id: {user_id}")
        profile_dict = {}
        
        for field, value in update_data.items():
            if field in ["surname", "first_name", "middle_name"]:
                profile_dict[f"encrypted_{field}"] = await encrypt_data(value.encode("utf-8"), decoded_key) if value is not None else None
            else:
                profile_dict[field] = value
        
        db_profile = Profile(user_id=user_id, **profile_dict)
        db.add(db_profile)
        await db.commit()
        await db.refresh(db_profile)
    
    return db_profile

async def upload_profile_photo(db: AsyncSession, user_id: str, file: UploadFile) -> Profile:
    """
    Загружает или обновляет фотографию профиля пользователя.
    """
    db_profile = await get_profile_by_user_id(db, user_id)    
    file_data = await file.read()
    db_profile.photo_data = file_data
    db_profile.photo_file_type = file.content_type

    await db.commit()
    await db.refresh(db_profile)
    return db_profile

async def get_profile_photo(db: AsyncSession, user_id: str) -> Optional[tuple[bytes, str]]:
    """
    Получает бинарные данные фотографии профиля и её тип.
    Возвращает кортеж (photo_data, photo_file_type) или None.
    """
    db_profile = await get_profile_by_user_id(db, user_id)
    if db_profile and db_profile.photo_data:
        return db_profile.photo_data, db_profile.photo_file_type
    return None