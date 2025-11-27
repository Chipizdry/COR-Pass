"""Health domain schemas"""
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
    from .shared import IndividualResult

# AUTH MODELS


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




class TonometrIncomingData(BaseModel):
    created_at: datetime
    member: List[str]
    results_list: List["IndividualResult"] = Field(..., alias="results")





class ECGMeasurementResponse(BaseModel):
    id: str 
    user_id: str
    created_at: datetime
    file_name: str

    class Config:
        from_attributes = True 




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




class PaginatedBloodPressureResponse(BaseModel):
    items: List[BloodPressureMeasurementResponse]
    total: int
    page: int
    page_size: int




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
