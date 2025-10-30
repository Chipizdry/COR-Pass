"""
Репозиторий для работы с медицинскими картами
"""
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from fastapi import HTTPException, status

from cor_pass.database.models import (
    MedicalCard,
    MedicalCardAccess,
    MedicalCardAccessLevel,
    MedicalCardPurpose,
    User,
    Profile,
)
from cor_pass.schemas import (
    MedicalCardUpdate,
    MedicalCardAccessCreate,
)


async def create_medical_card_for_user(
    user_cor_id: str,
    db: AsyncSession,
) -> MedicalCard:
    """
    Создание медицинской карты для нового пользователя.
    Вызывается автоматически при регистрации пользователя.
    
    Args:
        user_cor_id: COR ID пользователя
        db: Сессия базы данных
        
    Returns:
        Созданная медицинская карта
    """
    new_card = MedicalCard(
        owner_cor_id=user_cor_id,
    )
    
    db.add(new_card)
    await db.commit()
    await db.refresh(new_card)
    
    return new_card


async def get_user_medical_card(
    user_cor_id: str,
    db: AsyncSession,
) -> Optional[MedicalCard]:
    """
    Получение медицинской карты пользователя
    
    Args:
        user_cor_id: COR ID пользователя
        db: Сессия базы данных
        
    Returns:
        Медицинская карта или None
    """
    query = (
        select(MedicalCard)
        .options(joinedload(MedicalCard.owner))
        .where(MedicalCard.owner_cor_id == user_cor_id)
    )
    
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_accessible_medical_cards(
    user_cor_id: str,
    db: AsyncSession,
) -> List[Tuple[MedicalCard, MedicalCardAccess, User, Optional[Profile]]]:
    """
    Получение медицинских карт, к которым у пользователя есть доступ
    
    Args:
        user_cor_id: COR ID пользователя
        db: Сессия базы данных
        
    Returns:
        Список кортежей (медицинская карта, информация о доступе, владелец, профиль владельца)
    """
    query = (
        select(MedicalCard, MedicalCardAccess, User, Profile)
        .join(MedicalCardAccess, MedicalCard.id == MedicalCardAccess.medical_card_id)
        .join(User, MedicalCard.owner_cor_id == User.cor_id)
        .outerjoin(Profile, User.id == Profile.user_id)
        .where(
            and_(
                MedicalCardAccess.user_cor_id == user_cor_id,
                MedicalCardAccess.is_accepted == True,
                MedicalCardAccess.is_active == True,
                MedicalCard.is_active == True,
                or_(
                    MedicalCardAccess.expires_at.is_(None),
                    MedicalCardAccess.expires_at > datetime.now(timezone.utc)
                )
            )
        )
        .order_by(MedicalCard.created_at.desc())
    )
    
    result = await db.execute(query)
    return list(result.all())


async def get_medical_card_by_id(
    card_id: str,
    user_cor_id: str,
    db: AsyncSession,
) -> Optional[MedicalCard]:
    """
    Получение медицинской карты по ID с проверкой прав доступа
    
    Args:
        card_id: ID медицинской карты
        user_cor_id: COR ID пользователя
        db: Сессия базы данных
        
    Returns:
        Медицинская карта или None
        
    Raises:
        HTTPException: Если нет доступа к карте
    """
    query = select(MedicalCard).where(MedicalCard.id == card_id)
    result = await db.execute(query)
    card = result.scalar_one_or_none()
    
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Медицинская карта не найдена"
        )
    
    # Проверка прав доступа
    if card.owner_cor_id == user_cor_id:
        return card
    
    # Проверка доступа через MedicalCardAccess
    access_query = select(MedicalCardAccess).where(
        and_(
            MedicalCardAccess.medical_card_id == card_id,
            MedicalCardAccess.user_cor_id == user_cor_id,
            MedicalCardAccess.is_accepted == True,
            MedicalCardAccess.is_active == True,
            or_(
                MedicalCardAccess.expires_at.is_(None),
                MedicalCardAccess.expires_at > datetime.now(timezone.utc)
            )
        )
    )
    access_result = await db.execute(access_query)
    access = access_result.scalar_one_or_none()
    
    if not access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этой медицинской карте"
        )
    
    return card


async def update_medical_card(
    card_id: str,
    body: MedicalCardUpdate,
    user_cor_id: str,
    db: AsyncSession,
) -> MedicalCard:
    """
    Обновление медицинской карты (только настройки отображения)
    
    Args:
        card_id: ID медицинской карты
        body: Данные для обновления
        user_cor_id: COR ID пользователя
        db: AsyncSession
        
    Returns:
        Обновленная медицинская карта
        
    Raises:
        HTTPException: Если нет прав на редактирование
    """
    # Только владелец может редактировать свою карту
    card = await get_medical_card_by_id(card_id, user_cor_id, db)
    
    if card.owner_cor_id != user_cor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только владелец может редактировать медицинскую карту"
        )
    
    # Обновление полей
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(card, field, value)
    
    card.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(card)
    
    return card




