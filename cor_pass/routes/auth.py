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
from fastapi_limiter.depends import RateLimiter
from cor_pass.database.db import get_db
from cor_pass.schemas import (
    ConfirmLoginRequest,
    ConfirmLoginResponse,
    InitiateLoginRequest,
    InitiateLoginResponse,
    SessionLoginStatus,
    UserModel,
    ResponseUser,
    TokenModel,
    EmailSchema,
    VerificationModel,
    ChangePasswordModel,
    LoginResponseModel,
    RecoveryCodeModel,
    UserSessionDBModel,
    UserSessionModel,
)
from cor_pass.database.models import User, UserSession
from cor_pass.repository import person as repository_person
from cor_pass.repository import user_session as repository_session
from cor_pass.repository import cor_id as repository_cor_id
from cor_pass.services.auth import auth_service
from cor_pass.services import device_info as di
from cor_pass.services.email import (
    send_email_code,
    send_email_code_forgot_password,
)
from cor_pass.services.cipher import decrypt_data, decrypt_user_key, encrypt_data
from cor_pass.config.config import settings
from cor_pass.services.access import user_access
from cor_pass.services.logger import logger
from cor_pass.services import cor_otp
from fastapi import UploadFile

from collections import defaultdict
from datetime import datetime, timedelta
import re

from cor_pass.services.websocket import send_websocket_message

