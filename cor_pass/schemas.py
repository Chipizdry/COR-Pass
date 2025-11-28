from enum import Enum
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    EmailStr,
    PositiveInt,
    ValidationInfo,
    computed_field,
    field_validator,
    model_validator,
)
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar, Union
from datetime import datetime, time, timedelta, timezone, date

from cor_pass.database.models import (
    AccessLevel,
    PatientClinicStatus,
    PatientStatus,
    Status,
    MedicineIntakeStatus,
    Doctor_Status,
    MacroArchive,
    DecalcificationType,
    SampleType,
    MaterialType,
    UrgencyType,
    FixationType,
    StudyType,
    StainingType,
)
import re
from datetime import date

# AUTH MODELS



class UserModel(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=32)
    birth: Optional[int] = Field(
        None, 
        ge=1900, 
        description="Год рождения (например: 1990). Должен быть не раньше 1900 и не позже текущего года"
    )
    user_sex: Optional[Literal["M", "F", "*"]] = Field(
        None, 
        description="Пол пользователя: 'M' (мужской), 'F' (женский), '*' (другое/не указано)"
    )

    @field_validator("birth")
    @classmethod
    def validate_birth_year(cls, v: Optional[int]) -> Optional[int]:
        """Валидация года рождения - не может быть в будущем"""
        if v is None:
            return v
        
        current_year = datetime.now().year
        if v > current_year:
            raise ValueError(f"Год рождения не может быть больше текущего года ({current_year})")
        
        return v

    @field_validator("user_sex")
    @classmethod
    def user_sex_must_be_m_or_f(cls, v):
        if v is not None and v not in ["M", "F", "*"]:
            raise ValueError('user_sex должен быть "M" (мужской), "F" (женский) или "*" (другое)')
        return v


class UserDb(BaseModel):
    id: str
    cor_id: Optional[str] = Field(None, max_length=15)
    email: str
    account_status: Status
    is_active: bool
    last_password_change: datetime
    user_sex: Optional[str] = Field(None, max_length=1)
    birth: Optional[int] = Field(None, ge=1900)
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
    session_id: Optional[str] = None
    device_id: Optional[str] = None


class NewUserRegistration(BaseModel):
    email: EmailStr = Field(..., description="Email пользователя")
    birth_date: Optional[date] = Field(None, description="Дата рождения пациента")
    sex: Optional[str] = Field(
        None,
        max_length=1,
        description="Пол пациента, может быть 'M'(мужской) или 'F'(женский)",
    )

    @field_validator("sex")
    def user_sex_must_be_m_or_f(cls, v):
        if v not in ["M", "F"]:
            raise ValueError('user_sex must be "M" or "F"')
        return v


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
    device_id: Optional[str] = None


