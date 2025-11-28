"""
API маршруты для работы с топливной системой QR кодов
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.database.db import get_db
from cor_pass.database.models import User
from cor_pass.services.shared.access import user_access, admin_access
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
    FuelOfflineQRGenerateResponse,
    FuelOfflineQRVerifyRequest,
    FuelOfflineQRVerifyResponse,
    FuelOfflineTOTPSecretResponse,
    FinancePartnerLoginResponse,
    CreateAccountMemberRequest,
    AccountMemberResponse,
)
from cor_pass.repository.fuel import fuel_station

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


# ============================================================================
# Corporate Client Routes (Корпоративные клиенты)
# ============================================================================

@router.post(
    "/corporate-client/request",
    response_model=CorporateClientResponse,
    summary="Подача заявки на регистрацию корпоративного клиента",
    description="""
    Создаёт заявку на регистрацию компании как корпоративного клиента (статус pending).
    Заявка требует подтверждения администратором / юристом.
    
    **Важно:** Один пользователь может подавать заявки на несколько компаний.
    Проверяется только уникальность ЄДРПОУ/ИНН (tax_id).
    
    Параметры:
    - **company_format**: Форма підприємства (ТОВ, ФОП, ПП и т.д.)
    - **company_name**: Полное название компании
    - **address**: Юридический адрес
    - **phone_number**: Контактный телефон
    - **email**: Email компании
    - **tax_id**: ЄДРПОУ/ИНН (должен быть уникальным)
    
    Требует авторизации пользователя.
    
    **Возможные ошибки:**
    - 400: Компания с таким ЄДРПОУ/ИНН уже зарегистрирована
    """
)
async def create_corporate_request(
    body: CorporateClientCreate,
    user: User = Depends(user_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Подача заявки на регистрацию корпоративного клиента.
    Один пользователь может владеть несколькими компаниями.
    """
    return await fuel_station.create_corporate_client_request(
        body=body,
        user=user,
        db=db
    )


