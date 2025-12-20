"""
Repository для работы с топливной системой QR кодов
"""
import logging
import time
from typing import Optional
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from cor_pass.database.models import (
    FuelStationQRSession, 
    FinanceBackendAuth, 
    User,
    CorporateClient,
    Profile,
)
from cor_pass.services.shared.email import send_corporate_request_approved_email
from cor_pass.schemas import (
    FuelQRGenerateRequest,
    FuelQRGenerateResponse,
    FuelQRVerifyRequest,
    FuelQRVerifyResponse,
    FinanceBackendAuthConfigCreate,
    FinanceBackendAuthConfigResponse,
    CorporateClientCreate,
    CorporateClientResponse,
    CorporateClientWithOwner,
    CorporateClientUpdate,
    CorporateClientReject,
    CorporateClientBlock,
    FinanceCreateCompanyRequest,
    FinanceCreateCompanyResponse,
    FuelOfflineQRData,
    FuelOfflineQRGenerateResponse,
    FuelOfflineQRVerifyRequest,
    FuelOfflineQRVerifyResponse,
    FuelOfflineTOTPSecretResponse,
    CorporateClientReject,
)
from cor_pass.services.shared.totp_service import TOTPService
from cor_pass.services.fuel.fuel_qr_service import FuelQRService
from cor_pass.services.roles.finance_backend_service import FinanceBackendService
from cor_pass.services.user.cipher import encrypt_data, decrypt_data
from cor_pass.config.config import settings

logger = logging.getLogger(__name__)


def _normalize_aes_key(key: bytes) -> bytes:
    """
    Нормализует AES ключ до корректной длины (16, 24 или 32 байта)
    
    Args:
        key: Исходный ключ
        
    Returns:
        Нормализованный ключ
    """
    if len(key) < 16:
        return key.ljust(16, b'\0')
    elif len(key) > 32:
        return key[:32]
    elif 16 < len(key) < 24:
        return key.ljust(24, b'\0')
    elif 24 < len(key) < 32:
        return key.ljust(32, b'\0')
    return key


async def generate_qr_code_for_user(
    body: FuelQRGenerateRequest,
    db: AsyncSession,
    user: User,
) -> FuelQRGenerateResponse:
    """
    Генерация QR кода для пользователя
    
    Args:
        body: Данные запроса (validity_minutes - опционально)
        db: Сессия базы данных
        user: Авторизованный пользователь
        
    Returns:
        FuelQRGenerateResponse с данными QR кода
        
    Raises:
        HTTPException: Если конфигурация не настроена или произошла ошибка
    """
    try:
        # Проверяем, что есть активная конфигурация для финансового бэкенда
        query = select(FinanceBackendAuth).where(
            FinanceBackendAuth.is_active == True
        )
        result = await db.execute(query)
        auth_config = result.scalar_one_or_none()
        
        if not auth_config:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Finance backend authentication is not configured"
            )
        
        # Расшифровываем TOTP секрет используя системный AES ключ
        try:
            if isinstance(auth_config.totp_secret, bytes):
                aes_key = _normalize_aes_key(settings.aes_key.encode())
                totp_secret = await decrypt_data(auth_config.totp_secret, aes_key)
            else:
                totp_secret = auth_config.totp_secret
        except Exception as e:
            logger.error(f"Failed to decrypt TOTP secret: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to decrypt TOTP secret"
            )
        
        # Генерируем QR код
        qr_service = FuelQRService()
        qr_response = await qr_service.generate_qr_code(
            user=user,
            db=db,
            totp_secret=totp_secret,
            validity_minutes=body.validity_minutes,
            totp_interval=auth_config.totp_interval  # Используем интервал из конфигурации
        )
        
        logger.info(f"QR code generated for user {user.cor_id}")
        return qr_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating QR code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate QR code: {str(e)}"
        )


async def verify_qr_code_and_check_limit(
    body: FuelQRVerifyRequest,
    db: AsyncSession,
) -> FuelQRVerifyResponse:
    """
    Верификация QR кода и проверка лимита пользователя через финансовый бэкенд
    
    Args:
        body: Данные QR кода из сканера
        db: Сессия базы данных
        
    Returns:
        FuelQRVerifyResponse с результатом верификации и информацией о лимите
        
    Raises:
        HTTPException: Если произошла ошибка верификации
    """
    try:
        # Получаем конфигурацию для финансового бэкенда
        query = select(FinanceBackendAuth).where(
            FinanceBackendAuth.is_active == True
        )
        result = await db.execute(query)
        auth_config = result.scalar_one_or_none()
        
        if not auth_config:
            return FuelQRVerifyResponse(
                is_valid=False,
                message="Finance backend authentication is not configured",
                user_cor_id=None,
                limit_info=None
            )
        
        # Расшифровываем TOTP секрет используя AES ключ
        try:
            if isinstance(auth_config.totp_secret, bytes):
                aes_key = _normalize_aes_key(settings.aes_key.encode())
                totp_secret = await decrypt_data(auth_config.totp_secret, aes_key)
            else:
                totp_secret = auth_config.totp_secret
        except Exception as e:
            logger.error(f"Failed to decrypt TOTP secret: {e}")
            return FuelQRVerifyResponse(
                is_valid=False,
                message="Failed to decrypt TOTP secret",
                user_cor_id=None,
                limit_info=None
            )
        
        # Верифицируем QR код
        qr_service = FuelQRService()
        verification_result = await qr_service.verify_qr_code(
            qr_data_string=body.qr_data_string,
            db=db,
            totp_secret=totp_secret
        )
        
        if not verification_result.get("is_valid"):
            logger.warning(f"QR code verification failed: {verification_result.get('error_message')}")
            return FuelQRVerifyResponse(
                is_valid=False,
                message=verification_result.get("error_message", "QR code verification failed"),
                user_cor_id=None,
                limit_info=None
            )
        
        # QR код валиден - проверяем лимит через финансовый бэкенд

        # finance_service = FinanceBackendService()
        # limit_check = await finance_service.check_user_limit(
        #     cor_id=verification_result.get("user_cor_id"),
        #     db=db
        # )

        # Mock данные для тестирования
        from cor_pass.schemas import FuelUserLimitInfo
        class MockLimitCheck:
            has_limit = True
            limit_info = FuelUserLimitInfo(
                cor_id=verification_result.get("user_cor_id"),
                employee_name="Амалян Тигран",
                employee_limit=5000.00,
                organization_id="test-org-123",
                organization_name="ТОВ Кор Енерджи",
                organization_limit=16000.00,
                is_active=True
            )
        
        limit_check = MockLimitCheck()
        
        if not limit_check:
            logger.error(f"Failed to check limit for user {verification_result.get('user_cor_id')}")
            return FuelQRVerifyResponse(
                is_valid=False,
                message="Failed to check user limit with finance backend",
                user_cor_id=verification_result.get("user_cor_id"),
                limit_info=None
            )
        
        if not limit_check.has_limit:
            logger.info(f"User {verification_result.get('user_cor_id')} has no fuel limit")
            return FuelQRVerifyResponse(
                is_valid=False,
                message="User has no fuel limit available",
                user_cor_id=verification_result.get("user_cor_id"),
                limit_info=limit_check.limit_info
            )
        
        # Всё ОК - помечаем QR как использованный
        await qr_service.mark_qr_as_used(
            session_token=verification_result.get("session_token"),
            db=db
        )
        
        logger.info(f"QR code verified and limit checked for user {verification_result.get('user_cor_id')}")
        return FuelQRVerifyResponse(
            is_valid=True,
            message="QR code verified successfully, user has fuel limit",
            user_cor_id=verification_result.get("user_cor_id"),
            limit_info=limit_check.limit_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying QR code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify QR code: {str(e)}"
        )


