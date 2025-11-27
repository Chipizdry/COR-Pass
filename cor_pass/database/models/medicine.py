"""
Medicine domain models - first aid kits, medicines, schedules, prescriptions
"""

from sqlalchemy import Column, String, ForeignKey, DateTime, Integer, Float, Date, Boolean, Text, Index, LargeBinary, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from datetime import timedelta
from typing import Optional
import uuid

from .base import Base
from .enums import MedicineIntakeStatus


class FirstAidKit(Base):
    """
    Аптечка - контейнер для хранения лекарств пользователя
    """
    __tablename__ = "first_aid_kits"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    user_cor_id = Column(String(36), ForeignKey("users.cor_id", ondelete="CASCADE"), nullable=False)

    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    # Relationships
    medicines = relationship("FirstAidKitItem", back_populates="first_aid_kit", cascade="all, delete-orphan")
    user = relationship("User", back_populates="first_aid_kits")

    __table_args__ = (Index("idx_first_aid_kits_user_cor_id", "user_cor_id"),)


class Medicine(Base):
    """
    Лекарство - информация о медикаментах
    """
    __tablename__ = "medicines"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    active_substance = Column(String(255), nullable=True)
    intake_method = Column(String(100), nullable=True)  # перорально, подкожно и т.д.

    # Разные типы параметров в зависимости от метода
    dosage = Column(Float, nullable=True)        # для перорального
    unit = Column(String(50), nullable=True)     # мг, мл и т.д.
    concentration = Column(Float, nullable=True) # для мазей и растворов
    volume = Column(Float, nullable=True)        # для растворов

    created_by = Column(String(100), nullable=False)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    # Relationships
    schedules = relationship("MedicineSchedule", back_populates="medicine", cascade="all, delete-orphan")
    first_aid_kits = relationship("FirstAidKitItem", back_populates="medicine", cascade="all, delete-orphan")