class RecoveryResponseModel(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    message: Optional[str] = None
    confirmation: Optional[bool] = False
    session_id: Optional[str] = None
    device_id: Optional[str] = None


class EmailSchema(BaseModel):
    email: EmailStr


class VerificationModel(BaseModel):
    email: EmailStr
    verification_code: int


class ChangePasswordModel(BaseModel):
    email: Optional[str]
    password: str = Field(min_length=8, max_length=32)


class ChangeMyPasswordModel(BaseModel):
    old_password: str = Field(min_length=8, max_length=32)
    new_password: str = Field(min_length=8, max_length=32)


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
    jti: str
    access_token: str
    app_id: Optional[str] = None
    device_id: Optional[str] = None


class UserSessionResponseModel(BaseModel):
    id: str
    user_id: str
    device_type: str
    device_info: str
    ip_address: str
    device_os: str
    created_at: datetime
    updated_at: datetime
    jti: Optional[str]
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    region_name: Optional[str] = None
    city_name: Optional[str] = None


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


class UserMeResponse(BaseModel):
    corid: str | None
    roles: list[str]
    first_name: Optional[str] = None
    surname: Optional[str] = None
    middle_name: Optional[str] = None


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
    series: str = Field(..., min_length=1, max_length=50, description="Серия диплома")
    number: str = Field(..., min_length=1, max_length=50, description="Номер диплома")
    university: str = Field(..., min_length=2, max_length=250, description="Название ВУЗа")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator('date')
    @classmethod
    def validate_diploma_date(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v
        # Если дата naive (без timezone), делаем её UTC
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        # Диплом не может быть выдан в будущем
        if v > datetime.now(timezone.utc):
            raise ValueError("Дата выдачи диплома не может быть в будущем")
        # Диплом не может быть старше 1900 года
        if v.year < 1900:
            raise ValueError("Дата выдачи диплома не может быть раньше 1900 года")
        return v

    @field_validator('series', 'number')
    @classmethod
    def validate_not_empty(cls, v: str, info: ValidationInfo) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} не может быть пустым")
        return v.strip()

    @field_validator('university')
    @classmethod
    def validate_university(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Название ВУЗа не может быть пустым")
        return v.strip()


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
    series: str = Field(..., min_length=1, max_length=50, description="Серия сертификата")
    number: str = Field(..., min_length=1, max_length=50, description="Номер сертификата")
    university: str = Field(..., min_length=2, max_length=250, description="Название ВУЗа")

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True

    @field_validator('date')
    @classmethod
    def validate_certificate_date(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v
        # Если дата naive (без timezone), делаем её UTC
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        # Сертификат не может быть выдан в будущем
        if v > datetime.now(timezone.utc):
            raise ValueError("Дата выдачи сертификата не может быть в будущем")
        # Сертификат не может быть старше 1900 года
        if v.year < 1900:
            raise ValueError("Дата выдачи сертификата не может быть раньше 1900 года")
        return v

    @field_validator('series', 'number')
    @classmethod
    def validate_not_empty(cls, v: str, info: ValidationInfo) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} не может быть пустым")
        return v.strip()

    @field_validator('university')
    @classmethod
    def validate_university(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Название ВУЗа не может быть пустым")
        return v.strip()


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
    clinic_name: str = Field(..., min_length=2, max_length=250, description="Название клиники")
    department: Optional[str] = Field(None, max_length=250, description="Отделение")
    position: Optional[str] = Field(None, max_length=250, description="Должность")
    specialty: Optional[str] = Field(None, max_length=250, description="Специальность")

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True

    @field_validator('clinic_name')
    @classmethod
    def validate_clinic_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Название клиники не может быть пустым")
        return v.strip()

    @field_validator('department', 'position', 'specialty')
    @classmethod
    def validate_optional_fields(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() == "":
            return None
        return v.strip() if v else None


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
    middle_name: Optional[str]
    last_name: Optional[str]
    doctors_photo: Optional[str] = Field(None, description="Ссылка на фото")
    scientific_degree: Optional[str]
    date_of_last_attestation: Optional[date]
    passport_code: Optional[str] = Field(None, description="Номер паспорта")
    taxpayer_identification_number: Optional[str] = Field(None, description="ИНН")
    place_of_registration: Optional[str] = Field(None, description="Место прописки")
    reserv_scan: Optional[str] = Field(None, description="Ссылка на скан резерва")
    date_of_next_review: Optional[date] = Field(None, description="Дата следующей проверки")
    status: str
    diplomas: List[DiplomaResponse] = []
    certificates: List[CertificateResponse] = []
    clinic_affiliations: List[ClinicAffiliationResponse] = []

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class DoctorCreate(BaseModel):
    work_email: EmailStr = Field(
        ..., description="Рабочий имейл, должен быть уникальным"
    )
    phone_number: Optional[str] = Field(None, min_length=7, max_length=20, description="Номер телефона")
    first_name: str = Field(..., min_length=1, max_length=100, description="Имя врача")
    middle_name: str = Field(..., min_length=1, max_length=100, description="Отчество врача")
    last_name: str = Field(..., min_length=1, max_length=100, description="Фамилия врача")
    passport_code: str = Field(..., min_length=4, max_length=50, description="Номер паспорта")
    taxpayer_identification_number: str = Field(..., min_length=8, max_length=20, description="ИНН")
    place_of_registration: str = Field(..., min_length=5, max_length=500, description="Место прописки")
    scientific_degree: Optional[str] = Field(None, max_length=200, description="Научная степень")
    date_of_last_attestation: Optional[date] = Field(
        None, description="Дата последней атестации"
    )
    diplomas: List[DiplomaCreate] = []
    certificates: List[CertificateCreate] = []
    clinic_affiliations: List[ClinicAffiliationCreate] = []

    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        """
        Валидация номера телефона:
        - Разрешены цифры, пробелы, дефисы, скобки и знак +
        - Длина от 7 до 20 символов
        - Должен содержать хотя бы 7 цифр
        """
        if v is None:
            return v
        
        # Убираем пробелы для проверки
        cleaned = v.strip()
        if not cleaned:
            return None
        
        # Проверяем допустимые символы
        import re
        if not re.match(r'^[\d\s\-\(\)\+]+$', cleaned):
            raise ValueError(
                "Номер телефона может содержать только цифры, пробелы, дефисы, скобки и знак +"
            )
        
        # Проверяем количество цифр
        digits_only = re.sub(r'\D', '', cleaned)
        if len(digits_only) < 7:
            raise ValueError("Номер телефона должен содержать минимум 7 цифр")
        if len(digits_only) > 15:
            raise ValueError("Номер телефона не может содержать более 15 цифр")
        
        return cleaned

    @field_validator('first_name', 'middle_name', 'last_name')
    @classmethod
    def validate_names(cls, v: str, info: ValidationInfo) -> str:
        """Валидация имени, отчества, фамилии"""
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} не может быть пустым")
        
        # Проверяем, что имя содержит только буквы, дефисы и апострофы
        import re
        if not re.match(r"^[A-Za-zА-Яа-яЁёІіЇїЄєҐґ'\-\s]+$", v.strip()):
            raise ValueError(
                f"{info.field_name} может содержать только буквы, дефисы и апострофы"
            )
        
        return v.strip()

    @field_validator('passport_code', 'taxpayer_identification_number')
    @classmethod
    def validate_document_numbers(cls, v: str, info: ValidationInfo) -> str:
        """Валидация документов"""
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} не может быть пустым")
        return v.strip()

    @field_validator('place_of_registration')
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Валидация адреса"""
        if not v or not v.strip():
            raise ValueError("Место прописки не может быть пустым")
        if len(v.strip()) < 5:
            raise ValueError("Место прописки должно содержать минимум 5 символов")
        return v.strip()

    @field_validator('date_of_last_attestation')
    @classmethod
    def validate_attestation_date(cls, v: Optional[date]) -> Optional[date]:
        """Валидация даты аттестации"""
        if v is None:
            return v
        
        # Дата аттестации не может быть в будущем
        if v > date.today():
            raise ValueError("Дата аттестации не может быть в будущем")
        
        # Дата аттестации не может быть старше 100 лет
        if v.year < (date.today().year - 100):
            raise ValueError("Дата аттестации слишком старая")
        
        return v

    @field_validator('scientific_degree')
    @classmethod
    def validate_scientific_degree(cls, v: Optional[str]) -> Optional[str]:
        """Валидация научной степени"""
        if v is not None and v.strip() == "":
            return None
        return v.strip() if v else None

    class Config:
        json_schema_extra = {
            "example": {
                "work_email": "doctor@example.com",
                "phone_number": "+380666666666",
                "first_name": "John",
                "middle_name": "Doe",
                "last_name": "Smith",
                "passport_code": "CN123456",
                "taxpayer_identification_number": "1234567890",
                "place_of_registration": "Kyiv, Antona Tsedika 12",
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
    middle_name: Optional[str] = Field(None, description="Отчество врача")
    last_name: Optional[str] = Field(None, description="Фамилия врача")
    doctors_photo: Optional[str] = Field(None, description="Ссылка на фото врача")
    age: Optional[int] = Field(None, description="Возраст врача")
    scientific_degree: Optional[str] = Field(None, description="Научная степень")
    date_of_last_attestation: Optional[date] = Field(
        None, description="Дата последней атестации"
    )
    status: Doctor_Status
    place_of_registration: Optional[str] = Field(None, description="Место прописки")
    passport_code: Optional[str] = Field(None, description="Номер паспорта")
    taxpayer_identification_number: Optional[str] = Field(None, description="ИНН")

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class DoctorResponseForSignature(BaseModel):
    id: str = Field(..., description="ID врача")
    doctor_id: str = Field(..., description="COR-ID врача")
    work_email: EmailStr = Field(..., description="Рабочий имейл")
    phone_number: Optional[str] = Field(None, description="Номер телефона")
    first_name: Optional[str] = Field(None, description="Имя врача")
    middle_name: Optional[str] = Field(None, description="Отчество врача")
    last_name: Optional[str] = Field(None, description="Фамилия врача")

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class DoctorCreateResponse(BaseModel):
    id: str = Field(..., description="ID врача")
    doctor_cor_id: str = Field(..., description="COR-ID врача")
    work_email: EmailStr = Field(..., description="Рабочий имейл")
    phone_number: Optional[str] = Field(None, description="Номер телефона")
    first_name: str = Field(..., description="Имя врача")
    middle_name: str = Field(..., description="Отчество врача")
    last_name: str = Field(..., description="Фамилия врача")
    scientific_degree: Optional[str] = Field(None, description="Научная степень")
    date_of_last_attestation: Optional[date] = Field(
        None, description="Дата последней атестации"
    )
    status: Doctor_Status
    place_of_registration: Optional[str] = Field(None, description="Место прописки")
    passport_code: Optional[str] = Field(None, description="Номер паспорта")
    taxpayer_identification_number: Optional[str] = Field(None, description="ИНН")
    diploma_id: List = Field(..., description="ID дипломов")
    certificates_id: List = Field(..., description="ID сертификатов")
    clinic_affiliations_id: List = Field(..., description="ID записей о клиниках")

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class SimpleDoctorCreate(BaseModel):
    """Упрощенная схема для создания врача без дополнительных документов"""
    work_email: EmailStr = Field(
        ..., description="Рабочий имейл, должен быть уникальным"
    )
    phone_number: Optional[str] = Field(None, min_length=7, max_length=20, description="Номер телефона")
    first_name: str = Field(..., min_length=1, max_length=100, description="Имя врача")
    middle_name: str = Field(..., min_length=1, max_length=100, description="Отчество врача")
    last_name: str = Field(..., min_length=1, max_length=100, description="Фамилия врача")
    passport_code: str = Field(..., min_length=4, max_length=50, description="Номер паспорта")
    taxpayer_identification_number: str = Field(..., min_length=8, max_length=20, description="ИНН")
    place_of_registration: str = Field(..., min_length=5, max_length=500, description="Место прописки")
    scientific_degree: Optional[str] = Field(None, max_length=200, description="Научная степень")
    date_of_last_attestation: Optional[date] = Field(
        None, description="Дата последней атестации"
    )

    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cleaned = v.strip()
        if not cleaned:
            return None
        if not re.match(r'^[\d\s\-\(\)\+]+$', cleaned):
            raise ValueError(
                "Номер телефона может содержать только цифры, пробелы, дефисы, скобки и знак +"
            )
        digits_only = re.sub(r'\D', '', cleaned)
        if len(digits_only) < 7:
            raise ValueError("Номер телефона должен содержать минимум 7 цифр")
        if len(digits_only) > 15:
            raise ValueError("Номер телефона не может содержать более 15 цифр")
        return cleaned

    @field_validator('first_name', 'middle_name', 'last_name')
    @classmethod
    def validate_names(cls, v: str, info: ValidationInfo) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} не может быть пустым")
        if not re.match(r"^[A-Za-zА-Яа-яЁёІіЇїЄєҐґ'\-\s]+$", v.strip()):
            raise ValueError(
                f"{info.field_name} может содержать только буквы, дефисы и апострофы"
            )
        return v.strip()

    @field_validator('passport_code', 'taxpayer_identification_number')
    @classmethod
    def validate_document_numbers(cls, v: str, info: ValidationInfo) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} не может быть пустым")
        return v.strip()

    @field_validator('place_of_registration')
    @classmethod
    def validate_address(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Место прописки не может быть пустым")
        if len(v.strip()) < 5:
            raise ValueError("Место прописки должно содержать минимум 5 символов")
        return v.strip()

    @field_validator('date_of_last_attestation')
    @classmethod
    def validate_attestation_date(cls, v: Optional[date]) -> Optional[date]:
        if v is None:
            return v
        if v > date.today():
            raise ValueError("Дата аттестации не может быть в будущем")
        if v.year < (date.today().year - 100):
            raise ValueError("Дата аттестации слишком старая")
        return v


class SimpleDoctorResponse(BaseModel):
    """Упрощенный ответ при создании врача"""
    id: str = Field(..., description="ID врача")
    doctor_cor_id: str = Field(..., description="COR-ID врача")
    work_email: EmailStr = Field(..., description="Рабочий имейл")
    phone_number: Optional[str] = Field(None, description="Номер телефона")
    first_name: str = Field(..., description="Имя врача")
    middle_name: str = Field(..., description="Отчество врача")
    last_name: str = Field(..., description="Фамилия врача")
    scientific_degree: Optional[str] = Field(None, description="Научная степень")
    date_of_last_attestation: Optional[date] = Field(
        None, description="Дата последней атестации"
    )
    status: Doctor_Status
    place_of_registration: Optional[str] = Field(None, description="Место прописки")
    passport_code: Optional[str] = Field(None, description="Номер паспорта")
    taxpayer_identification_number: Optional[str] = Field(None, description="ИНН")

    class Config:
        from_attributes = True


class AddDoctorDiplomaRequest(BaseModel):
    """Схема для добавления диплома к существующему врачу"""
    doctor_cor_id: str = Field(..., description="COR-ID врача")
    diploma: DiplomaCreate = Field(..., description="Данные диплома")


class AddDoctorCertificateRequest(BaseModel):
    """Схема для добавления сертификата к существующему врачу"""
    doctor_cor_id: str = Field(..., description="COR-ID врача")
    certificate: CertificateCreate = Field(..., description="Данные сертификата")


class AddDoctorClinicAffiliationRequest(BaseModel):
    """Схема для добавления привязки к клинике для существующего врача"""
    doctor_cor_id: str = Field(..., description="COR-ID врача")
    clinic_affiliation: ClinicAffiliationCreate = Field(..., description="Данные о клинике")


# CorIdAuthSession MODELS


class InitiateLoginRequest(BaseModel):
    email: Optional[EmailStr] = None
    cor_id: Optional[str] = None
    app_id: Optional[str] = None

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


class CheckSessionRequest(BaseModel):
    email: Optional[EmailStr] = None
    cor_id: Optional[str] = None
    session_token: str

    @model_validator(mode="before")
    def check_either_email_or_cor_id(cls, data: dict):
        email = data.get("email")
        cor_id = data.get("cor_id")
        if not email and not cor_id:
            raise ValueError("Требуется указать либо email, либо cor_id")
        return data


class ConfirmCheckSessionResponse(BaseModel):
    status: str = "approved"
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    device_id: Optional[str] = None


class WebInitiateLoginRequest(BaseModel):
    """Запрос для инициации входа с веб-фронтенда через COR-ID приложение"""
    email: EmailStr


class WebInitiateLoginResponse(BaseModel):
    """Ответ с данными для авторизации через COR-ID приложение"""
    session_token: str
    deep_link: str
    qr_code: str  # Base64 encoded PNG QR code (data:image/png;base64,...)
    expires_at: datetime


class QrScannedRequest(BaseModel):
    """Уведомление о сканировании QR-кода"""
    session_token: str


# PATIENTS MODELS


class PatientResponce(BaseModel):
    patient_cor_id: str
    encrypted_surname: Optional[bytes] = None
    encrypted_first_name: Optional[bytes] = None
    encrypted_middle_name: Optional[bytes] = None
    sex: Optional[str]
    birth_date: Optional[date]
    status: Optional[str]


class PatientDecryptedResponce(BaseModel):
    patient_cor_id: str
    surname: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    sex: Optional[str]
    birth_date: Optional[Union[date, int]] = None
    age: Optional[int] = None
    status: Optional[PatientStatus] = None


class PaginatedPatientsResponse(BaseModel):
    items: List[PatientResponce]
    total: int


class ExistingPatientRegistration(BaseModel):
    email: Optional[EmailStr] = Field(
        None, description="Email пациента (будет использован для создания пользователя)"
    )
    birth_date: int = Field(..., description="Дата рождения пациента")
    sex: str = Field(
        ...,
        max_length=1,
        description="Пол пациента, может быть 'M'(мужской) или 'F'(женский)",
    )

    @field_validator("sex")
    @classmethod
    def validate_sex_and_normalize(cls, v: str) -> str:
        normalized_v = v.upper()
        if normalized_v not in ["M", "F"]:
            raise ValueError('Пол пациента должен быть "M" или "F".')
        return normalized_v


class NewPatientRegistration(BaseModel):
    email: Optional[EmailStr] = Field(
        None, description="Email пациента (будет использован для создания пользователя)"
    )
    surname: str = Field(..., min_length=1, description="Фамилия пациента")
    first_name: str = Field(..., min_length=1, description="Имя пациента")
    middle_name: Optional[str] = Field(None, description="Отчество пациента")
    birth_date: date = Field(..., description="Дата рождения пациента")
    sex: str = Field(
        ...,
        max_length=1,
        description="Пол пациента, может быть 'M'(мужской) или 'F'(женский)",
    )
    phone_number: Optional[str] = Field(None, description="Номер телефона пациента")
    address: Optional[str] = Field(None, description="Адрес пациента")

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, v: Optional[str]) -> Optional[str]:
        if v == "":
            return None
        return v

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, v: Optional[date]) -> Optional[date]:
        if v is None:
            raise ValueError("Необходимо указать дату рождения")

        min_birth_date = date(1900, 1, 1)
        current_date = date.today()

        if v < min_birth_date:
            raise ValueError("Дата рождения не может быть раньше 1 января 1900 года.")

        if v > current_date:
            raise ValueError("Дата рождения не может быть в будущем.")

        return v

    @field_validator("sex")
    @classmethod
    def validate_sex_and_normalize(cls, v: str) -> str:
        normalized_v = v.upper()
        if normalized_v not in ["M", "F"]:
            raise ValueError('Пол пациента должен быть "M" или "F".')
        return normalized_v


class ExistingPatientAdd(BaseModel):
    cor_id: str = Field(
        ...,
        min_length=10,
        max_length=18,
        description="Cor ID существующего пользователя",
    )


class PatientCreationResponse(BaseModel):
    id: str
    patient_cor_id: str
    user_id: Optional[str] = None
    encrypted_surname: Optional[bytes]
    encrypted_first_name: Optional[bytes]
    encrypted_middle_name: Optional[bytes]
    birth_date: Optional[date]
    sex: Optional[str]
    email: Optional[EmailStr]
    phone_number: Optional[str]
    address: Optional[str]

    class Config:
        from_attributes = True  # Для совместимости с SQLAlchemy


# Модели для лабораторных исследований


class CaseOwnerResponse(BaseModel):
    id: Optional[str] = Field(None, description="ID врача")
    doctor_id: Optional[str] = Field(None, description="COR-ID врача")
    work_email: Optional[EmailStr] = Field(None, description="Рабочий имейл")
    phone_number: Optional[str] = Field(None, description="Номер телефона")
    first_name: Optional[str] = Field(None, description="Имя врача")
    middle_name: Optional[str] = Field(None, description="Отчество врача")
    last_name: Optional[str] = Field(None, description="Фамилия врача")
    is_case_owner: Optional[bool] = Field(False, description="Владелец кейса")


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


class ChangeGlassStaining(BaseModel):
    staining_type: StainingType = Field(
        ...,
        description="Тип окрашивания для стекла",
        example=StainingType.HE,
    )


class Glass(GlassBase):
    id: str
    cassette_id: str
    is_printed: Optional[bool]
    preview_url: Optional[str]

    class Config:
        from_attributes = True


class GlassForGlassPage(GlassBase):
    id: str
    # cassette_id: str

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


class CassetteUpdateComment(BaseModel):
    comment: Optional[str] = None


class Cassette(CassetteBase):
    id: str
    sample_id: str
    glasses: List["Glass"] = []

    class Config:
        from_attributes = True


class Cassette(CassetteBase):
    id: str
    sample_id: str
    is_printed: Optional[bool]
    glasses: List[Glass] = []

    class Config:
        from_attributes = True


class CassetteForGlassPage(BaseModel):
    # id: str
    # sample_id: str
    cassette_number: str
    glasses: List[Glass] = []

    class Config:
        from_attributes = True


class DeleteCassetteRequest(BaseModel):
    cassette_ids: List[str]


class DeleteCassetteResponse(BaseModel):
    deleted_count: int
    message: str


class Sample(SampleBase):
    id: str
    case_id: str
    macro_description: Optional[str] = None
    is_printed_cassette: Optional[bool]
    is_printed_glass: Optional[bool]
    cassettes: List[Cassette] = []

    class Config:
        from_attributes = True


class SampleForGlassPage(BaseModel):
    # id: str
    # case_id: str
    # macro_description: Optional[str] = None
    sample_number: str
    cassettes: List[CassetteForGlassPage] = []

    class Config:
        from_attributes = True


class UpdateSampleMacrodescription(BaseModel):
    macro_description: str


class DeleteSampleRequest(BaseModel):
    sample_ids: List[str]


class DeleteSampleResponse(BaseModel):
    deleted_count: int
    message: str


class DeleteCasesRequest(BaseModel):
    case_ids: List[str]


class DeleteCasesResponse(BaseModel):
    deleted_count: int
    message: str


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
        example=UrgencyType.S,
    )
    material_type: MaterialType = Field(
        ...,
        description="Тип исследования",
        example=MaterialType.R,
    )
    num_samples: int = Field(
        1, ge=1, description="Количество семплов для создания в каждом кейсе"
    )


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
    update_data: str = Field(
        min_length=5,
        max_length=5,
        description="Последние 5 целочисельных символлов кода кейса",
    )


class Case(BaseModel):
    id: str
    creation_date: datetime
    patient_id: str
    case_code: str
    bank_count: int
    cassette_count: int
    glass_count: int
    pathohistological_conclusion: Optional[str] = None
    microdescription: Optional[str] = None
    grossing_status: Optional[str] = None
    is_printed_cassette: Optional[bool]
    is_printed_glass: Optional[bool]
    is_printed_qr: Optional[bool]


    class Config:
        from_attributes = True

class CaseWithOwner(Case):
    is_case_owner: Optional[bool]

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
    is_printed_cassette: Optional[bool]
    is_printed_glass: Optional[bool]
    is_printed_qr: Optional[bool]
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
    container_count_actual: Optional[int]
    fixation: FixationType
    macro_description: Optional[str]

    class Config:
        from_attributes = True


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
    pathohistological_conclusion: Optional[str] = None
    microdescription: Optional[str] = None
    is_printed_cassette: Optional[bool]
    is_printed_glass: Optional[bool]
    is_printed_qr: Optional[bool]
    samples: List[SampleWithoutCassettesSchema | Sample]
    # case_owner: Optional[DoctorResponseForSignature] = None

    class Config:
        from_attributes = True


class SimpleCaseResponse(BaseModel):
    id: str
    case_code: str
    creation_date: datetime
    bank_count: int
    cassette_count: int
    glass_count: int
    pathohistological_conclusion: Optional[str] = None
    microdescription: Optional[str] = None


class CaseListResponse(BaseModel):
    items: List[Union[CaseDetailsResponse, SimpleCaseResponse]]


class CreateSampleWithDetails(BaseModel):
    created_samples: List[Sample]
    first_sample_details: Optional[Sample] = None


# Модели для внешних девайсов


class DeviceRegistration(BaseModel):
    device_token: str


class DeviceResponse(BaseModel):
    token: str  # JWT токен
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


class CreatePrintingDevice(BaseModel):
    device_class: str = Field(None, description="Клас устройства")
    device_identifier: str = Field(None, description="Идентификатор устройства")
    subnet_mask: Optional[str] = Field(None, max_length=20, description="Маска подсети")
    gateway: Optional[str] = Field(None, max_length=20, description="Шлюз")
    ip_address: str = Field(max_length=20, description="IP-адрес")
    port: Optional[int] = Field(None, le=65535, description="Порт")
    comment: Optional[str] = Field(None, description="Комментарий")
    location: Optional[str] = Field(None, description="Локация")


class ResponsePrintingDevice(BaseModel):
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


class Label(BaseModel):
    models_id: int
    content: str
    uuid: Optional[str] = None


class PrintRequest(BaseModel):
    labels: List[Label]


class ReferralAttachmentResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    file_url: Optional[str] = Field(None, description="URL файла")

    class Config:
        from_attributes = True


class ReferralAttachmentCreate(BaseModel):
    filename: str
    content_type: str
    file_data: bytes


class ReferralCreate(BaseModel):
    case_id: str = Field(..., description="ID связанного кейса")
    biomaterial_date: Optional[date] = Field(
        None, description="Дата забора биоматериала"
    )
    research_type: Optional[StudyType] = Field(None, description="Вид исследования")
    container_count: Optional[int] = Field(
        None, description="Фактическое количество контейнеров"
    )
    medical_card_number: Optional[str] = Field(None, description="Номер медкарты")
    clinical_data: Optional[str] = Field(None, description="Клинические данные")
    clinical_diagnosis: Optional[str] = Field(None, description="Клинический диагноз")
    medical_institution: Optional[str] = Field(
        None, description="Медицинское учреждение"
    )
    department: Optional[str] = Field(None, description="Отделение")
    attending_doctor: Optional[str] = Field(None, description="Лечащий врач")
    doctor_contacts: Optional[str] = Field(None, description="Контакты врача")
    medical_procedure: Optional[str] = Field(None, description="Медицинская процедура")
    final_report_delivery: Optional[str] = Field(
        None, description="Финальный репорт отправить"
    )
    issued_at: Optional[date] = Field(None, description="Выдано (дата)")


class ReferralResponse(BaseModel):
    id: str
    case_id: str
    case_number: str
    created_at: datetime
    biomaterial_date: Optional[date]
    research_type: Optional[StudyType]
    container_count: Optional[int]
    medical_card_number: Optional[str]
    clinical_data: Optional[str]
    clinical_diagnosis: Optional[str]
    medical_institution: Optional[str]
    department: Optional[str]
    attending_doctor: Optional[str]
    doctor_contacts: Optional[str]
    medical_procedure: Optional[str]
    final_report_delivery: Optional[str]
    issued_at: Optional[date]
    attachments: List[ReferralAttachmentResponse] = []

    class Config:
        from_attributes = True


class ReferralResponseForDoctor(BaseModel):
    case_details: Optional[Case]
    case_owner: Optional[CaseOwnerResponse]
    referral_id: Optional[str] = Field(..., description="Referral ID")
    attachments: Optional[List[ReferralAttachmentResponse]] = []

    class Config:
        from_attributes = True


class ReferralUpdate(BaseModel):
    case_number: Optional[str] = None
    research_type: Optional[str] = None
    container_count: Optional[int] = None
    medical_card_number: Optional[str] = None
    clinical_data: Optional[str] = None
    clinical_diagnosis: Optional[str] = None
    medical_institution: Optional[str] = None
    department: Optional[str] = None
    attending_doctor: Optional[str] = None
    doctor_contacts: Optional[str] = None
    medical_procedure: Optional[str] = None
    final_report_delivery: Optional[str] = None
    issued_at: Optional[date] = None

    class Config:
        from_attributes = True


class ProfileCreate(BaseModel):
    surname: Optional[str] = Field(None, max_length=25, description="Фамилия")
    first_name: Optional[str] = Field(None, max_length=25, description="Имя")
    middle_name: Optional[str] = Field(None, max_length=25, description="Отчество")
    birth_date: Optional[date] = Field(None, description="Дата рождения")
    phone_number: Optional[str] = Field(
        None, max_length=15, description="Номер телефона"
    )
    city: Optional[str] = Field(None, max_length=50, description="Город")
    car_brand: Optional[str] = Field(None, max_length=50, description="Марка авто")
    engine_type: Optional[str] = Field(None, max_length=50, description="Тип двигателя")
    fuel_tank_volume: Optional[int] = Field(
        None, ge=0, le=1000, description="Обьем бензобака"
    )

    class Config:
        from_attributes = True


class ProfileResponse(BaseModel):
    email: str = Field(description="Имейл пользователя")
    sex: str = Field(description="Пол пользователя")
    surname: Optional[str] = Field(None, description="Фамилия")
    first_name: Optional[str] = Field(None, description="Имя")
    middle_name: Optional[str] = Field(None, description="Отчество")
    birth_date: Optional[date] = Field(None, description="Дата рождения")
    phone_number: Optional[str] = Field(None, description="Номер телефона")
    city: Optional[str] = Field(None, description="Город")
    car_brand: Optional[str] = Field(None, description="Марка авто")
    engine_type: Optional[str] = Field(None, description="Тип двигателя")
    fuel_tank_volume: Optional[int] = Field(
        None, ge=0, le=1000, description="Обьем бензобака"
    )

    class Config:
        from_attributes = True


class DeleteMyAccount(BaseModel):
    password: str = Field(min_length=6, max_length=20)


class FullUserInfoResponse(BaseModel):
    user_info: UserDb
    user_roles: Optional[List[str]] = None
    profile: Optional[ProfileResponse] = None
    doctor_info: Optional[DoctorWithRelationsResponse] = None

    class Config:
        from_attributes = True


class UserDataResponse(BaseModel):
    user_info: UserDb

    class Config:
        from_attributes = True


class UserProfileResponseForAdmin(BaseModel):
    profile: Optional[ProfileResponse] = None

    class Config:
        from_attributes = True


class UserDoctorsDataResponseForAdmin(BaseModel):
    doctor_info: Optional[DoctorWithRelationsResponse] = None

    class Config:
        from_attributes = True


class UserRolesResponseForAdmin(BaseModel):
    user_roles: Optional[List[str]] = None

    class Config:
        from_attributes = True


class ReferralFileSchema(BaseModel):
    id: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_url: Optional[str] = None

    class Config:
        from_attributes = True


class FirstCaseReferralDetailsSchema(BaseModel):
    id: str
    case_code: str
    creation_date: datetime
    pathohistological_conclusion: Optional[str] = None
    microdescription: Optional[str] = None
    general_macrodescription: Optional[str] = None
    grossing_status: Optional[str] = None
    patient_cor_id: Optional[str] = None

    attachments: Optional[List[ReferralFileSchema]] = None

    class Config:
        from_attributes = True

class FirstCaseReferralDetailsWithOwner(FirstCaseReferralDetailsSchema):
    is_case_owner: Optional[bool]

    class Config:
        from_attributes = True

class DoctorSignatureBase(BaseModel):
    signature_name: Optional[str] = None
    is_default: bool = False


class DoctorSignatureCreate(DoctorSignatureBase):
    pass


class DoctorSignatureResponse(DoctorSignatureBase):
    id: str
    doctor_id: str
    signature_scan_data: Optional[str] = None
    signature_scan_type: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class DoctorSignatureResponseWithName(BaseModel):
    doctor_first_name: Optional[str] = None
    doctor_last_name: Optional[str] = None
    doctor_id: str
    signature_scan_data: Optional[str] = None
    signature_scan_type: Optional[str] = None

    class Config:
        from_attributes = True


class ReportSignatureSchema(BaseModel):
    id: str
    doctor: DoctorResponseForSignature
    signed_at: Optional[datetime] = None

    doctor_signature: Optional[DoctorSignatureResponse] = None

    class Config:
        from_attributes = True


class ReportBaseSchema(BaseModel):
    immunohistochemical_profile: Optional[str] = None
    molecular_genetic_profile: Optional[str] = None
    pathomorphological_diagnosis: Optional[str] = None
    icd_code: Optional[str] = None
    comment: Optional[str] = None

    attached_glass_ids: Optional[List[str]] = None


class ReportCreateSchema(ReportBaseSchema):
    pass


class ReportUpdateSchema(ReportBaseSchema):
    pass

class InitiateSignatureRequest(BaseModel):
    # doctor_cor_id: str = Field(..., description="COR-ID доктора, который подписывает")
    diagnosis_id: str = Field(..., description="ID диагноза, который будет подписан")
    doctor_signature_id: Optional[str] = Field(None, description="ID подписи")


class InitiateSignatureResponse(BaseModel):
    session_token: str
    deep_link: str
    expires_at: datetime
    status: Optional[str] = None


class ActionRequest(BaseModel):
    session_token: str
    status: SessionLoginStatus


class StatusResponse(BaseModel):
    session_token: str
    status: str
    deep_link: Optional[str] = None
    expires_at: datetime


class PatientResponseForSigning(BaseModel):
    patient_cor_id: str
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[date] = None
    sex: Optional[str] = None
    age: Optional[int] = None

class DoctorDiagnosisSchema(BaseModel):
    id: str
    report_id: str
    doctor: DoctorResponseForSignature
    created_at: datetime
    immunohistochemical_profile: Optional[str] = None
    molecular_genetic_profile: Optional[str] = None
    pathomorphological_diagnosis: Optional[str] = None
    icd_code: Optional[str] = None
    comment: Optional[str] = None
    report_microdescription: Optional[str] = None
    report_macrodescription: Optional[str] = None
    signature: Optional[ReportSignatureSchema] = None

    class Config:
        from_attributes = True


class FinalReportResponseSchema(BaseModel):
    id: Optional[str] = None
    case_id: str
    case_code: str

    biopsy_date: Optional[date] = None
    arrival_date: Optional[date] = None
    report_date: Optional[date] = None

    patient_cor_id: Optional[str] = None
    patient_first_name: Optional[str] = None
    patient_surname: Optional[str] = None
    patient_middle_name: Optional[str] = None
    patient_sex: Optional[str] = None
    patient_birth_date: Optional[date] = None
    patient_full_age: Optional[int] = None
    patient_phone_number: Optional[str] = None
    patient_email: Optional[str] = None

    concatenated_macro_description: Optional[str] = None

    medical_card_number: Optional[str] = None
    medical_institution: Optional[str] = None
    medical_department: Optional[str] = None
    attending_doctor: Optional[str] = None
    clinical_data: Optional[str] = None
    clinical_diagnosis: Optional[str] = None

    painting: Optional[List[StainingType]] = None

    macroarchive: Optional[MacroArchive] = None
    decalcification: Optional[DecalcificationType] = None
    fixation: Optional[FixationType] = None
    num_blocks: Optional[int] = None
    containers_recieved: Optional[int] = None
    containers_actual: Optional[int] = None

    doctor_diagnoses: List[DoctorDiagnosisSchema] = []

    # attached_glass_ids: List[str] = []
    attached_glasses: List[Glass] = []

    class Config:
        from_attributes = True


class PatientFinalReportPageResponse(BaseModel):
    all_cases: Optional[List[CaseWithOwner]] = None
    last_case_details: Optional[CaseWithOwner] = None
    case_owner: Optional[CaseOwnerResponse]
    report_details: Optional[FinalReportResponseSchema]
    current_signings: Optional[StatusResponse] = None

    class Config:
        from_attributes = True


class CaseFinalReportPageResponse(BaseModel):
    case_details: CaseWithOwner
    case_owner: Optional[CaseOwnerResponse]
    report_details: Optional[FinalReportResponseSchema]
    current_signings: Optional[StatusResponse] = None

    class Config:
        from_attributes = True


class PatientCasesWithReferralsResponse(BaseModel):
    all_cases: List[CaseWithOwner]
    case_details: Optional[CaseWithOwner]
    case_owner: Optional[CaseOwnerResponse]
    first_case_direction: Optional[FirstCaseReferralDetailsWithOwner] = None

    class Config:
        from_attributes = True


class FirstCaseGlassDetailsSchema(BaseModel):
    id: str
    case_code: str
    creation_date: datetime
    pathohistological_conclusion: Optional[str] = None
    microdescription: Optional[str] = None
    general_macrodescription: Optional[str] = None
    grossing_status: Optional[str] = None
    patient_cor_id: Optional[str] = None
    is_printed_cassette: Optional[bool]
    is_printed_glass: Optional[bool]
    is_printed_qr: Optional[bool]

    samples: List[SampleForGlassPage]

    class Config:
        from_attributes = True

class FirstCaseGlassDetailsSchemaWithOwner(FirstCaseGlassDetailsSchema):
    is_case_owner: Optional[bool]

    class Config:
        from_attributes = True


class PatientGlassPageResponse(BaseModel):
    all_cases: List[CaseWithOwner]
    first_case_details_for_glass: Optional[FirstCaseGlassDetailsSchemaWithOwner] = None
    case_owner: Optional[CaseOwnerResponse]
    report_details: Optional[FinalReportResponseSchema]

    class Config:
        from_attributes = True


class SingleCaseGlassPageResponse(BaseModel):
    single_case_for_glass_page: Optional[FirstCaseGlassDetailsSchema] = None
    case_owner: Optional[CaseOwnerResponse]
    report_details: Optional[FinalReportResponseSchema]


class PathohistologicalConclusionResponse(BaseModel):
    pathohistological_conclusion: Optional[str] = None


class UpdatePathohistologicalConclusion(BaseModel):
    pathohistological_conclusion: str


class MicrodescriptionResponse(BaseModel):
    microdescription: Optional[str] = None


class UpdateMicrodescription(BaseModel):
    microdescription: str


class SampleForExcisionPage(BaseModel):
    id: str
    sample_number: str
    is_archived: bool = False
    macro_description: Optional[str] = None

    class Config:
        from_attributes = True


class LastCaseExcisionDetailsSchema(BaseModel):
    id: str
    case_code: str
    creation_date: datetime
    pathohistological_conclusion: Optional[str] = None
    microdescription: Optional[str] = None
    case_parameters: Optional[CaseParametersScheema] = None
    grossing_status: Optional[str] = None
    patient_cor_id: Optional[str] = None
    is_printed_cassette: Optional[bool]
    is_printed_glass: Optional[bool]
    is_printed_qr: Optional[bool]

    samples: List[SampleForExcisionPage]

    class Config:
        from_attributes = True

class LastCaseExcisionDetailsSchemaWithOwner(LastCaseExcisionDetailsSchema):
    is_case_owner: Optional[bool]

    class Config:
        from_attributes = True

class PatientExcisionPageResponse(BaseModel):
    all_cases: List[CaseWithOwner]
    last_case_details_for_excision: Optional[LastCaseExcisionDetailsSchemaWithOwner] = None
    case_owner: Optional[CaseOwnerResponse]

    class Config:
        from_attributes = True


class SingleCaseExcisionPageResponse(BaseModel):

    case_details_for_excision: Optional[LastCaseExcisionDetailsSchemaWithOwner] = None
    case_owner: Optional[CaseOwnerResponse]

    class Config:
        from_attributes = True


# Тестовые схемы под репорт
class GlassTestModelScheema(BaseModel):
    id: str
    glass_number: int
    cassette_id: str
    staining: Optional[str] = None
    preview_url: Optional[str]


class CassetteTestForGlassPage(BaseModel):
    id: str
    cassette_number: str
    sample_id: str

    glasses: List[GlassTestModelScheema] = []


class SampleTestForGlassPage(BaseModel):
    id: str
    sample_number: str
    case_id: str
    sample_macro_description: Optional[str] = None

    cassettes: List[CassetteTestForGlassPage] = []


class FirstCaseTestGlassDetailsSchema(BaseModel):
    id: str
    case_code: str
    creation_date: datetime
    grossing_status: Optional[str] = None
    samples: List[SampleTestForGlassPage]

    class Config:
        from_attributes = True


class LabAssistantCreate(BaseModel):
    first_name: Optional[str] = Field(
        None, min_length=1, max_length=20, description="Имя лаборанта"
    )
    middle_name: Optional[str] = Field(
        None, min_length=1, max_length=20, description="Отчество лаборанта"
    )
    last_name: Optional[str] = Field(
        None, min_length=1, max_length=20, description="Фамилия лаборанта"
    )

    class Config:
        from_attributes = True


class LabAssistantResponse(BaseModel):

    id: str
    lab_assistant_cor_id: str
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None

    class Config:
        from_attributes = True


class EnergyManagerCreate(BaseModel):
    first_name: Optional[str] = Field(
        None, min_length=1, max_length=20, description="Имя менеджера энергии"
    )
    middle_name: Optional[str] = Field(
        None, min_length=1, max_length=20, description="Отчество менеджера энергии"
    )
    last_name: Optional[str] = Field(
        None, min_length=1, max_length=20, description="Фамилия менеджера энергии"
    )

    class Config:
        from_attributes = True


class EnergyManagerResponse(BaseModel):

    id: str
    energy_manager_cor_id: str
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None

    class Config:
        from_attributes = True


class PatientResponseForGetPatients(BaseModel):
    id: str
    patient_cor_id: str
    surname: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    birth_date: Optional[date] = None
    sex: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    change_date: Optional[datetime] = None
    doctor_status: Optional[PatientStatus] = None
    clinic_status: Optional[PatientClinicStatus] = None
    cases: Optional[List] = None


class GetAllPatientsResponce(BaseModel):
    patients: List[PatientResponseForGetPatients]
    total_count: int


class LawyerCreate(BaseModel):
    first_name: str = Field(
        ..., min_length=1, max_length=20, description="Имя менеджера энергии"
    )
    middle_name: str = Field(
        ..., min_length=1, max_length=20, description="Отчество менеджера энергии"
    )
    last_name: str = Field(
        ..., min_length=1, max_length=20, description="Фамилия менеджера энергии"
    )

    class Config:
        from_attributes = True


class LawyerResponse(BaseModel):

    id: str
    lawyer_cor_id: str
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None

    class Config:
        from_attributes = True


class FinancierCreate(BaseModel):
    first_name: str = Field(
        ..., min_length=1, max_length=20, description="Имя финансиста"
    )
    middle_name: str = Field(
        ..., min_length=1, max_length=20, description="Отчество финансиста"
    )
    last_name: str = Field(
        ..., min_length=1, max_length=20, description="Фамилия финансиста"
    )

    class Config:
        from_attributes = True


class FinancierResponse(BaseModel):

    id: str
    financier_cor_id: str
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None

    class Config:
        from_attributes = True


class ReportResponseSchema(BaseModel):
    id: str
    case_id: str
    case_details: Optional[Case] = None
    macro_description_from_case_params: Optional[str] = None
    microdescription_from_case: Optional[str] = None
    concatenated_macro_description: Optional[str] = None

    doctor_diagnoses: List[DoctorDiagnosisSchema] = []

    attached_glasses: List[Glass] = []

    class Config:
        from_attributes = True


class PatientReportPageResponse(BaseModel):
    all_cases: List[Case]

    last_case_for_report: Optional[Case] = None
    report_details: Optional[ReportResponseSchema] = None

    all_glasses_for_last_case: List[FirstCaseGlassDetailsSchema] = []

    class Config:
        from_attributes = True


class SignReportRequest(BaseModel):
    doctor_signature_id: Optional[str] = None


class PatientTestReportPageResponse(BaseModel):
    all_cases: List[CaseWithOwner]
    last_case_for_report: Optional[CaseWithOwner]
    case_owner: Optional[CaseOwnerResponse]
    report_details: Optional[ReportResponseSchema]
    all_glasses_for_last_case: Optional[FirstCaseTestGlassDetailsSchema] = None

    class Config:
        from_attributes = True


class CaseIDReportPageResponse(BaseModel):
    last_case_for_report: Optional[Case] = None
    case_owner: Optional[CaseOwnerResponse]
    report_details: Optional[ReportResponseSchema] = None
    all_glasses_for_last_case: Optional[FirstCaseTestGlassDetailsSchema] = None

    class Config:
        from_attributes = True


class DoctorDiagnosisInputSchema(BaseModel):
    report_microdescription: Optional[str] = None
    report_macrodescription: Optional[str] = None
    pathomorphological_diagnosis: Optional[str] = None
    icd_code: Optional[str] = None
    comment: Optional[str] = None
    immunohistochemical_profile: Optional[str] = None
    molecular_genetic_profile: Optional[str] = None


class ReportAndDiagnosisUpdateSchema(BaseModel):

    attached_glass_ids: Optional[List[str]] = None
    doctor_diagnosis_data: Optional[DoctorDiagnosisInputSchema] = None


class CaseCloseResponse(BaseModel):
    message: str
    case_id: str
    new_status: str


class CaseOwnershipResponse(BaseModel):
    case_details: Optional[CaseDetailsResponse]
    case_owner: Optional[CaseOwnerResponse]


class NewBloodPressureMeasurementResponse(BaseModel):
    id: str
    systolic_pressure: Optional[int]
    diastolic_pressure: Optional[int]
    pulse: Optional[int]
    measured_at: datetime
    user_id: str
    created_at: datetime


class BloodPressureMeasurementCreate(BaseModel):
    systolic_pressure: Optional[int] = Field(
        None, gt=0, description="Систолическое (верхнее) давление"
    )
    diastolic_pressure: Optional[int] = Field(
        None, gt=0, description="Диастолическое (нижнее) давление"
    )
    pulse: Optional[int] = Field(None, gt=0, description="Пульс")
    measured_at: datetime = Field(
        ..., description="Дата и время измерения (с устройства)"
    )

    @field_validator("systolic_pressure")
    @classmethod
    def validate_systolic_range(cls, v):
        if v is not None and not (50 <= v <= 250):
            raise ValueError(
                "Систолическое давление должно быть в диапазоне от 50 до 250."
            )
        return v

    @field_validator("diastolic_pressure")
    @classmethod
    def validate_diastolic_range(cls, v):
        if v is not None and not (30 <= v <= 150):
            raise ValueError(
                "Диастолическое давление должно быть в диапазоне от 30 до 150."
            )
        return v

    @model_validator(mode="after")
    def check_diastolic_less_than_systolic(self):
        if self.diastolic_pressure is not None and self.systolic_pressure is not None:
            if self.diastolic_pressure >= self.systolic_pressure:
                raise ValueError(
                    "Диастолическое давление не может быть выше или равно систолическому."
                )
        return self


class BloodPressureMeasurementResponse(BloodPressureMeasurementCreate):
    id: str = Field(..., description="Уникальный идентификатор измерения")
    user_id: str = Field(
        ..., description="Идентификатор пользователя, которому принадлежит измерение"
    )
    created_at: datetime = Field(..., description="Дата и время записи в БД")

    class Config:
        from_attributes = True


class MeasureValue(BaseModel):
    value: int


class BloodPressureMeasures(BaseModel):
    sistolic: int = Field(..., gt=0, description="Систолическое (верхнее) давление")
    diastolic: int = Field(..., gt=0, description="Диастолическое (нижнее) давление")

    @field_validator("sistolic")
    @classmethod
    def validate_systolic_range(cls, v):
        if not (50 <= v <= 250):
            raise ValueError(
                "Систолическое давление должно быть в диапазоне от 50 до 250."
            )
        return v

    @field_validator("diastolic")
    @classmethod
    def validate_diastolic_range(cls, v):
        if not (30 <= v <= 150):
            raise ValueError(
                "Диастолическое давление должно быть в диапазоне от 30 до 150."
            )
        return v

    @model_validator(mode="after")
    def check_diastolic_less_than_systolic(self):
        if self.diastolic >= self.sistolic:
            raise ValueError(
                "Диастолическое давление не может быть выше или равно систолическому."
            )
        return self


MeasuresValue = str


class IndividualResult(BaseModel):
    measures: MeasuresValue
    member: List[str]


class TonometrIncomingData(BaseModel):
    created_at: datetime
    member: List[str]
    results_list: List[IndividualResult] = Field(..., alias="results")



# Модели для ЭКГ

class ECGMeasurementResponse(BaseModel):
    id: str 
    user_id: str
    created_at: datetime
    file_name: str

    class Config:
        from_attributes = True 


# Модели для опроса инвертора


class FullDeviceMeasurementCreate(BaseModel):
    # Общая информация о измерении
    measured_at: datetime = Field(..., description="Время измерения")
    object_name: Optional[str] = Field(
        None, description="Имя устройства, если применимо"
    )
    energetic_object_id: str = Field(
        ..., description="ID обьекта"
    )  

    # агрегированные данные
    general_battery_power: float = Field(
        ..., description="Общая мощность батареи"
    )  
    inverter_total_ac_output: float = Field(
        ..., description="Общая выходная мощность AC инвертора"
    )  
    ess_total_input_power: float = Field(
        ..., description="Общая входная мощность ESS"
    )  
    solar_total_pv_power: float = Field(
        ..., description="Общая мощность солнечных панелей"
    )  
    soc: float = Field(
        ..., description="SOC - State of charge"
    )  

    class Config:
        from_attributes = True


class FullDeviceMeasurementResponse(FullDeviceMeasurementCreate):
    id: str
    created_at: datetime


class CerboMeasurementResponse(BaseModel):
    id: str = Field(..., description="Уникальный идентификатор записи")
    created_at: datetime = Field(..., description="Дата и время сохранения записи в БД")
    measured_at: datetime = Field(
        ..., description="Дата и время измерения, полученное с устройства"
    )
    object_name: Optional[str] = Field(None, description="Имя объекта/устройства")
    general_battery_power: float = Field(..., description="Мощность батареи")
    inverter_total_ac_output: float = Field(
        ..., description="Общая выходная мощность инвертора AC"
    )
    ess_total_input_power: float = Field(
        ..., description="Общая входная мощность ESS AC"
    )
    solar_total_pv_power: float = Field(
        ..., description="Общая мощность солнечных панелей"
    )
    soc: Optional[float] = Field(
        None, description="SOC - State of charge"
    )  

    class Config:
        from_attributes = True


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T] = Field(..., description="Список элементов на текущей странице")
    total_count: int = Field(..., description="Общее количество элементов")
    page: int = Field(..., description="Текущий номер страницы (начиная с 1)")
    page_size: int = Field(..., description="Количество элементов на странице")
    total_pages: int = Field(..., description="Общее количество страниц")


# Модель данных для управления ESS


class VebusSOCControl(BaseModel):
    soc_threshold: int


class EssAdvancedControl(BaseModel):
    ac_power_setpoint_fine: int = Field(..., ge=-100000, le=100000)


class GridLimitUpdate(BaseModel):
    enabled: bool  # True → 1, False → 0


class EssModeControl(BaseModel):
    switch_position: int = Field(..., ge=1, le=4)


class EssPowerControl(BaseModel):
    ess_power_setpoint_l1: Optional[int] = Field(None, ge=-32768, le=32767)
    ess_power_setpoint_l2: Optional[int] = Field(None, ge=-32768, le=32767)
    ess_power_setpoint_l3: Optional[int] = Field(None, ge=-32768, le=32767)


class EssFeedInControl(BaseModel):
    max_feed_in_l1: Optional[int] = None
    max_feed_in_l2: Optional[int] = None
    max_feed_in_l3: Optional[int] = None


"""
Модели для расписания
"""


class EnergeticScheduleBase(BaseModel):
    start_time: time = Field(..., description="Время начала работы режима (ЧЧ:ММ)")
    duration_hours: int = Field(
        ..., ge=0, description="Продолжительность режима в часах"
    )
    duration_minutes: int = Field(
        ..., ge=0, lt=60, description="Продолжительность режима в минутах (0-59)"
    )
    grid_feed_w: int = Field(..., ge=-100000, le=100000, description="Параметр отдачи в сеть (Вт)")
    battery_level_percent: int = Field(
        ..., ge=0, le=100, description="Целевой уровень батареи (%)"
    )
    charge_battery_value: int = Field(..., ge=-1, le=10000, description="заряжать батарею в этом режиме и с каким значением")
    is_manual_mode: bool = Field(
        False, description="Флаг: находится ли инвертор в ручном режиме"
    )

    class Config:
        from_attributes = True


class EnergeticScheduleCreate(EnergeticScheduleBase):
    pass

class EnergeticScheduleCreateForObject(EnergeticScheduleBase):
    energetic_object_id: str = Field(..., description="ID Энергетического обьекта")


class EnergeticScheduleResponse(BaseModel):

    id: str = Field(..., description="Уникальный идентификатор расписания")
    start_time: time = Field(..., description="Время начала работы режима (ЧЧ:ММ)")
    grid_feed_w: float = Field(..., ge=-100000, le=100000, description="Параметр отдачи в сеть (Вт)")
    battery_level_percent: int = Field(
        ..., ge=0, le=100, description="Целевой уровень батареи (%)"
    )
    charge_battery_value: int = Field(..., ge=-1, le=10000, description="заряжать батарею в этом режиме и с каким значением")
    is_active: bool = Field(True, description="Флаг: активно ли это расписание")
    is_manual_mode: bool = Field(
        False, description="Флаг: находится ли инвертор в ручном режиме"
    )
    duration: Optional[timedelta] = None

    @computed_field
    @property
    def formatted_duration(self) -> str:
        if isinstance(self.duration, timedelta):
            total_seconds = int(self.duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            parts = []
            if hours > 0:
                parts.append(f"{hours}h")
            if minutes > 0:
                parts.append(f"{minutes}m")
            if seconds > 0 or not parts:
                parts.append(f"{seconds}s")

            return " ".join(parts)
        return "N/A"

    class Config:
        from_attributes = True


class RegisterWriteRequest(BaseModel):
    slave_id: int
    register_number: int
    value: int


class InverterPowerPayload(BaseModel):
    inverter_power: float

class DVCCMaxChargeCurrentRequest(BaseModel):
    current_limit: int = Field(
        ..., ge=-1, le=32767, description="DVCCMaxChargeCurrent (-1 или положительное значение до 32767)"
    )





class SearchResultPatientOverview(PatientFirstCaseDetailsResponse):
    search_type: Literal["patient_overview"] = "patient_overview"

class SearchResultCaseDetails(PatientGlassPageResponse): 
    search_type: Literal["case_details"] = "case_details"

SearchResultUnion = Union[
    SearchResultPatientOverview,
    SearchResultCaseDetails
]

class UnifiedSearchResponse(BaseModel):
    data: SearchResultUnion = Field(discriminator='search_type')


class SearchCaseDetailsSimple(BaseModel):
    search_type: Literal["case_details"] = "case_details"
    case_id: str
    patient_id: str

class GeneralPrinting(BaseModel):
    printer_ip: Optional[str] = None
    number_models_id: Optional[str] = None
    clinic_name: Optional[str] = None
    hooper: Optional[str] = None
    # printing: bool

class GlassPrinting(BaseModel):
    printer_ip: Optional[str] = None
    model_id: Optional[str] = None
    clinic_name: Optional[str] = None
    hooper: Optional[str] = None
    glass_id: str
    printing: bool

class GlassResponseForPrinting(BaseModel):

    case_code: str
    sample_number: str
    cassette_number: str
    glass_number: int
    staining: str
    patient_cor_id: str

class CassettePrinting(BaseModel):
    printer_ip: Optional[str] = None
    number_models_id: Optional[int] = None
    clinic_name: Optional[str] = None
    hooper: Optional[str] = None
    cassete_id: str
    printing: bool

class CassetteResponseForPrinting(BaseModel):

    case_code: Optional[str] = None
    sample_number: str
    cassette_number: str
    patient_cor_id: Optional[str] = None



class PrintLabel(BaseModel):
    """Модель для одной метки для печати."""
    model_id: int
    content: str
    uuid: str 

class PrintRequest(BaseModel):
    """Модель для запроса на печать."""
    printer_ip: str
    labels: List[PrintLabel]


class FeedbackRatingScheema(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Оценка от 1 до 5")
    comment: str = Field(...,min_length=2,max_length=800, description="Комментарий до 800 символов")



class FeedbackProposalsScheema(BaseModel):
    proposal: str = Field(...,min_length=2,max_length=800, description="Предложения")

class UploadGlassSVSResponse(BaseModel):
    preview_url: str
    scan_url: str

class EnergeticObjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    protocol: Optional[str] = Field(None, description="Протокол связи")
    vendor: Optional[str] = Field(None, description="Производитель/вендор инвертора")
    ip_address: Optional[str] = Field(None, description="IP-адрес объекта")
    port: Optional[int] = Field(None, description="Порт объекта")
    inverter_login: Optional[str] = Field(None, description="Логин для доступа к инвертору")
    inverter_password: Optional[str] = Field(None, description="Пароль для доступа к инвертору")
    is_active: Optional[bool] = None
    timezone: str = Field(default="Europe/Kiev", description="Часовой пояс объекта (например: Europe/Kiev, America/New_York)")

class EnergeticObjectCreate(EnergeticObjectBase):
    pass

class EnergeticObjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    protocol: Optional[str] = Field(None, description="Протокол связи")
    vendor: Optional[str] = Field(None, description="Производитель/вендор инвертора")
    ip_address: Optional[str] = Field(None, description="IP-адрес объекта")
    port: Optional[int] = Field(None, description="Порт объекта")
    inverter_login: Optional[str] = Field(None, description="Логин для доступа к инвертору")
    inverter_password: Optional[str] = Field(None, description="Пароль для доступа к инвертору")
    is_active: Optional[bool] = None
    timezone: Optional[str] = Field(None, description="Часовой пояс объекта (например: Europe/Kiev, America/New_York)")

class EnergeticObjectResponse(EnergeticObjectBase):
    id: str

    class Config:
        orm_mode = True


class PaginatedBloodPressureResponse(BaseModel):
    items: List[BloodPressureMeasurementResponse]
    total: int
    page: int
    page_size: int


# схемы для лекарств

class UnitEnum(str, Enum):
    MG = "mg"
    G = "g"
    MCG = "mcg"
    ML = "ml"
    L = "l"
    IU = "iu"
    MG_ML = "mg/ml"
    PERCENT = "%"
    MG_M2 = "mg/m2"


class OralMedicine(BaseModel):
    """Пероральный способ — требует дозу и единицу измерения."""
    intake_method: Literal["Oral"]
    dosage: float = Field(..., description="Дозировка препарата")
    unit: UnitEnum = Field(..., description="Одиница измерения (мг, мл и т.д.)")
    concentration: Optional[float] = None
    volume: Optional[float] = None



class OintmentMedicine(BaseModel):
    """Мази / свечи — требуют концентрацию."""
    intake_method: Literal["Ointment/suppositories"]
    concentration: float = Field(..., description="Концентрация активного вещества (%)")
    dosage: Optional[float] = None
    unit: Optional[UnitEnum] = None
    volume: Optional[float] = None


class SolutionMedicine(BaseModel):
    """Растворы, внутривенно, внутримышечно — требуют концентрацию и объем."""
    intake_method: Literal["Intravenous", "Intramuscularly", "Solutions"]
    concentration: float = Field(..., description="Концентрация раствора (%)")
    volume: float = Field(..., description="Объем раствора (мл)")
    dosage: Optional[float] = None
    unit: Optional[UnitEnum] = None




class MedicineBase(BaseModel):
    name: str = Field(..., description="Название препарата")
    active_substance: Optional[str] = Field(None, description="Действующее вещество")


    method_data: Union[OralMedicine, OintmentMedicine, SolutionMedicine]

    class Config:
        orm_mode = True




class MedicineCreate(MedicineBase):
    pass


class MedicineUpdate(MedicineBase):
    name: Optional[str] = None




# class MedicineScheduleBase(BaseModel):
#     start_date: date
#     duration_days: Optional[int] = Field(None, description="Длительность приема")
#     times_per_day: Optional[int] = Field(None, description="Кратность в день: 1 раз / 2 раза / 3 раза в день")
#     intake_times: Optional[List[time]] = Field(None, description="Список времён приёма через запятую: 21:00 / 9:00 / и тд")
#     interval_minutes: Optional[int] = Field(None, description="Интервал между приемами")
#     notes: Optional[str] = Field(None, description="Заметка")


class MedicineScheduleBase(BaseModel):
    start_date: date
    duration_days: Optional[int] = Field(None, description="Длительность приема")
    times_per_day: Optional[int] = Field(
        None, description="Кратность в день: 1 раз / 2 раза / 3 раза в день"
    )
    intake_times: Optional[List[time]] = Field(
        None, description="Список времён приёма: 21:00, 9:00 и т.д."
    )
    interval_minutes: Optional[int] = Field(
        None, description="Интервал между приёмами в минутах"
    )
    symptomatically: Optional[bool] = Field(False, description="Симптоматический приём")
    notes: Optional[str] = Field(None, description="Заметка")


    @field_validator("intake_times", mode="before")
    @classmethod
    def validate_intake_times(cls, v: Optional[List], info: ValidationInfo):
        if v is None:
            return v
        
        # Преобразуем строки в time объекты
        result = []
        for item in v:
            if isinstance(item, str):
                # Парсим строку формата "HH:MM", "HH:MM:SS" или "HH:MM:SS.microseconds[Z]"
                try:
                    # Убираем timezone marker (Z) если есть
                    time_str = item.rstrip('Z')
                    
                    # Разделяем по двоеточию
                    time_parts = time_str.split(":")
                    
                    if len(time_parts) == 2:
                        # Формат HH:MM
                        result.append(time(int(time_parts[0]), int(time_parts[1])))
                    elif len(time_parts) == 3:
                        # Формат HH:MM:SS или HH:MM:SS.microseconds
                        seconds_part = time_parts[2]
                        
                        # Проверяем, есть ли миллисекунды/микросекунды
                        if '.' in seconds_part:
                            seconds_str, microseconds_str = seconds_part.split('.')
                            seconds = int(seconds_str)
                            # Преобразуем миллисекунды в микросекунды (datetime.time принимает микросекунды)
                            # Если пришло "39.554", то это 554 миллисекунды = 554000 микросекунд
                            microseconds = int(microseconds_str.ljust(6, '0')[:6])
                            result.append(time(int(time_parts[0]), int(time_parts[1]), seconds, microseconds))
                        else:
                            # Простой формат HH:MM:SS
                            result.append(time(int(time_parts[0]), int(time_parts[1]), int(seconds_part)))
                    else:
                        raise ValueError(f"Неверный формат времени: {item}. Ожидается HH:MM, HH:MM:SS или HH:MM:SS.microseconds")
                except (ValueError, IndexError) as e:
                    raise ValueError(f"Не удалось распарсить время '{item}': {e}")
            elif isinstance(item, time):
                result.append(item)
            else:
                raise ValueError(f"Неверный тип времени: {type(item)}. Ожидается строка или time объект")
        
        data = info.data or {}  
        times_per_day = data.get("times_per_day")

        if times_per_day is not None and result is not None:
            if len(result) != times_per_day:
                raise ValueError(
                    f"Количество вхождений часов приема ({len(result)}) должно соответствовать количеству приёмов в день({times_per_day})"
                )

        # Если times_per_day не указано, но intake_times есть — выставляем автоматически
        if result is not None and times_per_day is None:
            data["times_per_day"] = len(result)

        return result


    @field_validator("times_per_day")
    @classmethod
    def validate_times_per_day(cls, v: Optional[int]):
        if v is not None and v <= 0:
            raise ValueError("Количество приемов должно быть больше нуля")
        return v

    @model_validator(mode="after")
    def validate_schedule_logic(self):
        if self.intake_times and self.interval_minutes:
            raise ValueError(
                "Нельзя одновременно указывать и времена приема, и интервал между ними"
            )
        if not self.intake_times and not self.interval_minutes:
            raise ValueError(
                "Нужно указать либо конкретные времена приема, либо интервал между ними"
            )
        return self


class MedicineScheduleCreate(MedicineScheduleBase):
    medicine_id: str


class MedicineScheduleUpdate(MedicineScheduleBase):
    pass

class MedicineScheduleResponse(BaseModel):
    id: str
    start_date: date
    duration_days: Optional[int] 
    times_per_day: Optional[int]
    intake_times: Optional[List[time]] 
    interval_minutes: Optional[int] 
    symptomatically: Optional[bool] 
    notes: Optional[str] 

    class Config:
        from_attributes = True


# Схемы для истории приема лекарств
class MedicineIntakeBase(BaseModel):
    """Базовая схема приема медикамента"""
    planned_datetime: datetime = Field(..., description="Запланированное время приема")
    status: MedicineIntakeStatus = Field(
        default=MedicineIntakeStatus.PLANNED,
        description="Статус приема (запланирован/выполнен/пропущен/отложен)"
    )
    notes: Optional[str] = Field(None, description="Комментарий к приему")

class MedicineIntakeCreate(MedicineIntakeBase):
    """Схема для создания записи о приеме"""
    schedule_id: str = Field(..., description="ID расписания")
    user_cor_id: str = Field(..., description="ID пользователя")

class MedicineIntakeUpdate(BaseModel):
    """Схема для обновления записи о приеме"""
    status: MedicineIntakeStatus = Field(..., description="Новый статус приема")
    actual_datetime: Optional[datetime] = Field(None, description="Фактическое время приема")
    notes: Optional[str] = Field(None, description="Комментарий к приему")

class MedicineIntakeResponse(BaseModel):
    """Схема для ответа с информацией о приеме"""
    id: str
    schedule_id: str
    user_cor_id: str
    planned_datetime: datetime
    actual_datetime: Optional[datetime] = None
    status: MedicineIntakeStatus
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    name: str = Field(alias='medicine_name', description="Название лекарства")
    dosage: Optional[float] = Field(alias='medicine_dosage', description="Дозировка лекарства")
    unit: Optional[str] = Field(alias='medicine_unit', description="Единица измерения дозировки")
    intake_method: Optional[str] = Field(alias='medicine_intake_method', description="Способ приёма лекарства")
    # name: str
    # medicine_dosage: Optional[float] = None
    # medicine_unit: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedMedicineIntakeResponse(BaseModel):
    """Схема для пагинированного списка приемов лекарств"""
    items: List[MedicineIntakeResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)


class GroupedMedicineIntake(BaseModel):
    """Группа приемов лекарств на одно время"""
    time: str = Field(..., description="Время приема (HH:MM)")
    planned_datetime: datetime = Field(..., description="Полная дата и время планового приема")
    medicines: List[MedicineIntakeResponse] = Field(default_factory=list, description="Список лекарств на это время")
    total_count: int = Field(..., description="Количество лекарств в группе")
    
    model_config = ConfigDict(from_attributes=True)


class DailyMedicineIntakes(BaseModel):
    """Приемы лекарств на конкретную дату, сгруппированные по времени"""
    intake_date: date = Field(..., description="Дата")
    day_name: str = Field(..., description="Название дня недели")
    time_groups: List[GroupedMedicineIntake] = Field(default_factory=list, description="Группы приемов по времени")
    total_intakes: int = Field(..., description="Общее количество приемов за день")
    
    model_config = ConfigDict(from_attributes=True)


class GroupedMedicineIntakesResponse(BaseModel):
    """Список приемов лекарств, сгруппированных по дням и времени"""
    days: List[DailyMedicineIntakes] = Field(default_factory=list, description="Приемы по дням")
    total_days: int = Field(..., description="Количество дней")
    date_range: dict = Field(..., description="Диапазон дат (start, end)")
    
    model_config = ConfigDict(from_attributes=True)


class MedicineScheduleWithIntakes(MedicineScheduleResponse):
    intakes: List[MedicineIntakeResponse] = []

    class Config:
        from_attributes = True


# ===================================
# Схемы для медицинских карт
# ===================================

class MedicalCardUpdate(BaseModel):
    """Схема для обновления медицинской карты"""
    display_name: Optional[str] = Field(None, max_length=100, description="Кастомное имя карты")
    card_color: Optional[str] = Field(None, max_length=20, description="Цвет карты в интерфейсе")
    is_active: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class MedicalCardResponse(BaseModel):
    """Схема для ответа с информацией о медицинской карте"""
    id: str
    owner_cor_id: str
    display_name: Optional[str] = None
    card_color: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Дополнительная информация о владельце
    gender: Optional[str] = Field(None, description="Пол владельца (из User.user_sex)")
    birth_date: Optional[date] = Field(None, description="Полная дата рождения (из Profile.birth_date)")
    birth_year: Optional[int] = Field(None, description="Год рождения (из User.birth), если полной даты нет")

    model_config = ConfigDict(from_attributes=True)


class MedicalCardAccessCreate(BaseModel):
    """Схема для предоставления доступа к медицинской карте"""
    user_cor_id: str = Field(..., description="COR ID пользователя, которому предоставляется доступ")
    access_level: str = Field("view", pattern="^(view|edit|share)$", description="Уровень доступа: view (смотреть), edit (редактировать), share (распространять)")
    purpose: Optional[str] = Field(None, pattern="^(relative|doctor|other)$", description="Для кого: relative (родственник), doctor (врач), other (другое)")
    purpose_note: Optional[str] = Field(None, max_length=255, description="Дополнительное пояснение (если выбрано 'other')")
    expires_at: Optional[datetime] = Field(None, description="Дата истечения доступа")

    @field_validator('expires_at')
    @classmethod
    def validate_expires_at(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v and v <= datetime.now(v.tzinfo or timezone.utc):
            raise ValueError("Дата истечения должна быть в будущем")
        return v

    model_config = ConfigDict(from_attributes=True)


class MedicalCardAccessResponse(BaseModel):
    """Схема для ответа с информацией о доступе к медицинской карте"""
    id: str
    medical_card_id: str
    user_cor_id: str
    access_level: str
    purpose: Optional[str] = None
    purpose_note: Optional[str] = None
    granted_by_cor_id: Optional[str] = None
    granted_at: datetime
    expires_at: Optional[datetime] = None
    is_accepted: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MedicalCardWithAccessInfo(MedicalCardResponse):
    """Схема медицинской карты с информацией о доступе"""
    my_access_level: Optional[str] = Field(None, description="Уровень доступа текущего пользователя")
    is_owner: bool = Field(..., description="Является ли текущий пользователь владельцем")
    
    # Информация о владельце (из User/Profile)
    owner_name: Optional[str] = Field(None, description="ФИО владельца карты")
    owner_birth_year: Optional[int] = Field(None, description="Год рождения владельца")

    model_config = ConfigDict(from_attributes=True)


class MedicalCardListResponse(BaseModel):
    """Схема для списка медицинских карт"""
    my_card: Optional[MedicalCardResponse] = Field(None, description="Моя медицинская карта")
    accessible_cards: List[MedicalCardWithAccessInfo] = Field(default_factory=list, description="Доступные карты других пользователей")
    total_accessible: int = Field(0, description="Количество доступных карт")

    model_config = ConfigDict(from_attributes=True)


class MedicineScheduleWithIntakes(MedicineScheduleResponse):
    intakes: List[MedicineIntakeResponse] = []

    class Config:
        from_attributes = True


class MedicineScheduleRead(MedicineScheduleBase):
    id: str
    medicine_id: str
    # user_cor_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class MedicineRead(MedicineBase):
    id: str
    created_at: datetime
    updated_at: datetime
    schedules: Optional[List[MedicineScheduleResponse]] = []

    class Config:
        orm_mode = True


# схемы для аптечек


class FirstAidKitBase(BaseModel):
    name: str = Field(..., description="Название аптечки")
    description: Optional[str] = None



class FirstAidKitCreate(FirstAidKitBase):
    pass


class FirstAidKitUpdate(FirstAidKitBase):
    name: Optional[str] = None




class FirstAidKitItemBase(BaseModel):
    medicine_id: str
    quantity: Optional[int] = 1
    expiration_date: Optional[date] = None


class FirstAidKitItemCreate(FirstAidKitItemBase):
    # first_aid_kit_id: str
    pass


class FirstAidKitItemUpdate(FirstAidKitItemBase):
    pass


class FirstAidKitItemRead(FirstAidKitItemBase):
    id: str
    created_at: datetime
    medicine: Optional[MedicineRead]

    class Config:
        orm_mode = True

class FirstAidKitCreateResponse(FirstAidKitBase):
    id: str
    # user_id: str
    created_at: datetime
    # updated_at: datetime
    # medicines: Optional[List[FirstAidKitItemRead]] = []

    class Config:
        orm_mode = True


class FirstAidKitRead(FirstAidKitBase):
    id: str
    # user_id: str
    created_at: datetime
    updated_at: datetime
    # medicines: Optional[List[FirstAidKitItemRead]] = []

    class Config:
        orm_mode = True


class FirstAidKitItemAddRead(BaseModel):
    id: str
    quantity: int
    expiration_date: Optional[date] = None
    created_at: datetime
    medicine: MedicineRead
    first_aid_kit: FirstAidKitRead

    class Config:
        orm_mode = True

class SupportReportScheema(BaseModel):
    product_name: str = Field(...,min_length=2,max_length=20, description="Название продукта")
    report_text: str = Field(...,min_length=2,max_length=800, description="Текст ошибки")




class OphthalmologicalPrescriptionBase(BaseModel):
    # Параметры правого глаза (OD)
    od_sph: Optional[float] = Field(None, description="Sph правого глаза")
    od_cyl: Optional[float] = Field(None, description="Cyl правого глаза")
    od_ax: Optional[float] = Field(None, description="Ax правого глаза")
    od_prism: Optional[float] = Field(None, description="Prism правого глаза")
    od_base: Optional[str] = Field(None, description="Base правого глаза (Up / Down / In / Out)")
    od_add: Optional[float] = Field(None, description="Add правого глаза")

    # Параметры левого глаза (OS)
    os_sph: Optional[float] = Field(None, description="Sph левого глаза")
    os_cyl: Optional[float] = Field(None, description="Cyl левого глаза")
    os_ax: Optional[float] = Field(None, description="Ax левого глаза")
    os_prism: Optional[float] = Field(None, description="Prism левого глаза")
    os_base: Optional[str] = Field(None, description="Base левого глаза (Up / Down / Medial / Lateral)")
    os_add: Optional[float] = Field(None, description="Add левого глаза")

    # Общие параметры
    glasses_purpose: Literal["glasses_for_reading", "glasses_for_distance", "glasses_for_constant_wear"]
    glasses_type: Literal["monofocal_glasses", "bifocal_glasses", "multifocal_glasses"]

    issue_date: Optional[datetime] = Field(...)
    term_months: Optional[int] = Field(None, description="Срок действия рецепта в месяцах")
    note: Optional[str] = Field(None, description="Заметки")

    @field_validator("od_base", "os_base")
    @classmethod
    def validate_base_direction(cls, v):
        allowed = {"Up", "Down", "Medial", "Lateral", None}
        if v not in allowed:
            raise ValueError("Base должен быть одним из: Up, Down, Medial, Lateral")
        return v



class OphthalmologicalPrescriptionCreate(OphthalmologicalPrescriptionBase):
    patient_id: str
    doctor_signature_id: Optional[str] = None


class OphthalmologicalPrescriptionUpdate(OphthalmologicalPrescriptionBase):
    pass


class OphthalmologicalPrescriptionRead(OphthalmologicalPrescriptionBase):
    id: str
    patient_id: str
    expires_at: Optional[datetime] = None
    doctor_signature_id: Optional[str] = None
    signed_at: Optional[datetime] = None
    issue_date: datetime

    class Config:
        orm_mode = True

class OphthalmologicalPrescriptionReadWithSigning(BaseModel):
    ophthalmological_prescription: OphthalmologicalPrescriptionRead
    doctor_signing_info: Optional[DoctorSignatureResponseWithName] = None
    current_signings: Optional[StatusResponse] = None

class WSMessageBase(BaseModel):
    session_token: str
    data: str = Field(..., description="HEX команда в виде строки, например: '090300000000ac485'")
    
    @field_validator("data")
    @classmethod
    def validate_hex_string(cls, v: str) -> str:
        # Удаляем пробелы, если они есть
        v = v.replace(" ", "")
        # Проверяем, что строка содержит только hex символы
        if not all(c in "0123456789ABCDEFabcdef" for c in v):
            raise ValueError("Строка должна содержать только HEX символы")
        # Проверяем длину (должна быть четной)
        if len(v) % 2 != 0:
            raise ValueError("Длина HEX строки должна быть четной")
        return v

    def get_bytes(self) -> bytes:
        """Преобразует HEX строку в bytes"""
        return bytes.fromhex(self.data)


class PrescriptionFileBase(BaseModel):
    file_name: str = Field(..., description="Название файла рецепта")
    file_type: str = Field(..., description="Тип файла (image/jpeg, image/png, application/pdf)")
    file_size_kb: float = Field(..., description="Размер файла в килобайтах")
    issue_date: Optional[datetime] = Field(None, description="Дата выписки рецепта")

class PrescriptionFileRead(PrescriptionFileBase):
    id: str
    uploaded_at: datetime

    class Config:
        orm_mode = True


class LaboratoryBase(BaseModel):
    lab_name: Optional[str] = Field(None, description="Название лаборатории")
    lab_email: Optional[EmailStr] = Field(None, description="Email лаборатории")
    lab_phone_number: Optional[str] = Field(None, description="Телефон лаборатории")
    lab_website: Optional[str] = Field(None, description="Сайт лаборатории")
    lab_address: Optional[str] = Field(None, description="Адрес лаборатории")


class LaboratoryCreate(LaboratoryBase):
    pass


class LaboratoryUpdate(LaboratoryBase):
    pass


class LaboratoryRead(LaboratoryBase):
    id: str
    uploaded_at: Optional[datetime] = None
    lab_logo_type: Optional[str] = None

    class Config:
        orm_mode = True


# ============================================================================
# SIBIONICS CGM Integration Schemas
# ============================================================================

# Request/Response schemas for SIBIONICS API

class SibionicsAuthRequest(BaseModel):
    """Запрос на авторизацию в SIBIONICS (внутреннее использование)"""
    app_key: str = Field(..., description="App Key from SIBIONICS")
    secret: str = Field(..., description="Secret Key from SIBIONICS")


class SibionicsTokenResponse(BaseModel):
    """Ответ с токеном от SIBIONICS API"""
    access_token: str = Field(..., description="Access token")
    expires_in: int = Field(..., description="Token expiration timestamp (milliseconds)")


class SibionicsUserAuthCreate(BaseModel):
    """Создание связи пользователя с SIBIONICS аккаунтом"""
    biz_id: Optional[str] = Field(None, description="SIBIONICS Authorization resource ID (если есть)")
    access_token: Optional[str] = Field(None, description="Access token от Sibionics H5 авторизации")
    expires_in: Optional[int] = Field(None, description="Время жизни токена в секундах")
    refresh_token: Optional[str] = Field(None, description="Refresh token (если предоставлен)")


class SibionicsUserAuthResponse(BaseModel):
    """Информация об авторизации пользователя в SIBIONICS"""
    id: str
    user_id: str
    biz_id: Optional[str] = None
    access_token: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SibionicsDeviceData(BaseModel):
    """Данные устройства CGM от SIBIONICS API"""
    device_id: str = Field(..., alias="deviceId")
    device_name: str = Field(..., alias="deviceName")
    index: int = Field(..., description="Current data index")
    status: int = Field(..., description="0: Not started; 1: Monitoring; 2: Expired; 3: Init; 4: Abnormal")
    enable_time: int = Field(..., alias="enableTime", description="Device wearing start time (timestamp)")
    last_time: int = Field(..., alias="lastTime", description="Device wearing deadline (timestamp)")
    bluetooth_num: str = Field(..., alias="blueToothNum")
    serial_no: Optional[str] = Field(None, alias="serialNo")
    max_index: int = Field(..., alias="maxIndex")
    min_index: int = Field(..., alias="minIndex")
    data_gap: int = Field(..., alias="dataGap", description="Glucose index interval")

    model_config = ConfigDict(populate_by_name=True)


class SibionicsDeviceResponse(BaseModel):
    """Ответ с информацией об устройстве из БД"""
    id: str
    device_id: str
    device_name: Optional[str]
    bluetooth_num: Optional[str]
    serial_no: Optional[str]
    status: Optional[int]
    current_index: Optional[int]
    max_index: Optional[int]
    min_index: Optional[int]
    data_gap: Optional[int]
    enable_time: Optional[datetime]
    last_time: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SibionicsGlucoseData(BaseModel):
    """Данные глюкозы от SIBIONICS API"""
    i: int = Field(..., description="Index")
    v: float = Field(..., description="Glucose value in mmol/L")
    s: int = Field(..., description="Trend: 0=stable, ±1=slow, ±2=fast")
    ast: int = Field(..., description="Alarm status: 1=normal, 2-6=various alarms")
    t: int = Field(..., description="Timestamp (milliseconds)")


class SibionicsGlucoseResponse(BaseModel):
    """Ответ с данными глюкозы из БД"""
    id: str
    device_id: str
    index: int
    glucose_value: float
    trend: Optional[int]
    alarm_status: Optional[int]
    timestamp: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Fuel Station Schemas (Схемы для системы заправок)
# ============================================================================

class FuelQRGenerateRequest(BaseModel):
    """Запрос на генерацию QR кода для заправки"""
    validity_minutes: Optional[int] = Field(
        default=5, 
        ge=1, 
        le=30, 
        description="Время действия QR кода в минутах (1-30)"
    )


class FuelQRCodeData(BaseModel):
    """Данные QR кода для заправки"""
    cor_id: str = Field(..., description="COR ID сотрудника")
    totp_code: str = Field(..., description="TOTP код")
    timestamp_token: str = Field(..., description="Timestamp токен")
    session_token: str = Field(..., description="Уникальный токен сессии")
    expires_at: datetime = Field(..., description="Время истечения QR кода")


class FuelQRGenerateResponse(BaseModel):
    """Ответ при генерации QR кода"""
    qr_data: FuelQRCodeData
    qr_data_string: str = Field(..., description="Строка для генерации QR кода (JSON)")
    expires_in_seconds: int = Field(..., description="Через сколько секунд истекает")
    created_at: datetime


class FuelQRVerifyRequest(BaseModel):
    """Запрос на верификацию QR кода (от заправщика)"""
    qr_data_string: str = Field(..., description="Отсканированные данные QR кода (JSON)")


class FuelUserLimitInfo(BaseModel):
    """Информация о лимитах пользователя от бэкенда финансов"""
    cor_id: str
    employee_name: Optional[str] = Field(None, description="ФИО сотрудника")
    employee_limit: float = Field(..., description="Лимит сотрудника")
    organization_id: str = Field(..., description="ID организации")
    organization_name: str = Field(..., description="Название организации")
    organization_limit: float = Field(..., description="Лимит организации")
    is_active: bool = Field(..., description="Активен ли сотрудник")


class FuelQRVerifyResponse(BaseModel):
    """Ответ при верификации QR кода"""
    is_valid: bool = Field(..., description="Валиден ли QR код")
    message: str = Field(..., description="Сообщение о результате")
    
    # Данные пользователя (если успешно)
    user_cor_id: Optional[str] = None
    
    # Лимиты (если успешно получены от бэкенда финансов)
    limit_info: Optional[FuelUserLimitInfo] = None


# ============================================================================
# Offline QR Code Schemas (Офлайн QR коды)
# ============================================================================

class FuelOfflineQRData(BaseModel):
    """Данные офлайн QR кода для заправки (работает без интернета)"""
    cor_id: str = Field(..., description="COR ID сотрудника")
    totp_code: str = Field(..., description="TOTP код (6 цифр)")
    timestamp: int = Field(..., description="Unix timestamp генерации QR")
    # company_id: Optional[str] = Field(None, description="ID компании (опционально)")


class FuelOfflineQRGenerateResponse(BaseModel):
    """Ответ при генерации офлайн QR кода"""
    qr_data: FuelOfflineQRData
    qr_data_string: str = Field(..., description="JSON строка для QR кода")
    expires_in_seconds: int = Field(..., description="Через сколько секунд истекает TOTP код")
    totp_interval: int = Field(default=30, description="Интервал TOTP в секундах")


class FuelOfflineQRVerifyRequest(BaseModel):
    """Запрос на офлайн верификацию QR кода"""
    qr_data_string: str = Field(..., description="Отсканированные данные QR кода (JSON)")


class FuelOfflineQRVerifyResponse(BaseModel):
    """Ответ при офлайн верификации QR кода"""
    is_valid: bool = Field(..., description="Валиден ли QR код")
    message: str = Field(..., description="Сообщение о результате")
    user_cor_id: Optional[str] = Field(None, description="COR ID пользователя")
    # company_id: Optional[str] = Field(None, description="ID компании")
    verified_at: Optional[datetime] = Field(None, description="Время верификации")


class FuelOfflineTOTPSecretResponse(BaseModel):
    """Ответ с TOTP секретом для настройки офлайн режима
    
    Workflow для мобильных разработчиков:
    1. При первом логине проверить наличие сохранённого TOTP секрета
    2. Если секрета нет - сделать GET /api/fuel-station/offline/totp-secret
    3. Сохранить totp_secret локально (SharedPreferences/Keychain)
    4. Использовать сохранённый секрет для генерации TOTP кодов офлайн
    """
    totp_secret: str = Field(..., description="Base32 TOTP секрет для сохранения в приложении")
    totp_interval: int = Field(default=30, description="Интервал TOTP в секундах")
    

# Схемы для интеграции с бэкендом финансов

class FinanceBackendAuthRequest(BaseModel):
    """Запрос авторизации на бэкенде финансов"""
    totp_code: str = Field(..., description="TOTP код для авторизации")
    timestamp: int = Field(..., description="Unix timestamp")


class FinanceCheckLimitRequest(BaseModel):
    """Запрос проверки лимита сотрудника"""
    cor_id: str = Field(..., description="COR ID сотрудника")
    auth: FinanceBackendAuthRequest = Field(..., description="Данные авторизации")


class FinanceCheckLimitResponse(BaseModel):
    """Ответ от бэкенда финансов с лимитами"""
    cor_id: str
    employee_name: Optional[str] = None
    employee_limit: float
    organization_id: str
    organization_name: str
    organization_limit: float
    is_active: bool


# Схемы для настройки интеграции (только для админов)

class FinanceBackendAuthConfigCreate(BaseModel):
    """Создание конфигурации авторизации с бэкендом финансов"""
    service_name: str = Field(default="finance_backend", description="Название сервиса")
    api_endpoint: str = Field(..., description="URL бэкенда финансов")
    totp_secret: str = Field(..., description="TOTP секрет (Base32)")
    totp_interval: int = Field(default=30, description="Интервал TOTP в секундах")


class FinanceBackendAuthConfigResponse(BaseModel):
    """Ответ с конфигурацией (без секретов)"""
    id: str
    service_name: str
    api_endpoint: str
    totp_interval: int
    is_active: bool
    last_successful_auth: Optional[datetime]
    last_failed_auth: Optional[datetime]
    failed_attempts: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Corporate Client Schemas (Корпоративные клиенты)
# ============================================================================

class CorporateClientCreate(BaseModel):
    """Создание заявки на регистрацию корпоративного клиента"""
    company_format: str = Field(..., min_length=1, max_length=50, description="Форма підприємства: ТОВ, ФОП, ПП")
    company_name: str = Field(..., min_length=1, max_length=255, description="Полное название компании")
    address: str = Field(..., min_length=1, max_length=500, description="Юридический адрес")
    phone_number: str = Field(..., min_length=10, max_length=20, description="Контактный телефон")
    email: EmailStr = Field(..., description="Email компании")
    tax_id: str = Field(..., min_length=1, max_length=50, description="ЄДРПОУ/ИНН")


class CorporateClientResponse(BaseModel):
    """Ответ с данными корпоративного клиента"""
    id: str
    owner_cor_id: str
    company_format: str
    company_name: str
    address: str
    phone_number: str
    email: str
    tax_id: str
    status: str  # pending, active, blocked, rejected, limit_exceeded
    fuel_limit: float  # Лимит компании на топливо
    finance_company_id: Optional[int]
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    rejection_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class CorporateClientWithOwner(CorporateClientResponse):
    """Корпоративный клиент с информацией о владельце (для админа)"""
    owner_first_name: Optional[str] = None
    owner_last_name: Optional[str] = None
    owner_email: Optional[str] = None


class CorporateClientApprove(BaseModel):
    """Подтверждение заявки (перевод в статус active)"""
    pass  # Пустое тело


class CorporateClientReject(BaseModel):
    """Отклонение заявки (перевод в статус rejected)"""
    rejection_reason: str = Field(..., min_length=1, max_length=1000, description="Причина отклонения")


class CorporateClientBlock(BaseModel):
    """Блокировка компании (перевод в статус blocked)"""
    reason: Optional[str] = Field(None, max_length=1000, description="Причина блокировки")


class CorporateClientUpdate(BaseModel):
    """Обновление данных корпоративного клиента (админ)"""
    company_name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = Field(None, min_length=1, max_length=500)
    phone_number: Optional[str] = Field(None, min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    fuel_limit: Optional[float] = Field(None, ge=0, description="Лимит компании на топливо")


class FinancePartnerLoginResponse(BaseModel):
    """Ответ от финансового бэкенда при логине партнёра"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class CreateAccountMemberRequest(BaseModel):
    """Запрос на добавление пользователя в компанию"""
    cor_id: str = Field(..., description="COR-ID пользователя")
    first_name: str = Field(..., description="Имя пользователя")
    last_name: str = Field(..., description="Фамилия пользователя")
    account_id: int = Field(..., description="ID аккаунта в finance backend?")
    company_id: int = Field(..., description="ID компании в finance backend")
    limit_amount: float = Field(..., ge=0, description="Лимит пользователя")
    limit_period: Literal["day", "week", "month"] = Field(..., description="Период лимита")


class AccountMemberResponse(BaseModel):
    """Ответ от финансового бэкенда при создании участника компании"""
    id: int
    first_name: str
    last_name: str
    cor_id: str
    account_id: int
    limit_amount: str
    limit_period: str
    disabled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class FinanceCreateCompanyRequest(BaseModel):
    """Запрос на создание компании в финансовом бэкенде"""
    company_format: str
    name: str
    tax_id: str
    address: str
    phone_number: str
    email: str
    owner_id: int  # user_id владельца в finance backend


class FinanceCreateCompanyResponse(BaseModel):
    """Ответ от финансового бэкенда при создании компании"""
    id: int  # company_id в finance backend
    name: str
    owner_id: int


class SibionicsGlucoseListResponse(BaseModel):
    """Список данных глюкозы с пагинацией"""
    records: List[SibionicsGlucoseResponse]
    current_page: int
    page_size: int
    total_page: int
    total: int


class SibionicsSyncRequest(BaseModel):
    """Запрос на синхронизацию данных с SIBIONICS"""
    device_id: Optional[str] = Field(None, description="Specific device ID (optional)")
    start_index: Optional[int] = Field(60, ge=60, le=20160, description="Starting index for data sync")
    page_size: int = Field(1000, ge=1, le=1000, description="Number of records per request")


class SibionicsSyncResponse(BaseModel):
    """Результат синхронизации данных"""
    devices_synced: int
    total_records_added: int
    total_records_updated: int
    sync_timestamp: datetime
    details: List[Dict[str, Any]] = Field(default_factory=list)


class SibionicsH5AuthUrlRequest(BaseModel):
    """Запрос на получение H5 Authorization URL"""
    redirect_url: Optional[str] = Field(
        None,
        description="URL для редиректа после авторизации (опционально)"
    )


class SibionicsH5AuthUrlResponse(BaseModel):
    """H5 Authorization URL для авторизации пользователя в Sibionics"""
    auth_url: str = Field(
        ...,
        description="URL для авторизации пользователя в Sibionics",
        examples=["https://open-auth-uat.sisensing.com/?appKey=xxx&thirdBizId=123"]
    )
    third_biz_id: str = Field(
        ...,
        description="Уникальный ID пользователя в вашей системе (user.id)"
    )
    expires_in: int = Field(
        300,
        description="Время жизни URL в секундах (5 минут)"
    )


class SibionicsAuthCallbackContent(BaseModel):
    """Содержимое webhook type 201 - Authorization Success"""
    bizIds: List[str] = Field(
        ...,
        description="Массив SIBIONICS Authorization resource IDs",
        examples=[["1423159073910992896", "1423159073910992899"]]
    )
    thirdBizId: str = Field(
        ...,
        description="Ваш user_id, который был передан в H5 URL",
        examples=["18000000000"]
    )
    isAuthorized: bool = Field(
        ...,
        description="Статус авторизации"
    )
    grantTime: int = Field(
        ...,
        description="Timestamp авторизации (milliseconds)",
        examples=[1709705256289]
    )


class SibionicsCallbackRequest(BaseModel):
    """Webhook от Sibionics type 201 - Authorization Success Notification"""
    type: int = Field(
        ...,
        description="Тип события (201 = Authorization Success)",
        examples=[201]
    )
    content: SibionicsAuthCallbackContent = Field(
        ...,
        description="Содержимое события"
    )


class SibionicsCallbackResponse(BaseModel):
    """Ответ на callback от Sibionics"""
    success: bool
    message: str
    user_id: Optional[str] = None  # UUID string
    biz_ids: Optional[List[str]] = None
    primary_biz_id: Optional[str] = None


class SibionicsWebhookDeviceData(BaseModel):
    """Данные устройства в webhook от Sibionics"""
    device_id: str = Field(..., description="Device ID")
    device_name: Optional[str] = Field(None, description="Device name")
    device_type: Optional[str] = Field(None, description="Device type")
    last_sync_time: Optional[int] = Field(None, description="Last sync timestamp (milliseconds)")
    battery_level: Optional[int] = Field(None, description="Battery level (0-100)")


class SibionicsWebhookGlucoseRecord(BaseModel):
    """Запись глюкозы в webhook"""
    i: int = Field(..., description="Index", alias="i")
    v: float = Field(..., description="Glucose value (mg/dL)", alias="v")
    t: int = Field(..., description="Timestamp (milliseconds)", alias="t")
    trend: Optional[int] = Field(None, description="Trend arrow (0-8)")


class SibionicsWebhookRequest(BaseModel):
    """Webhook от Sibionics с данными устройства (шаг 6 на схеме)"""
    biz_id: str = Field(
        ...,
        description="SIBIONICS Authorization resource ID"
    )
    device_id: str = Field(
        ...,
        description="Device ID"
    )
    event_type: str = Field(
        ...,
        description="Тип события: new_data, device_online, device_offline, etc."
    )
    timestamp: int = Field(
        ...,
        description="Timestamp события (milliseconds)"
    )
    device_data: Optional[SibionicsWebhookDeviceData] = Field(
        None,
        description="Информация об устройстве"
    )
    glucose_records: Optional[List[SibionicsWebhookGlucoseRecord]] = Field(
        None,
        description="Новые записи глюкозы"
    )
    sign: Optional[str] = Field(
        None,
        description="Подпись для верификации webhook"
    )


class SibionicsWebhookResponse(BaseModel):
    """Ответ на webhook от Sibionics"""
    success: bool
    message: str
    records_processed: int = 0


# === User Actions Schemas (API 105) ===

class SibionicsActionData(BaseModel):
    """Данные действия пользователя (зависят от типа)"""
    actionImgs: Optional[List[str]] = Field(default_factory=list, description="Изображения действия")
    eventType: Optional[str] = Field(None, description="Тип события (напр. Lunch, Dinner для еды)")
    eventDetail: Optional[str] = Field(None, description="Детали события (напр. название еды, значение finger blood)")
    eventConsume: Optional[float] = Field(None, description="Потребление (калории для спорта, доза для лекарств/инсулина)")
    unit: Optional[str] = Field(None, description="Единица измерения (для лекарств)")


class SibionicsActionResponse(BaseModel):
    """Действие пользователя из Sibionics"""
    actionTime: str = Field(..., description="Время начала действия (ISO 8601 или timestamp)")
    actionEndTime: Optional[str] = Field(None, description="Время окончания действия (для сна)")
    createTime: str = Field(..., description="Время создания записи")
    type: int = Field(..., description="Тип: 1=еда, 2=спорт, 3=лекарства, 4=инсулин, 5=сон, 6=fingerBlood, 7=самочувствие")
    actionData: SibionicsActionData = Field(..., description="Данные действия")
    
    class Config:
        from_attributes = True