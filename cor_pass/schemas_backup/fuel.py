"""Fuel domain schemas"""
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
    from .user import FuelUserLimitInfo

# AUTH MODELS


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




class FuelQRVerifyResponse(BaseModel):
    """Ответ при верификации QR кода"""
    is_valid: bool = Field(..., description="Валиден ли QR код")
    message: str = Field(..., description="Сообщение о результате")
    
    # Данные пользователя (если успешно)
    user_cor_id: Optional[str] = None
    
    # Лимиты (если успешно получены от бэкенда финансов)
    limit_info: Optional["FuelUserLimitInfo"] = None




class FuelOfflineQRData(BaseModel):
    """Данные офлайн QR кода для заправки (работает без интернета)"""
    cor_id: str = Field(..., description="COR ID сотрудника")
    totp_code: str = Field(..., description="TOTP код (6 цифр)")
    timestamp: int = Field(..., description="Unix timestamp генерации QR")
    company_id: Optional[str] = Field(None, description="ID компании (опционально)")




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
    company_id: Optional[str] = Field(None, description="ID компании")
    verified_at: Optional[datetime] = Field(None, description="Время верификации")
