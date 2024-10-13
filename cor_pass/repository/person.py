from sqlalchemy.orm import Session
from sqlalchemy.future import select
from sqlalchemy import func
import uuid

from cor_pass.database.models import User, Status, Verification, UserSettings
from cor_pass.schemas import UserModel, PasswordStorageSettings, MedicalStorageSettings
from cor_pass.services.auth import auth_service
from cor_pass.services.logger import logger
from cor_pass.services.cipher import (
    generate_aes_key,
    encrypt_user_key,
    generate_recovery_code,
    encrypt_data,
)
from cor_pass.services.email import send_email_code_with_qr
from sqlalchemy.exc import NoResultFound


async def get_user_by_email(email: str, db: Session) -> User | None:
    """
    The get_user_by_email function takes in an email and a database session,
    then returns the user with that email.

    :param email: str: Pass in the email of the user that we want to get
    :param db: Session: Pass the database session to the function
    :return: The first user found with the email specified
    """
    return db.query(User).filter(User.email == email).first()


async def get_user_by_uuid(uuid: str, db: Session) -> User | None:
    """
    The get_user_by_uuid function takes in an uuid and a database session,
    then returns the user with that uuid.

    :param uuid: str: Pass in the uuid of the user that we want to get
    :param db: Session: Pass the database session to the function
    :return: The first user found with the uuid specified
    """
    return db.query(User).filter(User.id == uuid).first()


async def get_user_by_corid(cor_id: str, db: Session) -> User | None:
    """
    The get_user_by_corid function takes in an corid and a database session,
    then returns the user with that corid.

    :param corid: str: Pass in the corid of the user that we want to get
    :param db: Session: Pass the database session to the function
    :return: The first user found with the corid specified
    """
    return db.query(User).filter(User.cor_id == cor_id).first()


