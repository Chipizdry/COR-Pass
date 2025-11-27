"""Doctor domain schemas"""
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
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar, Union, TYPE_CHECKING
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
    from .laboratory import Case, CaseOwnerResponse, ReferralAttachmentResponse

# AUTH MODELS


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




class ReferralResponseForDoctor(BaseModel):
    case_details: Optional["Case"]
    case_owner: Optional["CaseOwnerResponse"]
    referral_id: Optional[str] = Field(..., description="Referral ID")
    attachments: Optional[List["ReferralAttachmentResponse"]] = []

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




class InitiateSignatureRequest(BaseModel):
    # doctor_cor_id: str = Field(..., description="COR-ID доктора, который подписывает")
    diagnosis_id: str = Field(..., description="ID диагноза, который будет подписан")
    doctor_signature_id: Optional[str] = Field(None, description="ID подписи")




class InitiateSignatureResponse(BaseModel):
    session_token: str
    deep_link: str
    expires_at: datetime
    status: Optional[str] = None




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




class DoctorDiagnosisInputSchema(BaseModel):
    report_microdescription: Optional[str] = None
    report_macrodescription: Optional[str] = None
    pathomorphological_diagnosis: Optional[str] = None
    icd_code: Optional[str] = None
    comment: Optional[str] = None
    immunohistochemical_profile: Optional[str] = None
    molecular_genetic_profile: Optional[str] = None
