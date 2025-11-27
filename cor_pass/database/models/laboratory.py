"""
Laboratory Domain Models

This module contains all models related to laboratory operations:
- Case: Патогистологический случай
- Sample: Банка с биоматериалом
- Cassette: Кассета для образцов
- Glass: Стекло с препаратом
- CaseParameters: Параметры обработки кейса
- Referral: Направление на исследование
- ReferralAttachment: Прикрепленные файлы к направлению
"""

import uuid
from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    DateTime,
    Integer,
    Boolean,
    Text,
    Enum,
    LargeBinary,
    func,
    ARRAY,
)
from sqlalchemy.orm import relationship

from .base import Base
from .enums import (
    Grossing_status,
    StainingType,
    MacroArchive,
    DecalcificationType,
    SampleType,
    MaterialType,
    UrgencyType,
    FixationType,
    StudyType,
)


class Case(Base):
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), index=True)
    creation_date = Column(DateTime, default=func.now())
    case_code = Column(String(250), index=True, unique=True)
    bank_count = Column(Integer, default=0)
    cassette_count = Column(Integer, default=0)
    glass_count = Column(Integer, default=0)
    grossing_status = Column(Enum(Grossing_status), default=Grossing_status.CREATED)
    pathohistological_conclusion = Column(Text, nullable=True)
    microdescription = Column(Text, nullable=True)
    general_macrodescription = Column(Text, nullable=True)
    case_owner = Column(String(36), ForeignKey("doctors.doctor_id"), nullable=True)
    closing_date = Column(DateTime, nullable=True)
    is_printed_cassette = Column(Boolean, nullable=True, default=False)
    is_printed_glass = Column(Boolean, nullable=True, default=False)
    is_printed_qr = Column(Boolean, nullable=True, default=False)

    samples = relationship(
        "Sample", back_populates="case", cascade="all, delete-orphan"
    )
    referral = relationship(
        "Referral", back_populates="case", cascade="all, delete-orphan"
    )
    case_parameters = relationship(
        "CaseParameters",
        uselist=False,
        back_populates="case",
        cascade="all, delete-orphan",
    )
    report = relationship(
        "Report", back_populates="case", uselist=False, cascade="all, delete-orphan"
    )
    owner_obj = relationship(
        "Doctor", back_populates="owned_cases", foreign_keys=[case_owner]
    )


class Sample(Base):
    """Банка с биоматериалом"""
    __tablename__ = "samples"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    sample_number = Column(String(50))
    cassette_count = Column(Integer, default=0)
    glass_count = Column(Integer, default=0)
    archive = Column(Boolean, default=False)
    macro_description = Column(Text, nullable=True)
    is_printed_cassette = Column(Boolean, nullable=True, default=False)
    is_printed_glass = Column(Boolean, nullable=True, default=False)

    case = relationship("Case", back_populates="samples")
    cassette = relationship(
        "Cassette", back_populates="sample", cascade="all, delete-orphan"
    )


class Cassette(Base):
    """Кассета для образцов"""
    __tablename__ = "cassettes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sample_id = Column(String(36), ForeignKey("samples.id"), nullable=False)
    cassette_number = Column(
        String(50)
    )  # Порядковый номер кассеты в рамках конкретной банки
    comment = Column(String(500), nullable=True)
    glass_count = Column(Integer, default=0)
    is_printed = Column(Boolean, nullable=True, default=False)
    glass = relationship(
        "Glass", back_populates="cassette", cascade="all, delete-orphan"
    )
    sample = relationship("Sample", back_populates="cassette")


class Glass(Base):
    """Стекло с препаратом"""
    __tablename__ = "glasses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cassette_id = Column(String(36), ForeignKey("cassettes.id"), nullable=False)
    glass_number = Column(Integer)  # Порядковый номер стекла
    staining = Column(Enum(StainingType), nullable=True)
    glass_data = Column(LargeBinary, nullable=True)
    is_printed = Column(Boolean, nullable=True, default=False)
    scan_url = Column(String, nullable=True)
    preview_url = Column(String, nullable=True)
    cassette = relationship("Cassette", back_populates="glass")


class CaseParameters(Base):
    """Параметры обработки кейса"""
    __tablename__ = "case_parameters"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), unique=True, nullable=False)
    macro_archive = Column(Enum(MacroArchive), default=MacroArchive.ESS)
    decalcification = Column(
        Enum(DecalcificationType), default=DecalcificationType.ABSENT
    )
    sample_type = Column(Enum(SampleType), default=SampleType.NATIVE)
    material_type = Column(Enum(MaterialType), default=MaterialType.B)
    urgency = Column(Enum(UrgencyType), default=UrgencyType.S)
    container_count_actual = Column(Integer, nullable=True)
    fixation = Column(Enum(FixationType), default=FixationType.NBF_10)
    macro_description = Column(Text, nullable=True)

    case = relationship("Case", back_populates="case_parameters")


