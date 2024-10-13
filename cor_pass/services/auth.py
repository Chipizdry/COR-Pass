from typing import Optional

from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from datetime import timedelta, datetime, timezone
from sqlalchemy.orm import Session

from cor_pass.database.db import get_db
from cor_pass.repository import person as repository_users
from cor_pass.config.config import settings
from cor_pass.services.logger import logger


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
            expire = datetime.now(timezone.utc) + timedelta(seconds=expires_delta)
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=60)
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
            expire = datetime.now(timezone.utc) + timedelta(seconds=expires_delta)
        else:
            expire = datetime.now(timezone.utc) + timedelta(days=7)
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
        It takes an access token as input and returns the user object if it's valid, otherwise raises an exception.

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
        try:

            payload = jwt.decode(token, key=self.SECRET_KEY, algorithms=self.ALGORITHM)

            if payload["scp"] == "access_token":
                cor_id = payload["oid"]
                if id is None:
                    raise credentials_exception
            else:
                raise credentials_exception
        except JWTError as e:
            raise credentials_exception

        user = await repository_users.get_user_by_corid(cor_id, db)
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


auth_service = Auth()
