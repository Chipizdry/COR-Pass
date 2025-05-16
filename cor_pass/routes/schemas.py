from enum import Enum
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    EmailStr,
    PositiveInt,
    ValidationInfo,
    field_validator,
    model_validator,
)
from typing import List, Optional, Union
from datetime import datetime
from cor_pass.database import models
from cor_pass.database.models import AccessLevel, Status, Doctor_Status, AuthSessionStatus, MacroArchive, DecalcificationType, SampleType, MaterialType, UrgencyType, FixationType, StudyType, StainingType
import re
from datetime import date

# AUTH MODELS


class UserModel(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=20)
    birth: Optional[int] = Field(None, ge=1945, le=2100)
    user_sex: Optional[str] = Field(None, max_length=1)
    cor_id: Optional[str] = Field(None, max_length=15)

    @field_validator("user_sex")
    def user_sex_must_be_m_or_f(cls, v):
        if v not in ["M", "F"]:
            raise ValueError('user_sex must be "M" or "F"')
        return v


class UserDb(BaseModel):
    id: str
    cor_id: Optional[str] = Field(None, max_length=15)
    email: str
    account_status: Status
    is_active: bool
    last_password_change: datetime
    user_sex: Optional[str] = Field(None, max_length=1)
    birth: Optional[int] = Field(None, ge=1945, le=2100)
    user_index: int
    created_at: datetime
    last_active: Optional[datetime] = None

    class Config:
        from_attributes = True


