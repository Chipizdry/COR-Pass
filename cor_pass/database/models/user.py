"""
User Domain Models
User accounts, authentication, sessions, records, and settings
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, relationship

from .base import Base
from .enums import Status, AuthSessionStatus


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cor_id = Column(String(250), nullable=True, index=True)  # Unique constraint реализован через partial index в миграции
    email = Column(String(250), unique=True, nullable=False)
    backup_email = Column(String(250), unique=True, nullable=True)
    password = Column(String(250), nullable=False)
    last_password_change = Column(DateTime, server_default=func.now())
    access_token = Column(String(500), nullable=True)
    refresh_token = Column(String(500), nullable=True)
    recovery_code = Column(
        LargeBinary, nullable=True
    )  # Уникальный код восстановление пользователя
    is_active = Column(Boolean, default=True)
    account_status: Mapped[Enum] = Column(
        "status", Enum(Status), default=Status.basic
    )  # Статус аккаунта: базовый / премиум
    unique_cipher_key = Column(
        String(250), nullable=False
    )  # уникальный ключ шифрования конкретного пользователя, в базе в зашифрованном виде, шифруется с помошью AES key переменной окружения
    user_sex = Column(String(10), nullable=True)
    birth = Column(Integer, nullable=True)
    user_index = Column(
        Integer, unique=True, nullable=True
    )  # индекс пользователя, используется в создании cor_id
    created_at = Column(DateTime, nullable=False, default=func.now())

    # Связи
    user_records = relationship(
        "Record", back_populates="user", cascade="all, delete-orphan"
    )
    user_settings = relationship(
        "UserSettings", back_populates="user", cascade="all, delete-orphan"
    )
    user_otp = relationship("OTP", back_populates="user", cascade="all, delete-orphan")

    user_sessions = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )
    user_doctors = relationship(
        "Doctor", back_populates="user", cascade="all, delete-orphan"
    )

    patient = relationship("Patient", back_populates="user", uselist=False)

    devices = relationship("Device", back_populates="user")
    granted_accesses = relationship(
        "DeviceAccess",
        foreign_keys="[DeviceAccess.granting_user_id]",
        back_populates="granting_user",
    )
    received_accesses = relationship(
        "DeviceAccess",
        foreign_keys="[DeviceAccess.accessing_user_id]",
        back_populates="accessing_user",
    )
    profile = relationship(
        "Profile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    user_lab_assistants = relationship(
        "LabAssistant", back_populates="user", cascade="all, delete-orphan"
    )
    user_energy_managers = relationship(
        "EnergyManager", back_populates="user", cascade="all, delete-orphan"
    )
    user_lawyers = relationship(
        "Lawyer", back_populates="user", cascade="all, delete-orphan"
    )
    user_financiers = relationship(
        "Financier", back_populates="user", cascade="all, delete-orphan"
    )
    blood_pressure_measurements = relationship(
        "BloodPressureMeasurement", back_populates="user", cascade="all, delete-orphan"
    )
    ecg_measurements = relationship(
        "ECGMeasurement", back_populates="user", cascade="all, delete-orphan"
    )

    first_aid_kits = relationship(
        "FirstAidKit", back_populates="user", cascade="all, delete-orphan"
    )
    medicine_schedules = relationship(
        "MedicineSchedule", back_populates="user", cascade="all, delete-orphan"
    )
    prescription_files = relationship(
        "PrescriptionFile", back_populates="user", cascade="all, delete-orphan"
    )
    medicine_intakes = relationship(
        "MedicineIntake", back_populates="user", cascade="all, delete-orphan"
    )
    
    # SIBIONICS CGM - ручные устройства для ввода глюкозы
    sibionics_manual_devices = relationship(
        "SibionicsDevice", 
        foreign_keys="[SibionicsDevice.user_id]",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # Медицинская карта 
    medical_card = relationship(
        "MedicalCard", back_populates="owner", foreign_keys="[MedicalCard.owner_cor_id]", 
        uselist=False, cascade="all, delete-orphan"
    )
    accessible_medical_cards = relationship(
        "MedicalCardAccess", back_populates="user", foreign_keys="[MedicalCardAccess.user_cor_id]", 
        cascade="all, delete-orphan"
    )
    
    # Корпоративные клиенты
    corporate_clients = relationship(
        "CorporateClient", back_populates="owner", foreign_keys="[CorporateClient.owner_cor_id]",
        cascade="all, delete-orphan"
    )
    reviewed_corporate_clients = relationship(
        "CorporateClient", back_populates="reviewer", foreign_keys="[CorporateClient.reviewed_by]"
    )

    # Индексы
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_cor_id", "cor_id"),
        # Unique index для cor_id (в PostgreSQL unique index позволяет несколько NULL значений)
        Index("users_cor_id_key", "cor_id", unique=True),
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.cor_id"), nullable=False)
    device_type = Column(String(250), nullable=True)
    device_info = Column(String(250), nullable=True)
    app_id = Column(String(250), nullable=True)  # Идентификатор апки
    device_id = Column(String(250), nullable=True)  # айди устройства
    ip_address = Column(String(250), nullable=True)
    device_os = Column(String(250), nullable=True)
    jti = Column(
        String,
        unique=True,
        nullable=True,
        comment="JTI последнего Access токена, выданного для этой сессии",
    )
    refresh_token = Column(LargeBinary, nullable=True)
    access_token = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Связи
    user = relationship("User", back_populates="user_sessions")

    # Индексы
    __table_args__ = (Index("idx_user_sessions_user_id", "user_id"),)


class CorIdAuthSession(Base):
    __tablename__ = "cor_id_auth_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), index=True, nullable=True)
    cor_id = Column(String(250), index=True, nullable=True)
    session_token = Column(String(36), unique=True, index=True, nullable=False)
    app_id = Column(String(250), nullable=True)
    device_id = Column(String(250), nullable=True)
    status = Column(
        Enum(AuthSessionStatus), default=AuthSessionStatus.PENDING, nullable=False
    )
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())

    __table_args__ = (Index("idx_cor_id_auth_sessions_token", "session_token"),)


class Verification(Base):
    __tablename__ = "verification"
    id = Column(Integer, primary_key=True)
    email = Column(String(250), unique=True, nullable=False)
    verification_code = Column(Integer, default=None)
    email_confirmation = Column(Boolean, default=False)

    # Индексы
    __table_args__ = (Index("idx_verification_email", "email"),)


class Record(Base):
    __tablename__ = "records"

    record_id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    record_name = Column(String(250), nullable=False)
    website = Column(String(250), nullable=True)
    username = Column(LargeBinary, nullable=True)
    password = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    edited_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
    notes = Column(Text, nullable=True)
    is_favorite = Column(Boolean, default=False, nullable=True)

    # Связи
    user = relationship("User", back_populates="user_records")
    tags = relationship("Tag", secondary="records_tags")

    # Индексы
    __table_args__ = (Index("idx_records_user_id", "user_id"),)


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)

    # Индексы
    __table_args__ = (Index("idx_tags_name", "name"),)


class RecordTag(Base):
    __tablename__ = "records_tags"

    record_id = Column(Integer, ForeignKey("records.record_id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id = Column(
        String(36), ForeignKey("users.id"), nullable=False, primary_key=True
    )
    local_password_storage = Column(Boolean, default=False)
    cloud_password_storage = Column(Boolean, default=True)
    local_medical_storage = Column(Boolean, default=False)
    cloud_medical_storage = Column(Boolean, default=True)

    # Связи
    user = relationship("User", back_populates="user_settings")


class OTP(Base):
    __tablename__ = "otp_records"

    record_id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    record_name = Column(String(250), nullable=False)
    username = Column(String(250), nullable=True)
    private_key = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    edited_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Связи
    user = relationship("User", back_populates="user_otp")

    # Индексы
    __table_args__ = (Index("idx_otp_records_user_id", "user_id"),)


class Profile(Base):
    """
    Профиль пользователя - расширенная информация о пользователе
    """
    __tablename__ = "profiles"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)

    # Зашифрованные персональные данные
    encrypted_surname = Column(LargeBinary, nullable=True)
    encrypted_first_name = Column(LargeBinary, nullable=True)
    encrypted_middle_name = Column(LargeBinary, nullable=True)

    # Основная информация
    birth_date = Column(Date, nullable=True)
    phone_number = Column(String(20), nullable=True)
    city = Column(String(100), nullable=True)

    # Информация об автомобиле
    car_brand = Column(String(100), nullable=True)
    engine_type = Column(String(50), nullable=True)
    fuel_tank_volume = Column(Integer, nullable=True)

    # Фото профиля
    photo_data = Column(LargeBinary, nullable=True)
    photo_file_type = Column(String, nullable=True)

    # Временные метки
    change_date = Column(DateTime, default=func.now(), onupdate=func.now())
    create_date = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User", back_populates="profile")

    def __repr__(self):
        return f"<Profile(id='{self.id}', user_id='{self.user_id}')>"