async def create_finance_backend_config(
    body: FinanceBackendAuthConfigCreate,
    db: AsyncSession,
) -> FinanceBackendAuthConfigResponse:
    """
    Создание конфигурации для интеграции с финансовым бэкендом (админ)
    
    Args:
        body: Данные конфигурации
        db: Сессия базы данных
        
    Returns:
        FinanceBackendAuthConfigResponse с созданной конфигурацией
        
    Raises:
        HTTPException: Если произошла ошибка создания
    """
    try:
        # Шифруем TOTP секрет используя AES ключ
        aes_key = _normalize_aes_key(settings.aes_key.encode())
        
        # Шифруем секрет
        encrypted_secret = await encrypt_data(
            body.totp_secret.encode('utf-8'),
            aes_key
        )
        
        # Проверяем существует ли конфигурация с таким service_name
        query = select(FinanceBackendAuth).where(
            FinanceBackendAuth.service_name == body.service_name
        )
        result = await db.execute(query)
        existing_config = result.scalar_one_or_none()
        
        if existing_config:
            # Обновляем существующую конфигурацию
            existing_config.api_endpoint = body.api_endpoint
            existing_config.totp_secret = encrypted_secret
            existing_config.totp_interval = body.totp_interval
            existing_config.is_active = True
            existing_config.failed_attempts = 0  
            new_config = existing_config
        else:
            # Создаём новую конфигурацию
            new_config = FinanceBackendAuth(
                id=str(uuid4()),
                service_name=body.service_name,
                api_endpoint=body.api_endpoint,
                totp_secret=encrypted_secret,
                totp_interval=body.totp_interval,
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.add(new_config)
        
        await db.commit()
        await db.refresh(new_config)
        
        logger.info(f"Finance backend configuration created: {body.service_name}")
        
        return FinanceBackendAuthConfigResponse(
            id=new_config.id,
            service_name=new_config.service_name,
            api_endpoint=new_config.api_endpoint,
            totp_interval=new_config.totp_interval,
            is_active=new_config.is_active,
            last_successful_auth=new_config.last_successful_auth,
            last_failed_auth=new_config.last_failed_auth,
            failed_attempts=new_config.failed_attempts,
            created_at=new_config.created_at
        )
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating finance backend config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create finance backend configuration: {str(e)}"
        )


async def get_active_finance_backend_config(
    db: AsyncSession,
) -> Optional[FinanceBackendAuthConfigResponse]:
    """
    Получение активной конфигурации финансового бэкенда (админ)
    
    Args:
        db: Сессия базы данных
        
    Returns:
        FinanceBackendAuthConfigResponse или None если конфигурации нет
    """
    try:
        query = select(FinanceBackendAuth).where(
            FinanceBackendAuth.is_active == True
        )
        result = await db.execute(query)
        config = result.scalar_one_or_none()
        
        if not config:
            return None
        
        return FinanceBackendAuthConfigResponse(
            id=config.id,
            service_name=config.service_name,
            api_endpoint=config.api_endpoint,
            totp_interval=config.totp_interval,
            is_active=config.is_active,
            last_successful_auth=config.last_successful_auth,
            last_failed_auth=config.last_failed_auth,
            failed_attempts=config.failed_attempts,
            created_at=config.created_at
        )
        
    except Exception as e:
        logger.error(f"Error getting finance backend config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get finance backend configuration: {str(e)}"
        )


# ============================================================================
# Corporate Client Functions (Корпоративные клиенты)
# ============================================================================

async def create_corporate_client_request(
    body: CorporateClientCreate,
    user: User,
    db: AsyncSession,
) -> CorporateClientResponse:
    """
    Создание заявки на регистрацию корпоративного клиента (статус pending)
    
    Один пользователь может подавать заявки на несколько компаний.
    Проверяется только уникальность tax_id (ЄДРПОУ/ИНН).
    
    Args:
        body: Данные заявки
        user: Пользователь, подающий заявку
        db: Сессия базы данных
        
    Returns:
        CorporateClientResponse с созданной заявкой
        
    Raises:
        HTTPException 400: Если компания с таким ЄДРПОУ/ИНН уже существует
    """
    try:
        # Проверяем, нет ли уже компании с таким tax_id (ЄДРПОУ/ИНН)
        # Один пользователь может иметь несколько компаний, но каждая компания должна иметь уникальный tax_id
        query_tax = select(CorporateClient).where(
            CorporateClient.tax_id == body.tax_id,
            CorporateClient.deleted_at.is_(None)
        )
        result_tax = await db.execute(query_tax)
        existing_company = result_tax.scalar_one_or_none()
        
        if existing_company:
            # Формируем подробное сообщение об ошибке
            status_messages = {
                "pending": "находится на рассмотрении",
                "active": "уже зарегистрирована и активна",
                "blocked": "заблокирована",
                "rejected": "была отклонена"
            }
            status_message = status_messages.get(existing_company.status, f"имеет статус {existing_company.status}")
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Компания с ЄДРПОУ/ИНН {body.tax_id} {status_message}"
            )
        
        # Создаём заявку (pending)
        new_request = CorporateClient(
            id=str(uuid4()),
            owner_cor_id=user.cor_id,
            company_format=body.company_format,
            company_name=body.company_name,
            address=body.address,
            phone_number=body.phone_number,
            email=body.email,
            tax_id=body.tax_id,
            status="pending",
            created_at=datetime.utcnow()
        )
        
        db.add(new_request)
        await db.commit()
        await db.refresh(new_request)
        
        logger.info(f"Corporate client request created: {new_request.id} by user {user.cor_id}")
        
        return CorporateClientResponse.model_validate(new_request)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating corporate client request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create corporate client request: {str(e)}"
        )


async def get_user_corporate_client(
    user: User,
    db: AsyncSession,
) -> list[CorporateClientResponse]:
    """
    Получение списка всех компаний/заявок текущего пользователя
    
    Один пользователь может владеть несколькими компаниями.
    Возвращаются все заявки, отсортированные по дате создания (новые первые).
    
    Args:
        user: Авторизованный пользователь
        db: Сессия базы данных
        
    Returns:
        Список CorporateClientResponse (может быть пустым)
    """
    try:
        query = select(CorporateClient).where(
            CorporateClient.owner_cor_id == user.cor_id,
            CorporateClient.deleted_at.is_(None)
        ).order_by(CorporateClient.created_at.desc())
        
        result = await db.execute(query)
        clients = result.scalars().all()
        
        return [CorporateClientResponse.model_validate(client) for client in clients]
        
    except Exception as e:
        logger.error(f"Error getting user corporate clients: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user corporate clients: {str(e)}"
        )


async def get_user_corporate_status_with_finance(
    user: User,
    db: AsyncSession,
):
    """
    Получает оптимизированный статус пользователя:
    1. Список заявок пользователя
    2. Корпоративный ID 
    3. Роль в финансовой системе 
    Args:
        user: Авторизованный пользователь
        db: Сессия базы данных
        
    Returns:
        MyCorporateStatusResponse с информацией по заявке, кор ID и роли
    """
    from cor_pass.schemas import MyCorporateStatusResponse
    
    try:
        applications = await get_user_corporate_client(user=user, db=db)
        cor_id = user.cor_id
        finance_role = None
        if cor_id:
            try:
                finance_service = FinanceBackendService()
                finance_data = await finance_service.get_company_summary_by_cor_id(
                    db=db,
                    cor_id=cor_id
                )
                
                if finance_data and isinstance(finance_data, dict):
                    finance_role = finance_data.get("role")
                    if not finance_role:
                        finance_role = finance_data.get("role", "account member")
                
            except HTTPException as http_err:
                if http_err.status_code == 404:
                    logger.debug(f"User {cor_id} not found in finance backend (404)")
                    finance_role = None
                else:
                    logger.warning(f"Finance backend error for user {cor_id}: {http_err.detail}")
                    
            except Exception as finance_error:
                logger.warning(f"Finance backend request failed for user {cor_id}: {finance_error}")
        return MyCorporateStatusResponse(
            applications=applications,
            cor_id=cor_id,
            finance_role=finance_role
        )
        
    except Exception as e:
        logger.error(f"Error getting user corporate status with finance: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get corporate status: {str(e)}"
        )


