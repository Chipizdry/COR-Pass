"""
Corporate Employee Invitation Model
Приглашение пользователей для добавления в корпоративный аккаунт
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    DateTime,
    String,
    Integer,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import relationship

from .base import Base


class CorporateEmployeeInvitation(Base):
    """
    Модель приглашения сотрудника в корпоративный аккаунт
    
    Workflow:
    1. Юрист/админ добавляет сотрудника по email (если юзер не существует)
    2. Создаётся запись в таблице с email, именем, фамилией, телефоном, данными компании и лимитом
    3. Отправляется email с просьбой пройти регистрацию и ссылками на приложения
    4. Пользователь регистрируется в COR-ID через приложение
    5. При регистрации проверяются приглашения для этого email
    6. После успешной регистрации приглашение используется и сотрудник добавляется в компанию
    """
    __tablename__ = "corporate_employee_invitations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Данные приглашаемого сотрудника
    email = Column(String(250), nullable=False, index=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=True)
    
    # Данные для добавления в компанию
    company_id = Column(Integer, nullable=False)  # ID компании в finance backend
    account_id = Column(Integer, nullable=True)   # ID аккаунта в finance backend (опционально)
    limit_amount = Column(Integer, nullable=False, default=0)  # Лимит пользователя
    limit_period = Column(String(20), nullable=False, default="day")  # Период лимита
    
    # Статус приглашения
    is_used = Column(Integer, default=0, nullable=False)  # Использовано ли приглашение (0=нет, 1=да)
    created_cor_id = Column(String(36), nullable=True)  # COR-ID пользователя после регистрации
    
    # Метаданные
    invited_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Кто пригласил
    created_at = Column(DateTime, nullable=False, default=func.now())
    used_at = Column(DateTime, nullable=True)  # Когда было использовано приглашение
    
    # Связь с пользователем, который пригласил
    inviter = relationship("User", foreign_keys=[invited_by])
    
    # Индексы для быстрого поиска
    __table_args__ = (
        Index('ix_corp_emp_inv_email_not_used', 'email', 'is_used'),
        Index('ix_corp_emp_inv_company_id', 'company_id'),
    )
