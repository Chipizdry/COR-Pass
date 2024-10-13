from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    status,
    Security,
    BackgroundTasks,
    Request,
    File,
    Form,
)
from fastapi.security import (
    OAuth2PasswordRequestForm,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.orm import Session
from random import randint

from cor_pass.database.db import get_db
from cor_pass.schemas import (
    UserModel,
    ResponseUser,
    TokenModel,
    EmailSchema,
    VerificationModel,
    ChangePasswordModel,
    LoginResponseModel,
    RecoveryCodeModel,
)
from cor_pass.database.models import User
from cor_pass.repository import person as repository_person
from cor_pass.repository import cor_id as repository_cor_id
from cor_pass.services.auth import auth_service
from cor_pass.services.email import (
    send_email_code,
    send_email_code_forgot_password,
)
from cor_pass.services.cipher import decrypt_data, decrypt_user_key, encrypt_data
from cor_pass.config.config import settings
from cor_pass.services.logger import logger
from cor_pass.services import cor_otp
from fastapi import UploadFile

from collections import defaultdict
from datetime import datetime, timedelta

auth_attempts = defaultdict(list)
blocked_ips = {}


router = APIRouter(prefix="/auth", tags=["Authorization"])
security = HTTPBearer()
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm


@router.post(
    "/signup", response_model=ResponseUser, status_code=status.HTTP_201_CREATED
)
async def signup(
    body: UserModel,
    db: Session = Depends(get_db),
):
    """
    **The signup function creates a new user in the database. / Регистрация нового юзера**\n
        It takes an email and password as input, hashes the password, and stores it in the database.
        If there is already a user with that email address, it returns an error message.

    :param body: UserModel: Get the data from the request body
    :param db: Session: Pass the database session to the function
    :return: A dict, but the function expects a usermodel
    """
    exist_user = await repository_person.get_user_by_email(body.email, db)
    if exist_user:
        logger.debug(f"{body.email} user already exist")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Account already exists"
        )
    body.password = auth_service.get_password_hash(body.password)
    new_user = await repository_person.create_user(body, db)
    if not new_user.cor_id:
        await repository_cor_id.create_corid(new_user, db)
    logger.debug(f"{body.email} user successfully created")
    return {"user": new_user, "detail": "User successfully created"}


@router.post(
    "/login",
    response_model=LoginResponseModel,
)
async def login(
    request: Request,
    body: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    **The login function is used to authenticate a user. / Логин пользователя**\n

    :param body: OAuth2PasswordRequestForm: Get the username and password from the request body
    :param db: Session: Get the database session
    :return: A dictionary with the access_token, refresh_token and token type
    """
    user = await repository_person.get_user_by_email(body.username, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found / invalid email",
        )
    if not auth_service.verify_password(body.password, user.password):
        client_ip = request.client.host
        auth_attempts[client_ip].append(datetime.now())

        if client_ip in blocked_ips and blocked_ips[client_ip] > datetime.now():
            print(f"IP-адрес {client_ip} заблокирован")
            raise HTTPException(status_code=429, detail="IP-адрес заблокирован")

        if len(auth_attempts[client_ip]) >= 5 and auth_attempts[client_ip][
            -1
        ] - auth_attempts[client_ip][0] <= timedelta(minutes=15):

            blocked_ips[client_ip] = datetime.now() + timedelta(minutes=15)
            print(
                f"Слишком много попыток авторизации, IP-адрес {client_ip} заблокирован на 15 минут"
            )
            raise HTTPException(
                status_code=429,
                detail="Слишком много попыток авторизации, IP-адрес заблокирован на 15 минут",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password"
        )
    access_token = await auth_service.create_access_token(
        data={"oid": user.cor_id}, expires_delta=3600
    )
    refresh_token = await auth_service.create_refresh_token(data={"oid": user.cor_id})
    await repository_person.update_token(user, refresh_token, db)
    logger.info("login success")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.get(
    "/refresh_token",
    response_model=TokenModel,
)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db),
):
    """
    **The refresh_token function is used to refresh the access token. / Маршрут для рефреш токена, обновление токенов по рефрешу **\n
    It takes in a refresh token and returns an access_token, a new refresh_token, and the type of token (bearer).


    :param credentials: HTTPAuthorizationCredentials: Get the credentials from the request header
    :param db: Session: Pass the database session to the function
    :return: A new access token and a new refresh token
    """
    token = credentials.credentials
    # id = await auth_service.decode_refresh_token(token)
    # user = await repository_person.get_user_by_uuid(id, db)
    cor_id = await auth_service.decode_refresh_token(token)
    user = await repository_person.get_user_by_corid(cor_id, db)
    if user.refresh_token != token:
        await repository_person.update_token(user, None, db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    access_token = await auth_service.create_access_token(data={"oid": user.cor_id})
    refresh_token = await auth_service.create_refresh_token(data={"oid": user.cor_id})
    user.refresh_token = refresh_token
    db.commit()
    await repository_person.update_token(user, refresh_token, db)
    logger.debug(f"{user.email}'s refresh token updated")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post(
    "/send_verification_code"
)  # Маршрут проверки почты в случае если это новая регистрация
async def send_verification_code(
    body: EmailSchema,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    **Отправка кода верификации на почту (проверка почты)** \n

    """
    verification_code = randint(100000, 999999)

    exist_user = await repository_person.get_user_by_email(body.email, db)
    if exist_user:

        logger.debug(f"{body.email}Account already exists")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already exists",
        )

    if exist_user == None:
        background_tasks.add_task(
            send_email_code, body.email, request.base_url, verification_code
        )
        logger.debug("Check your email for verification code.")
        await repository_person.write_verification_code(
            email=body.email, db=db, verification_code=verification_code
        )

    return {"message": "Check your email for verification code."}