@router.get(
    "/corporate-client/my-request",
    response_model=list[CorporateClientResponse],
    summary="Список своих компаний и заявок",
    description="""
    Возвращает список всех компаний и заявок текущего пользователя.
    
    Один пользователь может владеть несколькими компаниями.
    Список отсортирован по дате создания (новые первые).
    
    Возможные статусы каждой компании:
    - **pending**: Заявка ожидает рассмотрения
    - **active**: Заявка одобрена, компания активна
    - **rejected**: Заявка отклонена (с указанием причины в `rejection_reason`)
    - **blocked**: Компания заблокирована (с указанием причины в `rejection_reason`)
    - **limit_exceeded**: Превышен лимит расходов
    
    Если у пользователя нет заявок, возвращается пустой массив [].
    
    Требует авторизации пользователя.
    """
)
async def get_my_corporate_request(
    user: User = Depends(user_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Получение списка всех компаний/заявок текущего пользователя
    """
    return await fuel_station.get_user_corporate_client(
        user=user,
        db=db
    )


@router.post(
    "/admin/corporate-requests/{request_id}/approve",
    response_model=CorporateClientResponse,
    summary="Подтверждение заявки (админ)",
    description="""
    Подтверждает заявку на регистрацию — переводит статус pending → active.
    После подтверждения:
    1. Создаётся запись в finance backend
    2. Статус изменяется на active
    3. Заполняется finance_company_id
    
    Только для администраторов.
    """
)
async def approve_corporate_request(
    request_id: str,
    user: User = Depends(admin_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Подтверждение заявки — перевод в статус active
    """
    return await fuel_station.approve_corporate_client_request(
        request_id=request_id,
        admin_user=user,
        db=db
    )


@router.post(
    "/admin/corporate-requests/{request_id}/reject",
    response_model=CorporateClientResponse,
    summary="Отклонение заявки (админ)",
    description="""
    Отклоняет заявку — переводит статус pending → rejected с указанием причины.
    
    Только для администраторов.
    """
)
async def reject_corporate_request(
    request_id: str,
    body: CorporateClientReject,
    user: User = Depends(admin_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Отклонение заявки — перевод в статус rejected
    """
    return await fuel_station.reject_corporate_client_request(
        request_id=request_id,
        body=body,
        admin_user=user,
        db=db
    )


@router.post(
    "/admin/corporate-clients/{client_id}/block",
    response_model=CorporateClientResponse,
    summary="Блокировка корпоративного клиента (админ)",
    description="""
    Блокирует компанию — переводит статус active → blocked.
    
    Только для администраторов.
    """
)
async def block_corporate_client(
    client_id: str,
    body: CorporateClientBlock,
    user: User = Depends(admin_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Блокировка компании — перевод в статус blocked
    """
    return await fuel_station.block_corporate_client(
        client_id=client_id,
        body=body,
        admin_user=user,
        db=db
    )


@router.get(
    "/admin/corporate-clients",
    response_model=list[CorporateClientWithOwner],
    summary="Список корпоративных клиентов (админ)",
    description="""
    Возвращает список корпоративных клиентов и заявок.
    Можно фильтровать по статусу.
    
    Параметры:
    - **status**: Фильтр по статусу (pending, active, blocked, rejected, limit_exceeded). Если не указан - показывает всех клиентов
    - **skip**: Пропустить записей (пагинация)
    - **limit**: Максимум записей (пагинация, максимум 100)
    
    Только для администраторов.
    """
)
async def get_corporate_clients(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    user: User = Depends(admin_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Получение списка корпоративных клиентов (админ)
    """
    return await fuel_station.get_corporate_clients(
        db=db,
        status_filter=status,
        skip=skip,
        limit=limit
    )


@router.patch(
    "/admin/corporate-clients/{client_id}",
    response_model=CorporateClientResponse,
    summary="Обновление данных корпоративного клиента (админ)",
    description="""
    Обновляет данные корпоративного клиента.
    Можно обновить название, адрес, телефон, email.
    
    Только для администраторов.
    """
)
async def update_corporate_client(
    client_id: str,
    body: CorporateClientUpdate,
    user: User = Depends(admin_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Обновление корпоративного клиента (админ)
    """
    return await fuel_station.update_corporate_client(
        client_id=client_id,
        body=body,
        db=db
    )


@router.delete(
    "/admin/corporate-clients/{client_id}",
    summary="Удаление корпоративного клиента (админ)",
    description="""
    Удаляет корпоративного клиента из системы.
    
    **Внимание:** Удаление необратимо!
    
    Только для администраторов.
    """
)
async def delete_corporate_client(
    client_id: str,
    user: User = Depends(admin_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Удаление корпоративного клиента (админ)
    """
    return await fuel_station.delete_corporate_client(
        client_id=client_id,
        db=db
    )


@router.post(
    "/partner/finance-login",
    response_model=FinancePartnerLoginResponse,
    summary="Логин партнёра в финансовый бэкенд",
    description="""
    Аутентифицирует корпоративного партнёра в финансовом бэкенде используя TOTP.
    Возвращает токены доступа (access_token и refresh_token) от финансового бэкенда.

    """
)
async def partner_finance_login(
    user: User = Depends(user_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Логин корпоративного партнёра в финансовый бэкенд
    """
    return await fuel_station.partner_login_to_finance_backend(db=db)


@router.post(
    "/partner/account-member",
    response_model=AccountMemberResponse,
    summary="Добавить пользователя в компанию",
    description="""
    Добавляет пользователя в компанию в финансовом бэкенде.
    """
)
async def create_account_member(
    request: CreateAccountMemberRequest,
    user: User = Depends(user_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Добавление пользователя в компанию в finance backend
    """
    return await fuel_station.create_account_member_in_finance(
        db=db,
        cor_id=request.cor_id,
        first_name=request.first_name,
        last_name=request.last_name,
        account_id=request.account_id,
        company_id=request.company_id,
        limit_amount=request.limit_amount,
        limit_period=request.limit_period
    )


# ==================== Offline QR Code Routes ====================

@router.get(
    "/offline/totp-secret",
    response_model=FuelOfflineTOTPSecretResponse,
    summary="Получить TOTP секрет для офлайн верификации",
    description="""
    Возвращает TOTP секрет для настройки офлайн верификации на заправке.
    
    Используется для первоначальной настройки системы офлайн QR-кодов:
    - Клиент получает секрет
    - Сохраняет его локально
    - Использует для генерации TOTP кодов в офлайн режиме
    
    Доступно только авторизованным пользователям.
    """
)
async def get_offline_totp_secret(
    user: User = Depends(user_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Получение TOTP секрета для офлайн верификации
    """
    return await fuel_station.get_offline_totp_secret(
        user=user
    )


@router.post(
    "/offline/generate-qr",
    response_model=FuelOfflineQRGenerateResponse,
    summary="Сгенерировать офлайн QR-код (демо)",
    description="""
    Для теста генерации офлайн QR-кода.

    """
)
async def generate_offline_qr(
    user: User = Depends(user_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Генерация офлайн QR-кода 
    """
    return await fuel_station.generate_offline_qr_code(
        user=user
    )


@router.post(
    "/offline/generate-qr-image",
    response_class=Response,
    summary="Сгенерировать офлайн QR-код (изображение)",
    description="""
    Генерирует офлайн QR-код и возвращает его как PNG изображение.
    
    Content-Type: image/png
    """
)
async def generate_offline_qr_image(
    user: User = Depends(user_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Генерация офлайн QR-кода как PNG изображение
    """
    # Получаем данные QR-кода
    qr_data = await fuel_station.generate_offline_qr_code(user=user)
    
    # Генерируем QR-код из JSON строки
    import qrcode
    import io
    import base64
    
    # Создаем QR-код из JSON данных
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data.qr_data_string)
    qr.make(fit=True)
    
    # Создаем изображение
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Конвертируем в bytes
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_bytes = buffer.getvalue()
    
    return Response(
        content=qr_bytes,
        media_type="image/png",
        headers={"Content-Disposition": "inline; filename=offline-qr.png"}
    )


@router.post(
    "/offline/verify-qr",
    response_model=FuelOfflineQRVerifyResponse,
    summary="Проверить офлайн QR-код",
    description="""
    Тест проверка офлайн QR-кода.
    """
)
async def verify_offline_qr(
    body: FuelOfflineQRVerifyRequest,
    user: User = Depends(user_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Верификация офлайн QR-кода
    """
    return await fuel_station.verify_offline_qr_code(
        body=body
    )
