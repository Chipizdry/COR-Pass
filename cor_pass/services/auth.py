from enum import Enum
from typing import Optional

from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from datetime import timedelta, datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from cor_pass.database.db import get_db
from cor_pass.database.models import Device, DeviceAccess
from cor_pass.repository import person as repository_users
from cor_pass.repository import device as repository_devices
from cor_pass.config.config import settings
from cor_pass.services.logger import logger

from sqlalchemy.ext.asyncio import AsyncSession

class Auth:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    SECRET_KEY = settings.secret_key
    ALGORITHM = settings.algorithm
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

    def verify_password(self, plain_password, hashed_password):
        """
        The verify_password function takes a plain-text password and the hashed version of that password,
            and returns True if they match, False otherwise. This is used to verify that the user's login
            credentials are correct.

        :param self: Represent the instance of the class
        :param plain_password: Pass the password that is entered by the user
        :param hashed_password: Compare the plain_password parameter to see if they match
        :return: True if the password is correct, and false otherwise
        """
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str):
        """
        The get_password_hash function takes a password as input and returns the hash of that password.
            The function uses the pwd_context object to generate a hash from the given password.
        :param self: Represent the instance of the class
        :param password: str: Pass the password into the function
        :return: A hash of the password
        """
        return self.pwd_context.hash(password)

    async def create_access_token(
        self, data: dict, expires_delta: Optional[float] = None
    ):
        """
        The create_access_token function creates a new access token for the user.
        :param self: Represent the instance of the class
        :param data: dict: Pass the data to be encoded
        :param expires_delta: Optional[float]: Set the time limit for the token
        :return: A string
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + timedelta(hours=expires_delta)
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                seconds=settings.access_token_expiration
            )
        to_encode.update(
            {"iat": datetime.now(timezone.utc), "exp": expire, "scp": "access_token"}
        )

        encoded_access_token = jwt.encode(
            to_encode, key=self.SECRET_KEY, algorithm=self.ALGORITHM
        )
        logger.debug(f"Access token: {encoded_access_token}")
        return encoded_access_token

    async def create_refresh_token(
        self, data: dict, expires_delta: Optional[float] = None
    ):
        """
        The create_refresh_token function creates a refresh token for the user.
            Args:
                data (dict): A dictionary containing the user's id and username.
                expires_delta (Optional[float]): The number of seconds until the refresh token expires. Defaults to None, which sets it to 7 days from now.

        :param self: Represent the instance of the class
        :param data: dict: Pass in the user data that we want to encode
        :param expires_delta: Optional[float]: Set the expiration time of the refresh token
        :return: A refresh token that is encoded with the user's id, username, email and scope
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + timedelta(hours=expires_delta)
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                hours=settings.refresh_token_expiration
            )
        to_encode.update(
            {"iat": datetime.now(timezone.utc), "exp": expire, "scp": "refresh_token"}
        )

        encoded_refresh_token = jwt.encode(
            to_encode, key=self.SECRET_KEY, algorithm=self.ALGORITHM
        )
        logger.debug(f"refresh token: {encoded_refresh_token}")
        return encoded_refresh_token

    async def decode_refresh_token(self, refresh_token: str):
        """
        The decode_refresh_token function takes a refresh token and decodes it.
            If the scope is 'refresh_token', then we return the email address of the user.
            Otherwise, we raise an HTTPException with status code 401 (UNAUTHORIZED) and detail message 'Invalid scope for token'.


        :param self: Represent the instance of the class
        :param refresh_token: str: Pass in the refresh token that was sent by the user
        :return: The email of the user who requested it
        """
        try:

            payload = jwt.decode(
                refresh_token, key=self.SECRET_KEY, algorithms=self.ALGORITHM
            )

            if payload["scp"] == "refresh_token":
                id = payload["oid"]
                return id
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid scope for token",
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )

    async def get_current_user(
        self, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
    ):
        """
        The get_current_user function is a dependency that will be used in the protected routes.
        It takes an access token as input and returns the user object if it's valid.
        If the token is expired, it raises token_expired exception.

        :param self: Represent the instance of the class
        :param token: str: Get the token from the request header
        :param db: Session: Get the database session
        :return: An object of type user
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        token_expired_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please refresh the token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

        try:
            payload = jwt.decode(
                token, key=self.SECRET_KEY, algorithms=[self.ALGORITHM]
            )
            # Проверяем, есть ли время истечения
            exp = payload.get("exp")
            if exp is None:
                raise credentials_exception

            # Сравниваем текущее время с временем истечения токена
            if datetime.fromtimestamp(exp) < datetime.now():
                raise token_expired_exception

            if payload["scp"] == "access_token":
                oid = payload["oid"]
                if oid is None:
                    raise credentials_exception
            else:
                raise credentials_exception
        except JWTError:
            raise token_expired_exception

        # user = await repository_users.get_user_by_corid(cor_id, db)
        user = await repository_users.get_user_by_uuid(oid, db)
        if user is None:
            raise credentials_exception

        return user

    # Функция для проверки допустимости редирект URL
    # def is_valid_redirect_url(self, redirectUrl):
    #     allowed_urls = settings.allowed_redirect_urls
    #     parsed_url = urlparse(redirectUrl)
    #     if parsed_url.scheme not in ["http", "https"]:
    #         return False
    #     if f"{parsed_url.scheme}://{parsed_url.netloc}" not in allowed_urls:
    #         return False
    #     return True

    async def create_device_jwt(self, device_id: str, user_id: str, expires_delta: Optional[float] = None):
        to_encode = {"sub": device_id, "user_id": user_id}
        if expires_delta:
            expire = datetime.now(timezone.utc) + + timedelta(hours=expires_delta)
            to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, key=self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt
    
    async def get_current_device(self, token: str, db: AsyncSession) -> Device:

        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        token_expired_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please refresh the token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=self.ALGORITHM)
            device_id = payload.get("sub")
            if device_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Не удалось подтвердить учетные данные устройства"
                )
        except JWTError:
            raise credentials_exception
        
        device = await repository_devices.get_device_by_id(db=db, device_id=device_id)
        
        if device is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Устройство не найдено"
            )
        return device
    
    async def verify_device_access(self, device_id: str, current_user_id: str, db: AsyncSession, required_level: Optional[Enum] = None) -> Device:
        result_device = await db.execute(select(Device).where(Device.id == device_id))
        device = result_device.scalar_one_or_none()
        if not device:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Устройство не найдено")

        if device.user_id == current_user_id:
            return device  # Владелец имеет полный доступ

        result_access = await db.execute(
            select(DeviceAccess).where(
                DeviceAccess.device_id == device_id,
                DeviceAccess.accessing_user_id == current_user_id
            )
        )
        access = result_access.scalar_one_or_none()

        if not access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет прав доступа к устройству"
            )

        if required_level and access.access_level.value not in [required_level.value, "share", "read_write"]: # Владелец имеет все права
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Требуется уровень доступа: {required_level.value}, ваш уровень: {access.access_level.value}"
            )

        return device


auth_service = Auth()