class ResponseUser(BaseModel):
    user: UserDb
    detail: str = "User successfully created"
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenModel(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponseModel(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    # is_admin: bool
    session_id: Optional[str] = None
    requires_master_key: bool = False
    message: Optional[str] = None


class EmailSchema(BaseModel):
    email: EmailStr


class VerificationModel(BaseModel):
    email: EmailStr
    verification_code: int


class ChangePasswordModel(BaseModel):
    email: Optional[str]
    password: str = Field(min_length=6, max_length=20)


class ChangeMyPasswordModel(BaseModel):
    old_password: str = Field(min_length=6, max_length=20)
    new_password: str = Field(min_length=6, max_length=20)


class RecoveryCodeModel(BaseModel):
    email: EmailStr
    recovery_code: str


class PasswordStorageSettings(BaseModel):
    local_password_storage: bool
    cloud_password_storage: bool


class MedicalStorageSettings(BaseModel):
    local_medical_storage: bool
    cloud_medical_storage: bool


class UserSessionModel(BaseModel):
    cor_id: Optional[str] = Field(None, max_length=15)
    device_type: str
    device_info: str
    ip_address: str
    device_os: str
    refresh_token: str


class UserSessionResponseModel(BaseModel):
    id: str
    user_id: str
    device_type: str
    device_info: str
    ip_address: str
    device_os: str
    created_at: datetime
    updated_at: datetime


class UserSessionDBModel(BaseModel):
    id: str
    cor_id: Optional[str] = Field(None, max_length=15)
    device_type: str
    device_info: str
    ip_address: str
    device_os: str
    refresh_token: str
    created_at: datetime
    updated_at: datetime


# PASS-MANAGER MODELS


class TagModel(BaseModel):
    name: str = Field(max_length=25)


class TagResponse(TagModel):
    id: int
    name: str = Field(max_length=25)

    class Config:
        from_attributes = True


class CreateRecordModel(BaseModel):
    record_name: str = Field(max_length=25)
    website: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    notes: Optional[str] = None
    tag_names: List[str] = []


class RecordResponse(BaseModel):
    record_id: int
    record_name: str
    website: str
    username: str
    password: str
    created_at: datetime
    edited_at: datetime
    notes: str
    user_id: str
    is_favorite: bool

    # tags: List[TagModel]

    class Config:
        from_attributes = True


class MainscreenRecordResponse(BaseModel):
    record_id: int
    record_name: str
    website: str
    username: str
    password: str
    is_favorite: bool

    class Config:
        from_attributes = True


class UpdateRecordModel(BaseModel):
    record_name: str = Field(max_length=25)
    website: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    notes: Optional[str] = None
    tag_names: List[str] = []


# PASS-GENERATOR MODELS


class PasswordGeneratorSettings(BaseModel):
    length: int = Field(12, ge=8, le=128)
    include_uppercase: bool = True
    include_lowercase: bool = True
    include_digits: bool = True
    include_special: bool = True


class WordPasswordGeneratorSettings(BaseModel):
    length: int = Field(4, ge=1, le=7)
    separator_hyphen: bool = True
    separator_underscore: bool = True
    include_uppercase: bool = True


# MEDICAL MODELS


class CreateCorIdModel(BaseModel):
    medical_institution_code: str = Field(max_length=3)
    patient_number: str = Field(max_length=3)
    patient_birth: int = Field(ge=1900, le=2100)
    patient_sex: str = Field(max_length=1)

    @field_validator("patient_sex")
    def patient_sex_must_be_m_or_f(cls, v):
        if v not in ["M", "F"]:
            raise ValueError('patient_sex must be "M" or "F"')
        return v


class ResponseCorIdModel(BaseModel):
    cor_id: str = None


# OTP MODELS


class CreateOTPRecordModel(BaseModel):
    record_name: str = Field(max_length=50)
    username: str = Field(max_length=50)
    private_key: str = Field(max_length=50)

    @field_validator("private_key")
    def validate_private_key(cls, v):
        if not re.match(r"^[A-Z2-7]*$", v):
            raise ValueError("private_key must be a valid Base32 encoded string")
        return v


class OTPRecordResponse(BaseModel):
    record_id: int
    record_name: str
    username: str
    otp_password: str
    remaining_time: float


class UpdateOTPRecordModel(BaseModel):
    record_name: str = Field(max_length=50)
    username: str = Field(max_length=50)


# DOCTOR MODELS


class DiplomaCreate(BaseModel):
    scan: Optional[bytes] = Field(None, description="Скан диплома")
    date: Optional[datetime] = Field(..., description="Дата выдачи диплома")
    series: str = Field(..., max_length=50, description="Серия диплома")
    number: str = Field(..., max_length=50, description="Номер диплома")
    university: str = Field(..., max_length=250, description="Название ВУЗа")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class DiplomaResponse(BaseModel):
    id: str = Field(..., description="ID диплома")
    date: Optional[datetime] = Field(..., description="Дата выдачи диплома")
    series: str = Field(..., description="Серия диплома")
    number: str = Field(..., description="Номер диплома")
    university: str = Field(..., description="Название ВУЗа")
    file_data: Optional[str] = Field(
        None,
        description="Ссылка на документ",
    )

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class CertificateCreate(BaseModel):
    scan: Optional[bytes] = Field(None, description="Скан сертификата")
    date: Optional[datetime] = Field(..., description="Дата выдачи сертификата")
    series: str = Field(..., max_length=50, description="Серия сертификата")
    number: str = Field(..., max_length=50, description="Номер сертификата")
    university: str = Field(..., max_length=250, description="Название ВУЗа")

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class CertificateResponse(BaseModel):
    id: str = Field(..., description="ID сертификата")
    date: Optional[datetime] = Field(..., description="Дата выдачи сертификата")
    series: str = Field(..., description="Серия сертификата")
    number: str = Field(..., description="Номер сертификата")
    university: str = Field(..., description="Название ВУЗа")
    file_data: Optional[str] = Field(
        None,
        description="Ссылка на документ",
    )

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class ClinicAffiliationCreate(BaseModel):
    clinic_name: str = Field(..., max_length=250, description="Название клиники")
    department: Optional[str] = Field(None, max_length=250, description="Отделение")
    position: Optional[str] = Field(None, max_length=250, description="Должность")
    specialty: Optional[str] = Field(None, max_length=250, description="Специальность")

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class ClinicAffiliationResponse(BaseModel):
    id: str = Field(..., description="ID клиники")
    clinic_name: str = Field(..., description="Название клиники")
    department: Optional[str] = Field(None, description="Отделение")
    position: Optional[str] = Field(None, description="Должность")
    specialty: Optional[str] = Field(None, description="Специальность")

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class DoctorWithRelationsResponse(BaseModel):
    id: str
    doctor_id: str
    work_email: str
    phone_number: Optional[str]
    first_name: Optional[str]
    surname: Optional[str]
    last_name: Optional[str]
    doctors_photo: Optional[str] = Field(
        None, description="Ссылка на фото"
    )
    scientific_degree: Optional[str]
    date_of_last_attestation: Optional[date]
    status: str
    diplomas: List[DiplomaResponse] = []
    certificates: List[CertificateResponse] = []
    clinic_affiliations: List[ClinicAffiliationResponse] = []

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class DoctorCreate(BaseModel):
    work_email: str
    phone_number: Optional[str] = None
    first_name: str
    surname: str
    last_name: str
    passport_code: str
    taxpayer_identification_number: str
    scientific_degree: Optional[str] = None
    date_of_last_attestation: Optional[date] = None
    diplomas: List[DiplomaCreate] = []
    certificates: List[CertificateCreate] = []
    clinic_affiliations: List[ClinicAffiliationCreate] = []

    class Config:
        json_schema_extra = {
            "example": {
                "work_email": "doctor@example.com",
                "phone_number": "+3806666666",
                "first_name": "John",
                "surname": "Doe",
                "last_name": "Smith",
                "passport_code": "CN123456",
                "taxpayer_identification_number": "1234567890",
                "scientific_degree": "PhD",
                "date_of_last_attestation": "2022-12-31",
                "diplomas": [
                    {
                        "date": "2023-01-01",
                        "series": "AB",
                        "number": "123456",
                        "university": "Medical University",
                    }
                ],
                "certificates": [
                    {
                        "date": "2023-01-01",
                        "series": "CD",
                        "number": "654321",
                        "university": "Another University",
                    }
                ],
                "clinic_affiliations": [
                    {
                        "clinic_name": "City Hospital",
                        "department": "Cardiology",
                        "position": "Senior Doctor",
                        "specialty": "Cardiologist",
                    }
                ],
            }
        }


class DoctorResponse(BaseModel):
    id: str = Field(..., description="ID врача")
    doctor_id: str = Field(..., description="COR-ID врача")
    work_email: EmailStr = Field(..., description="Рабочий имейл")
    phone_number: Optional[str] = Field(None, description="Номер телефона")
    first_name: Optional[str] = Field(None, description="Имя врача")
    surname: Optional[str] = Field(None, description="Фамилия врача")
    last_name: Optional[str] = Field(None, description="Отчество врача")
    doctors_photo: Optional[str] = Field(
        None, description="Ссылка на фото врача"
    )
    scientific_degree: Optional[str] = Field(None, description="Научная степень")
    date_of_last_attestation: Optional[date] = Field(
        None, description="Дата последней атестации"
    )
    status: Doctor_Status

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class DoctorCreateResponse(BaseModel):
    id: str = Field(..., description="ID врача")
    doctor_cor_id: str = Field(..., description="COR-ID врача")
    work_email: EmailStr = Field(..., description="Рабочий имейл")
    phone_number: Optional[str] = Field(None, description="Номер телефона")
    first_name: Optional[str] = Field(None, description="Имя врача")
    surname: Optional[str] = Field(None, description="Фамилия врача")
    last_name: Optional[str] = Field(None, description="Отчество врача")
    scientific_degree: Optional[str] = Field(None, description="Научная степень")
    date_of_last_attestation: Optional[date] = Field(
        None, description="Дата последней атестации"
    )
    status: Doctor_Status
    diploma_id: List = Field(..., description="ID дипломов")
    certificates_id: List = Field(..., description="ID сертификатов")
    clinic_affiliations_id: List = Field(..., description="ID записей о клиниках")


    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


# CorIdAuthSession MODELS


class InitiateLoginRequest(BaseModel):
    email: Optional[EmailStr] = None
    cor_id: Optional[str] = None

    @model_validator(mode="before")
    def check_either_email_or_cor_id(cls, data: dict):
        email = data.get("email")
        cor_id = data.get("cor_id")
        if not email and not cor_id:
            raise ValueError("Требуется указать либо email, либо cor_id")
        return data


class InitiateLoginResponse(BaseModel):
    session_token: str


class SessionLoginStatus(str, Enum):
    approved = "approved"
    rejected = "rejected"


class ConfirmLoginRequest(BaseModel):
    email: Optional[EmailStr] = None
    cor_id: Optional[str] = None
    session_token: str
    status: SessionLoginStatus

    @model_validator(mode="before")
    def check_either_email_or_cor_id(cls, data: dict):
        email = data.get("email")
        cor_id = data.get("cor_id")
        if not email and not cor_id:
            raise ValueError("Требуется указать либо email, либо cor_id")
        return data


class ConfirmLoginResponse(BaseModel):
    message: str



# PATIENTS MODELS

class PatientResponce(BaseModel):
    patient_cor_id: str
    encrypted_surname: Optional[bytes] = None
    encrypted_first_name: Optional[bytes] = None
    encrypted_middle_name: Optional[bytes] = None
    sex: Optional[str]
    birth_date: Optional[date]
    status: Optional[str]


class PaginatedPatientsResponse(BaseModel):
    items: List[PatientResponce]
    total: int


class NewPatientRegistration(BaseModel):
    email: EmailStr = Field(
        ..., description="Email пациента (будет использован для создания пользователя)"
    )
    surname: str = Field(..., description="Фамилия пациента")
    first_name: str = Field(..., description="Имя пациента")
    middle_name: Optional[str] = Field(None, description="Отчество пациента")
    birth_date: Optional[date] = Field(None, description="Дата рождения пациента")
    sex: Optional[str] = Field(None, max_length=1, description="Пол пациента, может быть 'M'(мужской) или 'F'(женский)")
    phone_number: Optional[str] = Field(None, description="Номер телефона пациента")
    address: Optional[str] = Field(None, description="Адрес пациента")
    # photo: Optional[str] = Field(None, description="Фото пациента (base64 или blob)")
    # status: Optional[str] = Field("registered", description="Начальный статус пациента")

    @field_validator("sex")
    def user_sex_must_be_m_or_f(cls, v):
        if v not in ["M", "F"]:
            raise ValueError('user_sex must be "M" or "F"')
        return v


class ExistingPatientAdd(BaseModel):
    cor_id: str = Field(..., description="Cor ID существующего пользователя")


# Модели для лабораторных исследований

# class GrossingStatus(str, Enum):
#     processing = "processing"
#     completed = "completed"


class GlassBase(BaseModel):
    glass_number: int
    staining: Optional[str] = None


class GlassCreate(BaseModel):
    cassette_id: str
    staining_type: StainingType = Field(
        ...,
        description="Тип окрашивания для стекла",
        example=StainingType.HE,
    )
    num_glasses: int = Field(default=1, description="Количество создаваемых стекол")


class Glass(GlassBase):
    id: str
    cassette_id: str

    class Config:
        from_attributes = True


class DeleteGlassesRequest(BaseModel):
    glass_ids: List[str]

class DeleteGlassesResponse(BaseModel):
    deleted_count: int
    message: str
    not_found_ids: List[str] | None = None
class GetSample(BaseModel):
    sample_id: str

class SampleBase(BaseModel):
    sample_number: str
    archive: bool = False
    cassette_count: int = 0
    glass_count: int = 0


class SampleCreate(BaseModel):
    case_id: str
    num_samples: int = 1


class CassetteBase(BaseModel):
    cassette_number: str
    comment: Optional[str] = None


class CassetteCreate(BaseModel):
    sample_id: str
    num_cassettes: int = 1



class Cassette(CassetteBase):
    id: str
    sample_id: str
    glasses: List["Glass"] = []

    class Config:
        from_attributes = True

class Cassette(CassetteBase):
    id: str
    sample_id: str
    glasses: List[Glass] = []

    class Config:
        from_attributes = True

class Sample(SampleBase):
    id: str
    case_id: str
    cassettes: List[Cassette] = []
    class Config:
        from_attributes = True



class CaseBase(BaseModel):
    patient_cor_id: str
    # case_code: Optional[str] = None
    # grossing_status: str = Field(default="processing")


class CaseCreate(BaseModel):
    patient_cor_id: str
    num_cases: int = 1
    urgency: UrgencyType = Field(
        ...,
        description="Срочность иссследования",
        example=UrgencyType.S,)
    material_type: MaterialType = Field(
        ...,
        description="Тип исследования",
        example=MaterialType.R,)

class CaseCreateResponse(BaseModel):
    id: str
    case_code: str
    patient_id: str
    grossing_status: str
    creation_date: datetime
    cassette_count: int
    bank_count: int
    glass_count: int



class UpdateCaseCode(BaseModel):
    case_id: str
    update_data: str = Field(min_length=5, max_length=5, description="Последние 5 целочисельных символлов кода кейса")

class Case(BaseModel):
    id: str
    creation_date: datetime
    patient_id: str
    case_code: str
    bank_count: int
    cassette_count: int
    glass_count: int
    # samples: List = []  # Связь с банками
    # directions: List = []
    # case_parameters: Optional[List] = None

    class Config:
        from_attributes = True

class UpdateCaseCodeResponce(BaseModel):
    id: str
    patient_id: str
    creation_date: datetime
    case_code: str
    bank_count: int
    cassette_count: int
    glass_count: int

    class Config:
        from_attributes = True



class FirstCaseDetailsSchema(BaseModel):
    id: str
    case_code: str
    creation_date: datetime
    samples: List[Sample]

class PatientFirstCaseDetailsResponse(BaseModel):
    all_cases: List[Case]
    first_case_details: Optional[FirstCaseDetailsSchema] = None

class CaseParametersScheema(BaseModel):
    case_id: str
    macro_archive: MacroArchive
    decalcification: DecalcificationType
    sample_type: SampleType
    material_type: MaterialType
    urgency: UrgencyType
    container_count_actual: int
    fixation: FixationType
    macro_description: str


class SampleWithoutCassettesSchema(BaseModel):
    id: str
    sample_number: str
    case_id: str
    archive: bool
    cassette_count: int
    glass_count: int
    cassettes: List = []  # Для остальных семплов список кассет будет пустой

class CaseDetailsResponse(BaseModel):
    id: str
    case_code: str
    creation_date: datetime
    bank_count: int
    cassette_count: int
    glass_count: int
    samples: List[SampleWithoutCassettesSchema | Sample]

class SimpleCaseResponse(BaseModel):
    id: str
    case_code: str
    creation_date: datetime
    bank_count: int
    cassette_count: int
    glass_count: int

class CaseListResponse(BaseModel):
    items: List[Union[CaseDetailsResponse, SimpleCaseResponse]]

class CreateSampleWithDetails(BaseModel):
    created_samples: List[Sample]
    first_sample_details: Optional[Sample] = None


# Модели для внешних девайсов

class DeviceRegistration(BaseModel):
    device_token: str

class DeviceResponse(BaseModel):
    token: str # JWT токен
    device_name: str
    user_id: str

class GrantDeviceAccess(BaseModel):
    user_id: str
    device_id: int
    access_level: AccessLevel

class DeviceAccessResponse(BaseModel):
    id: int
    device_id: int
    granting_user_id: str
    accessing_user_id: str
    access_level: AccessLevel

class GenerateManufacturedDevices(BaseModel):
    count: PositiveInt


# Модели для принтеров



"""
    device_class = Column(String, nullable=False)
    device_identifier = Column(String, nullable=False, unique=True, index=True)
    subnet_mask = Column(String, nullable=True)
    gateway = Column(String, nullable=True)
    ip_address = Column(String, nullable=False)
    port = Column(Integer, nullable=True)
    comment = Column(String, nullable=True)
    location = Column(String, nullable=True)
"""


class CreatePrintingDevice(BaseModel):
    device_class: str = Field(None, description="Клас устройства")
    device_identifier: str = Field(None, description="Идентификатор устройства")
    subnet_mask: Optional[str] = Field(None, max_length=20, description="Маска подсети")
    gateway: Optional[str] = Field(None, max_length=20, description="Шлюз")
    ip_address: str = Field(max_length=20, description="IP-адрес")
    port: Optional[int] = Field(None, le=65535, description="Порт")
    comment: Optional[str] = Field(None, description="Комментарий")
    location: Optional[str] = Field(None, description="Локация")


class ResponcePrintingDevice(BaseModel):
    id: str
    device_class: str 
    device_identifier: str 
    subnet_mask: Optional[str] 
    gateway: Optional[str] 
    ip_address: str 
    port: Optional[int] 
    comment: Optional[str] 
    location: Optional[str] 


class UpdatePrintingDevice(BaseModel):
    device_class: str = Field(None, description="Клас устройства")
    device_identifier: str = Field(None, description="Идентификатор устройства")
    subnet_mask: Optional[str] = Field(None, max_length=20, description="Маска подсети")
    gateway: Optional[str] = Field(None, max_length=20, description="Шлюз")
    ip_address: str = Field(max_length=20, description="IP-адрес")
    port: Optional[int] = Field(None, le=65535, description="Порт")
    comment: Optional[str] = Field(None, description="Комментарий")
    location: Optional[str] = Field(None, description="Локация")