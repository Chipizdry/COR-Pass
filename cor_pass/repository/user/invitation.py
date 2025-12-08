"""
User Invitation Repository
Функции для работы с приглашениями пользователей
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from cor_pass.database.models import UserInvitation, User


async def create_invitation(
    email: str,
    invited_by_id: str,
    expires_in_days: int,
    db: AsyncSession
) -> UserInvitation:
    """
    Создаёт новое приглашение для пользователя
    
    Args:
        email: Email приглашаемого пользователя
        invited_by_id: ID пользователя, который создаёт приглашение
        expires_in_days: Срок действия приглашения в днях
        db: AsyncSession
        
    Returns:
        UserInvitation: Созданное приглашение
    """
    # Генерируем уникальный токен (64 символа, URL-safe)
    token = secrets.token_urlsafe(48)
    
    # Время истечения
    expires_at = datetime.now() + timedelta(days=expires_in_days)
    
    invitation = UserInvitation(
        email=email.lower(),
        token=token,
        invited_by=invited_by_id,
        expires_at=expires_at,
        is_used=False
    )
    
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)
    
    logger.info(
        f"Created invitation for {email} by user {invited_by_id}, "
        f"expires at {expires_at}, token={token[:12]}..."
    )
    
    return invitation


async def get_invitation_by_token(
    token: str,
    db: AsyncSession
) -> Optional[UserInvitation]:
    """
    Получает приглашение по токену
    
    Args:
        token: Токен приглашения
        db: AsyncSession
        
    Returns:
        Optional[UserInvitation]: Приглашение или None
    """
    stmt = select(UserInvitation).where(UserInvitation.token == token)
    result = await db.execute(stmt)
    invitation = result.scalar_one_or_none()
    
    return invitation


async def get_valid_invitation_by_token(
    token: str,
    db: AsyncSession
) -> Optional[UserInvitation]:
    """
    Получает валидное (не использованное и не истёкшее) приглашение по токену
    
    Args:
        token: Токен приглашения
        db: AsyncSession
        
    Returns:
        Optional[UserInvitation]: Валидное приглашение или None
    """
    now = datetime.now()
    
    stmt = select(UserInvitation).where(
        and_(
            UserInvitation.token == token,
            UserInvitation.is_used == False,
            UserInvitation.expires_at > now
        )
    )
    result = await db.execute(stmt)
    invitation = result.scalar_one_or_none()
    
    return invitation


async def mark_invitation_used(
    invitation: UserInvitation,
    db: AsyncSession
) -> UserInvitation:
    """
    Помечает приглашение как использованное
    
    Args:
        invitation: Приглашение
        db: AsyncSession
        
    Returns:
        UserInvitation: Обновлённое приглашение
    """
    invitation.is_used = True
    await db.commit()
    await db.refresh(invitation)
    
    logger.info(f"Marked invitation {invitation.id} as used (email: {invitation.email})")
    
    return invitation


async def get_pending_invitation_by_email(
    email: str,
    db: AsyncSession
) -> Optional[UserInvitation]:
    """
    Получает активное (не использованное и не истёкшее) приглашение по email
    
    Используется для проверки наличия существующего приглашения
    перед созданием нового
    
    Args:
        email: Email пользователя
        db: AsyncSession
        
    Returns:
        Optional[UserInvitation]: Активное приглашение или None
    """
    now = datetime.now()
    
    stmt = select(UserInvitation).where(
        and_(
            UserInvitation.email == email.lower(),
            UserInvitation.is_used == False,
            UserInvitation.expires_at > now
        )
    ).order_by(UserInvitation.created_at.desc())
    
    result = await db.execute(stmt)
    invitation = result.scalar_one_or_none()
    
    return invitation
