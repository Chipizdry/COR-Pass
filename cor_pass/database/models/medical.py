"""
Medical domain models - patients, medical cards, and access management
"""

from sqlalchemy import Column, String, ForeignKey, DateTime, Date, LargeBinary, Boolean, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import Enum
import datetime
import uuid

from .base import Base
from .enums import PatientClinicStatus, MedicalCardAccessLevel, MedicalCardPurpose


class Patient(Base):
    """
    Пациент - базовая модель для хранения информации о пациентах
    """
    __tablename__ = "patients"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_cor_id = Column(String(250), unique=True, nullable=False)  # Пациентский COR ID
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=True)  # Связь с User (опционально)

    # Зашифрованные персональные данные
    encrypted_surname = Column(LargeBinary, nullable=True)
    encrypted_first_name = Column(LargeBinary, nullable=True)
    encrypted_middle_name = Column(LargeBinary, nullable=True)
    
    # Основные данные
    birth_date = Column(Date, nullable=True)
    sex = Column(String(10), nullable=True)
    email = Column(String(250), nullable=True)
    phone_number = Column(String(20), nullable=True)
    address = Column(String(500), nullable=True)
    photo = Column(LargeBinary, nullable=True)  # Фото в бинарном виде
    
    # Поисковые токены (для поиска по зашифрованным данным)
    search_tokens = Column(Text, default="", nullable=False)
    
    # Временные метки
    change_date = Column(DateTime, default=func.now(), onupdate=func.now())
    create_date = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User", back_populates="patient")
    doctor_statuses = relationship("DoctorPatientStatus", back_populates="patient")
    clinic_statuses = relationship("PatientClinicStatusModel", back_populates="patient")

    def __repr__(self):
        return f"<Patient(id='{self.id}', patient_cor_id='{self.patient_cor_id}')>"


class PatientClinicStatusModel(Base):
    """
    Клинический статус пациента - отслеживание статуса пациента в клинике
    """
    __tablename__ = "clinic_patient_statuses"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False)
    patient_status_for_clinic = Column(Enum(PatientClinicStatus), default=PatientClinicStatus.registered)
    
    assigned_date = Column(DateTime, default=func.now())
    updated_date = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    patient = relationship("Patient", back_populates="clinic_statuses")


class MedicalCard(Base):
    """
    Медицинская карта пользователя - используется для шеринга медицинских данных
    (давление, глюкоза, лекарства) с другими пользователями.
    Создается автоматически при регистрации пользователя.
    """
    __tablename__ = "medical_cards"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_cor_id = Column(String(36), ForeignKey("users.cor_id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Настройки отображения для мобильного приложения
    card_color = Column(String(20), nullable=True, default="#4169E1")  # Цвет карты в интерфейсе
    display_name = Column(String(100), nullable=True)  # Кастомное имя карты
    
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    # Relationships
    owner = relationship("User", back_populates="medical_card", foreign_keys=[owner_cor_id])
    access_grants = relationship("MedicalCardAccess", back_populates="medical_card", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_medical_card_owner", "owner_cor_id"),
    )


class MedicalCardAccess(Base):
    """
    Права доступа к медицинским картам - управление доступом к медицинским данным
    """
    __tablename__ = "medical_card_access"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    medical_card_id = Column(String(36), ForeignKey("medical_cards.id", ondelete="CASCADE"), nullable=False)
    user_cor_id = Column(String(36), ForeignKey("users.cor_id", ondelete="CASCADE"), nullable=False)
    
    # Уровень доступа
    access_level = Column(
        Enum(MedicalCardAccessLevel, name="medicalcardaccesslevel", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=MedicalCardAccessLevel.VIEW
    )
    
    # Цель предоставления доступа (для кого)
    purpose = Column(
        Enum(MedicalCardPurpose, name="medicalcardpurpose", values_callable=lambda x: [e.value for e in x]),
        nullable=True
    )  # Для кого: родственник, врач, другое
    purpose_note = Column(String(255), nullable=True)  # Дополнительное пояснение
    
    # Метаданные о предоставлении доступа
    granted_by_cor_id = Column(String(36), ForeignKey("users.cor_id"), nullable=True)  # Кто предоставил доступ
    granted_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Дата истечения доступа
    
    # Флаги
    is_accepted = Column(Boolean, default=False)  # Принял ли пользователь приглашение
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    # Relationships
    medical_card = relationship("MedicalCard", back_populates="access_grants")
    user = relationship("User", foreign_keys=[user_cor_id])
    granted_by = relationship("User", foreign_keys=[granted_by_cor_id])
    
    __table_args__ = (
        Index("idx_medical_card_access_card_user", "medical_card_id", "user_cor_id"),
        Index("idx_medical_card_access_user", "user_cor_id"),
    )
