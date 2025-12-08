"""
User Invitation Models
Приглашение пользователей в систему через email
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    DateTime,
    String,
    Boolean,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import relationship

from .base import Base


class UserInvitation(Base):
    """
    Модель приглашения пользователя в систему
    
    Workflow:
    1. Администратор создаёт приглашение через POST /auth/invite
    2. Генерируется уникальный token
    3. Отправляется email с ссылкой: https://dev-corid.cor-medical.ua/api/signup?token={token}
    4. Пользователь переходит по ссылке и регистрируется
    5. Email из приглашения доступен только для чтения (readonly)
    6. После регистрации приглашение помечается как использованное (is_used=True)
    """
    __tablename__ = "user_invitations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(250), nullable=False, index=True)  # Email приглашаемого пользователя
    token = Column(String(250), unique=True, nullable=False, index=True)  # Уникальный токен приглашения
    invited_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Кто пригласил
    expires_at = Column(DateTime, nullable=False)  # Время истечения приглашения (обычно 7 дней)
    is_used = Column(Boolean, default=False, nullable=False)  # Использовано ли приглашение
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    # Связь с пользователем, который пригласил
    inviter = relationship("User", foreign_keys=[invited_by])
    
    # Индексы для быстрого поиска
    __table_args__ = (
        Index('ix_user_invitations_token_not_used', 'token', 'is_used'),
        Index('ix_user_invitations_email_not_used', 'email', 'is_used'),
    )
