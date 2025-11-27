"""
Fuel domain models - fuel station QR sessions, finance backend auth, corporate clients
"""

from sqlalchemy import Column, String, ForeignKey, DateTime, Integer, Boolean, Text, LargeBinary, Index, CheckConstraint, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from .base import Base


class FuelStationQRSession(Base):
    """
    Сессия QR кода для заправки - создаётся при генерации QR кода сотрудником
    для одноразовой верификации на заправке
    """
    __tablename__ = "fuel_station_qr_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_cor_id = Column(String(36), ForeignKey("users.cor_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # QR код данные
    session_token = Column(String(255), unique=True, nullable=False, index=True, comment="Уникальный токен сессии")
    totp_code = Column(String(10), nullable=False, comment="TOTP код на момент генерации")
    timestamp_token = Column(String(255), nullable=False, comment="Timestamp токен для защиты от replay атак")
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), comment="Время создания QR кода")
    expires_at = Column(DateTime(timezone=True), nullable=False, comment="Время истечения QR кода")
    
    # Статус использования (для предотвращения повторного использования)
    is_used = Column(Boolean, nullable=False, default=False, comment="Был ли использован QR код")
    used_at = Column(DateTime(timezone=True), nullable=True, comment="Время использования")
    
    __table_args__ = (
        Index("idx_fuel_qr_user", "user_cor_id"),
        Index("idx_fuel_qr_token", "session_token"),
        Index("idx_fuel_qr_created", "created_at"),
    )


class FinanceBackendAuth(Base):
    """
    Авторизация финансового бэкенда - хранение TOTP секретов для server-to-server аутентификации
    """
    __tablename__ = "finance_backend_auth"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Идентификация
    service_name = Column(String(100), unique=True, nullable=False, comment="Название сервиса (finance_backend)")
    api_endpoint = Column(String(500), nullable=False, comment="URL бэкенда финансов")
    
    # TOTP для авторизации
    totp_secret = Column(LargeBinary, nullable=False, comment="Зашифрованный TOTP секрет")
    totp_interval = Column(Integer, nullable=False, default=30, comment="Интервал TOTP в секундах")
    
    # Метаданные
    is_active = Column(Boolean, nullable=False, default=True, comment="Активна ли интеграция")
    last_successful_auth = Column(DateTime(timezone=True), nullable=True, comment="Последняя успешная авторизация")
    last_failed_auth = Column(DateTime(timezone=True), nullable=True, comment="Последняя неудачная авторизация")
    failed_attempts = Column(Integer, nullable=False, default=0, comment="Количество неудачных попыток подряд")
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index("idx_finance_auth_service", "service_name"),
    )


class CorporateClient(Base):
    """
    Корпоративный клиент - компания для системы заправок с лимитом на топливо
    """
    __tablename__ = "corporate_clients"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Кто подал заявку (владелец компании)
    owner_cor_id = Column(String(36), ForeignKey("users.cor_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Данные компании
    company_format = Column(String(50), nullable=False, comment="Форма підприємства: ТОВ, ФОП, ПП")
    company_name = Column(String(255), nullable=False, comment="Полное название компании")
    address = Column(String(500), nullable=False, comment="Юридический адрес")
    phone_number = Column(String(20), nullable=False, comment="Контактный телефон")
    email = Column(String(255), nullable=False, comment="Email компании")
    tax_id = Column(String(50), nullable=False, comment="ЄДРПОУ/ИНН")
    
    # Статус компании
    status = Column(
        String(20),
        default="pending",
        nullable=False,
        comment="Статус: pending (на рассмотрении), active (активна), blocked (заблокирована), rejected (отклонена), limit_exceeded (превышен лимит)"
    )
    
    # Лимит компании
    fuel_limit = Column(
        Numeric(10, 2), 
        nullable=False, 
        default=16000.00,
        server_default="16000.00",
        comment="Лимит компании на топливо (грн)"
    )
    
    # ID в finance backend (создаётся после одобрения)
    finance_company_id = Column(Integer, nullable=True, unique=True, comment="ID компании в финансовом бэкенде")
    
    # Обработка заявки
    reviewed_by = Column(String(36), ForeignKey("users.cor_id", ondelete="SET NULL"), nullable=True, comment="Кто рассмотрел/изменил статус")
    reviewed_at = Column(DateTime(timezone=True), nullable=True, comment="Когда изменён статус")
    rejection_reason = Column(Text, nullable=True, comment="Причина отклонения (если rejected)")
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True, default=None, comment="Soft delete timestamp")
    
    # Relationships
    owner = relationship("User", foreign_keys=[owner_cor_id], back_populates="corporate_clients")
    reviewer = relationship("User", foreign_keys=[reviewed_by], back_populates="reviewed_corporate_clients")
    
    __table_args__ = (
        Index("idx_corp_client_owner", "owner_cor_id"),
        Index("idx_corp_client_status", "status"),
        Index("idx_corp_client_finance_id", "finance_company_id"),
        Index("idx_corp_client_created", "created_at"),
        # Partial unique indexes для soft delete (unique только для не удалённых записей)
        Index("uq_corp_client_company_name", "company_name", unique=True, postgresql_where=Column("deleted_at").is_(None)),
        Index("uq_corp_client_tax_id", "tax_id", unique=True, postgresql_where=Column("deleted_at").is_(None)),
        CheckConstraint("status IN ('pending', 'active', 'blocked', 'rejected', 'limit_exceeded')", name="ck_corporate_clients_status"),
    )