class Referral(Base):
    """Направление на исследование"""
    __tablename__ = "referrals"

    id = Column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )
    case_id = Column(
        String,
        ForeignKey("cases.id"),
        unique=True,
        nullable=False,
        comment="ID связанного кейса",
    )
    case_number = Column(String, index=True, nullable=False, comment="Номер кейса")
    created_at = Column(
        DateTime, default=func.now(), comment="Дата создания направления"
    )
    research_type = Column(Enum(StudyType), nullable=True, comment="Вид исследования")
    container_count = Column(
        Integer, nullable=True, comment="Фактическое количество контейнеров"
    )
    medical_card_number = Column(String, nullable=True, comment="Номер медкарты")
    clinical_data = Column(Text, nullable=True, comment="Клинические данные")
    clinical_diagnosis = Column(String, nullable=True, comment="Клинический диагноз")
    medical_institution = Column(
        String, nullable=True, comment="Медицинское учреждение"
    )
    department = Column(String, nullable=True, comment="Отделение")
    attending_doctor = Column(String, nullable=True, comment="Лечащий врач")
    doctor_contacts = Column(String, nullable=True, comment="Контакты врача")
    medical_procedure = Column(String, nullable=True, comment="Медицинская процедура")
    final_report_delivery = Column(
        Text, nullable=True, comment="Финальный репорт отправить"
    )
    issued_at = Column(DateTime, nullable=True, comment="Выдано (дата)")
    biomaterial_date = Column(
        DateTime, nullable=True, comment="Дата забора биоматериала"
    )

    case = relationship("Case", back_populates="referral")

    attachments = relationship(
        "ReferralAttachment",
        back_populates="referral",
        cascade="all, delete-orphan",
        lazy="joined",
    )


class ReferralAttachment(Base):
    """Прикрепленные файлы к направлению"""
    __tablename__ = "referral_attachments"

    id = Column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )
    referral_id = Column(
        String,
        ForeignKey("referrals.id"),
        nullable=False,
        comment="ID связанного направления",
    )
    filename = Column(String, nullable=False, comment="Имя файла")
    content_type = Column(
        String,
        nullable=False,
        comment="Тип содержимого (например, image/jpeg, application/pdf)",
    )
    file_data = Column(LargeBinary, nullable=False, comment="Бинарные данные файла")

    referral = relationship("Referral", back_populates="attachments")


class MedicalLaboratory(Base):
    """
    Медицинская лаборатория - информация о партнерских лабораториях
    """
    __tablename__ = "medical_laboratories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lab_name = Column(String(255), nullable=True)
    lab_email = Column(String(255), nullable=True)
    lab_phone_number = Column(String(255), nullable=True)
    lab_website = Column(String(255), nullable=True)
    lab_address = Column(String(255), nullable=True)

    lab_logo_type = Column(String(50), nullable=True)  # MIME-type
    lab_logo_data = Column(LargeBinary, nullable=True)  # Логотип лаборатории
    
    uploaded_at = Column(DateTime(timezone=True), nullable=True, default=func.now())


class ReportSignature(Base):
    """
    Подпись отчета - подпись врача на отчете
    """
    __tablename__ = "report_signatures"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    diagnosis_entry_id = Column(String(36), ForeignKey("doctor_diagnoses.id"), nullable=True, unique=True)
    doctor_id = Column(String(36), ForeignKey("doctors.id"), nullable=False)
    doctor_signature_id = Column(String(36), ForeignKey("doctor_signatures.id"), nullable=True)
    signed_at = Column(DateTime, default=func.now())

    # Relationships
    doctor_diagnosis_entry = relationship("DoctorDiagnosis", back_populates="signature")
    doctor = relationship("Doctor")
    doctor_signature = relationship("DoctorSignature")


class Report(Base):
    """
    Отчет - патогистологический отчет по кейсу
    """
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), unique=True, nullable=False)
    attached_glass_ids = Column(ARRAY(String(36)), nullable=True, default=[])
    
    # Relationships
    case = relationship("Case", back_populates="report")
    doctor_diagnoses = relationship(
        "DoctorDiagnosis",
        back_populates="report",
        order_by="DoctorDiagnosis.created_at",
    )
