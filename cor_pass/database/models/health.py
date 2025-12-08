"""
Health domain models - health measurements, medical laboratory, Sibionics CGM integration
"""

from sqlalchemy import Column, String, ForeignKey, DateTime, Integer, Float, Boolean, LargeBinary, Text, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from .base import Base


class BloodPressureMeasurement(Base):
    """
    Измерение артериального давления - данные с устройств измерения давления
    """
    __tablename__ = "blood_pressure_measurements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    systolic_pressure = Column(Integer, nullable=False, comment="Систолическое (верхнее) артериальное давление")
    diastolic_pressure = Column(Integer, nullable=False, comment="Диастолическое (нижнее) артериальное давление")
    pulse = Column(Integer, nullable=False, comment="Частота сердечных сокращений (пульс)")

    measured_at = Column(DateTime, nullable=False, comment="Дата и время измерения, полученное с устройства")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="Дата и время сохранения записи в БД")

    # Relationships
    user = relationship("User", back_populates="blood_pressure_measurements")

    __table_args__ = (
        Index("idx_bpm_user_id", "user_id"),
        Index("idx_bpm_measured_at", "measured_at"),
    )


class ECGMeasurement(Base):
    """
    ЭКГ измерение - данные электрокардиограммы
    """
    __tablename__ = "ecg_measurements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    file_data = Column(LargeBinary, nullable=False)  # Данные ЭКГ в бинарном виде
    file_name = Column(String, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="Дата и время сохранения записи в БД")

    # Relationships
    user = relationship("User", back_populates="ecg_measurements")


# ============================================================================
# SIBIONICS CGM Integration Models
# ============================================================================

class SibionicsAuth(Base):
    """
    Авторизация SIBIONICS - хранение токенов доступа для интеграции с CGM SIBIONICS
    """
    __tablename__ = "sibionics_auth"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    biz_id = Column(String(255), nullable=True)  # SIBIONICS Authorization resource ID (может быть NULL при H5 авторизации)
    access_token = Column(String(500), nullable=True)
    expires_in = Column(DateTime(timezone=True), nullable=True)  # Token expiration time
    is_active = Column(Boolean, default=True)  # Статус авторизации
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="sibionics_auth")
    devices = relationship("SibionicsDevice", back_populates="auth", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_sibionics_auth_user_id", "user_id"),
        Index("idx_sibionics_auth_biz_id", "biz_id"),
    )


class SibionicsDevice(Base):
    """
    Устройство SIBIONICS CGM - информация об устройствах непрерывного мониторинга глюкозы
    """
    __tablename__ = "sibionics_devices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    auth_id = Column(String(36), ForeignKey("sibionics_auth.id", ondelete="CASCADE"), nullable=True)  # NULL для ручных устройств
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)  # Только для ручных устройств
    device_id = Column(String(255), nullable=False)  # SIBIONICS Device ID или "manual_entry"
    device_name = Column(String(255), nullable=True)
    device_type = Column(String(50), nullable=True, default="cgm")  # "cgm" или "manual"
    sn = Column(String(255), nullable=True)  # Serial Number
    model = Column(String(255), nullable=True)  # Model name
    bluetooth_num = Column(String(255), nullable=True)
    serial_no = Column(String(255), nullable=True)
    status = Column(Integer, nullable=True)  # 0: Not started; 1: Monitoring; 2: Expired; 3: Init; 4: Abnormal
    current_index = Column(Integer, nullable=True)  # Current data index
    max_index = Column(Integer, nullable=True)
    min_index = Column(Integer, nullable=True)
    data_gap = Column(Integer, nullable=True)  # Glucose index interval (minutes)
    enable_time = Column(DateTime(timezone=True), nullable=True)  # Device wearing start time
    last_time = Column(DateTime(timezone=True), nullable=True)  # Device wearing deadline
    last_sync = Column(DateTime(timezone=True), nullable=True)  # Время последней синхронизации данных
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    # Relationships
    auth = relationship("SibionicsAuth", back_populates="devices")
    user = relationship("User", foreign_keys=[user_id])  # Для ручных устройств
    glucose_data = relationship("SibionicsGlucose", back_populates="device", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_sibionics_device_auth_id", "auth_id"),
        Index("idx_sibionics_device_user_id", "user_id"),
        Index("idx_sibionics_device_device_id", "device_id"),
    )


class SibionicsGlucose(Base):
    """
    Данные глюкозы SIBIONICS - измерения уровня глюкозы с устройств CGM
    """
    __tablename__ = "sibionics_glucose"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), ForeignKey("sibionics_devices.id", ondelete="CASCADE"), nullable=False)
    index = Column(Integer, nullable=False)  # Glucose data index
    glucose_value = Column(Float, nullable=False)  # Glucose value in mmol/L
    trend = Column(Integer, nullable=True)  # 0: stable; ±1: slow; ±2: fast
    alarm_status = Column(Integer, nullable=True)  # 1: normal; 2-6: various alarms
    timestamp = Column(DateTime(timezone=True), nullable=False)  # Measurement timestamp
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Relationships
    device = relationship("SibionicsDevice", back_populates="glucose_data")

    __table_args__ = (
        Index("idx_sibionics_glucose_device_id", "device_id"),
        Index("idx_sibionics_glucose_timestamp", "timestamp"),
        UniqueConstraint("device_id", "index", name="uq_device_index"),
    )