async def get_corporate_client_requests(
    db: AsyncSession,
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    include_deleted: bool = False,
) -> list[CorporateClientWithOwner]:
    """
    Получение списка корпоративных клиентов (для админа)
    Если status_filter не указан, показывает всех клиентов
    
    Для компаний с finance_company_id получает актуальный баланс из финбэка
    и сохраняет его в БД.
    
    Args:
        db: Сессия базы данных
        status_filter: Фильтр по статусу (pending, active, blocked, rejected, limit_exceeded, deleted)
        skip: Пропустить записей
        limit: Максимум записей
        
    Returns:
        Список клиентов с информацией о владельцах и актуальным балансом
    """
    try:
        query = select(CorporateClient).join(
            User, CorporateClient.owner_cor_id == User.cor_id
        )
        # Deleted handling: if explicitly filtering by 'deleted', show soft-deleted records
        if status_filter == "deleted":
            query = query.where(CorporateClient.deleted_at.is_not(None))
            query = query.where(CorporateClient.status == "deleted")
        else:
            if not include_deleted:
                query = query.where(CorporateClient.deleted_at.is_(None))
            if status_filter:
                query = query.where(CorporateClient.status == status_filter)
        
        query = query.order_by(CorporateClient.created_at.desc())
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        clients = result.scalars().all()
        
        # Инициализируем сервис финансового бэкенда
        finance_service = FinanceBackendService()
        
        # Формируем ответ с информацией о владельцах
        response = []
        for client in clients:
            # Загружаем пользователя
            user_query = select(User).where(User.cor_id == client.owner_cor_id)
            user_result = await db.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            # Если у компании есть finance_company_id, получаем актуальный баланс из финбэка
            if client.finance_company_id:
                try:
                    summary = await finance_service.get_partner_company_summary(
                        company_id=client.finance_company_id,
                        db=db
                    )
                    
                    if summary and not isinstance(summary, dict) or "error" not in summary:
                        # summary возвращает массив с одним объектом
                        if isinstance(summary, list) and len(summary) > 0:
                            company_data = summary[0]
                            balance = company_data.get("balance")
                            
                            if balance is not None:
                                # Обновляем баланс в БД
                                client.current_balance = float(balance)
                                client.last_balance_update = datetime.utcnow()
                                logger.info(f"Updated balance for company {client.id}: {balance}")
                except Exception as finance_err:
                    logger.warning(f"Failed to get balance for company {client.id} from finance backend: {finance_err}")
            
            client_dict = CorporateClientResponse.model_validate(client).model_dump()
            client_dict["owner_first_name"] = None  # user.first_name if user else None
            client_dict["owner_last_name"] = None  # user.last_name if user else None
            client_dict["owner_email"] = user.email if user else None
            
            response.append(CorporateClientWithOwner(**client_dict))
        
        # Сохраняем обновлённые балансы
        await db.commit()
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting corporate client requests: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get corporate client requests: {str(e)}"
        )


async def approve_corporate_client_request(
    request_id: str,
    admin_user: User,
    db: AsyncSession,
) -> CorporateClientResponse:
    """
    Подтверждение заявки — перевод статуса pending → active
    
    При подтверждении:
    1. Создаётся владелец компании в finance backend (POST /v1/partner_companies/owner/)
    2. Создаётся сама компания в finance backend (POST /v1/partner_companies/)
    3. Статус переводится в active
    
    Args:
        request_id: ID заявки
        admin_user: Администратор, подтверждающий заявку
        db: Сессия базы данных
        
    Returns:
        CorporateClientResponse с обновлённой записью
        
    Raises:
        HTTPException 404: Заявка не найдена
        HTTPException 400: Заявка уже обработана или ошибка создания в finance backend
    """
    try:
        # Получаем заявку
        query = select(CorporateClient).where(
            CorporateClient.id == request_id,
            CorporateClient.deleted_at.is_(None)
        )
        result = await db.execute(query)
        client = result.scalar_one_or_none()
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Заявка не найдена"
            )
        
        if client.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Заявка уже обработана (статус: {client.status})"
            )
        
        user_query = select(User).where(User.cor_id == client.owner_cor_id)
        user_result = await db.execute(user_query)
        owner_user = user_result.scalar_one_or_none()
        
        if not owner_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Владелец с cor_id {client.owner_cor_id} не найден"
            )
        
        profile_query = select(Profile).where(Profile.user_id == owner_user.id)
        profile_result = await db.execute(profile_query)
        profile = profile_result.scalar_one_or_none()
        
        # Расшифровываем имя и фамилию из Profile если есть
        first_name = owner_user.email.split('@')[0]  # Fallback
        last_name = ""  # Fallback
        
        if profile:
            try:
                aes_key = _normalize_aes_key(settings.aes_key.encode())
                
                if profile.encrypted_first_name:
                    decrypted_first_name = await decrypt_data(profile.encrypted_first_name, aes_key)
                    if decrypted_first_name:
                        first_name = decrypted_first_name
                
                if profile.encrypted_surname:
                    decrypted_surname = await decrypt_data(profile.encrypted_surname, aes_key)
                    if decrypted_surname:
                        last_name = decrypted_surname
                        
                logger.info(f"Using Profile data for owner {client.owner_cor_id}: {first_name} {last_name}")
            except Exception as e:
                logger.warning(f"Failed to decrypt Profile data for {client.owner_cor_id}, using email fallback: {e}")
        else:
            logger.info(f"No Profile found for owner {client.owner_cor_id}, using email fallback")
        
        finance_service = FinanceBackendService()
        
        owner_response = await finance_service.create_partner_company_owner(
            owner_cor_id=client.owner_cor_id,
            first_name=first_name,
            last_name=last_name,
            email=owner_user.email,
            db=db
        )
        
        if not owner_response:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось создать владельца компании в финансовом бэкенде"
            )
        
        if "error" in owner_response:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ошибка при создании владельца: {owner_response['error']}"
            )
        
        logger.info(f"Partner company owner created in finance backend: {client.owner_cor_id}")
        
        # Используем current_balance как стартовый баланс (если не задан, то 0)
        start_balance = float(client.current_balance) if client.current_balance else 0.0
        
        company_response = await finance_service.create_partner_company(
            name=client.company_name,
            company_format=client.company_format,
            phone_number=client.phone_number,
            tax_id=client.tax_id,
            address=client.address,
            owner_id_or_cor_id=client.owner_cor_id,
            email=client.email,
            start_balance=start_balance,
            db=db
        )
        
        if not company_response:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось создать компанию в финансовом бэкенде"
            )
        
        if "error" in company_response:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ошибка при создании компании: {company_response['error']}"
            )
        
        logger.info(f"Partner company created in finance backend: tax_id={client.tax_id}, id={company_response.get('id')}")
        
        finance_company_id = company_response.get("id")
        
        # Обновляем запись — переводим в active
        client.status = "active"
        client.finance_company_id = finance_company_id
        client.reviewed_by = admin_user.cor_id
        client.reviewed_at = datetime.utcnow()
        
        # Устанавливаем credit_limit (fuel_limit) в финбэке если задан
        if client.fuel_limit and float(client.fuel_limit) > 0:
            try:
                await finance_service.update_partner_company_limits(
                    company_id=finance_company_id,
                    payload={"credit_limit": float(client.fuel_limit)},
                    db=db
                )
                logger.info(f"Credit limit set for company {finance_company_id}: {client.fuel_limit}")
            except Exception as limit_err:
                logger.warning(f"Failed to set credit limit for company {finance_company_id}: {limit_err}")
        
        await db.commit()
        await db.refresh(client)
        
        logger.info(f"Corporate client approved: {client.id}, finance_company_id: {finance_company_id}")
        
        # Отправляем уведомление об одобрении заявки владельцу компании
        try:
            await send_corporate_request_approved_email(
                email=owner_user.email,
                company_name=client.company_name
            )
            logger.info(f"Approval email sent to {owner_user.email} for company {client.company_name}")
        except Exception as email_err:
            logger.warning(f"Failed to send approval email to {owner_user.email}: {email_err}")
            # Не прерываем процесс одобрения если письмо не отправилось
        
        return CorporateClientResponse.model_validate(client)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error approving corporate client request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve corporate client request: {str(e)}"
        )


