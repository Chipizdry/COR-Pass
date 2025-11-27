"""
Doctor Domain Models
Medical professionals, credentials, signatures, and patient assignments
"""
import uuid
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from .base import Base
from .enums import Doctor_Status, PatientStatus


class Doctor(Base):
    __tablename__ = "doctors"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id = Column(
        String(36), ForeignKey("users.cor_id"), unique=True, nullable=False
    )
    work_email = Column(String(250), unique=True, nullable=False)
    phone_number = Column(String(20), nullable=True)
    first_name = Column(String(100), nullable=True)
    middle_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    doctors_photo = Column(LargeBinary, nullable=True)
    scientific_degree = Column(String(100), nullable=True)
    date_of_last_attestation = Column(Date, nullable=True)
    status = Column(Enum(Doctor_Status), default=Doctor_Status.pending, nullable=False)
    passport_code = Column(String(20), nullable=True)
    taxpayer_identification_number = Column(String(20), nullable=True)
    reserv_scan_data = Column(LargeBinary, nullable=True)
    reserv_scan_file_type = Column(String, nullable=True)
    date_of_next_review = Column(Date, nullable=True)
    place_of_registration = Column(String, nullable=True)

    user = relationship("User", back_populates="user_doctors")
    diplomas = relationship(
        "Diploma", back_populates="doctor", cascade="all, delete-orphan"
    )
    certificates = relationship(
        "Certificate", back_populates="doctor", cascade="all, delete-orphan"
    )
    clinic_affiliations = relationship(
        "ClinicAffiliation", back_populates="doctor", cascade="all, delete-orphan"
    )
    patient_statuses = relationship(
        "DoctorPatientStatus", back_populates="doctor", cascade="all, delete-orphan"
    )
    signatures = relationship(
        "DoctorSignature", back_populates="doctor", cascade="all, delete-orphan"
    )
    doctor_diagnoses = relationship("DoctorDiagnosis", back_populates="doctor")
    signed_diagnoses = relationship("ReportSignature", back_populates="doctor")
    owned_cases = relationship("Case", back_populates="owner_obj")


class Lawyer(Base):
    """Legal professionals (also accessible via routes as Lawyer role)"""
    __tablename__ = "lawyers"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lawyer_cor_id = Column(
        String(36), ForeignKey("users.cor_id"), unique=True, nullable=False
    )
    first_name = Column(String(100), nullable=True)
    surname = Column(String(100), nullable=True)
    middle_name = Column(String(100), nullable=True)

    user = relationship("User", back_populates="user_lawyers")


class Diploma(Base):
    __tablename__ = "diplomas"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id = Column(String(36), ForeignKey("doctors.doctor_id"), nullable=False)
    file_data = Column(LargeBinary, nullable=True)
    file_type = Column(String, nullable=True)
    date = Column(Date, nullable=False)
    series = Column(String(50), nullable=False)
    number = Column(String(50), nullable=False)
    university = Column(String(250), nullable=False)

    doctor = relationship("Doctor", back_populates="diplomas")


class Certificate(Base):
    __tablename__ = "certificates"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id = Column(String(36), ForeignKey("doctors.doctor_id"), nullable=False)
    file_data = Column(LargeBinary, nullable=True)
    file_type = Column(String, nullable=True)
    date = Column(Date, nullable=False)
    series = Column(String(50), nullable=False)
    number = Column(String(50), nullable=False)
    university = Column(String(250), nullable=False)

    doctor = relationship("Doctor", back_populates="certificates")


class ClinicAffiliation(Base):
    __tablename__ = "clinic_affiliations"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id = Column(String(36), ForeignKey("doctors.doctor_id"), nullable=False)
    clinic_name = Column(String(250), nullable=False)
    department = Column(String(250), nullable=True)
    position = Column(String(250), nullable=True)
    specialty = Column(String(250), nullable=True)

    doctor = relationship("Doctor", back_populates="clinic_affiliations")


class DoctorSignature(Base):
    __tablename__ = "doctor_signatures"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id = Column(String(36), ForeignKey("doctors.id"), nullable=False)
    signature_name = Column(String(255), nullable=True)
    signature_scan_data = Column(LargeBinary, nullable=True)
    signature_scan_type = Column(String, nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

    # Связи
    doctor = relationship("Doctor", back_populates="signatures")


class DoctorSignatureSession(Base):
    __tablename__ = "doctor_signature_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_token = Column(String, unique=True, nullable=False)
    doctor_cor_id = Column(String(36), nullable=False)
    diagnosis_id = Column(String(36), nullable=True)
    ophthalmological_prescription_id = Column(String(36), nullable=True)
    doctor_signature_id = Column(String(36), nullable=True)
    status = Column(String, default="pending")  # pending/approved/rejected/expired
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())


class DoctorDiagnosis(Base):
    __tablename__ = "doctor_diagnoses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String(36), ForeignKey("reports.id"), nullable=False)
    doctor_id = Column(String(36), ForeignKey("doctors.doctor_id"), nullable=False)
    created_at = Column(DateTime, default=func.now())

    immunohistochemical_profile = Column(Text, nullable=True)
    molecular_genetic_profile = Column(Text, nullable=True)
    pathomorphological_diagnosis = Column(Text, nullable=True)

    icd_code = Column(String(50), nullable=True)
    comment = Column(Text, nullable=True)

    report_macrodescription = Column(Text, nullable=True)
    report_microdescription = Column(Text, nullable=True)

    # Связи
    report = relationship("Report", back_populates="doctor_diagnoses")
    doctor = relationship("Doctor")
    signature = relationship(
        "ReportSignature", uselist=False, back_populates="doctor_diagnosis_entry"
    )


class DoctorPatientStatus(Base):
    __tablename__ = "doctor_patient_statuses"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(String(36), ForeignKey("doctors.id"), nullable=False)
    status = Column(Enum(PatientStatus), nullable=False)
    assigned_date = Column(DateTime, default=func.now())
    updated_date = Column(DateTime, default=func.now(), onupdate=func.now())

    patient = relationship("Patient", back_populates="doctor_statuses")
    doctor = relationship("Doctor", back_populates="patient_statuses")

    __table_args__ = (
        # Каждый врач имеет только 1 конкретный статус под пациента
        UniqueConstraint(
            "patient_id", "doctor_id", name="unique_patient_doctor_status"
        ),
    )
