"""
Роуты для доступа к медицинским данным через систему медкарт.
Позволяет просматривать данные других пользователей при наличии соответствующего доступа.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional

from cor_pass.database.db import get_db
from cor_pass.database.models import (
    User, MedicalCard, MedicalCardAccess, MedicalCardAccessLevel,
    Medicine, SibionicsDevice
)
from cor_pass.repository.blood_pressure import get_measurements_paginated
from cor_pass.repository.medicine import get_user_medicines_with_schedules
from cor_pass.repository import sibionics_repository
from cor_pass.repository.blood_pressure import create_measurement
from cor_pass.schemas import (
    PaginatedBloodPressureResponse,
    BloodPressureMeasurementResponse,
    BloodPressureMeasurementCreate,
    MedicineRead,
    OralMedicine,
    OintmentMedicine,
    SolutionMedicine,
    SibionicsDeviceResponse,
    SibionicsGlucoseResponse,
)
from cor_pass.services.auth import auth_service
from cor_pass.services.access import user_access
from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix="/v1/medical-cards/data",
    tags=["Medical Card Data Access"]
)


async def verify_medical_card_access(
    card_id: str,
    current_user: User,
    db: AsyncSession,
    required_level: Optional[MedicalCardAccessLevel] = None
) -> MedicalCard:
    """
    Проверяет доступ пользователя к медкарте.
    
    Args:
        card_id: ID медицинской карты
        current_user: Текущий пользователь
        db: Сессия базы данных
        required_level: Требуемый минимальный уровень доступа (VIEW, EDIT, SHARE)
    
    Returns:
        MedicalCard: Объект медицинской карты
        
    Raises:
        HTTPException: Если карта не найдена или доступ запрещен
    """
    # Получаем медкарту
    query = select(MedicalCard).where(
        and_(
            MedicalCard.id == card_id,
            MedicalCard.is_active == True
        )
    )
    result = await db.execute(query)
    card = result.scalar_one_or_none()
    
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Медицинская карта не найдена"
        )
    
    # Если это владелец карты - доступ разрешен
    if card.owner_cor_id == current_user.cor_id:
        return card
    
    # Проверяем права доступа
    access_query = select(MedicalCardAccess).where(
        and_(
            MedicalCardAccess.medical_card_id == card_id,
            MedicalCardAccess.user_cor_id == current_user.cor_id,
            MedicalCardAccess.is_accepted == True,
            MedicalCardAccess.is_active == True
        )
    )
    result = await db.execute(access_query)
    access = result.scalar_one_or_none()
    
    if not access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас нет доступа к этой медицинской карте"
        )
    
    # Проверяем, не истек ли срок доступа
    if access.expires_at and access.expires_at < datetime.now(access.expires_at.tzinfo):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Срок доступа к медицинской карте истек"
        )
    
    # Проверяем уровень доступа, если требуется
    if required_level:
        level_hierarchy = {
            MedicalCardAccessLevel.VIEW: 1,
            MedicalCardAccessLevel.EDIT: 2,
            MedicalCardAccessLevel.SHARE: 3
        }
        
        if level_hierarchy.get(access.access_level, 0) < level_hierarchy.get(required_level, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Требуется уровень доступа: {required_level.value}"
            )
    
    return card


@router.get(
    "/{card_id}/blood-pressure",
    response_model=PaginatedBloodPressureResponse,
    dependencies=[Depends(user_access)],
    summary="Получить измерения давления из медицинской карты",
    description="""
    Получает измерения артериального давления и пульса из медицинской карты другого пользователя.
    
    **Требования:**
    - Пользователь должен иметь принятый доступ к медкарте (любой уровень: view/edit/share)
    - Доступ не должен быть истекшим
    - Медкарта должна быть активна
    
    **Доступные периоды:**
    - `all` — все измерения
    - `week` — последние 7 дней
    - `month` — текущий месяц
    - `custom` — произвольный период (требуется start_date и end_date)
    """
)
async def get_blood_pressure_by_card(
    card_id: str,
    page: int = Query(1, ge=1, description="Номер страницы (начиная с 1)"),
    page_size: int = Query(10, ge=1, le=1000, description="Количество элементов на странице"),
    period: Optional[str] = Query(
        "all",
        pattern="^(all|week|month|custom)$",
        description="Период выборки: all, week, month, custom"
    ),
    start_date: Optional[datetime] = Query(
        None,
        description="Начальная дата (только если period=custom), ISO 8601, например '2023-01-01T00:00:00'"
    ),
    end_date: Optional[datetime] = Query(
        None,
        description="Конечная дата (только если period=custom), ISO 8601, например '2023-01-01T00:00:00'"
    ),
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает список измерений давления и пульса из медицинской карты с пагинацией и фильтрами.
    """
    # Проверяем доступ к медкарте
    card = await verify_medical_card_access(
        card_id=card_id,
        current_user=current_user,
        db=db,
        required_level=MedicalCardAccessLevel.VIEW  # Минимум VIEW для чтения данных
    )
    
    # Получаем владельца карты
    owner_query = select(User).where(User.cor_id == card.owner_cor_id)
    result = await db.execute(owner_query)
    owner = result.scalar_one_or_none()
    
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Владелец медицинской карты не найден"
        )
    
    # Получаем измерения владельца карты
    measurements, total = await get_measurements_paginated(
        db=db,
        user_id=owner.id,
        page=page,
        page_size=page_size,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )
    
    logger.info(
        f"User {current_user.cor_id} accessed blood pressure data from card {card_id} "
        f"(owner: {card.owner_cor_id}), page {page}, total: {total}"
    )
    
    return PaginatedBloodPressureResponse(
        items=measurements,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{card_id}/blood-pressure/latest",
    response_model=BloodPressureMeasurementResponse,
    dependencies=[Depends(user_access)],
    summary="Получить последнее измерение давления из медкарты",
    description="""
    Получает самое последнее измерение артериального давления из медицинской карты.
    
    Полезно для быстрого просмотра актуального состояния пациента.
    """
)
async def get_latest_blood_pressure_by_card(
    card_id: str,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает последнее измерение давления из медицинской карты.
    """
    # Проверяем доступ к медкарте
    card = await verify_medical_card_access(
        card_id=card_id,
        current_user=current_user,
        db=db,
        required_level=MedicalCardAccessLevel.VIEW
    )
    
    # Получаем владельца карты
    owner_query = select(User).where(User.cor_id == card.owner_cor_id)
    result = await db.execute(owner_query)
    owner = result.scalar_one_or_none()
    
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Владелец медицинской карты не найден"
        )
    
    # Получаем последнее измерение (первая страница, 1 элемент)
    measurements, total = await get_measurements_paginated(
        db=db,
        user_id=owner.id,
        page=1,
        page_size=1,
        period="all",
        start_date=None,
        end_date=None,
    )
    
    if not measurements:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Измерения давления не найдены"
        )
    
    logger.info(
        f"User {current_user.cor_id} accessed latest blood pressure from card {card_id} "
        f"(owner: {card.owner_cor_id})"
    )
    
    return measurements[0]


@router.post(
    "/{card_id}/blood-pressure",
    response_model=BloodPressureMeasurementResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_access)],
    summary="Добавить измерение давления в медицинскую карту",
    description="""
    Добавляет новое измерение артериального давления и пульса в медицинскую карту.
    
    **Требования:**
    - Пользователь должен иметь уровень доступа EDIT или SHARE к медкарте
    - Доступ не должен быть истекшим
    - Медкарта должна быть активна
    
    **Применение:**
    - Врач добавляет измерения для пациента
    - Родственник добавляет данные за пожилого человека
    - Медсестра вносит данные с медицинского оборудования
    """
)
async def create_blood_pressure_for_card(
    card_id: str,
    body: BloodPressureMeasurementCreate,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Добавляет новое измерение давления в медицинскую карту.
    
    Требуется уровень доступа EDIT или SHARE.
    """

    card = await verify_medical_card_access(
        card_id=card_id,
        current_user=current_user,
        db=db,
        required_level=MedicalCardAccessLevel.EDIT  
    )
    

    owner_query = select(User).where(User.cor_id == card.owner_cor_id)
    result = await db.execute(owner_query)
    owner = result.scalar_one_or_none()
    
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Владелец медицинской карты не найден"
        )
    
    new_measurement = await create_measurement(db=db, body=body, user=owner)
    
    logger.info(
        f"User {current_user.cor_id} created blood pressure measurement for card {card_id} "
        f"(owner: {card.owner_cor_id}): {body.systolic_pressure}/{body.diastolic_pressure}, "
        f"pulse: {body.pulse}"
    )
    
    return BloodPressureMeasurementResponse(
        systolic_pressure=new_measurement.systolic_pressure,
        diastolic_pressure=new_measurement.diastolic_pressure,
        pulse=new_measurement.pulse,
        measured_at=new_measurement.measured_at,
        id=new_measurement.id,
        user_id=new_measurement.user_id,
        created_at=new_measurement.created_at,
    )


