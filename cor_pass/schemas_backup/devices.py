"""Devices domain schemas"""
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




class GeneralPrinting(BaseModel):
    printer_ip: Optional[str] = None
    number_models_id: Optional[str] = None
    clinic_name: Optional[str] = None
    hooper: Optional[str] = None
    # printing: bool



class PrintLabel(BaseModel):
    """Модель для одной метки для печати."""
    model_id: int
    content: str
    uuid: str 



class PrintRequest(BaseModel):
    labels: List[Label]




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
