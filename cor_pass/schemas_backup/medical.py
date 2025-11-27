"""Medical domain schemas"""
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

# Cross-domain imports (real imports for inheritance)
from .laboratory import PatientFirstCaseDetailsResponse


# AUTH MODELS


class MedicalStorageSettings(BaseModel):
    local_medical_storage: bool
    cloud_medical_storage: bool




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




class PatientResponseForSigning(BaseModel):
    patient_cor_id: str
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[date] = None
    sex: Optional[str] = None
    age: Optional[int] = None



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




class SearchResultPatientOverview(PatientFirstCaseDetailsResponse):
    search_type: Literal["patient_overview"] = "patient_overview"



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
