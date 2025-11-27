"""Energy domain schemas"""
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