@router.get(
    "/{card_id}/medicines",
    response_model=List[MedicineRead],
    dependencies=[Depends(user_access)],
    summary="Получить список лекарств из медицинской карты",
    description="""
    Получает список всех лекарств и расписаний приема из медицинской карты другого пользователя.
    
    **Требования:**
    - Пользователь должен иметь принятый доступ к медкарте (уровень VIEW или выше)
    - Доступ не должен быть истекшим
    """
)
async def get_medicines_by_card(
    card_id: str,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает список лекарств из медицинской карты с расписаниями приема.
    """
    # Проверяем доступ к медкарте
    card = await verify_medical_card_access(
        card_id=card_id,
        current_user=current_user,
        db=db,
        required_level=MedicalCardAccessLevel.VIEW
    )
    
    # Получаем владельца карты
    owner_query = select(User).where(User.cor_id == card.owner_cor_id)
    result = await db.execute(owner_query)
    owner = result.scalar_one_or_none()
    
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Владелец медицинской карты не найден"
        )
    
    # Получаем лекарства владельца карты
    medicines = await get_user_medicines_with_schedules(db=db, user=owner)
    
    result = []
    for med in medicines:
        # Создаем method_data в зависимости от типа метода приема
        method_data = None
        
        try:
            if med.intake_method == "Oral":
                method_data = OralMedicine(
                    intake_method=med.intake_method,
                    dosage=med.dosage,
                    unit=med.unit,
                    concentration=med.concentration,
                    volume=med.volume,
                )
            elif med.intake_method == "Ointment/suppositories":
                method_data = OintmentMedicine(
                    intake_method=med.intake_method,
                    concentration=med.concentration,
                    dosage=med.dosage,
                    unit=med.unit,
                    volume=med.volume,
                )
            elif med.intake_method in ["Intravenous", "Intramuscularly", "Solutions"]:
                method_data = SolutionMedicine(
                    intake_method=med.intake_method,
                    concentration=med.concentration,
                    volume=med.volume,
                    dosage=med.dosage,
                    unit=med.unit,
                )
        except Exception as e:
            logger.warning(
                f"Failed to create method_data for medicine {med.id} "
                f"(method: {med.intake_method}): {str(e)}"
            )
            # Если не удалось создать метод, пропускаем это лекарство
            continue

        result.append(
            MedicineRead(
                id=med.id,
                name=med.name,
                active_substance=med.active_substance,
                method_data=method_data,
                schedules=med.schedules,
                created_at=med.created_at,
                updated_at=med.updated_at,
            )
        )
    
    logger.info(
        f"User {current_user.cor_id} accessed medicines from card {card_id} "
        f"(owner: {card.owner_cor_id}), total: {len(result)}"
    )
    
    return result


# @router.get(
#     "/{card_id}/glucose/devices",
#     response_model=List[SibionicsDeviceResponse],
#     dependencies=[Depends(user_access)],
#     summary="Получить список устройств CGM из медкарты",
#     description="""
#     Получает список устройств непрерывного мониторинга глюкозы (CGM) 
#     из медицинской карты другого пользователя.
    
#     **Требования:**
#     - Пользователь должен иметь принятый доступ к медкарте (уровень VIEW или выше)
#     - У владельца карты должны быть подключенные устройства SIBIONICS CGM
#     """
# )
# async def get_glucose_devices_by_card(
#     card_id: str,
#     current_user: User = Depends(auth_service.get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     Возвращает список устройств CGM из медицинской карты.
#     """
#     # Проверяем доступ к медкарте
#     card = await verify_medical_card_access(
#         card_id=card_id,
#         current_user=current_user,
#         db=db,
#         required_level=MedicalCardAccessLevel.VIEW
#     )
    
#     # Получаем владельца карты
#     owner_query = select(User).where(User.cor_id == card.owner_cor_id)
#     result = await db.execute(owner_query)
#     owner = result.scalar_one_or_none()
    
#     if not owner:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Владелец медицинской карты не найден"
#         )
    
#     # Получаем авторизацию SIBIONICS владельца
#     auth = await sibionics_repository.get_user_auth_by_user_id(
#         db=db,
#         user_id=owner.id
#     )
    
#     if not auth:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="У владельца карты не подключены устройства SIBIONICS CGM"
#         )
    
#     # Получаем устройства
#     devices = await sibionics_repository.get_devices_by_auth_id(
#         db=db,
#         auth_id=auth.id
#     )
    
#     logger.info(
#         f"User {current_user.cor_id} accessed glucose devices from card {card_id} "
#         f"(owner: {card.owner_cor_id}), devices: {len(devices)}"
#     )
    
#     return [SibionicsDeviceResponse.model_validate(device) for device in devices]


# @router.get(
#     "/{card_id}/glucose/devices/{device_id}/data",
#     response_model=List[SibionicsGlucoseResponse],
#     dependencies=[Depends(user_access)],
#     summary="Получить данные глюкозы из устройства CGM",
#     description="""
#     Получает данные непрерывного мониторинга глюкозы с конкретного устройства
#     из медицинской карты другого пользователя.
    
#     **Параметры:**
#     - `device_id` - ID устройства в БД (получить через `/glucose/devices`)
#     - `start_time` - начало периода выборки (опционально)
#     - `end_time` - конец периода выборки (опционально)
#     - `limit` - максимальное количество записей (по умолчанию 1000)
    
#     **Требования:**
#     - Пользователь должен иметь принятый доступ к медкарте (уровень VIEW или выше)
#     """
# )
# async def get_glucose_data_by_card(
#     card_id: str,
#     device_id: str,
#     start_time: Optional[datetime] = Query(None, description="Начало периода (ISO 8601)"),
#     end_time: Optional[datetime] = Query(None, description="Конец периода (ISO 8601)"),
#     limit: int = Query(1000, ge=1, le=10000, description="Максимальное количество записей"),
#     current_user: User = Depends(auth_service.get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     Возвращает данные глюкозы с устройства CGM из медицинской карты.
#     """
#     # Проверяем доступ к медкарте
#     card = await verify_medical_card_access(
#         card_id=card_id,
#         current_user=current_user,
#         db=db,
#         required_level=MedicalCardAccessLevel.VIEW
#     )
    
#     # Получаем владельца карты
#     owner_query = select(User).where(User.cor_id == card.owner_cor_id)
#     result = await db.execute(owner_query)
#     owner = result.scalar_one_or_none()
    
#     if not owner:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Владелец медицинской карты не найден"
#         )
    
#     # Получаем устройство и проверяем, что оно принадлежит владельцу карты
#     device = await sibionics_repository.get_device_by_id(db=db, device_db_id=device_id)
    
#     if not device:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Устройство не найдено"
#         )
    
#     # Проверяем, что устройство принадлежит владельцу карты
#     auth = await sibionics_repository.get_user_auth_by_user_id(
#         db=db,
#         user_id=owner.id
#     )
    
#     if not auth or device.auth_id != auth.id:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Устройство не принадлежит владельцу медицинской карты"
#         )
    
#     # Получаем данные глюкозы
#     glucose_data = await sibionics_repository.get_glucose_data(
#         db=db,
#         device_db_id=device_id,
#         start_time=start_time,
#         end_time=end_time,
#         limit=limit
#     )
    
#     logger.info(
#         f"User {current_user.cor_id} accessed glucose data from card {card_id} "
#         f"(owner: {card.owner_cor_id}), device: {device_id}, records: {len(glucose_data)}"
#     )
    
#     return [SibionicsGlucoseResponse.model_validate(record) for record in glucose_data]
