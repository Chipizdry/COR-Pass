"""
COR-ID Authentication API

Этот модуль содержит все endpoints для авторизации и аутентификации пользователей.

================================================================================
ОСНОВНЫЕ ТИПЫ АВТОРИЗАЦИИ
================================================================================

1. ПРЯМАЯ АВТОРИЗАЦИЯ (Direct Auth)
   - Используется: COR-ID приложение, Desktop приложения
   - Endpoints: /signup, /login
   - Требует: email + password
   - Возвращает: токены сразу
   
2. OAuth-LIKE FLOW (Delegated Auth)
   - Используется: Cor-Energy, Cor-Medical
   - Endpoints: /v1/initiate-login → /v1/confirm-login → /v1/check_session_status
   - Требует: подтверждение в COR-ID приложении
   - Возвращает: токены через WebSocket или polling

================================================================================
БЫСТРАЯ НАВИГАЦИЯ
================================================================================

РЕГИСТРАЦИЯ И ВХОД:
  POST /auth/signup                    - Регистрация нового пользователя
  POST /auth/login                     - Вход по email и паролю
  
ПРИГЛАШЕНИЯ ПОЛЬЗОВАТЕЛЕЙ:
  POST /auth/invite                    - Создать приглашение (с автоматической отправкой email)
  POST /auth/validate-invitation       - Проверить токен приглашения
  POST /auth/accept-invitation         - Регистрация по приглашению
  
OAuth-LIKE FLOW (для сторонних приложений):
  POST /auth/v1/initiate-login         - [ШАГ 1] Создать сессию авторизации (мобильные)
  POST /auth/web/initiate-login        - [ШАГ 1] Создать сессию для веб-фронтенда
  POST /auth/v1/confirm-login          - [ШАГ 2] Подтвердить в COR-ID приложении  
  POST /auth/v1/check_session_status   - [ШАГ 3a] Получить токены (polling)

УПРАВЛЕНИЕ ТОКЕНАМИ:
  GET  /auth/refresh_token             - Обновить access и refresh токены
  GET  /auth/verify                    - Проверить валидность access_token
  GET  /auth/verify_session            - Проверить сессию + получить device_id

ВОССТАНОВЛЕНИЕ ДОСТУПА:
  POST /auth/send_verification_code    - Отправить код на email (регистрация)
  POST /auth/confirm_email             - Подтвердить email кодом
  POST /auth/forgot_password           - Отправить код восстановления
  POST /auth/restore_account_by_text   - Восстановить по recovery коду (текст)
  POST /auth/restore_account_by_recovery_file - Восстановить по файлу

================================================================================
СХЕМА OAuth-LIKE FLOW
================================================================================

Сценарий: Пользователь хочет войти в Cor-Energy через COR-ID

1. [Cor-Energy] → POST /v1/initiate-login
   ↓
   Получает: session_token + deep_link
   
2. [Пользователь] Открывает COR-ID приложение (по QR или deep link)
   
3. [COR-ID App] → POST /v1/confirm-login (status="approved")
   ↓
   Отправляет токены через WebSocket
   
4. [Cor-Energy Mobile] → Polling POST /v1/check_session_status
    ↓
    Получает: access_token + refresh_token
    
5. [Приложение] Сохраняет токены и работает с API

================================================================================
БЕЗОПАСНОСТЬ
================================================================================

IP-BASED RATE LIMITING:
  - 15 неудачных попыток логина → блокировка IP на 15 минут
  - Хранится в Redis для работы в кластере
  
DEVICE-BASED SESSIONS:
  - Каждая сессия привязана к device_id
  - Мобильные устройства требуют master key при первом входе
  - Desktop приложения имеют упрощённую проверку
  
TOKEN SECURITY:
  - Access token: короткий срок жизни (1 час)
  - Refresh token: зашифрован в БД
  - JTI (JWT ID) для отзыва токенов
  - Вечные токены только для админов

================================================================================
"""


from uuid import uuid4
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
    RecoveryResponseModel,
    SessionLoginStatus,
    UserModel,
    UserDb,
    ResponseUser,
    EmailSchema,
    VerificationModel,
    LoginResponseModel,
    RecoveryCodeModel,
    UserSessionModel,
    WebInitiateLoginRequest,
    WebInitiateLoginResponse,
    QrScannedRequest,
    UserMeResponse,
    InviteUserRequest,
    InviteUserResponse,
    ValidateInvitationRequest,
    ValidateInvitationResponse,
    AcceptInvitationRequest,
    AcceptInvitationResponse,
)
from cor_pass.database.models import User
from cor_pass.repository.user import person as repository_person
from cor_pass.repository.user import user_session as repository_session
from cor_pass.repository.user import cor_id as repository_cor_id
from cor_pass.repository.user import invitation as repository_invitation
from cor_pass.services.user.auth import auth_service
from cor_pass.services.shared import device_info as di
from cor_pass.services.shared.qr_code import generate_qr_code
from cor_pass.services.shared.email import (
    send_email_code,
    send_email_code_forgot_password,
    send_invitation_email,
)
from cor_pass.services.shared.websocket_events_manager import websocket_events_manager
from cor_pass.services.user.cipher import decrypt_data, decrypt_user_key, encrypt_data
from cor_pass.config.config import settings
from cor_pass.services.shared.access import user_access
from loguru import logger
from fastapi import UploadFile

from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import quote
import base64

from cor_pass.services.shared.websocket import send_websocket_message

from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError
from cor_pass.database.redis_db import redis_client
import time

# ============================================================================
# IP-BASED RATE LIMITING CONFIGURATION
# ============================================================================
# Защита от брутфорс атак на /login endpoint
# Использует Redis для хранения счётчиков и блокировок (работает в кластере)
# ============================================================================

# Префиксы Redis ключей
IP_ATTEMPTS_PREFIX = "login:ip_attempts:"  # Счётчик попыток: login:ip_attempts:192.168.1.1
IP_BLOCKED_PREFIX = "login:ip_blocked:"    # Timestamp блокировки: login:ip_blocked:192.168.1.1

# Пороги блокировки
MAX_ATTEMPTS_PER_IP = 15           # Максимум неудачных попыток с одного IP
BLOCK_DURATION_SECONDS = 15 * 60   # Длительность блокировки: 15 минут

# Логика:
# 1. При неудачном логине → INCR login:ip_attempts:{ip}
# 2. Если счётчик >= 15 → SET login:ip_blocked:{ip} = timestamp + 15 минут
# 3. При успешном логине → DELETE обоих ключей
# 4. TTL на ключах = 15 минут (автоматически удаляются)


router = APIRouter(prefix="/auth", tags=["Authorization"])
security = HTTPBearer()

SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm

# Список тестовых email для ускоренного истечения access токена
# ВАЖНО: для тестовых пользователей сокращаем ТОЛЬКО срок жизни access токена.
# Refresh токен оставляем стандартным, чтобы механизм обновления не ломался.
TEST_EMAILS = [
    "vadym.borshchevskyi.work@gmail.com",
    "o.zhovtenko@cor-int.com"
]
TEST_ACCESS_EXPIRES_DELTA = 1/60  # 1 минута (в часах)