async def reject_corporate_client_request(
    request_id: str,
    body: CorporateClientReject,
    admin_user: User,
    db: AsyncSession,
) -> CorporateClientResponse:
    """
    Отклонение заявки — перевод статуса pending → rejected
    
    Args:
        request_id: ID заявки
        body: Причина отклонения
        admin_user: Администратор, отклоняющий заявку
        db: Сессия базы данных
        
    Returns:
        CorporateClientResponse с обновлённой записью
    """
    try:
        # Получаем заявку
        query = select(CorporateClient).where(
            CorporateClient.id == request_id,
            CorporateClient.deleted_at.is_(None)
        )
        result = await db.execute(query)
        client = result.scalar_one_or_none()
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Заявка не найдена"
            )
        
        if client.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Заявка уже обработана (статус: {client.status})"
            )
        
        # Отклоняем заявку
        client.status = "rejected"
        client.reviewed_by = admin_user.cor_id
        client.reviewed_at = datetime.utcnow()
        client.rejection_reason = body.rejection_reason
        
        await db.commit()
        await db.refresh(client)
        
        logger.info(f"Corporate client request rejected: {request_id}")
        
        return CorporateClientResponse.model_validate(client)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error rejecting corporate client request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject corporate client request: {str(e)}"
        )


async def block_corporate_client(
    client_id: str,
    body: CorporateClientBlock,
    admin_user: User,
    db: AsyncSession,
) -> CorporateClientResponse:
    """
    Блокировка компании — перевод статуса active → blocked
    
    Интегрируется с финансовым бэкендом:
    - Вызывает PUT /v1/partner_companies/{id}/disable на финбэке
    
    Args:
        client_id: ID клиента
        body: Причина блокировки (опционально)
        admin_user: Администратор
        db: Сессия базы данных
        
    Returns:
        CorporateClientResponse с обновлённой записью
        
    Raises:
        HTTPException: Если клиент не найден, не активен или ошибка на финбэке
    """
    try:
        query = select(CorporateClient).where(
            CorporateClient.id == client_id,
            CorporateClient.deleted_at.is_(None)
        )
        result = await db.execute(query)
        client = result.scalar_one_or_none()
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Корпоративный клиент не найден"
            )
        
        if client.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Можно блокировать только активные компании (текущий статус: {client.status})"
            )
        
        # Блокируем на финансовом бэкенде если есть finance_company_id
        if client.finance_company_id:
            try:
                finance_service = FinanceBackendService()
                disable_result = await finance_service.disable_partner_company(
                    company_id=client.finance_company_id,
                    db=db
                )
                
                if not disable_result:
                    logger.warning(f"Failed to disable partner company {client.finance_company_id} in finance backend")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Failed to disable company in finance backend"
                    )
                
                if "error" in disable_result:
                    logger.warning(f"Finance backend error disabling company {client.finance_company_id}: {disable_result['error']}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Finance backend error: {disable_result['error']}"
                    )
                
                logger.info(f"Partner company disabled in finance backend: {client.finance_company_id}")
            except HTTPException:
                raise
            except Exception as finance_err:
                logger.error(f"Error disabling partner company {client.finance_company_id}: {finance_err}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to disable company in finance backend: {str(finance_err)}"
                )
        
        # Обновляем статус локально
        client.status = "blocked"
        client.reviewed_by = admin_user.cor_id
        client.reviewed_at = datetime.utcnow()
        if body.reason:
            client.rejection_reason = body.reason  # Используем то же поле
        
        await db.commit()
        await db.refresh(client)
        
        logger.info(f"Corporate client blocked: {client_id} (company: {client.company_name})")
        
        return CorporateClientResponse.model_validate(client)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error blocking corporate client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to block corporate client: {str(e)}"
        )


async def unblock_corporate_client(
    client_id: str,
    admin_user: User,
    db: AsyncSession,
) -> CorporateClientResponse:
    """
    Разблокировка компании — перевод статуса blocked → active
    
    Интегрируется с финансовым бэкендом:
    - Вызывает PUT /v1/partner_companies/{id}/enable на финбэке
    
    Args:
        client_id: ID клиента
        admin_user: Администратор
        db: Сессия базы данных
        
    Returns:
        CorporateClientResponse с обновлённой записью
        
    Raises:
        HTTPException: Если клиент не найден, не заблокирован или ошибка на финбэке
    """
    try:
        query = select(CorporateClient).where(
            CorporateClient.id == client_id,
            CorporateClient.deleted_at.is_(None)
        )
        result = await db.execute(query)
        client = result.scalar_one_or_none()
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Корпоративный клиент не найден"
            )
        
        if client.status != "blocked":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Можно разблокировать только заблокированные компании (текущий статус: {client.status})"
            )
        
        # Разблокируем на финансовом бэкенде если есть finance_company_id
        if client.finance_company_id:
            try:
                finance_service = FinanceBackendService()
                enable_result = await finance_service.enable_partner_company(
                    company_id=client.finance_company_id,
                    db=db
                )
                
                if not enable_result:
                    logger.warning(f"Failed to enable partner company {client.finance_company_id} in finance backend")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Failed to enable company in finance backend"
                    )
                
                if "error" in enable_result:
                    logger.warning(f"Finance backend error enabling company {client.finance_company_id}: {enable_result['error']}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Finance backend error: {enable_result['error']}"
                    )
                
                logger.info(f"Partner company enabled in finance backend: {client.finance_company_id}")
            except HTTPException:
                raise
            except Exception as finance_err:
                logger.error(f"Error enabling partner company {client.finance_company_id}: {finance_err}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to enable company in finance backend: {str(finance_err)}"
                )
        
        # Обновляем статус локально
        client.status = "active"
        client.reviewed_by = admin_user.cor_id
        client.reviewed_at = datetime.utcnow()
        # Очищаем причину блокировки
        client.rejection_reason = None
        
        await db.commit()
        await db.refresh(client)
        
        logger.info(f"Corporate client unblocked: {client_id} (company: {client.company_name})")
        
        return CorporateClientResponse.model_validate(client)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error blocking corporate client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to block corporate client: {str(e)}"
        )


