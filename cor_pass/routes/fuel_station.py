"""
API маршруты для работы с топливной системой QR кодов
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.database.db import get_db
from cor_pass.database.models import User
from cor_pass.services.access import user_access, admin_access
from cor_pass.schemas import (
    FuelQRGenerateRequest,
    FuelQRGenerateResponse,
    FuelQRVerifyRequest,
    FuelQRVerifyResponse,
    FinanceBackendAuthConfigCreate,
    FinanceBackendAuthConfigResponse,
)
from cor_pass.repository import fuel_station

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/generate-qr",
    response_model=FuelQRGenerateResponse,
    summary="Генерация QR кода для заправки",
    description="""
    Генерирует защищённый одноразовый QR код для корпоративного клиента, который можно использовать
    на заправке. QR код содержит TOTP код, timestamp token и уникальный
    session token для защиты от повторного использования.
    
    - **validity_minutes**: Опционально, время действия QR кода в минутах (по умолчанию 5)
    
    Требует авторизации пользователя.
    """
)
async def generate_qr_code(
    body: FuelQRGenerateRequest,
    user: User = Depends(user_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Генерация QR кода для авторизованного корпоративного клиента
    """
    return await fuel_station.generate_qr_code_for_user(
        body=body,
        db=db,
        user=user
    )


@router.post(
    "/verify-qr",
    response_model=FuelQRVerifyResponse,
    summary="Верификация QR кода заправщиком",
    description="""
    Проверяет валидность QR кода и запрашивает информацию о лимите пользователя
    из финансового бэкенда. 
    """
)
async def verify_qr_code(
    body: FuelQRVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Верификация QR кода и проверка лимита пользователя
    
    """
    return await fuel_station.verify_qr_code_and_check_limit(
        body=body,
        db=db
    )


@router.post(
    "/admin/finance-config",
    response_model=FinanceBackendAuthConfigResponse,
    summary="Создание конфигурации финансового бэкенда (админ)",
    description="""
    Создаёт конфигурацию для интеграции с финансовым бэкендом.
    Автоматически деактивирует все предыдущие конфигурации.
    
    Параметры:
    - **service_name**: Название сервиса (например, "Finance Backend")
    - **api_endpoint**: URL эндпоинта для проверки лимитов
    - **totp_secret**: Общий TOTP секрет для server-to-server аутентификации
    - **totp_interval**: Интервал TOTP в секундах (по умолчанию 30)
    
    Только администраторы могут создавать и изменять конфигурацию.
    """
)
async def create_finance_backend_config(
    body: FinanceBackendAuthConfigCreate,
    user: User = Depends(admin_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Создание конфигурации для финансового бэкенда
    """
    return await fuel_station.create_finance_backend_config(
        body=body,
        db=db
    )


@router.get(
    "/admin/finance-config",
    response_model=Optional[FinanceBackendAuthConfigResponse],
    summary="Получение конфигурации финансового бэкенда (админ)",
    description="""
    Возвращает активную конфигурацию для интеграции с финансовым бэкендом.
    """
)
async def get_finance_backend_config(
    user: User = Depends(admin_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Получение активной конфигурации финансового бэкенда (админ)
    """
    return await fuel_station.get_active_finance_backend_config(db=db)
