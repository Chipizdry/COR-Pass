from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import List, Optional
from datetime import datetime
from cor_pass.database.models import Status
import re

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


class TokenModel(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponseModel(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    is_admin: bool
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

    tags: List[TagModel]

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