async def restore_corporate_client(
    client_id: str,
    admin_user: User,
    db: AsyncSession,
) -> CorporateClientResponse:
    """
    Восстановление удалённой компании:
    - Снимает soft-delete (deleted_at -> None)
    - Повторно создаёт владельца и компанию на финбэке (как в approve)
    - Переводит статус в active и выставляет лимит, если задан
    """
    try:
        # Ищем компанию (включая удалённые)
        query = select(CorporateClient).where(CorporateClient.id == client_id)
        result = await db.execute(query)
        client = result.scalar_one_or_none()

        if not client:
            raise HTTPException(status_code=404, detail="Корпоративный клиент не найден")

        if client.deleted_at is None:
            raise HTTPException(status_code=400, detail="Компания не помечена как удалённая")

        # Получаем владельца
        user_query = select(User).where(User.cor_id == client.owner_cor_id)
        user_result = await db.execute(user_query)
        owner_user = user_result.scalar_one_or_none()
        if not owner_user:
            raise HTTPException(status_code=404, detail=f"Владелец с cor_id {client.owner_cor_id} не найден")

        # Профиль владельца (для имён)
        profile_query = select(Profile).where(Profile.user_id == owner_user.id)
        profile_result = await db.execute(profile_query)
        profile = profile_result.scalar_one_or_none()

        first_name = owner_user.email.split('@')[0]
        last_name = ""
        if profile:
            try:
                aes_key = _normalize_aes_key(settings.aes_key.encode())
                if profile.encrypted_first_name:
                    decrypted_first_name = await decrypt_data(profile.encrypted_first_name, aes_key)
                    if decrypted_first_name:
                        first_name = decrypted_first_name
                if profile.encrypted_surname:
                    decrypted_surname = await decrypt_data(profile.encrypted_surname, aes_key)
                    if decrypted_surname:
                        last_name = decrypted_surname
            except Exception as e:
                logger.warning(f"Failed to decrypt Profile data for {client.owner_cor_id}: {e}")

        finance_service = FinanceBackendService()

        # 1) Создаём владельца в финбэке (идемпотентно по логике финбэка)
        owner_response = await finance_service.create_partner_company_owner(
            owner_cor_id=client.owner_cor_id,
            first_name=first_name,
            last_name=last_name,
            email=owner_user.email,
            db=db,
        )
        if not owner_response:
            raise HTTPException(status_code=503, detail="Не удалось создать владельца компании в финансовом бэкенде")
        if isinstance(owner_response, dict) and owner_response.get("error"):
            raise HTTPException(status_code=400, detail=f"Ошибка при создании владельца: {owner_response['error']}")

        # 2) Создаём саму компанию (финбэк должен восстановить/реюзнуть при совпадении данных)
        start_balance = float(client.current_balance) if client.current_balance else 0.0
        company_response = await finance_service.create_partner_company(
            name=client.company_name,
            company_format=client.company_format,
            phone_number=client.phone_number,
            tax_id=client.tax_id,
            address=client.address,
            owner_id_or_cor_id=client.owner_cor_id,
            email=client.email,
            start_balance=start_balance,
            db=db,
        )
        if not company_response:
            raise HTTPException(status_code=503, detail="Не удалось создать компанию в финансовом бэкенде")
        if isinstance(company_response, dict) and company_response.get("error"):
            raise HTTPException(status_code=400, detail=f"Ошибка при создании компании: {company_response['error']}")

        finance_company_id = company_response.get("id")

        # 3) Снимаем soft-delete и переводим в active
        client.deleted_at = None
        client.status = "active"
        client.finance_company_id = finance_company_id
        client.reviewed_by = admin_user.cor_id
        client.reviewed_at = datetime.utcnow()
        client.rejection_reason = None

        # Выставляем кредитный лимит в финбэке, если задан
        if client.fuel_limit and float(client.fuel_limit) > 0:
            try:
                await finance_service.update_partner_company_limits(
                    company_id=finance_company_id,
                    payload={"credit_limit": float(client.fuel_limit)},
                    db=db,
                )
                logger.info(f"Credit limit set for restored company {finance_company_id}: {client.fuel_limit}")
            except Exception as limit_err:
                logger.warning(f"Failed to set credit limit for restored company {finance_company_id}: {limit_err}")

        await db.commit()
        await db.refresh(client)

        logger.info(f"Corporate client restored: {client.id}, finance_company_id: {finance_company_id}")
        return CorporateClientResponse.model_validate(client)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error restoring corporate client {client_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restore corporate client: {str(e)}")


async def get_corporate_clients(
    db: AsyncSession,
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    include_deleted: bool = True,
) -> list[CorporateClientWithOwner]:
    """
    Получение списка корпоративных клиентов (для админа)
    По умолчанию показывает все, можно фильтровать
    
    Args:
        db: Сессия базы данных
        status_filter: Фильтр по статусу (pending, active, blocked, rejected)
        skip: Пропустить записей
        limit: Максимум записей
        
    Returns:
        Список компаний с информацией о владельцах
    """
    # Просто используем ту же функцию get_corporate_client_requests
    return await get_corporate_client_requests(db, status_filter, skip, limit, include_deleted)


async def update_corporate_client(
    client_id: str,
    body: CorporateClientUpdate,
    db: AsyncSession,
) -> CorporateClientResponse:
    """
    Обновление данных корпоративного клиента (админ)
    
    Args:
        client_id: ID клиента
        body: Данные для обновления
        db: Сессия базы данных
        
    Returns:
        CorporateClientResponse с обновлённым клиентом
    """
    try:
        # Получаем клиента
        query = select(CorporateClient).where(
            CorporateClient.id == client_id,
            CorporateClient.deleted_at.is_(None)
        )
        result = await db.execute(query)
        client = result.scalar_one_or_none()
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Корпоративный клиент не найден"
            )
        
        # Обновляем поля
        if body.company_name is not None:
            client.company_name = body.company_name
        if body.address is not None:
            client.address = body.address
        if body.phone_number is not None:
            client.phone_number = body.phone_number
        if body.email is not None:
            client.email = body.email
        if body.fuel_limit is not None:
            client.fuel_limit = body.fuel_limit
        
        await db.commit()
        await db.refresh(client)
        
        logger.info(f"Corporate client updated: {client_id}")
        
        return CorporateClientResponse.model_validate(client)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating corporate client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update corporate client: {str(e)}"
        )


async def update_company_limits_in_finance(
    finance_company_id: int,
    credit_limit: Optional[float] = None,
    balance_level_alert_limit: Optional[float] = None,
    balance_level_hook_url: Optional[str] = None,
    db: AsyncSession = None,
    update_local_fuel_limit: bool = True,
) -> dict:
    """
    Обновляет лимиты компании в финансовом бэкенде.
    
    Обновляет:
    - credit_limit - кредитный лимит (на сколько можно лазить в минус) - сохраняется в fuel_limit локально
    - balance_level_alert_limit - уровень баланса, при котором послать вебхук (по умолчанию = credit_limit)
    - balance_level_hook_url - URL вебхука для уведомления о превышении лимита
    
    Args:
        finance_company_id: ID компании в финбэке
        credit_limit: Кредитный лимит (будет сохранён в fuel_limit локально)
        balance_level_alert_limit: Оборот для отправки вебхука (если не указан, используется credit_limit)
        balance_level_hook_url: URL вебхука (если не указан, используется дефолтный в зависимости от окружения)
        db: Сессия базы данных
        update_local_fuel_limit: Обновлять ли локальное поле fuel_limit при изменении credit_limit
        
    Returns:
        dict с данными от финбэке
    """
    try:
        from cor_pass.config.config import settings
        
        finance_service = FinanceBackendService()
        
        # Формируем тело реквеста
        update_payload = {}
        if credit_limit is not None:
            update_payload["credit_limit"] = credit_limit
            
            # Если balance_level_alert_limit не указан, по умолчанию берём credit_limit
            if balance_level_alert_limit is None:
                balance_level_alert_limit = credit_limit
        
        if balance_level_alert_limit is not None:
            update_payload["balance_level_alert_limit"] = balance_level_alert_limit
        
        # Если balance_level_hook_url не указан, берём дефолтный в зависимости от окружения
        if balance_level_hook_url is None:
            if settings.app_env == "production":
                balance_level_hook_url = "https://prod01.cor-id.cor-medical.ua/api/webhooks/balance-level-alert"
            else:
                balance_level_hook_url = "https://dev-corid.cor-medical.ua/api/webhooks/balance-level-alert"
        
        if balance_level_hook_url is not None:
            update_payload["balance_level_hook_url"] = balance_level_hook_url
        
        if not update_payload:
            raise ValueError("No fields to update")
        
        result = await finance_service.update_partner_company_limits(
            company_id=finance_company_id,
            payload=update_payload,
            db=db
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to communicate with finance backend"
            )
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Finance backend error: {result['error']}"
            )
        
        # Обновляем локальное поле fuel_limit если изменён credit_limit
        if credit_limit is not None and update_local_fuel_limit and db:
            try:
                query = select(CorporateClient).where(
                    CorporateClient.finance_company_id == finance_company_id,
                    CorporateClient.deleted_at.is_(None)
                )
                db_result = await db.execute(query)
                local_client = db_result.scalar_one_or_none()
                
                if local_client:
                    local_client.fuel_limit = credit_limit
                    
                    # Если компания была в статусе 'limit_exceeded', проверяем, нужно ли вернуть её в 'active'
                    # Превышение лимита считается, если абс(баланс) > лимит
                    if local_client.status == "limit_exceeded" and local_client.current_balance is not None:
                        current_balance_abs = abs(float(local_client.current_balance))
                        # Если новый лимит достаточен для текущего дефицита, возвращаем в active
                        if current_balance_abs <= credit_limit:
                            local_client.status = "active"
                            logger.info(f"Company {local_client.id} status reverted to 'active' (limit_exceeded resolved): new_limit={credit_limit}, current_balance={local_client.current_balance}")
                    
                    await db.commit()
                    logger.info(f"Local fuel_limit updated for company {local_client.id}: {credit_limit}")
            except Exception as local_err:
                logger.warning(f"Failed to update local fuel_limit: {local_err}")
        
        logger.info(f"Company limits updated in finance backend: {finance_company_id}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating company limits in finance backend: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update company limits: {str(e)}"
        )