@router.get("/me", response_model=UserMeResponse, summary="Текущий пользователь и роли")
async def get_current_user_profile(
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает данные текущего пользователя и актуальный список ролей.
    
    """
    user_roles = await repository_person.get_user_roles(email=current_user.email, db=db)
    
    # Получаем профиль, если он есть
    first_name = None
    surname = None
    middle_name = None
    
    if current_user.profile:
        try:
            # Расшифровываем данные профиля, если они есть
            user_key = await decrypt_user_key(current_user.unique_cipher_key)
            
            if current_user.profile.encrypted_first_name:
                first_name = await decrypt_data(
                    encrypted_data=current_user.profile.encrypted_first_name,
                    key=user_key
                )
            
            if current_user.profile.encrypted_surname:
                surname = await decrypt_data(
                    encrypted_data=current_user.profile.encrypted_surname,
                    key=user_key
                )
            
            if current_user.profile.encrypted_middle_name:
                middle_name = await decrypt_data(
                    encrypted_data=current_user.profile.encrypted_middle_name,
                    key=user_key
                )
        except Exception as e:
            logger.warning(f"Failed to decrypt profile data for user {current_user.email}: {e}")
    
    return UserMeResponse(
        corid=current_user.cor_id,
        roles=user_roles,
        first_name=first_name,
        surname=surname,
        middle_name=middle_name,
    )



@router.post(
    "/signup",
    response_model=ResponseUser,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
)
async def signup(
    body: UserModel,
    request: Request,
    db: AsyncSession = Depends(get_db),
    device_info: dict = Depends(di.get_device_header),
):
    """
    **Регистрация нового пользователя (прямая регистрация)**
    
    Создаёт новый аккаунт в системе COR-ID. После регистрации пользователь
    автоматически авторизуется и получает токены доступа.
    
    ---
    
    **Использование:**
    - Регистрация в COR-ID мобильном приложении
    - Регистрация в Cor-Energy (если нужен новый аккаунт)
    - Любые приложения экосистемы для создания новых пользователей
    
    ---
    
    **Параметры:**
    - `email` (str) - Email пользователя (уникальный)
    - `password` (str) - Пароль (будет захеширован)
    
    ---
    
    **Возвращает:**
    - `user` - Объект пользователя (без пароля)
    - `access_token` - JWT токен для доступа к API
    - `refresh_token` - JWT токен для обновления access_token
    - `token_type` - Тип токена (всегда "bearer")
    - `device_id` - ID устройства/сессии
    - `detail` - Сообщение об успехе
    
    ---
    
    **Что происходит:**
    1. ✅ Проверяется уникальность email
    2. 🔐 Хешируется пароль (bcrypt)
    3. 👤 Создаётся пользователь в БД
    4. 🆔 Генерируется уникальный COR-ID
    5. 🔑 Генерируются access_token и refresh_token
    6. 💾 Создаётся сессия для текущего устройства
    
    ---
    
    **Безопасность:**
    - Пароль никогда не хранится в открытом виде
    - Rate limit: 10 регистраций в минуту с одного IP
    - Проверка на существующий email
    - Автоматическое создание уникального шифровального ключа пользователя
    
    ---
    
    **Возможные ошибки:**
    - 409 Conflict - Пользователь с таким email уже существует
    - 429 Too Many Requests - Превышен лимит запросов
    
    """
    client_ip = request.client.host
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
    app_id = device_information.get("app_id")
    device_id = device_information.get("device_id")
    legacy_device_info = device_information.get("device_info")
    if not device_id:
        device_id = str(uuid4())
    if not app_id:
        app_id = "unknown app"
    # ---- Создание новой сессии ----
    session_data = {
        "user_id": new_user.cor_id,
        "app_id": app_id,
        "device_id": device_id,
        "device_type": device_information["device_type"],
        "device_info": legacy_device_info,  # для legacy клиентов
        "ip_address": device_information["ip_address"],
        "device_os": device_information["device_os"],
        "jti": access_token_jti,
        "refresh_token": refresh_token,
        "access_token": access_token,
    }
    new_session = await repository_session.create_user_session(
        body=UserSessionModel(**session_data),  # Передаём данные для сессии
        user=new_user,
        db=db,
    )
    logger.debug(
        f"Успешная регистрация пользователя {new_user.email} "
        f"с IP {client_ip}, app_id={app_id}, device_id={device_id}, "
        f"device_info={legacy_device_info}"
    )

    return ResponseUser(
        user=new_user,
        detail="User successfully created",
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        device_id= device_id
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
    **Вход в систему (прямая авторизация)**
    
    Авторизует существующего пользователя по email и паролю.
    Используется для прямого входа в приложения экосистемы.
    
    ---
    
    **Использование:**
    - Вход в COR-ID мобильное приложение
    - Вход в десктоп версию любого приложения
    - Быстрый вход для мобильных приложений (если есть сохранённый master key)
    
    ---
    
    **Параметры:**
    - `username` (str) - Email пользователя (OAuth2 стандарт требует название "username")
    - `password` (str) - Пароль пользователя
    
    ---
    
    **Возвращает:**
    - `access_token` - JWT токен для доступа к API (срок жизни: 1 час)
    - `refresh_token` - JWT токен для обновления access_token
    - `token_type` - Тип токена (всегда "bearer")
    - `session_id` - ID созданной сессии
    - `device_id` - ID устройства для этой сессии
    
    ---
    
    **Безопасность - Защита от брутфорса:**
    
    **IP-based rate limiting через Redis:**
    - Максимум 15 неудачных попыток с одного IP
    - После 15 попыток → IP блокируется на 15 минут
    - Счётчик сбрасывается при успешном входе
    - Блокировки хранятся в Redis для работы в кластере
    
    **Дополнительные проверки для мобильных устройств:**
    - При входе с нового мобильного устройства требуется master key (recovery code)
    - Desktop приложения могут входить без master key
    - Проверяется наличие существующей сессии для device_id
    
    ---
    
    **Что происходит:**
    
    1. 🔍 Проверка блокировки IP адреса
    2. 👤 Поиск пользователя по email
    3. 🔐 Проверка пароля (bcrypt)
    4. 📱 **Для мобильных:** Проверка наличия сессии (master key)
    5. 🔑 Генерация access_token и refresh_token
    6. 💾 Создание новой сессии для устройства
    7. ✅ Сброс счётчика неудачных попыток
    
    ---
    
    **Логика для мобильных устройств:**
    
    ```
    Первый вход с нового устройства:
    └─> Требуется master key (recovery code)
    └─> После ввода создаётся сессия для device_id
    
    Последующие входы с того же устройства:
    └─> Сессия найдена → вход разрешён
    └─> Создаётся новая сессия с новыми токенами
    ```
    
    ---
    
    **Возможные ошибки:**
    
    - **401 Unauthorized** - Неверный email или пароль
    - **429 Too Many Requests** - IP заблокирован (15 неудачных попыток)
      ```json
      {
        "detail": "Слишком много попыток авторизации. IP-адрес заблокирован до 2025-11-13T13:15:00"
      }
      ```
    - **400 Bad Request** - Требуется master key для нового мобильного устройства
      ```json
      {
        "detail": "Нужен ввод мастер-ключа"
      }
      ```
    
    ---
    
    **Интеграция с другими endpoints:**
    
    После получения токенов используйте:
    - `/auth/refresh_token` - Обновление токенов при истечении
    - `/auth/verify` - Проверка валидности access_token
    - `/auth/verify_session` - Проверка сессии и получение device_id
    """
    device_information = di.get_device_info(request)
    client_ip = device_information["ip_address"]

    # ---- Блокировки по IP (rate limit) ----
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
        # успешный логин → сбрасываем счётчики
        await redis_client.delete(f"{IP_ATTEMPTS_PREFIX}{client_ip}")
        await redis_client.delete(f"{IP_BLOCKED_PREFIX}{client_ip}")

    # ---- Информация об устройстве ----
    

    # 🔹 Новое: различаем app_id / device_id
    app_id = device_information.get("app_id")
    device_id = device_information.get("device_id")
    legacy_device_info = device_information.get("device_info")

    # 🔹 Проверка на мобильных устройствах (master key)
    if (
        device_information["device_type"] == "Mobile"
        and body.username not in ["apple-test@cor-software.com", "google-test@cor-software.com"]
    ):
        if app_id and device_id:
            existing_sessions = await repository_session.get_user_sessions_by_device(
                user.cor_id,
                db=db,
                app_id=device_information["app_id"],
                device_id=device_information["device_id"],
                device_info=device_information["device_info"]
            )
        else:
            # fallback для старых клиентов
            existing_sessions = await repository_session.get_user_sessions_by_device_info(
                user.cor_id, legacy_device_info, db
            )

        if not existing_sessions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нужен ввод мастер-ключа",
            )

    # ---- Роли ----
    user_roles = await repository_person.get_user_roles(email=user.email, db=db)

    # ---- Генерация токенов ----
    token_data = {"oid": str(user.id), "corid": user.cor_id, "roles": user_roles}

    # Тестовые аккаунты: сокращаем только access, refresh оставляем стандартным
    if user.email in TEST_EMAILS:
        access_expires_delta = TEST_ACCESS_EXPIRES_DELTA
        refresh_expires_delta = None
    else:
        base_expires = (
            settings.eternal_token_expiration
            if user.email in settings.eternal_accounts
            else None
        )
        access_expires_delta = base_expires
        refresh_expires_delta = base_expires

    access_token, access_token_jti = await auth_service.create_access_token(
        data=token_data, expires_delta=access_expires_delta
    )
    refresh_token = await auth_service.create_refresh_token(
        data=token_data, expires_delta=refresh_expires_delta
    )

    if not device_id:
        device_id = str(uuid4())
    # ---- Создание новой сессии ----
    session_data = {
        "user_id": user.cor_id,
        "app_id": app_id,
        "device_id": device_id,
        "device_type": device_information["device_type"],
        "device_info": legacy_device_info,  # для legacy клиентов
        "ip_address": device_information["ip_address"],
        "device_os": device_information["device_os"],
        "jti": access_token_jti,
        "refresh_token": refresh_token,
        "access_token": access_token,
    }
    new_session = await repository_session.create_user_session(
        body=UserSessionModel(**session_data),  # Передаём данные для сессии
        user=user,
        db=db,
    )

    logger.debug(
        f"Успешный вход пользователя {user.email} "
        f"с IP {client_ip}, app_id={app_id}, device_id={device_id}, "
        f"device_info={legacy_device_info}"
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "session_id": str(new_session.id),
        "device_id": device_id
    }



