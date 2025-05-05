import enum
import uuid
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Enum,
    Text,
    Date,
    Index,
    UniqueConstraint,
    func,
    Boolean,
    LargeBinary,
)
from sqlalchemy.orm import declarative_base, relationship, Mapped
from sqlalchemy.sql.sqltypes import DateTime
from cor_pass.database.db import engine

Base = declarative_base()


class Status(enum.Enum):
    premium: str = "premium"
    basic: str = "basic"


class DoctorStatus(enum.Enum):
    PENDING: str = "pending"
    APPROVED: str = "approved"


class AuthSessionStatus(enum.Enum):
    PENDING: str = "pending"
    APPROVED: str = "approved"
    REJECTED: str = "rejected"
    TIMEOUT: str = "timeout"


class PatientStatus(enum.Enum):
    registered = "registered"
    under_treatment = "under_treatment"
    discharged = "discharged"


# Типы макроархива для параметров кейса
class MacroArchive(enum.Enum):
    ESS = "ESS - без остатка"
    RSS = "RSS - остаток"


# Типы декальцинации для параметров кейса
class DecalcificationType(enum.Enum):
    ABSENT = "Отсутствует"
    EDTA = "EDTA"
    ACIDIC = "Кислотная"


# Типы образцов для параметров кейса
class SampleType(enum.Enum):
    NATIVE = "Нативный биоматериал"
    BLOCKS = "Блоки/Стекла"


# Типы материалов (исследований) для параметров кейса
class MaterialType(enum.Enum):
    R = "Resectio"
    B = "Biopsy"
    E = "Excisio"
    C = "Cytology"
    CB = "Cellblock"
    S = "Second Opinion"
    A = "Autopsy"
    EM = "Electron Microscopy"


# Типы срочности для параметров кейса
class UrgencyType(enum.Enum):
    S = "Standard"
    U = "Urgent"
    F = "Frozen"


# Типы фиксации для параметров кейса
class FixationType(enum.Enum):
    NBF_10 = "10% NBF"
    OSMIUM = "Osmium"
    BOUIN = "Bouin"
    ALCOHOL = "Alcohol"
    GLUTARALDEHYDE_2 = "2% Glutaraldehyde"
    OTHER = "Другое"


# Типы исследований для направления
class StudyType(enum.Enum):
    CYTOLOGY = "цитология"
    HISTOPATHOLOGY = "патогистология"
    IMMUNOHISTOCHEMISTRY = "иммуногистохимия"
    FISH_CISH = "FISH/CISH"


# Типы окрашивания для стёкол
class StainingType(enum.Enum):
    HE = "H&E"
    ALCIAN_PAS = "Alcian PAS"
    CONGO_RED = "Congo red"
    MASSON_TRICHROME = "Masson Trichrome"
    VAN_GIESON = "van Gieson"
    ZIEHL_NEELSEN = "Ziehl Neelsen"
    WARTHIN_STARRY_SILVER = "Warthin-Starry Silver"
    GROCOTT_METHENAMINE_SILVER = "Grocott's Methenamine Silver"
    TOLUIDINE_BLUE = "Toluidine Blue"
    PERLS_PRUSSIAN_BLUE = "Perls Prussian Blue"
    PAMS = "PAMS"
    PICROSIRIUS = "Picrosirius"
    SIRIUS_RED = "Sirius red"
    THIOFLAVIN_T = "Thioflavin T"
    TRICHROME_AFOG = "Trichrome AFOG"
    VON_KOSSA = "von Kossa"
    GIEMSA = "Giemsa"
    OTHAR = "Othar"


class Grossing_status(enum.Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cor_id = Column(String(250), unique=True, nullable=True)
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

    user_doctors = relationship(
        "Doctor", back_populates="user", cascade="all, delete-orphan"
    )
    patient = relationship("Patient", back_populates="user", uselist=False)

    # Индексы
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_cor_id", "cor_id"),
    )


class Doctor(Base):
    __tablename__ = "doctors"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id = Column(
        String(36), ForeignKey("users.cor_id"), unique=True, nullable=False
    )
    work_email = Column(String(250), unique=True, nullable=False)
    phone_number = Column(String(20), nullable=True)
    first_name = Column(String(100), nullable=True)
    surname = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    doctors_photo = Column(LargeBinary, nullable=True)
    scientific_degree = Column(String(100), nullable=True)
    date_of_last_attestation = Column(Date, nullable=True)
    status = Column(Enum(DoctorStatus), default=DoctorStatus.PENDING, nullable=False)

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
    patient_statuses = relationship("DoctorPatientStatus", back_populates="doctor")