async def handle_balance_level_webhook(
    payload: dict,
    db: AsyncSession,
) -> dict:
    """
    Обрабатывает вебхук от финансового бэкенда с информацией о текущем балансе.
    
    При превышении лимита:
    - Обновляем статус компании на 'limit_exceeded'
    - Обновляем текущий баланс
    
    Payload от финбэке:
    {
        "company_id": int,
        "company_owner_id": int,
        "current_balance": float,
        "company_name": str,
        "cor_id_of_owner": str,
        "timestamp": str,
        "account_id": int
    }
    
    Args:
        payload: Вебхук payload от финбэке
        db: Сессия базы данных
        
    Returns:
        dict с результатом обработки
    """
    try:
        finance_company_id = payload.get("company_id")
        current_balance = payload.get("current_balance")
        cor_id_owner = payload.get("cor_id_of_owner")
        timestamp = payload.get("timestamp")
        
        logger.info(f"Received balance webhook: company_id={finance_company_id}, balance={current_balance}, owner={cor_id_owner}")
        
        if not finance_company_id or cor_id_owner is None:
            raise ValueError("Missing required fields: company_id or cor_id_of_owner")
        
        # Сначала пытаемся найти компанию по finance_company_id
        query = select(CorporateClient).where(
            CorporateClient.finance_company_id == finance_company_id,
            CorporateClient.deleted_at.is_(None)
        )
        result = await db.execute(query)
        corporate_client = result.scalar_one_or_none()
        
        # Если не найдена по finance_company_id, ищем по cor_id владельца (дополнительная проверка)
        if not corporate_client:
            logger.warning(f"Corporate client not found for finance_company_id={finance_company_id}, trying to find by owner cor_id={cor_id_owner}")
            
            query_by_owner = select(CorporateClient).where(
                CorporateClient.owner_cor_id == cor_id_owner,
                CorporateClient.finance_company_id == finance_company_id,
                CorporateClient.deleted_at.is_(None)
            )
            result_owner = await db.execute(query_by_owner)
            corporate_client = result_owner.scalar_one_or_none()
        
        if not corporate_client:
            logger.warning(f"Corporate client not found for finance_company_id={finance_company_id} and owner cor_id={cor_id_owner}")
            return {"status": "warning", "message": "Corporate client not found for this company and owner"}
        
        # Логируем найденную компанию
        logger.info(f"Found corporate client: {corporate_client.id}, company_name={corporate_client.company_name}, owner_cor_id={corporate_client.owner_cor_id}")
        
        # Обновляем статус на 'limit_exceeded'
        corporate_client.status = "limit_exceeded"
        corporate_client.current_balance = float(current_balance) if current_balance else None
        corporate_client.last_balance_update = datetime.utcnow()
        
        await db.commit()
        await db.refresh(corporate_client)
        
        logger.info(f"Corporate client status updated to 'limit_exceeded': {corporate_client.id}, balance={current_balance}")
        
        return {
            "status": "success",
            "message": "Webhook processed successfully",
            "client_id": corporate_client.id,
            "company_name": corporate_client.company_name,
            "balance": current_balance
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error handling balance webhook: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error processing webhook: {str(e)}"
        }


async def delete_corporate_client(
    client_id: str,
    db: AsyncSession,
) -> dict:
    """
    Удаление корпоративного клиента (админ)
    
    Логика удаления в зависимости от статуса:
    - active, blocked: удаляет компанию на финбэке
    - pending, rejected: удаляет только у нас
    - limit_exceeded: не удаляется (ни у нас, ни на финбэке)
    
    Args:
        client_id: ID клиента для удаления
        db: Сессия базы данных
        
    Returns:
        dict с сообщением об успешном удалении
        
    Raises:
        HTTPException: Если клиент не найден, уже удалён или в статусе limit_exceeded
    """
    try:
        # Получаем клиента
        query = select(CorporateClient).where(CorporateClient.id == client_id)
        result = await db.execute(query)
        client = result.scalar_one_or_none()
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Корпоративный клиент не найден"
            )
        
        if client.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Корпоративный клиент уже удалён"
            )
        
        if client.status == "limit_exceeded":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Невозможно удалить компанию в статусе 'limit_exceeded'. Решите проблему с балансом и попробуйте снова."
            )
        
        if client.status in ["active", "blocked"] and client.finance_company_id:
            try:
                finance_service = FinanceBackendService()
                delete_result = await finance_service.delete_partner_company(
                    company_id=client.finance_company_id,
                    db=db
                )
                
                if not delete_result:
                    logger.warning(f"Failed to delete partner company {client.finance_company_id} in finance backend")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Failed to delete company in finance backend"
                    )
                
                if "error" in delete_result:
                    logger.warning(f"Finance backend error deleting company {client.finance_company_id}: {delete_result['error']}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Finance backend error: {delete_result['error']}"
                    )
                
                logger.info(f"Partner company deleted in finance backend: {client.finance_company_id}")
            except HTTPException:
                raise
            except Exception as finance_err:
                logger.error(f"Error deleting partner company {client.finance_company_id}: {finance_err}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete company in finance backend: {str(finance_err)}"
                )
        
        # Soft delete - устанавливаем timestamp удаления и статус
        from sqlalchemy.sql import func
        client.status = "deleted"
        client.deleted_at = func.now()
        await db.commit()
        
        logger.info(f"Corporate client deleted: {client_id} (company: {client.company_name}, status: {client.status})")
        
        return {
            "message": "Корпоративный клиент успешно удалён",
            "deleted_id": client_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting corporate client {client_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete corporate client: {str(e)}"
        )


async def partner_login_to_finance_backend(
    db: AsyncSession,
) -> dict:
    """
    Логин корпоративного партнёра в финансовый бэкенд.
    Использует TOTP для аутентификации и возвращает токены доступа.
    
    Args:
        db: Сессия базы данных
        
    Returns:
        dict с access_token, refresh_token и token_type
        
    Raises:
        HTTPException: Если произошла ошибка аутентификации
    """
    try:
        finance_service = FinanceBackendService()
        result = await finance_service.partner_login(db=db)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to communicate with finance backend"
            )
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Finance backend authentication failed: {result['error']}"
            )
        
        logger.info("Partner successfully logged into finance backend")
        
        return {
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
            "token_type": result["token_type"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during partner login to finance backend: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to login to finance backend: {str(e)}"
        )


async def create_account_member_in_finance(
    db: AsyncSession,
    cor_id: str,
    first_name: str,
    last_name: str,
    account_id: Optional[int],
    company_id: int,
    limit_amount: Optional[float],
    limit_period: Optional[str]
) -> dict:
    """
    Добавляет пользователя в компанию в финансовом бэкенде.
    Сначала проверяет наличие пользователя в COR-ID системе,
    затем создаёт участника компании в finance backend.
    
    Args:
        db: Сессия базы данных
        cor_id: COR-ID пользователя
        first_name: Имя пользователя (указывает владелец компании)
        last_name: Фамилия пользователя (указывает владелец компании)
        account_id: ID аккаунта в finance backend
        company_id: ID компании в finance backend
        limit_amount: Лимит пользователя
        limit_period: Период лимита (day, week, month)
        
    Returns:
        dict с данными созданного участника
        
    Raises:
        HTTPException: Если пользователь не найден или произошла ошибка
    """
    try:
        # Проверяем существование пользователя в COR-ID системе
        stmt = select(User).where(User.cor_id == cor_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with cor_id {cor_id} not found in COR-ID system"
            )
        

        finance_service = FinanceBackendService()
        result = await finance_service.create_account_member(
            db=db,
            first_name=first_name,
            last_name=last_name,
            cor_id=cor_id,
            account_id=account_id,
            company_id=company_id,
            limit_amount=limit_amount,
            limit_period=limit_period
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to communicate with finance backend"
            )
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Finance backend error: {result['error']}"
            )
        
        logger.info(f"Account member created for user {cor_id}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating account member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create account member: {str(e)}"
        )