# ============================================================================
# OAuth-LIKE AUTHENTICATION FLOW (Login via COR-ID)
# ============================================================================
# Используется внешними приложениями (Cor-Energy, Cor-Medical)
# для авторизации пользователей через COR-ID приложение
#
# FLOW:
# 1. Внешнее приложение → POST /v1/initiate-login → получает session_token + deep_link
# 2. Пользователь открывает COR-ID приложение по deep_link или QR коду
# 3. COR-ID приложение → POST /v1/confirm-login → подтверждает/отклоняет вход
# 4. Мобильное приложение (Cor-Energy) → POST /v1/check_session_status → получает токены
# ============================================================================

@router.post(
    "/v1/initiate-login",
    response_model=InitiateLoginResponse,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
)
async def initiate_login(
    body: InitiateLoginRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    """
    **[ШАГ 1] Инициация входа через COR-ID (OAuth-like flow)**
    
    Создаёт сессию авторизации, которую пользователь должен подтвердить в COR-ID приложении.
    
    ---
    
    **Кто использует:**
    - Cor-Energy (мобильное приложение)
    - Cor-Medical (мобильное приложение)
    - Любые будущие приложения экосистемы
    
    ---
    
    **Параметры:**
    - `email` (Optional[str]) - Email пользователя (если известен)
    - `cor_id` (Optional[str]) - COR ID пользователя (если известен)
    - `app_id` (str) - Идентификатор приложения (например: "cor-energy")
    - `device_id` (str) - Уникальный ID устройства/браузера
    
    **Примечание:** Нужно указать либо `email`, либо `cor_id`, либо оба
    
    ---
    
    **Возвращает:**
    - `session_token` (str) - Уникальный токен сессии для отслеживания статуса
    - `deep_link` (Optional[str]) - Deep link для открытия COR-ID приложения
    - `qr_code` (Optional[str]) - QR код для сканирования в COR-ID приложении
    - `expires_at` (datetime) - Время истечения сессии (обычно 5 минут)
    
    ---

    **Безопасность:**
    - Session token одноразовый (удаляется после получения токенов)
    - Сессия истекает через 5 минут без подтверждения
    - Rate limit: 5 запросов в минуту
    
    """
    device_information = di.get_device_info(request)
    if not body.app_id:
        body.app_id = device_information["app_id"]

    session_token = await repository_session.create_auth_session(request=body, db=db)

    return {"session_token": session_token}


@router.post(
    "/web/initiate-login",
    response_model=WebInitiateLoginResponse,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
)
async def web_initiate_login(
    body: WebInitiateLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    **[ВЕБ-ФРОНТЕНД] Инициация входа через COR-ID приложение**
    
    Создаёт сессию авторизации для входа с веб-сайта через мобильное приложение COR-ID.
    Пользователь вводит email на веб-сайте, получает QR-код или deep link для открытия 
    мобильного приложения и подтверждения входа.
    
    ---
    
    **Безопасность:**
    - Session token одноразовый (удаляется после получения токенов)
    - Сессия истекает через 10 минут без подтверждения
    - Rate limit: 5 запросов в минуту
    - Проверяется существование пользователя с указанным email
    
    ---
    
    **Возможные ошибки:**
    - 404 Not Found - Пользователь с таким email не найден
    - 429 Too Many Requests - Превышен лимит запросов
    """
    # Проверяем существование пользователя
    email = body.email.lower()
    user = await repository_person.get_user_by_email(email, db)
    
    if not user:
        logger.warning(f"Web login attempt for non-existent email: {email}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found with this email address"
        )
    
    # Создаём сессию авторизации
    device_information = di.get_device_info(request)
    
    # Для веб-фронтенда используем app_id = "web"
    initiate_request = InitiateLoginRequest(
        email=email,
        cor_id=user.cor_id,
        app_id="web"
    )
    
    session_token = await repository_session.create_auth_session(
        request=initiate_request,
        db=db
    )
    
    # Генерируем deep link для COR-ID приложения
    encoded_email = quote(email)
    encoded_token = quote(session_token)
    deep_link = f"coridapp://open?email={encoded_email}&sessionToken={encoded_token}"
    
    # Генерируем QR-код из deep link
    qr_code_bytes = generate_qr_code(deep_link)
    qr_code_base64 = base64.b64encode(qr_code_bytes).decode('utf-8')
    qr_code_data_url = f"data:image/png;base64,{qr_code_base64}"
    
    # Время истечения (из create_auth_session - 10 минут)
    expires_at = datetime.now() + timedelta(minutes=10)
    
    logger.info(
        f"Web login session created for {email}: "
        f"session_token={session_token[:8]}..., qr_code_size={len(qr_code_bytes)} bytes, expires_at={expires_at}"
    )
    
    return WebInitiateLoginResponse(
        session_token=session_token,
        deep_link=deep_link,
        qr_code=qr_code_data_url,
        expires_at=expires_at
    )


@router.post(
    "/web/qr-scanned",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
)
async def notify_qr_scanned(
    body: QrScannedRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    **[МОБИЛЬНОЕ ПРИЛОЖЕНИЕ] Уведомление о сканировании QR-кода**
    
    Вызывается COR-ID мобильным приложением сразу после открытия по deep link.
    Отправляет WebSocket событие веб-фронтенду для показа анимации "Ожидание подтверждения".
    
    
    **Параметры:**
    - `session_token` (str) - Токен сессии из deep link (query параметр)
    
    ---
    
    **Безопасность:**
    - Проверяется существование сессии
    - Сессия должна быть в статусе PENDING
    - Rate limit: 10 запросов в минуту
    - WebSocket событие отправляется только для конкретной сессии
    
    ---
    
    **Возможные ошибки:**
    - 404 Not Found - Сессия не найдена или истекла
    - 400 Bad Request - Неверный статус сессии (уже подтверждена/отклонена)
    - 429 Too Many Requests - Превышен rate limit
    """
    session_token = body.session_token
    
    db_session = await repository_session.get_auth_session(session_token, db)
    
    if not db_session:
        logger.warning(f"QR scanned notification for non-existent session: {session_token[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сессия не найдена или истекла"
        )
    

    qr_scanned_event = {
        "event": "qr_scanned",
        "timestamp": datetime.now().isoformat()
    }
    
    await websocket_events_manager.send_to_session(
        session_id=session_token,
        event_data=qr_scanned_event
    )
    
    logger.info(
        f"QR code scanned for session {session_token[:8]}... (email: {db_session.email})"
    )
    
    return {
        "message": "QR scanned notification sent",
        "session_token": session_token
    }


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
    **[ШАГ 3a - для МОБИЛЬНЫХ приложений] Проверка статуса сессии и получение токенов**
    
    Используется мобильными приложениями (Cor-Energy, Cor-Medical) для:
    1. Polling - периодическая проверка подтвердил ли пользователь вход
    2. Получение access_token и refresh_token после подтверждения
    
    ---
    
    **Параметры:**
    - `session_token` (str) - Токен из ответа `/v1/initiate-login`
    - `email` (Optional[str]) - Email для дополнительной проверки
    - `cor_id` (Optional[str]) - COR ID для дополнительной проверки
    
    ---
    
    **Возвращает:**
    
    **Если пользователь ЕЩЁ НЕ подтвердил:**
    - HTTP 404 - "Сессия не найдена или отменена пользователем"
    
    **Если пользователь ПОДТВЕРДИЛ:**
    ```json
    {
      "status": "approved",
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer",
      "device_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    ```
    
    **Если пользователь ОТКЛОНИЛ:**
    - Сессия удаляется, вернётся HTTP 404
    

    ---

    - Rate limit: 60 запросов в минуту (каждые 1-2 секунды polling)
    - Сессия автоматически создаётся в БД для устройства после подтверждения
    
    ---
    
    **Безопасность:**
    - Проверяется соответствие email/cor_id с данными сессии
    - Session token удаляется после использования (в будущем)
    - Создаётся новая сессия с device_id для работы refresh_token
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

    if user.email in TEST_EMAILS:
        access_expires_delta = TEST_ACCESS_EXPIRES_DELTA
        refresh_expires_delta = None
    else:
        base_expires = (
            settings.eternal_token_expiration
            if user.email in settings.eternal_accounts
            else None
        )
        access_expires_delta = base_expires
        refresh_expires_delta = base_expires
    access_token, access_token_jti = await auth_service.create_access_token(
        data=token_data, expires_delta=access_expires_delta
    )
    refresh_token = await auth_service.create_refresh_token(
        data=token_data, expires_delta=refresh_expires_delta
    )
    # Создаём новую сессию
    device_information = di.get_device_info(request)
    existing_sessions = await repository_session.get_user_sessions_by_device(
                user.cor_id,
                db=db,
                app_id=db_session.app_id,
                device_id=db_session.device_id,
                device_info=device_information["device_info"]
            )
    if not existing_sessions:
        session_data = {
            "user_id": user.cor_id,
            "app_id": db_session.app_id,
            "device_id": db_session.device_id,
            "refresh_token": refresh_token,
            "device_type": "Mobile" + f" {db_session.app_id}",  # Тип устройства
            "device_info": device_information["device_info"]
            + f" {db_session.app_id}",  # Информация об устройстве
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
    else:
        await repository_session.update_session_token(
            user=user,
            token=refresh_token,
            device_id=db_session.device_id,
            device_info=device_information["device_info"]
            + f" {db_session.app_id}",
            app_id=db_session.app_id,
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
        device_id=db_session.device_id
    )
    return response


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
    **[ШАГ 2] Подтверждение или отклонение входа в COR-ID приложении**
    
    Вызывается **ТОЛЬКО из COR-ID мобильного приложения** когда пользователь:
    - Сканирует QR код или переходит по deep link
    - Видит запрос на вход от другого приложения (Cor-Energy и т.д.)
    - Нажимает "Подтвердить" или "Отклонить"
    
    ---
    
    **Требования:**
    - Пользователь должен быть авторизован в COR-ID приложении
    - Authorization header с валидным access_token обязателен
    
    ---
    
    **Параметры:**
    - `session_token` (str) - Токен сессии из QR кода или deep link
    - `email` (Optional[str]) - Email пользователя для проверки
    - `cor_id` (Optional[str]) - COR ID пользователя для проверки
    - `status` (SessionLoginStatus) - "approved" или "rejected"
    
    ---
    
    **Что происходит при подтверждении (status="approved"):**
    
    1. ✅ Проверяется что текущий пользователь соответствует запросу
    2. 🔐 Генерируются новые access_token и refresh_token
    3. 💾 Создаётся сессия для устройства внешнего приложения
    4. 📡 Отправляется WebSocket событие с токенами
    5. ✅ Внешнее приложение получает уведомление через WebSocket
    
    **Что происходит при отклонении (status="rejected"):**
    
    1. ❌ Сессия помечается как отклонённая
    2. 📡 Отправляется WebSocket событие об отклонении
    3. ❌ Внешнее приложение показывает ошибку "Вход отклонён"
    
    ---

    **Безопасность:**
    - Требуется валидный access_token авторизованного пользователя
    - Проверяется соответствие email/cor_id текущего пользователя с запросом
    - Session token одноразовый (должен использоваться только один раз)
    - WebSocket события отправляются только для конкретной сессии
    
    ---
    
    **Возможные ошибки:**
    - 401 Unauthorized - Невалидный токен или пользователь не авторизован
    - 400 Bad Request - Неверный email/cor_id для данной сессии
    - 404 Not Found - Сессия не найдена или истекла
    - 400 Bad Request - Неверный статус подтверждения
    
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

        if user.email in TEST_EMAILS:
            access_expires_delta = TEST_ACCESS_EXPIRES_DELTA
            refresh_expires_delta = None
        else:
            base_expires = (
                settings.eternal_token_expiration
                if user.email in settings.eternal_accounts
                else None
            )
            access_expires_delta = base_expires
            refresh_expires_delta = base_expires
        access_token, access_token_jti = await auth_service.create_access_token(
            data=token_data, expires_delta=access_expires_delta
        )
        refresh_token = await auth_service.create_refresh_token(
            data=token_data, expires_delta=refresh_expires_delta
        )

        # Создаём новую сессию
        device_information = di.get_device_info(request)
        session_data = {
            "user_id": user.cor_id,
            "app_id": db_session.app_id,
            "device_id": db_session.device_id,
            "refresh_token": refresh_token,
            "device_type": "Mobile" + f" {db_session.app_id}",  # Тип устройства
            "device_info": device_information["device_info"]
            + f" {db_session.app_id}",  # Информация об устройстве
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
        # await send_websocket_message(
        #     session_token=session_token,message=
        #     {
        #         "status": "approved",
        #         "access_token": access_token,
        #         "refresh_token": refresh_token,
        #         "token_type": "bearer",
        #         "device_id": db_session.device_id,
        #     },
        # )
        data = {
                "status": "approved",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "device_id": db_session.device_id,
            }
        await websocket_events_manager.send_to_session(session_id=session_token, event_data=data)
        return {"message": "Вход успешно подтвержден"}

    elif confirmation_status == SessionLoginStatus.rejected.value.lower():
        await repository_session.update_session_status(
            db_session, confirmation_status, db
        )
        data = {"status": "rejected"}
        #await send_websocket_message(session_token=session_token, message={"status": "rejected"})
        await websocket_events_manager.send_to_session(session_id=session_token, event_data=data)
        return {"message": "Вход отменен пользователем"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный статус подтверждения",
        )


async def get_user_device_rate_limit_key(request: Request) -> str:
    """
    Генерирует уникальный ключ для rate limiting на основе пользователя и устройства.
    
    Используется в /refresh_token для ограничения частоты обновления токенов.
    Каждая комбинация user_id + device_type + device_info имеет свой отдельный лимит.
    
    Формат ключа:
    - Авторизованный: "user:{user_id}_device_type:{Mobile}_device_info:{iOS 17.0}"
    - Неавторизованный: "ip:{192.168.1.1}_ua:{Mozilla/5.0...}"
    
    Почему так:
    - Один пользователь может обновлять токены на разных устройствах одновременно
    - Каждое устройство имеет свой лимит (1 запрос в 5 секунд)
    - Предотвращает злоупотребление refresh endpoint
    
    Args:
        request: FastAPI Request объект с headers
        
    Returns:
        str: Уникальный ключ для rate limiter
        
    Example:
        user:550e8400-e29b-41d4-a716-446655440000_device_type:Mobile_device_info:iOS 17.0
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


@router.get("/refresh_token", response_model=dict,dependencies=[
        Depends(
            RateLimiter(times=1, seconds=5, identifier=get_user_device_rate_limit_key)
        )
    ],)
async def refresh_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db),
    device_info: dict = Depends(di.get_device_header),
):
    """
    **Обновление access и refresh токенов**
    
    Выдаёт новую пару токенов на основе валидного refresh_token.
    Работает ТОЛЬКО если существует активная сессия для данного устройства.
    
    ---
    
    **Когда использовать:**
    - Access token истёк (обычно через 1 час)
    - Приложение запускается и нужно проверить токены
    - Периодическое обновление токенов в фоне
    
    ---
    
    **Требования:**
    - Валидный refresh_token в Authorization header
    - Активная сессия для данного устройства в БД
    - Device headers (X-App-ID, X-Device-ID или X-Device-Info)
    
    ---
    
    **Headers:**
    ```
    Authorization: Bearer <refresh_token>
    X-App-ID: cor-energy (или другой app_id)
    X-Device-ID: 550e8400-e29b-41d4-a716-446655440000
    X-Device-Info: iOS 17.0, iPhone 15 Pro (legacy, для совместимости)
    ```
    
    ---
    
    **Возвращает:**
    - `access_token` - Новый JWT токен для доступа
    - `refresh_token` - Новый JWT refresh токен
    - `token_type` - "bearer"
    - `device_id` - ID устройства (только для мобильных)
    
    ---
    
    **Безопасность:**
    
    **Для мобильных устройств (строгая проверка):**
    1. 🔍 Находится сессия по app_id + device_id
    2. 🔐 Расшифровывается сохранённый refresh_token
    3. ✅ Сравнивается с переданным refresh_token
    4. ❌ Если не совпадает → 401 Unauthorized
    5. ✅ Если совпадает → выдаются новые токены
    
    **Для desktop приложений (упрощённая проверка):**
    1. 🔍 Проверяется наличие сессии
    2. ✅ Выдаются новые токены без проверки старого
    
    ---
    
    **Что происходит:**
    
    1. 🔓 Декодируется refresh_token
    2. 👤 Находится пользователь по user_id из токена
    3. 📱 Находится сессия по device_id
    4. 🔐 **Мобильные:** Проверяется совпадение refresh_token
    5. 🔑 Генерируются новые access_token и refresh_token
    6. 💾 Обновляется сессия в БД (новые токены и JTI)
    7. ✅ Возвращаются новые токены
    
    ---
    
    **Rate limiting:**
    - 1 запрос в 5 секунд **на пользователя + устройство**
    - Уникальный лимит для каждой комбинации user_id + device_id
    - Предотвращает злоупотребление обновлением токенов
    
    ---
    
    **Возможные ошибки:**
    
    - **401 Unauthorized** - Невалидный refresh_token
      ```json
      {"detail": "Invalid refresh token"}
      ```
    
    - **401 Unauthorized** - Сессия не найдена для устройства
      ```json
      {"detail": "Session not found for this device"}
      ```
    
    - **401 Unauthorized** - Refresh token не совпадает (мобильные)
      ```json
      {"detail": "Invalid refresh token for this device"}
      ```
    
    - **404 Not Found** - Пользователь не найден
      ```json
      {"detail": "User not found"}
      ```
    
    - **429 Too Many Requests** - Превышен rate limit
      ```json
      {"detail": "Rate limit exceeded. Try again in 5 seconds"}
      ```
    
    ---
    
    **Логика определения устройства:**
    
    ```python
    # Приоритет определения device_id:
    1. X-Device-ID header (новые клиенты)
    2. X-Device-Info header (legacy клиенты)
    3. Генерация нового UUID (fallback)
    
    # Приоритет определения app_id:
    1. X-App-ID header (cor-energy,  etc.)
    2. "unknown app" (fallback)
    ```
    
    ---
    
    **Связанные endpoints:**
    - `/auth/login` - Получение первичных токенов
    - `/auth/verify` - Проверка валидности access_token
    - `/auth/verify_session` - Проверка сессии с device_id
    """
    token = credentials.credentials
    logger.info(
        f"[REFRESH] START: token_prefix={token[:14] if token else None}, "
        f"X-App-Id={request.headers.get('X-App-Id')}, "
        f"X-Device-Id={request.headers.get('X-Device-Id')}, "
        f"X-Device-Type={request.headers.get('X-Device-Type')}, "
        f"X-Device-Info={request.headers.get('X-Device-Info')}"
    )
    user_id = await auth_service.decode_refresh_token(token)
    if not user_id:
        logger.warning(f"[REFRESH] FAILED: invalid refresh token prefix={token[:14] if token else None}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    logger.debug(f"[REFRESH] Step 1: Token decoded, user_id={user_id}")
    # Получаем пользователя
    user = await repository_person.get_user_by_uuid(user_id, db)
    if not user:
        logger.warning(f"[REFRESH] FAILED: User not found for user_id={user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    logger.debug(f"[REFRESH] Step 2: User found, email={user.email} cor_id={user.cor_id}")
    # Получаем информацию об устройстве
    device_information = di.get_device_info(request)
    logger.debug(
        f"[REFRESH] Step 3: Device info, type={device_information.get('device_type')} "
        f"app_id={device_information.get('app_id')} device_id={device_information.get('device_id')} "
        f"device_info={device_information.get('device_info')} os={device_information.get('device_os')} "
        f"ip={device_information.get('ip_address')}"
    )
    # app_id = device_information.get("app_id")
    # device_id = device_information.get("device_id")
    # legacy_device_info = device_information.get("device_info")

    # Находим сессию по device_id
    session = await repository_session.get_user_sessions_by_device(
                user.cor_id,
                db=db,
                app_id=device_information["app_id"],
                device_id=device_information["device_id"],
                device_info=device_information["device_info"]
            )
    if not session:
        logger.warning(
            f"[REFRESH] FAILED: Session not found, email={user.email} "
            f"app_id={device_information.get('app_id')} device_id={device_information.get('device_id')} "
            f"device_info={device_information.get('device_info')}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found for this device",
        )
    else:
        logger.debug(f"[REFRESH] Step 4: Session found, count={len(session)} session_id={session[0].id if session else None}")
    
    # Проверяем refresh токен
    try:
        session_refresh_token = await decrypt_data(
            encrypted_data=session[0].refresh_token,
            key=await decrypt_user_key(user.unique_cipher_key),
        )
        logger.debug(f"[REFRESH] Step 5: Decrypted stored token, prefix={session_refresh_token[:14]}")
    except Exception:
        logger.warning(f"Failed to decrypt refresh token for session {session[0].id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )


    if device_information["device_type"] == "Desktop":
        logger.debug(f"[REFRESH] Step 6: Desktop branch, device_id={device_information.get('device_id')} app_id={device_information.get('app_id')}")
        user_roles = await repository_person.get_user_roles(email=user.email, db=db)
        token_data = {"oid": str(user.id), "corid": user.cor_id, "roles": user_roles}
        if user.email in TEST_EMAILS:
            access_expires_delta = TEST_ACCESS_EXPIRES_DELTA
            refresh_expires_delta = None
        else:
            base_expires = (
                settings.eternal_token_expiration
                if user.email in settings.eternal_accounts
                else None
            )
            access_expires_delta = base_expires
            refresh_expires_delta = base_expires

        access_token, access_token_jti = await auth_service.create_access_token(
            data=token_data, expires_delta=access_expires_delta
        )
        refresh_token = await auth_service.create_refresh_token(
            data=token_data, expires_delta=refresh_expires_delta
        )

        # Обновляем сессию
        await repository_session.update_session_token(
            user=user,
            token=refresh_token,
            device_id=device_information["device_id"],
            device_info=device_information["device_info"],
            app_id=device_information["app_id"],
            db=db,
            jti=access_token_jti,
            access_token=access_token,
        )
        logger.info(
            f"[REFRESH] SUCCESS (Desktop): email={user.email} "
            f"device_id={device_information.get('device_id')} jti={access_token_jti[:12] if access_token_jti else None}"
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    else:
        if session_refresh_token != token:
            logger.warning(
                f"[REFRESH] FAILED (token mismatch): provided_prefix={token[:14]} "
                f"stored_prefix={session_refresh_token[:14]} email={user.email} "
                f"device_id={device_information.get('device_id')}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token for this device",
            )
        logger.debug(f"[REFRESH] Step 6: Mobile branch, token verified for email={user.email} device_id={device_information.get('device_id')}")
        # Если всё ок → выдаём новые токены
        user_roles = await repository_person.get_user_roles(email=user.email, db=db)
        token_data = {"oid": str(user.id), "corid": user.cor_id, "roles": user_roles}
        if user.email in TEST_EMAILS:
            access_expires_delta = TEST_ACCESS_EXPIRES_DELTA
            refresh_expires_delta = None
        else:
            base_expires = (
                settings.eternal_token_expiration
                if user.email in settings.eternal_accounts
                else None
            )
            access_expires_delta = base_expires
            refresh_expires_delta = base_expires

        access_token, access_token_jti = await auth_service.create_access_token(
            data=token_data, expires_delta=access_expires_delta
        )
        refresh_token = await auth_service.create_refresh_token(
            data=token_data, expires_delta=refresh_expires_delta
        )

        # Обновляем сессию
        session = await repository_session.update_session_token(
            user=user,
            token=refresh_token,
            device_id=device_information["device_id"],
            device_info=device_information["device_info"],
            app_id=device_information["app_id"],
            db=db,
            jti=access_token_jti,
            access_token=access_token,
        )
        logger.info(
            f"[REFRESH] SUCCESS (Mobile): email={user.email} "
            f"device_id={device_information.get('device_id')} jti={access_token_jti[:12] if access_token_jti else None}"
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "device_id": session.device_id
        }



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

@router.get("/verify_session")
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
    decoded_jti = jwt.decode(
    token,
    key="",  
    options={"verify_signature": False, "verify_exp": False}
)
    jti = decoded_jti.get("jti")
    user_session = await repository_session.get_session_by_jti(user=user, db=db, jti=jti)
    return {"detail": "Token is valid",
            "session_id": user_session.device_id}


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
    response_model=RecoveryResponseModel
)
async def restore_account_by_text(
    body: RecoveryCodeModel,
    request: Request,
    device_info: dict = Depends(di.get_device_header),
    db: AsyncSession = Depends(get_db),
):
    """
    **Проверка кода восстановления с помощью текста**\n
    """
    client_ip = request.client.host
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

    if decrypted_recovery_code != body.recovery_code:
        logger.debug(f"{body.email} - Invalid recovery code")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid recovery code"
        )

    confirmation = True
    user.recovery_code = await encrypt_data(
        data=body.recovery_code, key=await decrypt_user_key(user.unique_cipher_key)
    )
    await db.commit()

    # Проверка ролей
    user_roles = await repository_person.get_user_roles(email=user.email, db=db)

    token_data = {"oid": str(user.id), "corid": user.cor_id, "roles": user_roles}

    if user.email in TEST_EMAILS:
        access_expires_delta = TEST_ACCESS_EXPIRES_DELTA
        refresh_expires_delta = None
    else:
        base_expires = (
            settings.eternal_token_expiration
            if user.email in settings.eternal_accounts
            else None
        )
        access_expires_delta = base_expires
        refresh_expires_delta = base_expires

    access_token, access_token_jti = await auth_service.create_access_token(
        data=token_data, expires_delta=access_expires_delta
    )
    refresh_token = await auth_service.create_refresh_token(
        data=token_data, expires_delta=refresh_expires_delta
    )

    # Информация об устройстве
    device_information = di.get_device_info(request)
    app_id = device_information.get("app_id")
    device_id = device_information.get("device_id")
    legacy_device_info = device_information.get("device_info")
    if not device_id:
        # генерируем UUID для старых клиентов
        device_id = str(uuid4())
    if not app_id:
        app_id = "unknown app"

    # ---- Создание новой сессии ----
    session_data = {
        "user_id": user.cor_id,
        "app_id": app_id,
        "device_id": device_id,
        "device_type": device_information["device_type"],
        "device_info": legacy_device_info,  # для legacy клиентов
        "ip_address": device_information["ip_address"],
        "device_os": device_information["device_os"],
        "jti": access_token_jti,
        "refresh_token": refresh_token,
        "access_token": access_token,
    }
    new_session = await repository_session.create_user_session(
        body=UserSessionModel(**session_data),  # Передаём данные для сессии
        user=user,
        db=db,
    )

    logger.debug(
        f"Успешный вход пользователя {user.email} "
        f"с IP {client_ip}, app_id={app_id}, device_id={device_id}, "
        f"device_info={legacy_device_info}"
    )
    response = RecoveryResponseModel(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        message="Recovery code is correct",
        confirmation=confirmation,
        session_id=str(new_session.id),
        device_id=device_id
    )
    return response


@router.post(
    "/restore_account_by_recovery_file",
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
    response_model=RecoveryResponseModel
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
    client_ip = request.client.host
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
        if user.email in TEST_EMAILS:
            access_expires_delta = TEST_ACCESS_EXPIRES_DELTA
            refresh_expires_delta = None
        else:
            base_expires = (
                settings.eternal_token_expiration
                if user.email in settings.eternal_accounts
                else None
            )
            access_expires_delta = base_expires
            refresh_expires_delta = base_expires
        access_token, access_token_jti = await auth_service.create_access_token(
            data=token_data, expires_delta=access_expires_delta
        )
        refresh_token = await auth_service.create_refresh_token(
            data=token_data, expires_delta=refresh_expires_delta
        )
        # Создаём новую сессию
        device_information = di.get_device_info(request)
        app_id = device_information.get("app_id")
        device_id = device_information.get("device_id")
        legacy_device_info = device_information.get("device_info")
        if not device_id:
            device_id = str(uuid4())
        if not app_id:
            app_id = "unknown app"
        session_data = {
        "user_id": user.cor_id,
        "app_id": app_id,
        "device_id": device_id,
        "device_type": device_information["device_type"],
        "device_info": legacy_device_info,  # для legacy клиентов
        "ip_address": device_information["ip_address"],
        "device_os": device_information["device_os"],
        "jti": access_token_jti,
        "refresh_token": refresh_token,
        "access_token": access_token,
    }
        new_session = await repository_session.create_user_session(
            body=UserSessionModel(**session_data),  # Передаём данные для сессии
            user=user,
            db=db,
        )
        logger.debug(
        f"Успешный вход пользователя {user.email} "
        f"с IP {client_ip}, app_id={app_id}, device_id={device_id}, "
        f"device_info={legacy_device_info}"
    )
        response = RecoveryResponseModel(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            message="Recovery code is correct",
            confirmation=confirmation,
            session_id=str(new_session.id),
            device_id=device_id
        )
        return response
    else:
        logger.debug(f"{email} - Invalid recovery file")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid recovery file"
        )


# ============================================================================
# USER INVITATION ENDPOINTS (Приглашение пользователей)
# ============================================================================

@router.post(
    "/invite",
    response_model=InviteUserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
)
async def invite_user(
    body: InviteUserRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Создание приглашения для нового пользователя**
    
    Создаёт приглашение с уникальным токеном, которое можно отправить пользователю
    для регистрации в системе. Email из приглашения будет доступен только для чтения
    при регистрации.
    
    **После создания приглашения автоматически отправляется email с ссылкой для регистрации.**
    
    ---

    **Workflow:**
    1. Администратор создаёт приглашение
    2. Система генерирует уникальный токен
    3. **Автоматически отправляется email с ссылкой на регистрацию**
    4. Пользователь переходит по ссылке и видит форму регистрации
    5. Email в форме предзаполнен и readonly
    6. После регистрации приглашение помечается как использованное
    
    ---
    
    **Возможные ошибки:**
    - 409 Conflict - Уже существует активное приглашение для этого email
    - 409 Conflict - Пользователь с таким email уже зарегистрирован
    - 401 Unauthorized - Не авторизован
    - 429 Too Many Requests - Превышен rate limit
    """
    email = body.email.lower()
    
    existing_user = await repository_person.get_user_by_email(email, db)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Пользователь с email {email} уже зарегистрирован"
        )
    
    existing_invitation = await repository_invitation.get_pending_invitation_by_email(email, db)
    if existing_invitation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Активное приглашение для {email} уже существует (истекает {existing_invitation.expires_at})"
        )
    
    invitation = await repository_invitation.create_invitation(
        email=email,
        invited_by_id=current_user.id,
        expires_in_days=body.expires_in_days or 7,
        db=db
    )
    
    base_url = "https://dev-corid.cor-medical.ua/api"  # или из settings
    invitation_link = f"{base_url}/signup?token={invitation.token}"
    
    # Отправляем email в фоновом режиме
    background_tasks.add_task(
        send_invitation_email,
        email=email,
        invitation_link=invitation_link,
        invited_by_email=current_user.email,
        expires_at=invitation.expires_at.isoformat(),
    )
    
    logger.info(
        f"User {current_user.email} created invitation for {email}, "
        f"token={invitation.token[:12]}..., expires_at={invitation.expires_at}, "
        f"email will be sent in background"
    )
    
    return InviteUserResponse(
        invitation_id=invitation.id,
        email=invitation.email,
        token=invitation.token,
        invitation_link=invitation_link,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at
    )


@router.post(
    "/validate-invitation",
    response_model=ValidateInvitationResponse,
    dependencies=[Depends(RateLimiter(times=30, seconds=60))],
)
async def validate_invitation(
    body: ValidateInvitationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    **Проверка валидности токена приглашения**
    
    Используется фронтендом для проверки токена перед показом формы регистрации.
    Возвращает email, который нужно использовать при регистрации.
    
    ---
    
    **Параметры:**
    - `token` (str) - Токен приглашения из URL query параметра
    
    ---
    
    **Возвращает:**
    - `is_valid` (bool) - Валиден ли токен
    - `email` (str, optional) - Email для регистрации (если валиден)
    - `expires_at` (datetime, optional) - Когда истекает (если валиден)
    - `message` (str, optional) - Сообщение об ошибке (если невалиден)
    
    ---
    
    **Невалидные случаи:**
    - Приглашение не найдено
    - Приглашение уже использовано
    - Приглашение истекло
    
    ---
    
    **Безопасность:**
    - Rate limit: 30 проверок в минуту
    - Не требует авторизации (публичный endpoint)
    """
    invitation = await repository_invitation.get_invitation_by_token(body.token, db)
    
    if not invitation:
        return ValidateInvitationResponse(
            is_valid=False,
            message="Приглашение не найдено"
        )
    
    if invitation.is_used:
        return ValidateInvitationResponse(
            is_valid=False,
            message="Это приглашение уже было использовано"
        )
    
    if invitation.expires_at < datetime.now():
        return ValidateInvitationResponse(
            is_valid=False,
            message=f"Приглашение истекло {invitation.expires_at}"
        )
    
    return ValidateInvitationResponse(
        is_valid=True,
        email=invitation.email,
        expires_at=invitation.expires_at
    )


@router.post(
    "/accept-invitation",
    response_model=AcceptInvitationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
)
async def accept_invitation(
    body: AcceptInvitationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    device_info: dict = Depends(di.get_device_header),
):
    """
    **Регистрация пользователя по приглашению**
    
    Создаёт нового пользователя на основе валидного токена приглашения.
    Email берётся из приглашения (readonly), пользователь указывает только пароль
    и опциональные персональные данные.
    
    ---
    
    **Параметры:**
    - `token` (str) - Токен приглашения
    - `password` (str) - Пароль пользователя (8-32 символа)
    - `birth` (int, optional) - Год рождения (>= 1900)
    - `user_sex` (str, optional) - Пол: 'M', 'F', '*'
    
    ---
    
    **Безопасность:**
    - Rate limit: 5 регистраций в минуту
    - Приглашение одноразовое (is_used=True)
    - Email readonly (берётся из приглашения)
    - Пароль хешируется перед сохранением
    
    ---
    
    **Возможные ошибки:**
    - 404 Not Found - Приглашение не найдено
    - 400 Bad Request - Приглашение уже использовано
    - 400 Bad Request - Приглашение истекло
    - 409 Conflict - Пользователь с таким email уже существует
    - 429 Too Many Requests - Превышен rate limit
    """
    # Проверяем валидность приглашения
    invitation = await repository_invitation.get_valid_invitation_by_token(body.token, db)
    
    if not invitation:
        # Проверяем, существует ли приглашение вообще
        any_invitation = await repository_invitation.get_invitation_by_token(body.token, db)
        
        if not any_invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Приглашение не найдено"
            )
        
        if any_invitation.is_used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Это приглашение уже было использовано"
            )
        
        if any_invitation.expires_at < datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Приглашение истекло {any_invitation.expires_at}"
            )
    
    email = invitation.email
    
    # Проверяем, не зарегистрирован ли уже пользователь
    existing_user = await repository_person.get_user_by_email(email, db)
    if existing_user:
        # Помечаем приглашение как использованное даже если пользователь уже существует
        await repository_invitation.mark_invitation_used(invitation, db)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с этим email уже зарегистрирован"
        )
    
    # Создаём пользователя
    user_data = UserModel(
        email=email,
        password=body.password,
        birth=body.birth,
        user_sex=body.user_sex
    )
    user_data.password = auth_service.get_password_hash(user_data.password)
    
    new_user = await repository_person.create_user(user_data, db)
    
    if not new_user.cor_id:
        await repository_cor_id.create_new_corid(new_user, db)
    
    logger.info(f"User {email} registered via invitation (invited_by={invitation.invited_by})")
    
    # Помечаем приглашение как использованное
    await repository_invitation.mark_invitation_used(invitation, db)
    
    # Получаем роли пользователя
    user_roles = await repository_person.get_user_roles(email=new_user.email, db=db)
    
    # Создаём токены
    access_token, access_token_jti = await auth_service.create_access_token(
        data={"oid": str(new_user.id), "corid": new_user.cor_id, "roles": user_roles}
    )
    refresh_token = await auth_service.create_refresh_token(
        data={"oid": str(new_user.id), "corid": new_user.cor_id, "roles": user_roles}
    )
    
    # Создаём сессию
    device_information = di.get_device_info(request)
    app_id = device_information.get("app_id")
    device_id = device_information.get("device_id")
    legacy_device_info = device_information.get("device_info")
    
    if not device_id:
        device_id = str(uuid4())
    if not app_id:
        app_id = "unknown app"
    
    session_data = {
        "user_id": new_user.cor_id,
        "app_id": app_id,
        "device_id": device_id,
        "device_type": device_information["device_type"],
        "device_info": legacy_device_info,
        "ip_address": device_information["ip_address"],
        "device_os": device_information["device_os"],
        "jti": access_token_jti,
        "refresh_token": refresh_token,
        "access_token": access_token,
    }
    
    new_session = await repository_session.create_user_session(
        body=UserSessionModel(**session_data),
        user=new_user,
        db=db,
    )
    
    logger.info(
        f"User {new_user.email} successfully registered via invitation, "
        f"session created: device_id={device_id}, app_id={app_id}"
    )
    
    return AcceptInvitationResponse(
        user=UserDb.model_validate(new_user),
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        device_id=device_id,
        message="Регистрация по приглашению успешно завершена"
    )