async def create_user(body: UserModel, db: Session) -> User:
    """
    The create_user function creates a new user in the database.
        Args:
            body (UserModel): The UserModel object containing the information to be added to the database.
            db (Session): The SQLAlchemy Session object used for querying and updating data in the database.
        Returns:
            User: A User object representing a newly created user.

    :param body: UserModel: Pass the data from the request body into our create_user function
    :param db: Session: Create a database session
    :return: A user object
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

    # new_user.recovery_code = auth_service.get_password_hash(new_user.recovery_code)

    new_user.recovery_code = encrypted_recovery_code

    try:
        db.add(new_user)
        db.add(user_settings)
        db.commit()
        db.refresh(new_user)
        db.refresh(user_settings)
        return new_user
    except Exception as e:
        db.rollback()
        raise e


async def update_token(user: User, token: str | None, db: Session) -> None:
    """
    The update_token function updates the refresh token for a user.

    :param user: User: Identify the user that is being updated
    :param token: str | None: Pass the token to the function
    :param db: Session: Commit the changes to the database
    :return: None, so the return type should be none
    """
    user.refresh_token = token
    db.commit()
    db.refresh(user)


async def get_users(skip: int, limit: int, db: Session) -> list[User]:
    """
    The get_users function returns a list of all users from the database.

    :param skip: int: Skip the first n records in the database
    :param limit: int: Limit the number of results returned
    :param db: Session: Pass the database session to the function
    :return: A list of all users
    """
    query = db.query(User).offset(skip).limit(limit).all()
    return query


# переписать
async def make_user_status(email: str, account_status: Status, db: Session) -> None:
    """
    The make_user_status function takes in an email and a status, and then updates the user's status to that new one.
    Args:
    email (str): The user's email address.
    status (Status): The new Status for the user.

    :param email: str: Get the user by email
    :param status: Status: Set the status of the user
    :param db: Session: Pass the database session to the function
    :return: None
    """

    user = await get_user_by_email(email, db)
    user.account_status = account_status
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise e


async def get_user_status(email: str, db: Session):

    user = await get_user_by_email(email, db)
    status = user.account_status
    return status


async def write_verification_code(
    email: str, db: Session, verification_code: int
) -> None:
    """
    :param email: str: Pass the email address of the user to be confirmed
    :param db: Session: Pass the database session into the function
    :return: None
    """
    verification_record = (
        db.query(Verification).filter(Verification.email == email).first()
    )
    if verification_record:
        verification_record.verification_code = verification_code
        try:
            db.commit()
            logger.debug("Updated verification code in the existing record")
        except Exception as e:
            db.rollback()
            raise e
    else:
        verification_record = Verification(
            email=email, verification_code=verification_code
        )
        try:
            db.add(verification_record)
            db.commit()
            db.refresh(verification_record)
            logger.debug("Created new verification record")
        except Exception as e:
            db.rollback()
            raise e


async def verify_verification_code(
    email: str, db: Session, verification_code: int
) -> None:
    """
    :param email: str: Pass the email address of the user to be confirmed
    :param db: Session: Pass the database session into the function
    :return: None
    """
    try:
        verification_record = (
            db.query(Verification).filter(Verification.email == email).first()
        )
        if verification_record.verification_code == verification_code:
            verification_record.email_confirmation = True
            return True
        else:
            None
    except Exception as e:
        raise e


async def change_user_password(email: str, password: str, db: Session) -> None:

    user = await get_user_by_email(email, db)
    password = auth_service.get_password_hash(password)
    user.password = password
    try:
        db.commit()
        logger.debug("Password has changed")
    except Exception as e:
        db.rollback()
        raise e


async def change_user_email(email: str, current_user, db: Session) -> None:
    current_user.email = email
    try:
        db.commit()
        logger.debug("Email has changed")
    except Exception as e:
        db.rollback()
        raise e


async def add_user_backup_email(email, current_user: User, db: Session) -> None:
    current_user.backup_email = email
    try:
        db.commit()
        logger.debug("Backup email has added")
    except Exception as e:
        db.rollback()
        raise e
    

async def delete_user_by_email(db: Session, email: str):
    try:
        user = db.query(User).filter(User.email == email).one()  
        db.delete(user)  
        db.commit()  
    except NoResultFound:
        print("Пользователь не найден.")
    except Exception as e:
        db.rollback()  
        print(f"Произошла ошибка при удалении пользователя: {e}")


async def get_settings(user: User, db: Session):
    user_settings = (
        db.query(UserSettings).join(User, UserSettings.user_id == User.id).first()
    )
    if user_settings:
        return user_settings
    else:
        user_settings = UserSettings(user_id=user.id)
        try:
            db.add(user_settings)
            db.commit()
            db.refresh(user_settings)
            logger.debug("Created new user_settings")
        except Exception as e:
            db.rollback()
            raise e
    return user_settings


async def get_max_user_index(db: Session):
    try:
        result = db.execute(select(func.max(User.user_index)))
        max_index = result.scalar()
        if max_index is None:
            logger.debug("No users found in the database.")
            return None
        return max_index
    except Exception as e:
        logger.error(f"Failed to get max user_index: {e}")
        db.rollback()
        raise e


async def change_password_storage_settings(
    current_user: User, settings: PasswordStorageSettings, db: Session
) -> None:
    user_settings = (
        db.query(UserSettings).join(User, UserSettings.user_id == User.id).first()
    )
    if user_settings:
        user_settings.local_password_storage = settings.local_password_storage
        user_settings.cloud_password_storage = settings.cloud_password_storage
        db.commit()
        db.refresh(user_settings)
    else:
        user_settings = UserSettings(
            user_id=current_user.id,
        )
        user_settings.local_password_storage = settings.local_password_storage
        user_settings.cloud_password_storage = settings.cloud_password_storage
        try:
            db.add(user_settings)
            db.commit()
            db.refresh(user_settings)
            logger.debug("Created new user_settings")
        except Exception as e:
            db.rollback()
            raise e
    return user_settings


async def change_medical_storage_settings(
    current_user: User, settings: MedicalStorageSettings, db: Session
) -> None:
    user_settings = (
        db.query(UserSettings).join(User, UserSettings.user_id == User.id).first()
    )
    if user_settings:
        user_settings.local_medical_storage = settings.local_medical_storage
        user_settings.cloud_medical_storage = settings.cloud_medical_storage
        db.commit()
        db.refresh(user_settings)
    else:
        user_settings = UserSettings(
            user_id=current_user.id,
        )
        user_settings.local_medical_storage = settings.local_medical_storage
        user_settings.cloud_medical_storage = settings.cloud_medical_storage
        try:
            db.add(user_settings)
            db.commit()
            db.refresh(user_settings)
            logger.debug("Created new user_settings")
        except Exception as e:
            db.rollback()
            raise e
    return user_settings
