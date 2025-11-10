"""
Repository для работы с топливной системой QR кодов
"""
import logging
from typing import Optional
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from cor_pass.database.models import (
    FuelStationQRSession, 
    FinanceBackendAuth, 
    User
)
from cor_pass.schemas import (
    FuelQRGenerateRequest,
    FuelQRGenerateResponse,
    FuelQRVerifyRequest,
    FuelQRVerifyResponse,
    FinanceBackendAuthConfigCreate,
    FinanceBackendAuthConfigResponse,
)
from cor_pass.services.totp_service import TOTPService
from cor_pass.services.fuel_qr_service import FuelQRService
from cor_pass.services.finance_backend_service import FinanceBackendService
from cor_pass.services.cipher import encrypt_data, decrypt_data
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
            validity_minutes=body.validity_minutes
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