class Diploma(Base):
    __tablename__ = "diplomas"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id = Column(String(36), ForeignKey("doctors.doctor_id"), nullable=False)
    scan = Column(LargeBinary, nullable=True)
    date = Column(Date, nullable=False)
    series = Column(String(50), nullable=False)
    number = Column(String(50), nullable=False)
    university = Column(String(250), nullable=False)

    doctor = relationship("Doctor", back_populates="diplomas")


class Certificate(Base):
    __tablename__ = "certificates"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id = Column(String(36), ForeignKey("doctors.doctor_id"), nullable=False)
    scan = Column(LargeBinary, nullable=True)
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


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.cor_id"), nullable=False)
    device_type = Column(String(250), nullable=True)
    device_info = Column(String(250), nullable=True)
    ip_address = Column(String(250), nullable=True)
    device_os = Column(String(250), nullable=True)
    refresh_token = Column(LargeBinary, nullable=True)
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


class Patient(Base):
    __tablename__ = "patients"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_cor_id = Column(
        String(36), ForeignKey("users.cor_id"), unique=True, nullable=False
    )
    encrypted_surname = Column(LargeBinary, nullable=True)  # Зашифрована фамилия
    encrypted_first_name = Column(LargeBinary, nullable=True)  # Зашифрованное имя
    encrypted_middle_name = Column(
        LargeBinary, nullable=True
    )  # Зашифрованное отчество (может быть null)
    birth_date = Column(Date, nullable=True)
    sex = Column(String(10), nullable=True)
    email = Column(String(250), nullable=True)
    phone_number = Column(String(20), nullable=True)
    address = Column(String(500), nullable=True)
    photo = Column(LargeBinary, nullable=True)  # Хранение фото как бинарные данные
    change_date = Column(DateTime, default=func.now(), onupdate=func.now())
    create_date = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="patient")
    doctor_statuses = relationship("DoctorPatientStatus", back_populates="patient")

    def __repr__(self):
        return f"<Patient(id='{self.id}', patient_cor_id='{self.patient_cor_id}')>"


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


# Кейс
class Case(Base):
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), index=True)
    creation_date = Column(DateTime, default=func.now())
    case_code = Column(String(250), index=True)
    bank_count = Column(Integer, default=0)
    cassette_count = Column(Integer, default=0)
    glass_count = Column(Integer, default=0)
    grossing_status = Column(
        Enum(Grossing_status), default=Grossing_status.PROCESSING
    )

    samples = relationship(
        "Sample", back_populates="case", cascade="all, delete-orphan"
    )
    # directions = relationship("Direction", back_populates="case")
    case_parameters = relationship(
        "CaseParameters",
        uselist=False,
        back_populates="case",
        cascade="all, delete-orphan",
    )


# Банка
class Sample(Base):
    __tablename__ = "samples"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    sample_number = Column(String(50))
    cassette_count = Column(Integer, default=0)
    glass_count = Column(Integer, default=0)
    archive = Column(Boolean, default=False)

    case = relationship("Case", back_populates="samples")
    cassette = relationship(
        "Cassette", back_populates="sample", cascade="all, delete-orphan"
    )


# Касета
class Cassette(Base):
    __tablename__ = "cassettes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sample_id = Column(String(36), ForeignKey("samples.id"), nullable=False)
    cassette_number = Column(String(50))  # Порядковый номер кассеты в рамках конкретной банки
    comment = Column(String(500), nullable=True)
    glass_count = Column(Integer, default=0)
    glass = relationship(
        "Glass", back_populates="cassette", cascade="all, delete-orphan"
    )
    sample = relationship("Sample", back_populates="cassette")


# Стекло
class Glass(Base):
    __tablename__ = "glasses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cassette_id = Column(String(36), ForeignKey("cassettes.id"), nullable=False)
    glass_number = Column(Integer)  # Порядковый номер стекла
    staining = Column(Enum(StainingType), nullable=True)
    glass_data = Column(LargeBinary, nullable=True)
    cassette = relationship("Cassette", back_populates="glass")


# Параметры кейса
class CaseParameters(Base):
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


# Направление на исследование
# class Direction(Base):
#     __tablename__ = "directions"

#     id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
#     case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
#     study_type = Column(Enum(StudyType), nullable=False)
#     container_count = Column(String(50), nullable=True)
#     medical_record_number = Column(String(250), nullable=True)
#     clinical_data = Column(Text, nullable=True)
#     medical_institution = Column(String(250), nullable=True)
#     department = Column(String(250), nullable=True)
#     doctor_contacts = Column(String(250), nullable=True)
#     medical_procedure = Column(String(250), nullable=True)
#     final_report_send_to = Column(String(250), nullable=True)
#     released = Column(String(250), nullable=True)

#     case = relationship("Case", back_populates="directions")


# Base.metadata.create_all(bind=engine)
