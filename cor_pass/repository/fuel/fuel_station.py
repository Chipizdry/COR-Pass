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


async def get_corporate_client_requests(
    db: AsyncSession,
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> list[CorporateClientWithOwner]:
    """
    Получение списка корпоративных клиентов (для админа)
    Если status_filter не указан, показывает всех клиентов
    
    Args:
        db: Сессия базы данных
        status_filter: Фильтр по статусу (pending, active, blocked, rejected, limit_exceeded)
        skip: Пропустить записей
        limit: Максимум записей
        
    Returns:
        Список клиентов с информацией о владельцах
    """
    try:
        query = select(CorporateClient).join(
            User, CorporateClient.owner_cor_id == User.cor_id
        ).where(CorporateClient.deleted_at.is_(None))
        
        if status_filter:
            query = query.where(CorporateClient.status == status_filter)
        
        query = query.order_by(CorporateClient.created_at.desc())
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        clients = result.scalars().all()
        
        # Формируем ответ с информацией о владельцах
        response = []
        for client in clients:
            # Загружаем пользователя
            user_query = select(User).where(User.cor_id == client.owner_cor_id)
            user_result = await db.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            client_dict = CorporateClientResponse.model_validate(client).model_dump()
            # TODO: Расшифровать first_name/last_name из Profile когда понадобится
            client_dict["owner_first_name"] = None  # user.first_name if user else None
            client_dict["owner_last_name"] = None  # user.last_name if user else None
            client_dict["owner_email"] = user.email if user else None
            
            response.append(CorporateClientWithOwner(**client_dict))
        
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
        
        company_response = await finance_service.create_partner_company(
            name=client.company_name,
            company_format=client.company_format,
            phone_number=client.phone_number,
            tax_id=client.tax_id,
            address=client.address,
            owner_id_or_cor_id=client.owner_cor_id,
            email=client.email,
            start_balance=0.0,
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
        
        await db.commit()
        await db.refresh(client)
        
        logger.info(f"Corporate client approved: {client.id}, finance_company_id: {finance_company_id}")
        
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
    
    Args:
        client_id: ID клиента
        body: Причина блокировки (опционально)
        admin_user: Администратор
        db: Сессия базы данных
        
    Returns:
        CorporateClientResponse с обновлённой записью
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
        
        client.status = "blocked"
        client.reviewed_by = admin_user.cor_id
        client.reviewed_at = datetime.utcnow()
        if body.reason:
            client.rejection_reason = body.reason  # Используем то же поле
        
        await db.commit()
        await db.refresh(client)
        
        logger.info(f"Corporate client blocked: {client_id}")
        
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


async def get_corporate_clients(
    db: AsyncSession,
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
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
    return await get_corporate_client_requests(db, status_filter, skip, limit)


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


async def delete_corporate_client(
    client_id: str,
    db: AsyncSession,
) -> dict:
    """
    Удаление корпоративного клиента (админ)
    
    Args:
        client_id: ID клиента для удаления
        db: Сессия базы данных
        
    Returns:
        dict с сообщением об успешном удалении
        
    Raises:
        HTTPException: Если клиент не найден или ошибка БД
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
        
        # Soft delete - устанавливаем timestamp удаления
        from sqlalchemy.sql import func
        client.deleted_at = func.now()
        await db.commit()
        
        logger.info(f"Corporate client deleted: {client_id} (company: {client.company_name})")
        
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
    account_id: int,
    company_id: int,
    limit_amount: float,
    limit_period: str
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