@router.post("/confirm_email")
async def confirm_email(body: VerificationModel, db: Session = Depends(get_db)):
    """
    **Проверка кода верификации почты** \n

    """

    ver_code = await repository_person.verify_verification_code(
        body.email, db, body.verification_code
    )
    confirmation = False
    if ver_code:
        confirmation = True
        logger.debug(f"Your {body.email} is confirmed")
        return {
            "message": "Your email is confirmed",  # Сообщение для JS о том что имейл подтвержден
            "confirmation": confirmation,
        }
    else:
        logger.debug(f"{body.email} - Invalid verification code")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification code"
        )


@router.post("/forgot_password")
async def forgot_password_send_verification_code(
    body: EmailSchema,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    **Отправка кода верификации на почту в случае если забыли пароль (проверка почты)** \n
    """

    verification_code = randint(100000, 999999)
    exist_user = await repository_person.get_user_by_email(body.email, db)
    if exist_user == None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if exist_user:
        background_tasks.add_task(
            send_email_code_forgot_password,
            body.email,
            request.base_url,
            verification_code,
        )
        await repository_person.write_verification_code(
            email=body.email, db=db, verification_code=verification_code
        )
        logger.debug(f"{body.email} - Check your email for verification code.")
    return {"message": "Check your email for verification code."}


@router.post("/restore_account_by_text")
async def restore_account_by_text(
    body: RecoveryCodeModel, db: Session = Depends(get_db)
):
    """
    **Проверка кода восстановления с помощью текста**\n
    """
    user = await repository_person.get_user_by_email(body.email, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found / invalid email",
        )
    user.recovery_code = await decrypt_data(
        encrypted_data=user.recovery_code,
        key=await decrypt_user_key(user.unique_cipher_key),
    )
    if not user.recovery_code == body.recovery_code:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid recovery code"
        )
    confirmation = False
    if user.recovery_code == body.recovery_code:
        confirmation = True
        # logger.debug(f"Recovery code is correct")
        # return {
        #     "message": "Recovery code is correct",  # Сообщение для JS о том что код востановления верный
        #     "confirmation": confirmation,
        # }
        user.recovery_code = await encrypt_data(
            data=user.recovery_code, key=await decrypt_user_key(user.unique_cipher_key)
        )
        access_token = await auth_service.create_access_token(
            data={"oid": user.cor_id}, expires_delta=3600
        )
        refresh_token = await auth_service.create_refresh_token(
            data={"oid": user.cor_id}
        )
        await repository_person.update_token(user, refresh_token, db)
        logger.debug(f"{user.email}  login success")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "message": "Recovery code is correct",  # Сообщение для JS о том что код востановления верный
            "confirmation": confirmation,
        }
    else:
        logger.debug(f"{body.email} - Invalid recovery code")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid recovery code"
        )


@router.post("/restore_account_by_recovery_file")
async def upload_recovery_file(
    file: UploadFile = File(...),
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    **Загрузка и проверка файла восстановления**\n
    """
    user = await repository_person.get_user_by_email(email, db)
    confirmation = False
    file_content = await file.read()

    recovery_code = await decrypt_data(
        encrypted_data=user.recovery_code,
        key=await decrypt_user_key(user.unique_cipher_key),
    )

    if file_content == recovery_code.encode():
        confirmation = True
        # logger.debug(f"Restoration code is correct")
        # return {
        #     "message": "Recovery file is correct",  # Сообщение для JS о том что файл востановления верный
        #     "confirmation": confirmation,
        # }
        recovery_code = await encrypt_data(
            data=user.recovery_code, key=await decrypt_user_key(user.unique_cipher_key)
        )
        access_token = await auth_service.create_access_token(
            data={"oid": user.cor_id}, expires_delta=3600
        )
        refresh_token = await auth_service.create_refresh_token(
            data={"oid": user.cor_id}
        )
        await repository_person.update_token(user, refresh_token, db)
        logger.debug(f"{user.email}  login success")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "message": "Recovery file is correct",  # Сообщение для JS о том что файл востановления верный
            "confirmation": confirmation,
        }
    else:
        logger.debug(f"{email} - Invalid recovery code")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid recovery code"
        )
