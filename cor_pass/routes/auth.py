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
from random import randint
from fastapi_limiter.depends import RateLimiter
from cor_pass.database.db import get_db
from cor_pass.schemas import (
    CheckSessionRequest,
    ConfirmCheckSessionResponse,
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
    LoginResponseModel,
    RecoveryCodeModel,
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
from loguru import logger
from fastapi import UploadFile

from collections import defaultdict
from datetime import datetime, timedelta

from cor_pass.services.websocket import send_websocket_message

from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError
from cor_pass.database.redis_db import redis_client
import time

# auth_attempts = defaultdict(list)
# blocked_ips = {}

# Константы для Redis ключей и порогов
IP_ATTEMPTS_PREFIX = "login:ip_attempts:"
IP_BLOCKED_PREFIX = "login:ip_blocked:"
MAX_ATTEMPTS_PER_IP = 15
BLOCK_DURATION_SECONDS = 15 * 60  # 15 минут в секундах


router = APIRouter(prefix="/auth", tags=["Authorization"])
security = HTTPBearer()
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm


@router.post(
    "/signup",
    response_model=ResponseUser,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
)
async def signup(
    body: UserModel,
    request: Request,
    db: AsyncSession = Depends(get_db),
    device_info: dict = Depends(di.get_device_header),
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

    # Проверка ролей
    user_roles = await repository_person.get_user_roles(email=body.email, db=db)

    # Создаём токены
    access_token, access_token_jti = await auth_service.create_access_token(
        data={"oid": str(new_user.id), "corid": new_user.cor_id, "roles": user_roles}
    )
    refresh_token = await auth_service.create_refresh_token(
        data={"oid": str(new_user.id), "corid": new_user.cor_id, "roles": user_roles}
    )

    # Создаём новую сессию
    device_information = di.get_device_info(request)
    session_data = {
        "user_id": new_user.cor_id,
        "refresh_token": refresh_token,
        "device_type": device_information["device_type"],  # Тип устройства
        "device_info": device_information["device_info"],  # Информация об устройстве
        "ip_address": device_information["ip_address"],  # IP-адрес
        "device_os": device_information["device_os"],
        "jti": access_token_jti,
        "access_token": access_token,
    }
    new_session = await repository_session.create_user_session(
        body=UserSession(**session_data),  # Передаём данные для сессии
        user=new_user,
        db=db,
    )
    return ResponseUser(
        user=new_user,
        detail="User successfully created",
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post(
    "/login",
    response_model=LoginResponseModel,
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
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

    blocked_until_str = await redis_client.get(f"{IP_BLOCKED_PREFIX}{client_ip}")
    if blocked_until_str:
        blocked_until_timestamp = float(blocked_until_str)
        if blocked_until_timestamp > time.time():
            block_dt = datetime.fromtimestamp(blocked_until_timestamp)
            logger.warning(f"IP-адрес {client_ip} заблокирован до {block_dt} (Redis).")
            raise HTTPException(
                status_code=429,
                detail=f"IP-адрес заблокирован до {block_dt}",
            )
        else:
            await redis_client.delete(f"{IP_BLOCKED_PREFIX}{client_ip}")

    user = await repository_person.get_user_by_email(body.username, db)

    if user is None or not auth_service.verify_password(body.password, user.password):
        log_message = (
            f"Неудачная попытка входа для пользователя {body.username} с IP {client_ip}: "
            f"{'Пользователь не найден' if user is None else 'Неверный пароль'}"
        )
        logger.warning(log_message)

        current_attempts = await redis_client.incr(f"{IP_ATTEMPTS_PREFIX}{client_ip}")
        if current_attempts == 1:
            await redis_client.expire(
                f"{IP_ATTEMPTS_PREFIX}{client_ip}", BLOCK_DURATION_SECONDS
            )

        if current_attempts >= MAX_ATTEMPTS_PER_IP:
            block_until_timestamp = time.time() + BLOCK_DURATION_SECONDS
            await redis_client.set(
                f"{IP_BLOCKED_PREFIX}{client_ip}",
                str(block_until_timestamp),
                ex=BLOCK_DURATION_SECONDS,
            )
            block_dt = datetime.fromtimestamp(block_until_timestamp)
            logger.warning(
                f"Слишком много попыток авторизации с IP-адреса {client_ip}. Блокировка до {block_dt} (Redis)."
            )
            raise HTTPException(
                status_code=429,
                detail=f"Слишком много попыток авторизации. IP-адрес заблокирован до {block_dt}",
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found / invalid email or password",
        )
    else:
        await redis_client.delete(f"{IP_ATTEMPTS_PREFIX}{client_ip}")
        await redis_client.delete(f"{IP_BLOCKED_PREFIX}{client_ip}")

    # Получаем информацию об устройстве
    device_information = di.get_device_info(request)

    # Если устройство мобильное, проверяем, есть ли у пользователя сессии на этом устройстве
    if (device_information["device_type"] == "Mobile"and body.username not in ["apple-test@cor-software.com", "google-test@cor-software.com"]):
        existing_sessions = await repository_session.get_user_sessions_by_device_info(
            user.cor_id, device_information["device_info"], db
        )
        if not existing_sessions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нужен ввод мастер-ключа",
            )

    # Проверка ролей
    user_roles = await repository_person.get_user_roles(email=user.email, db=db)

    # Получаем токены
    token_data = {"oid": str(user.id), "corid": user.cor_id, "roles": user_roles}
    expires_delta = (
        settings.eternal_token_expiration
        if user.email in settings.eternal_accounts
        else None
    )

    access_token, access_token_jti = await auth_service.create_access_token(
        data=token_data, expires_delta=expires_delta
    )
    refresh_token = await auth_service.create_refresh_token(
        data=token_data, expires_delta=expires_delta
    )

    # Создаём новую сессию
    session_data = {
        "user_id": user.cor_id,
        "refresh_token": refresh_token,
        "device_type": device_information["device_type"],  # Тип устройства
        "device_info": device_information["device_info"],  # Информация об устройстве
        "ip_address": device_information["ip_address"],  # IP-адрес
        "device_os": device_information["device_os"],
        "jti": access_token_jti,
        "access_token": access_token,
    }
    new_session = await repository_session.create_user_session(
        body=UserSessionModel(**session_data),  # Передаём данные для сессии
        user=user,
        db=db,
    )

    logger.debug(
        f"Успешный вход пользователя {user.email} с IP {client_ip} и устройства {device_information.get('device_info')}"
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "session_id": str(new_session.id),
    }


@router.post(
    "/v1/initiate-login",
    response_model=InitiateLoginResponse,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
)
async def initiate_login(
    body: InitiateLoginRequest, db: AsyncSession = Depends(get_db)
):
    """
    Инициирует процесс входа пользователя через Cor-ID.
    Получает email и/или cor-id, генерирует session_token и сохраняет информацию о сессии CorIdAuthSession.
    """

    session_token = await repository_session.create_auth_session(request=body, db=db)

    return {"session_token": session_token}


# вызывается на стороне Кор-енерджи
@router.post(
    "/v1/check_session_status",
    response_model=ConfirmCheckSessionResponse,
    dependencies=[Depends(RateLimiter(times=60, seconds=60))],
)
async def check_session_status(
    body: CheckSessionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    device_info: dict = Depends(di.get_device_header),
):
    """
    Проверка стутуса заявки на вход и возврат токенов в случае её подтверждения
    """
    email = body.email
    email = email.lower()
    cor_id = body.cor_id
    session_token = body.session_token
    db_session = await repository_session.get_auth_approved_session(session_token, db)
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сессия не найдена или отменена пользователем",
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

    user = await repository_person.get_user_by_email(db_session.email, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found / invalid email",
        )
    # Проверка ролей
    user_roles = await repository_person.get_user_roles(email=user.email, db=db)

    # Получаем токены
    token_data = {"oid": str(user.id), "corid": user.cor_id, "roles": user_roles}
    expires_delta = (
        settings.eternal_token_expiration
        if user.email in settings.eternal_accounts
        else None
    )
    access_token, access_token_jti = await auth_service.create_access_token(
        data=token_data, expires_delta=expires_delta
    )
    refresh_token = await auth_service.create_refresh_token(
        data=token_data, expires_delta=expires_delta
    )
    # Создаём новую сессию
    device_information = di.get_device_info(request)
    existing_sessions = await repository_session.get_user_sessions_by_device_info(
        user.cor_id, device_information["device_info"], db
    )
    if not existing_sessions:
        session_data = {
            "user_id": user.cor_id,
            "refresh_token": refresh_token,
            "device_type": "Mobile CorEnergy",  # Тип устройства
            "device_info": device_information[
                "device_info"
            ],  # Информация об устройстве "iOS 18.5 MobileCorEnergy"
            "ip_address": device_information["ip_address"],  # IP-адрес
            "device_os": device_information["device_os"],
            "jti": access_token_jti,
            "access_token": access_token,
        }
        new_session = await repository_session.create_user_session(
            body=UserSession(**session_data),  # Передаём данные для сессии
            user=user,
            db=db,
        )
    else:
        await repository_session.update_session_token(
            user=user,
            token=refresh_token,
            device_info=device_information["device_info"],
            db=db,
            jti=access_token_jti,
            access_token=access_token,
        )
        logger.debug(
            f"{user.email}'s refresh token updated for device {device_information.get('device_info')}"
        )
    response = ConfirmCheckSessionResponse(
        status="approved",
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )
    return response


# вызывается на стороне Кор-айди
@router.post(
    "/v1/confirm-login",
    response_model=ConfirmLoginResponse,
    dependencies=[Depends(user_access)],
)
async def confirm_login(
    request: Request,
    body: ConfirmLoginRequest,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
    device_info: dict = Depends(di.get_device_header),
):
    """
    Подтверждает или отклоняет запрос на вход от Cor-ID.
    Получает email и/или cor-id, session_token и статус, обновляет сессию и отправляет результат через WebSocket.
    Требует авторизацию
    """
    email = body.email
    email = email.lower()
    cor_id = body.cor_id

    if email and current_user.email != email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы не можете подтвердить вход под данным аккаунтом",
        )

    elif cor_id and current_user.cor_id != cor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы не можете подтвердить вход под данным аккаунтом",
        )

    session_token = body.session_token
    confirmation_status = body.status.lower()

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

        # Проверка ролей
        user_roles = await repository_person.get_user_roles(email=user.email, db=db)

        # Получаем токены
        token_data = {"oid": str(user.id), "corid": user.cor_id, "roles": user_roles}
        expires_delta = (
            settings.eternal_token_expiration
            if user.email in settings.eternal_accounts
            else None
        )
        # Временно увеличиваем срок жизни токенов кор-енерджи
        access_token, access_token_jti = await auth_service.create_access_token(
            data=token_data, expires_delta=expires_delta
        )
        refresh_token = await auth_service.create_refresh_token(
            data=token_data, expires_delta=expires_delta
        )

        # Создаём новую сессию
        device_information = di.get_device_info(request)
        session_data = {
            "user_id": user.cor_id,
            "refresh_token": refresh_token,
            "device_type": "Mobile CorEnergy",  # Тип устройства
            "device_info": device_information["device_info"]
            + " MobileCorEnergy",  # Информация об устройстве
            "ip_address": device_information["ip_address"],  # IP-адрес
            "device_os": device_information["device_os"],
            "jti": access_token_jti,
            "access_token": access_token,
        }
        new_session = await repository_session.create_user_session(
            body=UserSession(**session_data),  # Передаём данные для сессии
            user=user,
            db=db,
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


async def get_user_device_rate_limit_key(request: Request) -> str:
    """
    Создает уникальный идентификатор для рейт-лимитера на основе user_id и device_info.
    """
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
            key=auth_service.SECRET_KEY,
            algorithms=auth_service.ALGORITHM,
            options={"verify_exp": False},
        )

        user_id = payload.get("oid")
    except JWTError as e:
        logger.debug(f"Failed to decode token for rate limiter key (JWTError): {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_user_id_from_token_sync: {e}")
        return None
    device_type = request.headers.get("X-Device-Type", "unknown")
    device_info_str = request.headers.get("X-Device-Info", "unknown")
    if user_id:
        return f"user:{user_id}_device_type:{device_type}_device_info:{device_info_str}"
    else:
        user_agent = request.headers.get("User-Agent", "unknown-agent")
        return f"ip:{request.client.host}_ua:{user_agent}"


@router.get(
    "/refresh_token",
    response_model=TokenModel,
    dependencies=[
        Depends(
            RateLimiter(times=1, seconds=5, identifier=get_user_device_rate_limit_key)
        )
    ],
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
    logger.debug(f"Detected device type: {device_information['device_type']}")
    logger.debug(
        f"Detected existing_sessions: {device_information["device_info"]} - {existing_sessions}"
    )
    is_valid_session = False
    if device_information["device_type"] == "Mobile":
        # logger.debug(">>> Entered Mobile validation block <<<")
        if not existing_sessions:
            logger.debug(
                f"existing_sessions for mobile device - {existing_sessions}, need master key"
            )
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
                # logger.debug(f"Comparing tokens: received={token} vs decrypted_session={session_token}")
                if session_token == token:
                    is_valid_session = True
                    logger.debug(f"Mobile session validation is {is_valid_session}")
                    break
            except Exception:
                logger.warning(
                    f"Failed to decrypt refresh token for session {session.id}"
                )

        if not is_valid_session:
            logger.debug(
                f"Invalid refresh token for this mobile device. Mobile session validation is {is_valid_session}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token for this device",
            )
    elif device_information["device_type"] == "Mobile CorEnergy":
        # logger.debug(">>> Entered Mobile CorEnergy validation block <<<")
        if not existing_sessions:
            logger.debug(f"Session not found for this device for cor-energy app")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session not found for this device",
            )
        for session in existing_sessions:
            try:
                session_token = await decrypt_data(
                    encrypted_data=session.refresh_token,
                    key=await decrypt_user_key(user.unique_cipher_key),
                )
                # logger.debug(f"Comparing tokens: received={token} vs decrypted_session={session_token}")
                if session_token == token:
                    is_valid_session = True
                    logger.debug(
                        f"Mobile cor-energy session validation is {is_valid_session}"
                    )
                    break
            except Exception:
                logger.warning(
                    f"Failed to decrypt refresh token for cor-energy session {session.id}"
                )
        if not is_valid_session:
            logger.debug(
                f"Invalid refresh token for this cor-energy mobile device. Mobile session validation is {is_valid_session}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token for this device",
            )
    elif device_information["device_type"] == "MobileCorEnergy":
        # logger.debug(">>> Entered Mobile CorEnergy validation block <<<")
        if not existing_sessions:
            logger.debug(f"Session not found for this device for cor-energy app")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session not found for this device",
            )
        for session in existing_sessions:
            try:
                session_token = await decrypt_data(
                    encrypted_data=session.refresh_token,
                    key=await decrypt_user_key(user.unique_cipher_key),
                )
                # logger.debug(f"Comparing tokens: received={token} vs decrypted_session={session_token}")
                if session_token == token:
                    is_valid_session = True
                    logger.debug(
                        f"Mobile cor-energy session validation is {is_valid_session}"
                    )
                    break
            except Exception:
                logger.warning(
                    f"Failed to decrypt refresh token for cor-energy session {session.id}"
                )
        if not is_valid_session:
            logger.debug(
                f"Invalid refresh token for this cor-energy mobile device. Mobile session validation is {is_valid_session}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token for this device",
            )
    elif device_information["device_type"] == "Desktop":
        # logger.debug(">>> Entered Desktop validation block <<<")
        is_valid_session = True
    if is_valid_session:
        # Проверка ролей
        user_roles = await repository_person.get_user_roles(email=user.email, db=db)

        # Получаем токены
        token_data = {"oid": str(user.id), "corid": user.cor_id, "roles": user_roles}
        expires_delta = (
            settings.eternal_token_expiration
            if user.email in settings.eternal_accounts
            else None
        )

        access_token, access_token_jti = await auth_service.create_access_token(
            data=token_data, expires_delta=expires_delta
        )
        refresh_token = await auth_service.create_refresh_token(
            data=token_data, expires_delta=expires_delta
        )

        await repository_session.update_session_token(
            user=user,
            token=refresh_token,
            device_info=device_information["device_info"],
            db=db,
            jti=access_token_jti,
            access_token=access_token,
        )
        logger.debug(
            f"{user.email}'s refresh token updated for device {device_information.get('device_info')}"
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
    else:
        logger.debug(
            f"Invalid refresh token for this device {device_information["device_type"]} {device_information["device_info"]}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )


@router.get("/verify")
async def verify_access_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db),
):
    """
    **The verify_access_token function is used to verify the access token. / Маршрут для проверки валидности токена доступа **\n

    :param credentials: HTTPAuthorizationCredentials: Get the credentials from the request header
    :param db: AsyncSession: Pass the database session to the function
    :return: JSON message

    """
    token = credentials.credentials
    user = await auth_service.get_current_user(token=token, db=db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token"
        )
    return {"detail": "Token is valid"}


