"""Roles domain schemas"""
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
