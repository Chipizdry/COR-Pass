"""Shared domain schemas"""
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
    from .user import FinanceBackendAuthRequest, SessionLoginStatus
    from .medical import SearchResultPatientOverview
    from .laboratory import SearchResultCaseDetails
    
    SearchResultUnion = Union["SearchResultPatientOverview", "SearchResultCaseDetails"]

# AUTH MODELS


class DeleteMyAccount(BaseModel):
    password: str = Field(min_length=6, max_length=20)




class ActionRequest(BaseModel):
    session_token: str
    status: "SessionLoginStatus"




class StatusResponse(BaseModel):
    session_token: str
    status: str
    deep_link: Optional[str] = None
    expires_at: datetime




class MeasureValue(BaseModel):
    value: int




class IndividualResult(BaseModel):
    measures: MeasureValue
    member: List[str]


# Type variable for generic pagination
T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T] = Field(..., description="Список элементов на текущей странице")
    total_count: int = Field(..., description="Общее количество элементов")
    page: int = Field(..., description="Текущий номер страницы (начиная с 1)")
    page_size: int = Field(..., description="Количество элементов на странице")
    total_pages: int = Field(..., description="Общее количество страниц")




class UnifiedSearchResponse(BaseModel):
    data: "SearchResultUnion" = Field(discriminator='search_type')




class FeedbackRatingScheema(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Оценка от 1 до 5")
    comment: str = Field(...,min_length=2,max_length=800, description="Комментарий до 800 символов")





class FeedbackProposalsScheema(BaseModel):
    proposal: str = Field(...,min_length=2,max_length=800, description="Предложения")



class EnergeticObjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    protocol: Optional[str] = Field(None, description="Протокол связи")
    ip_address: Optional[str] = Field(None, description="IP-адрес объекта")
    port: Optional[int] = Field(None, description="Порт объекта")
    inverter_login: Optional[str] = Field(None, description="Логин для доступа к инвертору")
    inverter_password: Optional[str] = Field(None, description="Пароль для доступа к инвертору")
    modbus_registers: Optional[dict] = None
    is_active: Optional[bool] = None
    timezone: str = Field(default="Europe/Kiev", description="Часовой пояс объекта (например: Europe/Kiev, America/New_York)")



class EnergeticObjectCreate(EnergeticObjectBase):
    pass



class EnergeticObjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    protocol: Optional[str] = Field(None, description="Протокол связи")
    ip_address: Optional[str] = Field(None, description="IP-адрес объекта")
    port: Optional[int] = Field(None, description="Порт объекта")
    inverter_login: Optional[str] = Field(None, description="Логин для доступа к инвертору")
    inverter_password: Optional[str] = Field(None, description="Пароль для доступа к инвертору")
    modbus_registers: Optional[dict] = None
    is_active: Optional[bool] = None
    timezone: Optional[str] = Field(None, description="Часовой пояс объекта (например: Europe/Kiev, America/New_York)")



class EnergeticObjectResponse(EnergeticObjectBase):
    id: str

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




class FinanceCheckLimitRequest(BaseModel):
    """Запрос проверки лимита сотрудника"""
    cor_id: str = Field(..., description="COR ID сотрудника")
    auth: "FinanceBackendAuthRequest" = Field(..., description="Данные авторизации")




class FinanceCheckLimitResponse(BaseModel):
    """Ответ от бэкенда финансов с лимитами"""
    cor_id: str
    employee_name: Optional[str] = None
    employee_limit: float
    organization_id: str
    organization_name: str
    organization_limit: float
    is_active: bool




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