async def share_medical_card(
    card_id: str,
    body: MedicalCardAccessCreate,
    granting_user_cor_id: str,
    db: AsyncSession,
) -> MedicalCardAccess:
    """
    Предоставление доступа к медицинской карте другому пользователю
    
    Args:
        card_id: ID медицинской карты
        body: Данные для предоставления доступа
        granting_user_cor_id: COR ID пользователя, предоставляющего доступ
        db: Сессия базы данных
        
    Returns:
        Запись о доступе к карте
        
    Raises:
        HTTPException: Если нет прав на предоставление доступа
    """
    # Проверка существования карты и прав
    card = await get_medical_card_by_id(card_id, granting_user_cor_id, db)
    
    # Проверка прав: только владелец или пользователь с уровнем SHARE
    can_share = False
    if card.owner_cor_id == granting_user_cor_id:
        can_share = True
    else:
        # Проверка, есть ли у пользователя уровень SHARE
        access_query = select(MedicalCardAccess).where(
            and_(
                MedicalCardAccess.medical_card_id == card_id,
                MedicalCardAccess.user_cor_id == granting_user_cor_id,
                MedicalCardAccess.access_level == MedicalCardAccessLevel.SHARE,
                MedicalCardAccess.is_accepted == True,
                MedicalCardAccess.is_active == True
            )
        )
        result = await db.execute(access_query)
        if result.scalar_one_or_none():
            can_share = True
    
    if not can_share:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только владелец или пользователь с уровнем доступа 'share' может предоставлять доступ к медицинской карте"
        )
    
    # Проверка существования целевого пользователя
    target_user_query = select(User).where(User.cor_id == body.user_cor_id)
    target_user_result = await db.execute(target_user_query)
    target_user = target_user_result.scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    # Нельзя предоставить доступ самому себе
    if body.user_cor_id == granting_user_cor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя предоставить доступ к своей карте самому себе"
        )
    
    # Проверка существующего доступа
    existing_access_query = select(MedicalCardAccess).where(
        and_(
            MedicalCardAccess.medical_card_id == card_id,
            MedicalCardAccess.user_cor_id == body.user_cor_id
        )
    )
    result = await db.execute(existing_access_query)
    existing_access = result.scalar_one_or_none()
    
    if existing_access:
        # Обновление существующего доступа
        existing_access.access_level = MedicalCardAccessLevel[body.access_level.upper()]
        existing_access.purpose = MedicalCardPurpose[body.purpose.upper()] if body.purpose else None
        existing_access.purpose_note = body.purpose_note
        existing_access.expires_at = body.expires_at
        existing_access.is_active = True
        existing_access.is_accepted = False  # Требуется повторное подтверждение
        existing_access.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(existing_access)
        return existing_access
    
    # Создание нового доступа
    new_access = MedicalCardAccess(
        medical_card_id=card_id,
        user_cor_id=body.user_cor_id,
        access_level=MedicalCardAccessLevel[body.access_level.upper()],
        purpose=MedicalCardPurpose[body.purpose.upper()] if body.purpose else None,
        purpose_note=body.purpose_note,
        granted_by_cor_id=granting_user_cor_id,
        expires_at=body.expires_at,
        is_accepted=False,  # Требуется подтверждение
    )
    
    db.add(new_access)
    await db.commit()
    await db.refresh(new_access)
    
    return new_access


async def accept_medical_card_access(
    access_id: str,
    user_cor_id: str,
    db: AsyncSession,
) -> MedicalCardAccess:
    """
    Принятие приглашения на доступ к медицинской карте
    
    Args:
        access_id: ID записи о доступе
        user_cor_id: COR ID пользователя
        db: Сессия базы данных
        
    Returns:
        Обновленная запись о доступе
        
    Raises:
        HTTPException: Если приглашение не найдено или не принадлежит пользователю
    """
    query = select(MedicalCardAccess).where(MedicalCardAccess.id == access_id)
    result = await db.execute(query)
    access = result.scalar_one_or_none()
    
    if not access:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Приглашение не найдено"
        )
    
    if access.user_cor_id != user_cor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Это приглашение не адресовано вам"
        )
    
    access.is_accepted = True
    access.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(access)
    
    return access


async def revoke_medical_card_access(
    card_id: str,
    target_user_cor_id: str,
    revoking_user_cor_id: str,
    db: AsyncSession,
) -> None:
    """
    Отзыв доступа к медицинской карте
    
    Args:
        card_id: ID медицинской карты
        target_user_cor_id: COR ID пользователя, у которого отзывается доступ
        revoking_user_cor_id: COR ID пользователя, отзывающего доступ
        db: Сессия базы данных
        
    Raises:
        HTTPException: Если нет прав на отзыв доступа
    """
    # Проверка прав: только владелец может отзывать доступ
    card = await get_medical_card_by_id(card_id, revoking_user_cor_id, db)
    
    if card.owner_cor_id != revoking_user_cor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только владелец может отзывать доступ к медицинской карте"
        )
    
    # Поиск записи о доступе
    query = select(MedicalCardAccess).where(
        and_(
            MedicalCardAccess.medical_card_id == card_id,
            MedicalCardAccess.user_cor_id == target_user_cor_id
        )
    )
    result = await db.execute(query)
    access = result.scalar_one_or_none()
    
    if not access:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запись о доступе не найдена"
        )
    
    access.is_active = False
    access.updated_at = datetime.now(timezone.utc)
    
    await db.commit()


async def get_pending_invitations(
    user_cor_id: str,
    db: AsyncSession,
) -> List[Tuple[MedicalCardAccess, MedicalCard]]:
    """
    Получение списка ожидающих приглашений на доступ к медицинским картам
    
    
    Args:
        user_cor_id: COR ID пользователя
        db: Сессия базы данных
        
    Returns:
        Список кортежей (доступ, медицинская карта)
    """
    query = (
        select(MedicalCardAccess, MedicalCard)
        .join(MedicalCard, MedicalCardAccess.medical_card_id == MedicalCard.id)
        .where(
            and_(
                MedicalCardAccess.user_cor_id == user_cor_id,
                MedicalCardAccess.is_accepted == False,
                MedicalCardAccess.is_active == True
            )
        )
        .order_by(MedicalCardAccess.granted_at.desc())
    )
    
    result = await db.execute(query)
    return list(result.all())