# ============================================================================
# Offline QR Code Functions (Офлайн QR коды для заправки)
# ============================================================================

FUEL_STATION_TOTP_INTERVAL=120

async def get_offline_totp_secret(
    user: User,
) -> FuelOfflineTOTPSecretResponse:
    """
    Получение TOTP секрета для настройки офлайн режима
    
    Используется мобильным приложением для получения общего TOTP секрета.
    Приложение должно:
    1. Вызвать этот endpoint один раз при первом логине (если секрета нет локально)
    2. Сохранить totp_secret в защищённом хранилище (Keychain/Keystore)
    3. Использовать сохранённый секрет для генерации TOTP кодов офлайн
    
    Args:
        user: Авторизованный пользователь
        
    Returns:
        FuelOfflineTOTPSecretResponse с секретом для сохранения в приложении
    """
    try:
        # Получаем общий TOTP секрет из конфигурации
        totp_secret = settings.fuel_station_totp_secret
        
        if not totp_secret or totp_secret == "FUEL_STATION_TOTP_SECRET":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Offline TOTP secret not configured. Please set FUEL_STATION_TOTP_SECRET in environment."
            )
        
        logger.info(f"TOTP secret provided to user {user.cor_id} for offline mode setup")
        
        return FuelOfflineTOTPSecretResponse(
            totp_secret=totp_secret,
            totp_interval=TOTPService.TOTP_INTERVAL
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting offline TOTP secret: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get offline TOTP secret: {str(e)}"
        )


async def generate_offline_qr_code(
    user: User,
    company_id: Optional[str] = None,
) -> FuelOfflineQRGenerateResponse:
    """
    Генерация офлайн QR кода (без интернета на стороне клиента)
    
    Для тестов
    
    Args:
        user: Авторизованный пользователь
        
    Returns:
        FuelOfflineQRGenerateResponse с данными для QR кода
    """
    try:
        # Получаем TOTP секрет
        totp_secret = settings.fuel_station_totp_secret
        
        if not totp_secret or totp_secret == "FUEL_STATION_TOTP_SECRET":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Offline TOTP secret not configured"
            )
        
        # Генерируем текущий TOTP код
        totp_service_instance = TOTPService()
        totp_code, time_remaining = totp_service_instance.generate_totp_code(
            totp_secret, 
            interval=FUEL_STATION_TOTP_INTERVAL
        )
        
        # Текущий timestamp
        current_timestamp = int(time.time())
        
        # Формируем данные для QR
        qr_data = FuelOfflineQRData(
            cor_id=user.cor_id,
            totp_code=totp_code,
            timestamp=current_timestamp
        )
        

        import json
        qr_data_string = json.dumps(qr_data.model_dump(), ensure_ascii=False)
        
        # Экранируем строку для безопасной передачи в JSON запросах
        qr_data_string_escaped = qr_data_string.replace('"', '\\"')
        
        logger.info(f"Generated offline QR code for user {user.cor_id}")
        
        return FuelOfflineQRGenerateResponse(
            qr_data=qr_data,
            qr_data_string=qr_data_string_escaped,
            expires_in_seconds=time_remaining,
            totp_interval=FUEL_STATION_TOTP_INTERVAL
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating offline QR code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate offline QR code: {str(e)}"
        )


