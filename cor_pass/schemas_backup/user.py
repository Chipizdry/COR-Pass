"""User domain schemas"""
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
from typing import TYPE_CHECKING, Any, Dict, Generic, List, Literal, Optional, TypeVar, Union
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

# Cross-domain imports
if TYPE_CHECKING:
    from .doctor import DoctorWithRelationsResponse

# AUTH MODELS


class UserModel(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=32)
    birth: Optional[int] = Field(None, ge=1900)
    user_sex: Optional[str] = Field(None, max_length=1)
    cor_id: Optional[str] = Field(None, max_length=15)

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
    def user_sex_must_be_m_or_f(cls, v):
        if v not in ["M", "F", "*"]:
            raise ValueError('user_sex must be "M" or "F" or "*" (other)')
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




class DeviceRegistration(BaseModel):
    device_token: str




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




class FullUserInfoResponse(BaseModel):
    user_info: UserDb
    user_roles: Optional[List[str]] = None
    profile: Optional[ProfileResponse] = None
    doctor_info: Optional["DoctorWithRelationsResponse"] = None

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
    doctor_info: Optional["DoctorWithRelationsResponse"] = None

    class Config:
        from_attributes = True




class UserRolesResponseForAdmin(BaseModel):
    user_roles: Optional[List[str]] = None

    class Config:
        from_attributes = True




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
    biz_id: str = Field(..., description="SIBIONICS Authorization resource ID")




class SibionicsUserAuthResponse(BaseModel):
    """Информация об авторизации пользователя в SIBIONICS"""
    id: str
    user_id: str
    biz_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)




class FuelUserLimitInfo(BaseModel):
    """Информация о лимитах пользователя от бэкенда финансов"""
    cor_id: str
    employee_name: Optional[str] = Field(None, description="ФИО сотрудника")
    employee_limit: float = Field(..., description="Лимит сотрудника")
    organization_id: str = Field(..., description="ID организации")
    organization_name: str = Field(..., description="Название организации")
    organization_limit: float = Field(..., description="Лимит организации")
    is_active: bool = Field(..., description="Активен ли сотрудник")




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
    



class FinanceBackendAuthRequest(BaseModel):
    """Запрос авторизации на бэкенде финансов"""
    totp_code: str = Field(..., description="TOTP код для авторизации")
    timestamp: int = Field(..., description="Unix timestamp")




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