class FirstAidKitItem(Base):
    """
    Наполнение аптечки - связь между аптечкой и лекарствами
    """
    __tablename__ = "first_aid_kit_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    first_aid_kit_id = Column(String(36), ForeignKey("first_aid_kits.id", ondelete="CASCADE"), nullable=False)
    medicine_id = Column(String(36), ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    expiration_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Relationships
    first_aid_kit = relationship("FirstAidKit", back_populates="medicines")
    medicine = relationship("Medicine", back_populates="first_aid_kits")

    __table_args__ = (
        Index("idx_first_aid_kit_items_kit_id", "first_aid_kit_id"),
        Index("idx_first_aid_kit_items_medicine_id", "medicine_id"),
    )


class MedicineSchedule(Base):
    """
    Расписание приема лекарств
    """
    __tablename__ = "medicine_schedules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    medicine_id = Column(String(36), ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False)
    user_cor_id = Column(String(36), ForeignKey("users.cor_id", ondelete="CASCADE"), nullable=False)

    start_date = Column(Date, nullable=False)
    duration_days = Column(Integer, nullable=True)
    times_per_day = Column(Integer, nullable=True)
    intake_times = Column(JSONB, nullable=True)
    interval_minutes = Column(Integer, nullable=True)
    symptomatically = Column(Boolean, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    # Relationships
    intakes = relationship("MedicineIntake", back_populates="schedule", cascade="all, delete-orphan")
    medicine = relationship("Medicine", back_populates="schedules")
    user = relationship("User", back_populates="medicine_schedules")

    __table_args__ = (
        Index("idx_medicine_schedules_user_cor_id", "user_cor_id"),
        Index("idx_medicine_schedules_medicine_id", "medicine_id"),
    )


class MedicineIntake(Base):
    """
    Прием лекарства - история и статус приема медикаментов
    """
    __tablename__ = "medicine_intakes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    schedule_id = Column(String(36), ForeignKey("medicine_schedules.id", ondelete="CASCADE"), nullable=False)
    user_cor_id = Column(String(36), ForeignKey("users.cor_id", ondelete="CASCADE"), nullable=False)
    
    # Запланированная дата и время приема
    planned_datetime = Column(DateTime(timezone=True), nullable=False)
    # Фактическая дата и время приема (если был выполнен)
    actual_datetime = Column(DateTime(timezone=True), nullable=True)
    # Статус приема (запланирован/выполнен/пропущен/отложен)
    status = Column(Enum(MedicineIntakeStatus), nullable=False, default=MedicineIntakeStatus.PLANNED)
    # Комментарий (например, причина пропуска/переноса)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    # Relationships
    schedule = relationship("MedicineSchedule", back_populates="intakes")
    user = relationship("User", back_populates="medicine_intakes")

    @property
    def medicine_name(self) -> str:
        """Название лекарства"""
        return self.schedule.medicine.name if self.schedule and self.schedule.medicine else None

    @property
    def medicine_dosage(self) -> Optional[float]:
        """Дозировка лекарства"""
        return self.schedule.medicine.dosage if self.schedule and self.schedule.medicine else None

    @property
    def medicine_unit(self) -> Optional[str]:
        """Единица измерения дозировки"""
        return self.schedule.medicine.unit if self.schedule and self.schedule.medicine else None

    @property
    def medicine_intake_method(self) -> Optional[str]:
        """Способ приёма лекарства"""
        return self.schedule.medicine.intake_method if self.schedule and self.schedule.medicine else None

    @property
    def method_data(self):
        """Формирует данные о способе приёма лекарства для API."""
        if self.intake_method == "Oral":
            return {
                "intake_method": self.intake_method,
                "dosage": self.dosage,
                "unit": self.unit,
                "concentration": self.concentration,
                "volume": self.volume,
            }
        elif self.intake_method == "Ointment/suppositories":
            return {
                "intake_method": self.intake_method,
                "concentration": self.concentration,
                "dosage": self.dosage,
                "unit": self.unit,
                "volume": self.volume,
            }
        elif self.intake_method in ("Intravenous", "Intramuscularly", "Solutions"):
            return {
                "intake_method": self.intake_method,
                "concentration": self.concentration,
                "volume": self.volume,
                "dosage": self.dosage,
                "unit": self.unit,
            }
        return None


class OphthalmologicalPrescription(Base):
    """
    Офтальмологический рецепт - рецепт на очки
    """
    __tablename__ = "ophthalmological_prescriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), index=True, nullable=False)

    # ---------- правый глаз (OD) ----------
    od_sph = Column(Float, nullable=True)
    od_cyl = Column(Float, nullable=True)
    od_ax = Column(Float, nullable=True)
    od_prism = Column(Float, nullable=True)
    od_base = Column(String(10), nullable=True)
    od_add = Column(Float, nullable=True)

    # ---------- левый глаз (OS) ----------
    os_sph = Column(Float, nullable=True)
    os_cyl = Column(Float, nullable=True)
    os_ax = Column(Float, nullable=True)
    os_prism = Column(Float, nullable=True)
    os_base = Column(String(10), nullable=True)
    os_add = Column(Float, nullable=True)

    # ---------- Общие параметры ----------
    glasses_purpose = Column(String(50), nullable=False)
    glasses_type = Column(String(50), nullable=False)

    issue_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    term_months = Column(Float, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    note = Column(Text, nullable=True)

    doctor_signature_id = Column(String(36), ForeignKey("doctor_signatures.id", ondelete="SET NULL"), nullable=True)
    signed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    doctor_signature = relationship("DoctorSignature", lazy="joined")

    def set_expiration(self):
        """Устанавливает дату истечения рецепта"""
        if self.term_months:
            self.expires_at = self.issue_date + timedelta(days=30 * self.term_months)
        else:
            self.expires_at = self.issue_date + timedelta(days=90)


class PrescriptionFile(Base):
    """
    Файл рецепта - загруженные пользователем рецепты
    """
    __tablename__ = "prescription_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_cor_id = Column(String(36), ForeignKey("users.cor_id", ondelete="CASCADE"), nullable=False)

    file_name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # MIME-type
    file_size_kb = Column(Float, nullable=False)
    file_data = Column(LargeBinary, nullable=False)
    
    issue_date = Column(DateTime(timezone=True), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Relationships
    user = relationship("User", back_populates="prescription_files")