async def verify_offline_qr_code(
    body: FuelOfflineQRVerifyRequest,
) -> FuelOfflineQRVerifyResponse:
    """
    Верификация офлайн QR кода (без интернета на стороне заправщика)
    
    для тестов
    
    Args:
        body: Данные отсканированного QR кода
        
    Returns:
        FuelOfflineQRVerifyResponse с результатом верификации
    """
    try:
        # Парсим данные QR кода
        import json
        try:
            # Логируем полученную строку для отладки
            logger.debug(f"Received QR data string: {body.qr_data_string}")
            
            # Если строка была экранирована, разэкранируем её
            unescaped_string = body.qr_data_string.replace('\\"', '"')
            
            qr_data_dict = json.loads(unescaped_string)
            qr_data = FuelOfflineQRData(**qr_data_dict)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error in offline QR code: {e}")
            return FuelOfflineQRVerifyResponse(
                is_valid=False,
                message=f"Невалидный JSON формат QR кода: {e}"
            )
        except Exception as e:
            logger.warning(f"Invalid offline QR code format: {e}")
            return FuelOfflineQRVerifyResponse(
                is_valid=False,
                message="Невалидный формат QR кода"
            )
        
        # Получаем TOTP секрет
        totp_secret = settings.fuel_station_totp_secret
        
        if not totp_secret or totp_secret == "FUEL_STATION_TOTP_SECRET":
            return FuelOfflineQRVerifyResponse(
                is_valid=False,
                message="TOTP секрет не настроен"
            )
        
        # Проверяем timestamp (не слишком старый - макс 5 минут)
        current_timestamp = int(time.time())
        timestamp_diff = abs(current_timestamp - qr_data.timestamp)
        
        if timestamp_diff > 300:  # 5 минут
            logger.warning(f"Offline QR code too old: {timestamp_diff}s")
            return FuelOfflineQRVerifyResponse(
                is_valid=False,
                message=f"QR код слишком старый ({timestamp_diff}s)"
            )
        
        # Проверяем TOTP код (с окном ±3 интервала)
        totp_service_instance = TOTPService()
        is_valid_totp = totp_service_instance.verify_totp_code(
            secret=totp_secret,
            code=qr_data.totp_code,
            window=3,
            interval=FUEL_STATION_TOTP_INTERVAL
        )
        
        if not is_valid_totp:
            logger.warning(f"Invalid TOTP code in offline QR: {qr_data.cor_id}")
            return FuelOfflineQRVerifyResponse(
                is_valid=False,
                message="Невалидный TOTP код"
            )
        
        # Всё ОК
        logger.info(f"Offline QR code verified successfully: {qr_data.cor_id}")
        
        return FuelOfflineQRVerifyResponse(
            is_valid=True,
            message="QR код валиден",
            user_cor_id=qr_data.cor_id,
            # company_id=qr_data.company_id,
            verified_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error verifying offline QR code: {e}")
        return FuelOfflineQRVerifyResponse(
            is_valid=False,
            message=f"Ошибка верификации: {str(e)}"
        )


async def add_employee_by_email(
    db: AsyncSession,
    identifier: str,
    first_name: str,
    last_name: str,
    phone_number: str,
    company_id: int,
    account_id: Optional[int],
    limit_amount: Optional[float],
    limit_period: Optional[str],
    invited_by_user_id: str,
    background_tasks,
) -> dict:
    """
    Добавляет сотрудника в компанию с поддержкой трёх сценариев (одно поле identifier):
    1. identifier = cor_id → добавляем сразу (пользователь должен существовать)
    2. identifier = email (существует в системе) → добавляем
    3. identifier = email (пользователь не найден) → создаём приглашение и отправляем письмо
    
    Args:
        db: Сессия БД
        identifier: Email сотрудника или его COR-ID
        first_name: Имя сотрудника
        last_name: Фамилия сотрудника
        phone_number: Телефон сотрудника
        company_id: ID компании в finance backend
        account_id: ID аккаунта в finance backend (опционально)
        limit_amount: Лимит сотрудника
        limit_period: Период лимита
        invited_by_user_id: ID пользователя, пригласившего сотрудника
        background_tasks: BackgroundTasks для отправки писем
        
    Returns:
        dict: результат операции
    """
    from cor_pass.repository.user import person as repository_person
    from cor_pass.repository.fuel import corporate_employee_invitation as repo_invitation
    from cor_pass.services.shared.email import send_employee_invitation_email, send_employee_added_email
    from cor_pass.schemas import AccountMemberResponse
    from sqlalchemy import select

    if not identifier or not identifier.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нужно передать email или cor_id",
        )

    identifier_clean = identifier.strip()
    # Простая эвристика: если есть '@' → email, иначе считаем cor_id
    if "@" in identifier_clean:
        email_lower = identifier_clean.lower()
        cor_id_value = None
    else:
        email_lower = None
        cor_id_value = identifier_clean

    # ===== Сценарий 1: identifier как cor_id =====
    if cor_id_value:
        # Проверяем, что пользователь с таким COR-ID существует
        user_stmt = select(User).where(User.cor_id == cor_id_value)
        user_result = await db.execute(user_stmt)
        user_obj = user_result.scalar_one_or_none()
        if not user_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь с cor_id {cor_id_value} не найден",
            )

        logger.info(f"Adding employee by cor_id={cor_id_value} to company {company_id}")
        result = await create_account_member_in_finance(
            db=db,
            cor_id=cor_id_value,
            first_name=first_name,
            last_name=last_name,
            account_id=account_id,
            company_id=company_id,
            limit_amount=limit_amount,
            limit_period=limit_period,
        )
        account_member = AccountMemberResponse(**result)
        account_member_data = account_member.model_dump()
        # Отправляем уведомление о добавлении
        background_tasks.add_task(
            send_employee_added_email,
            email=user_obj.email,
            first_name=first_name,
            last_name=last_name,
        )
        return {
            "status": "success",
            "message": f"Сотрудник {first_name} {last_name} добавлен в компанию",
            "added_directly": True,
            "cor_id": cor_id_value,
            "account_member": account_member_data
        }

    # ===== Сценарий 2: identifier как email, пользователь существует =====
    user = await repository_person.get_user_by_email(email_lower, db)
    if user:
        logger.info(f"User {email_lower} exists, adding to company {company_id}")

        result = await create_account_member_in_finance(
            db=db,
            cor_id=user.cor_id,
            first_name=first_name,
            last_name=last_name,
            account_id=account_id,
            company_id=company_id,
            limit_amount=limit_amount,
            limit_period=limit_period,
        )
        account_member = AccountMemberResponse(**result)
        account_member_data = account_member.model_dump()

        background_tasks.add_task(
            send_employee_added_email,
            email=user.email,
            first_name=first_name,
            last_name=last_name,
        )

        return {
            "status": "success",
            "message": f"Сотрудник {first_name} {last_name} добавлен в компанию",
            "added_directly": True,
            "cor_id": user.cor_id,
            "account_member": account_member_data
        }

    # ===== Сценарий 3: identifier как email, пользователя нет — создаём приглашение =====
    logger.info(f"User {email_lower} does not exist, creating invitation")

    invitation = await repo_invitation.create_employee_invitation(
        db=db,
        email=email_lower,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        company_id=company_id,
        account_id=account_id,
        limit_amount=limit_amount or 0,
        limit_period=limit_period or "day",
        invited_by_user_id=invited_by_user_id,
    )

    # Отправляем письмо с приглашением
    background_tasks.add_task(
        send_employee_invitation_email,
        email=email_lower,
        first_name=first_name,
        last_name=last_name,
    )

    # Возвращаем приглашение в том же формате, что и pending_invitations
    invitation_payload = {
        "id": invitation.id,
        "email": invitation.email,
        "first_name": invitation.first_name,
        "last_name": invitation.last_name,
        "phone_number": invitation.phone_number,
        "company_id": invitation.company_id,
        "account_id": invitation.account_id,
        "limit_amount": invitation.limit_amount,
        "limit_period": invitation.limit_period,
        "invited_by": invitation.invited_by,
        "is_used": invitation.is_used,
        "created_at": invitation.created_at,
        "used_at": invitation.used_at,
    }

    return {
        "status": "pending",
        "message": f"Приглашение отправлено на {email_lower}. Сотрудник будет добавлен после регистрации.",
        "added_directly": False,
        "invitation": invitation_payload,
    }


async def get_company_invitations(
    db: AsyncSession,
    company_id: int,
):
    """
    Возвращает список неиспользованных приглашений по компании.
    """
    from cor_pass.repository.fuel import corporate_employee_invitation as repo_invitation

    invitations = await repo_invitation.get_invitations_by_company(db=db, company_id=company_id)
    return invitations


async def delete_company_invitation(
    db: AsyncSession,
    invitation_id: str,
):
    """
    Удаляет неподтверждённое приглашение.
    """
    from cor_pass.repository.fuel import corporate_employee_invitation as repo_invitation

    deleted = await repo_invitation.delete_pending_invitation(db=db, invitation_id=invitation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Приглашение не найдено или уже использовано",
        )
    return {"status": "deleted", "invitation_id": invitation_id}


async def get_account_members_from_finance(
    finance_id: str,
    db: AsyncSession,
):
    """
    Получает список сотрудников компании из финансового бэкенда.
    
    Args:
        finance_id: ID или COR-ID компании в финансовом бэкенде
        db: Database session
        
    Returns:
        Список сотрудников или None если ошибка при обращении к финбэку
    """
    import httpx
    from cor_pass.config.config import settings
    
    try:
        # Получаем конфиг финансового бэкенда
        config = await get_active_finance_backend_config(db=db)
        if not config or not config.api_endpoint:
            logger.warning("Finance backend config not found")
            return None
        
        # Формируем URL для получения сотрудников
        base_url = config.api_endpoint.rstrip('/')
        url = f"{base_url}/v1/partner_companies/{finance_id}/account-members"
        
        # Подготавливаем заголовки с авторизацией
        headers = {}
        # if config.totp_secret:
        #     pass

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                members_data = response.json()
                logger.info(f"Got {len(members_data) if isinstance(members_data, list) else 0} members from finance backend")
                return members_data
            else:
                logger.error(
                    f"Finance backend error: {response.status_code} - {response.text}"
                )
                return None
                
    except httpx.RequestError as e:
        logger.error(f"Error connecting to finance backend: {e}")
        return None
    except Exception as e:
        logger.error(f"Error getting account members from finance: {e}", exc_info=True)
        return None