from sqlalchemy.ext.asyncio import AsyncSession


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
    db: AsyncSession = Depends(get_db),
):
    """
    **The signup function creates a new user in the database. / Регистрация нового юзера**\n
        It takes an email and password as input, hashes the password, and stores it in the database.
        If there is already a user with that email address, it returns an error message.

    :param body: UserModel: Get the data from the request body
    :param db: AsyncSession: Pass the database session to the function
    :return: A ResponseUser object
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
        await repository_cor_id.create_new_corid(new_user, db)
    logger.debug(f"{body.email} user successfully created")
    return ResponseUser(user=new_user, detail="User successfully created")


@router.post(
    "/login",
    response_model=LoginResponseModel,
)
async def login(
    request: Request,
    body: OAuth2PasswordRequestForm = Depends(),
    device_info: dict = Depends(di.get_device_header),
    db: AsyncSession = Depends(get_db),
):
    """
    **The login function is used to authenticate a user. / Логин пользователя**\n

    :param body: OAuth2PasswordRequestForm: Get the username and password from the request body
    :param db: AsyncSession: Get the database session
    :return: A dictionary with the access_token, refresh_token, token type, is_admin and session_id
    """
    client_ip = request.client.host
    if client_ip not in auth_attempts:
        auth_attempts[client_ip] = []

    # Получаем пользователя по email
    user = await repository_person.get_user_by_email(body.username, db)
    if user is None:
        logger.warning(
            f"Неудачная попытка входа для пользователя {body.username} с IP {client_ip}: Пользователь не найден"
        )
        auth_attempts[client_ip].append(datetime.now())
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found / invalid email",
        )

    # Проверяем пароль
    if not auth_service.verify_password(body.password, user.password):
        logger.warning(
            f"Неудачная попытка входа для пользователя {body.username} с IP {client_ip}: Неверный пароль"
        )
        auth_attempts[client_ip].append(datetime.now())

        if client_ip in blocked_ips and blocked_ips[client_ip] > datetime.now():
            logger.warning(
                f"IP-адрес {client_ip} заблокирован до {blocked_ips[client_ip]}"
            )
            raise HTTPException(
                status_code=429,
                detail=f"IP-адрес заблокирован до {blocked_ips[client_ip]}",
            )

        if len(auth_attempts[client_ip]) >= 15 and auth_attempts[client_ip][
            -1
        ] - auth_attempts[client_ip][0] <= timedelta(minutes=15):
            block_until = datetime.now() + timedelta(minutes=15)
            blocked_ips[client_ip] = block_until
            logger.warning(
                f"Слишком много попыток авторизации с IP-адреса {client_ip}. Блокировка до {block_until}"
            )
            raise HTTPException(
                status_code=429,
                detail=f"Слишком много попыток авторизации. IP-адрес заблокирован до {block_until}",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password"
        )
    else:
        # Успешная авторизация, сбрасываем счетчик попыток
        if client_ip in auth_attempts:
            del auth_attempts[client_ip]

    # Получаем информацию об устройстве
    device_information = di.get_device_info(request)

    # Если устройство мобильное, проверяем, есть ли у пользователя сессии на этом устройстве
    if device_information["device_type"] == "Mobile":
        existing_sessions = await repository_session.get_user_sessions_by_device_info(
            user.cor_id, device_information["device_info"], db
        )
        if not existing_sessions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нужен ввод мастер-ключа",
            )

    # Создаём токены
    if user.email in settings.eternal_accounts:
        access_token = await auth_service.create_access_token(
            data={"oid": str(user.id), "corid": user.cor_id},
            expires_delta=settings.eternal_token_expiration,
        )
        refresh_token = await auth_service.create_refresh_token(
            data={"oid": str(user.id), "corid": user.cor_id},
            expires_delta=settings.eternal_token_expiration,
        )
    else:
        access_token = await auth_service.create_access_token(
            data={"oid": str(user.id), "corid": user.cor_id}
        )
        refresh_token = await auth_service.create_refresh_token(
            data={"oid": str(user.id), "corid": user.cor_id}
        )

    # Создаём новую сессию
    session_data = {
        "user_id": user.cor_id,
        "refresh_token": refresh_token,
        "device_type": device_information["device_type"],  # Тип устройства
        "device_info": device_information["device_info"],  # Информация об устройстве
        "ip_address": device_information["ip_address"],  # IP-адрес
        "device_os": device_information["device_os"],  # Операционная система
    }
    new_session = await repository_session.create_user_session(
        body=UserSessionModel(**session_data),  # Передаём данные для сессии
        user=user,
        db=db,
    )

    # Проверяем, является ли пользователь администратором
    is_admin = user.email in settings.admin_accounts

    # Логируем успешный вход
    logger.info(
        f"Успешный вход пользователя {user.email} с IP {client_ip} и устройства {device_information.get('device_info')}"
    )
    logger.info(f"is_admin - {is_admin}")

    # Возвращаем ответ
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "is_admin": is_admin,
        "session_id": str(
            new_session.id
        ),  # Добавляем ID сессии в ответ (преобразуем UUID в str)
    }


@router.post(
    "/v1/initiate-login",
    response_model=InitiateLoginResponse,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
)
async def initiate_login(
    request: InitiateLoginRequest, db: AsyncSession = Depends(get_db)
):
    """
    Инициирует процесс входа пользователя через Cor-ID.
    Получает email и/или cor-id, генерирует session_token и сохраняет информацию о сессии CorIdAuthSession.
    """

    session_token = await repository_session.create_auth_session(request, db)

    return {"session_token": session_token}


@router.post(
    "/v1/confirm-login",
    response_model=ConfirmLoginResponse,
    dependencies=[Depends(user_access)],
)
async def confirm_login(
    request: ConfirmLoginRequest, db: AsyncSession = Depends(get_db)
):
    """
    Подтверждает или отклоняет запрос на вход от Cor-ID.
    Получает email и/или cor-id, session_token и статус, обновляет сессию и отправляет результат через WebSocket.
    Требует авторизацию
    """
    email = request.email
    cor_id = request.cor_id
    session_token = request.session_token
    confirmation_status = request.status.lower()

    db_session = await repository_session.get_auth_session(session_token, db)

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сессия не найдена или истекла",
        )

    if email and db_session.email != email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный email для данной сессии",
        )

    elif cor_id and db_session.cor_id != cor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный cor_id для данной сессии",
        )

    if confirmation_status == SessionLoginStatus.approved.value.lower():
        await repository_session.update_session_status(
            db_session, confirmation_status, db
        )
        # Получаем пользователя по email
        user = await repository_person.get_user_by_email(db_session.email, db)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found / invalid email",
            )
        # Получаем токены
        token_data = {"oid": str(user.id), "corid": user.cor_id}
        expires_delta = (
            settings.eternal_token_expiration
            if user.email in settings.eternal_accounts
            else None
        )

        access_token = await auth_service.create_access_token(
            data=token_data, expires_delta=expires_delta
        )
        refresh_token = await auth_service.create_refresh_token(
            data=token_data, expires_delta=expires_delta
        )

        await send_websocket_message(
            session_token,
            {
                "status": "approved",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
            },
        )
        return {"message": "Вход успешно подтвержден"}

    elif confirmation_status == SessionLoginStatus.rejected.value.lower():
        await repository_session.update_session_status(
            db_session, confirmation_status, db
        )
        await send_websocket_message(session_token, {"status": "rejected"})
        return {"message": "Вход отменен пользователем"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный статус подтверждения",
        )


@router.get(
    "/refresh_token",
    response_model=TokenModel,
)
async def refresh_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db),
    device_info: dict = Depends(di.get_device_header),
):
    """
    **The refresh_token function is used to refresh the access token. / Маршрут для рефреш токена, обновление токенов по рефрешу **\n
    It takes in a refresh token and returns an access_token, a new refresh_token, and the type of token (bearer).


    :param credentials: HTTPAuthorizationCredentials: Get the credentials from the request header
    :param db: AsyncSession: Pass the database session to the function
    :return: A new access token and a new refresh token
    """
    token = credentials.credentials
    user_id = await auth_service.decode_refresh_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    user = await repository_person.get_user_by_uuid(user_id, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Получаем информацию об устройстве
    device_information = di.get_device_info(request)
    # Если устройство мобильное, проверяем, есть ли у пользователя сессии на этом устройстве
    existing_sessions = await repository_session.get_user_sessions_by_device_info(
        user.cor_id, device_information["device_info"], db
    )
    is_valid_session = False
    if device_information["device_type"] == "Mobile":
        if not existing_sessions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нужен ввод мастер-ключа",
            )
        for session in existing_sessions:
            try:
                session_token = await decrypt_data(
                    encrypted_data=session.refresh_token,
                    key=await decrypt_user_key(user.unique_cipher_key),
                )
                if session_token == token:
                    is_valid_session = True
                    break
            except Exception:
                logger.warning(
                    f"Failed to decrypt refresh token for session {session.id}"
                )
        if not is_valid_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token for this device",
            )
    elif existing_sessions:
        # For non-mobile, we might just check if any session exists for the device
        is_valid_session = True

    if not is_valid_session and device_information["device_type"] != "Mobile":
        logger.warning(
            f"No active session found for user {user.email} on device {device_information.get('device_info')}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="No active session found"
        )

    if user.email in settings.eternal_accounts:
        access_token = await auth_service.create_access_token(
            data={"oid": str(user.id), "corid": user.cor_id},
            expires_delta=settings.eternal_token_expiration,
        )
        refresh_token = await auth_service.create_refresh_token(
            data={"oid": str(user.id), "corid": user.cor_id},
            expires_delta=settings.eternal_token_expiration,
        )
    else:
        access_token = await auth_service.create_access_token(
            data={"oid": str(user.id), "corid": user.cor_id}
        )
        refresh_token = await auth_service.create_refresh_token(
            data={"oid": str(user.id), "corid": user.cor_id}
        )

    await repository_session.update_session_token(
        user, refresh_token, device_information["device_info"], db
    )
    logger.debug(
        f"{user.email}'s refresh token updated for device {device_information.get('device_info')}"
    )
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
    db: AsyncSession = Depends(get_db),
):
    """
    **Отправка кода верификации на почту (проверка почты)** \n

    """
    verification_code = randint(100000, 999999)

    exist_user = await repository_person.get_user_by_email(body.email, db)
    if exist_user:
        logger.debug(f"{body.email} Account already exists")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already exists",
        )

    if not exist_user:
        background_tasks.add_task(
            send_email_code, body.email, request.base_url, verification_code
        )
        logger.debug("Check your email for verification code.")
        await repository_person.write_verification_code(
            email=body.email, db=db, verification_code=verification_code
        )

    return {"message": "Check your email for verification code."}


@router.post("/confirm_email")
async def confirm_email(body: VerificationModel, db: AsyncSession = Depends(get_db)):
    """
    **Проверка кода верификации почты** \n

    """

    ver_code = await repository_person.verify_verification_code(
        body.email, db, body.verification_code
    )
    confirmation = False
    access_token = None
    exist_user = await repository_person.get_user_by_email(body.email, db)

    if ver_code:
        confirmation = True
        logger.debug(f"Your {body.email} is confirmed")
        if exist_user:
            access_token = await auth_service.create_access_token(
                data={"oid": str(exist_user.id), "corid": exist_user.cor_id}
            )
        return {
            "message": "Your email is confirmed",
            "detail": "Confirmation success",  # Сообщение для JS о том что имейл подтвержден
            "confirmation": confirmation,
            "access_token": access_token,
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
    db: AsyncSession = Depends(get_db),
):
    """
    **Отправка кода верификации на почту в случае если забыли пароль (проверка почты)** \n
    """

    verification_code = randint(100000, 999999)
    exist_user = await repository_person.get_user_by_email(body.email, db)
    if not exist_user:
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
    body: RecoveryCodeModel,
    request: Request,
    device_info: dict = Depends(
        di.get_device_header
    ),  # Добавляем request для получения User-Agent
    db: AsyncSession = Depends(get_db),
):
    """
    **Проверка кода восстановления с помощью текста**\n
    """
    # Получаем пользователя по email
    user = await repository_person.get_user_by_email(body.email, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found / invalid email",
        )

    # Расшифровываем recovery_code
    try:
        decrypted_recovery_code = await decrypt_data(
            encrypted_data=user.recovery_code,
            key=await decrypt_user_key(user.unique_cipher_key),
        )
    except Exception:
        logger.warning(f"Failed to decrypt recovery code for user {body.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid recovery code format",
        )

    # Проверяем recovery_code
    if decrypted_recovery_code != body.recovery_code:
        logger.debug(f"{body.email} - Invalid recovery code")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid recovery code"
        )

    # Если recovery_code верный
    confirmation = True
    user.recovery_code = await encrypt_data(
        data=body.recovery_code, key=await decrypt_user_key(user.unique_cipher_key)
    )
    await db.commit()  # Commit the change to recovery_code

    # Создаём токены
    access_token = await auth_service.create_access_token(
        data={"oid": str(user.id), "corid": user.cor_id}, expires_delta=3600
    )
    refresh_token = await auth_service.create_refresh_token(
        data={"oid": str(user.id), "corid": user.cor_id}
    )

    # Создаём новую сессию
    device_information = di.get_device_info(request)
    session_data = {
        "user_id": user.cor_id,
        "refresh_token": refresh_token,
        "device_type": device_information["device_type"],  # Тип устройства
        "device_info": device_information["device_info"],  # Информация об устройстве
        "ip_address": device_information["ip_address"],  # IP-адрес
        "device_os": device_information["device_os"],  # Операционная система
    }
    new_session = await repository_session.create_user_session(
        body=UserSession(**session_data),  # Передаём данные для сессии
        user=user,
        db=db,
    )

    # Логируем успешный вход
    logger.debug(f"{user.email} login success via recovery code")

    # Возвращаем ответ
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "message": "Recovery code is correct",  # Сообщение для JS о том что код восстановления верный
        "confirmation": confirmation,
        "session_id": str(new_session.id),  # Добавляем ID сессии в ответ
    }


@router.post("/restore_account_by_recovery_file")
async def upload_recovery_file(
    request: Request,
    file: UploadFile = File(...),
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
    device_info: dict = Depends(di.get_device_header),
):
    """
    **Загрузка и проверка файла восстановления**\n
    """
    user = await repository_person.get_user_by_email(email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    confirmation = False
    file_content = await file.read()

    try:
        recovery_code = await decrypt_data(
            encrypted_data=user.recovery_code,
            key=await decrypt_user_key(user.unique_cipher_key),
        )
    except Exception:
        logger.warning(f"Failed to decrypt recovery code for user {email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid recovery code format",
        )

    if file_content == recovery_code.encode():
        confirmation = True
        recovery_code = await encrypt_data(
            data=recovery_code, key=await decrypt_user_key(user.unique_cipher_key)
        )
        await db.commit()

        access_token = await auth_service.create_access_token(
            data={"oid": str(user.id), "corid": user.cor_id}, expires_delta=3600
        )
        refresh_token = await auth_service.create_refresh_token(
            data={"oid": str(user.id), "corid": user.cor_id}
        )
        # Создаём новую сессию
        device_information = di.get_device_info(request)
        session_data = {
            "user_id": user.cor_id,
            "refresh_token": refresh_token,
            "device_type": device_information["device_type"],  # Тип устройства
            "device_info": device_information[
                "device_info"
            ],  # Информация об устройстве
            "ip_address": device_information["ip_address"],  # IP-адрес
            "device_os": device_information["device_os"],  # Операционная система
        }
        new_session = await repository_session.create_user_session(
            body=UserSession(**session_data),  # Передаём данные для сессии
            user=user,
            db=db,
        )
        logger.debug(f"{user.email} login success via recovery file")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "message": "Recovery file is correct",  # Сообщение для JS о том что файл востановления верный
            "confirmation": confirmation,
            "session_id": str(new_session.id),  # Добавляем ID сессии в ответ
        }
    else:
        logger.debug(f"{email} - Invalid recovery file")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid recovery file"
        )