@router.post(
    "/send_verification_code",
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
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


@router.post(
    "/confirm_email", dependencies=[Depends(RateLimiter(times=10, seconds=60))]
)
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
            access_token, jti = await auth_service.create_access_token(
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


@router.post(
    "/forgot_password",
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
)
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


@router.post(
    "/restore_account_by_text",
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
)
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

    # Проверка ролей
    user_roles = await repository_person.get_user_roles(email=user.email, db=db)

    # Получаем токены
    token_data = {"oid": str(user.id), "corid": user.cor_id, "roles": user_roles}
    expires_delta = (
        settings.eternal_token_expiration
        if user.email in settings.eternal_accounts
        else None
    )

    access_token, access_token_jti = await auth_service.create_access_token(
        data=token_data, expires_delta=expires_delta
    )
    refresh_token = await auth_service.create_refresh_token(
        data=token_data, expires_delta=expires_delta
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
        "jti": access_token_jti,
        "access_token": access_token,
    }
    new_session = await repository_session.create_user_session(
        body=UserSession(**session_data),  # Передаём данные для сессии
        user=user,
        db=db,
    )

    logger.debug(f"{user.email} login success via recovery code")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "message": "Recovery code is correct",  # Сообщение для JS о том что код восстановления верный
        "confirmation": confirmation,
        "session_id": str(new_session.id),  # Добавляем ID сессии в ответ
    }


@router.post(
    "/restore_account_by_recovery_file",
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
)
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
    # Проверка ролей
    user_roles = await repository_person.get_user_roles(email=user.email, db=db)

    if file_content == recovery_code.encode():
        confirmation = True
        recovery_code = await encrypt_data(
            data=recovery_code, key=await decrypt_user_key(user.unique_cipher_key)
        )
        await db.commit()

        # Получаем токены
        token_data = {"oid": str(user.id), "corid": user.cor_id, "roles": user_roles}
        expires_delta = (
            settings.eternal_token_expiration
            if user.email in settings.eternal_accounts
            else None
        )
        access_token, access_token_jti = await auth_service.create_access_token(
            data=token_data, expires_delta=expires_delta
        )
        refresh_token = await auth_service.create_refresh_token(
            data=token_data, expires_delta=expires_delta
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
            "jti": access_token_jti,
            "access_token": access_token,
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
