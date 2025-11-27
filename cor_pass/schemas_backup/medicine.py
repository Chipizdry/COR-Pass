"""Medicine domain schemas"""
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
    from .doctor import DoctorSignatureResponseWithName
    from .shared import StatusResponse

# AUTH MODELS


class UnitEnum(str, Enum):
    MG = "mg"
    G = "g"
    MCG = "mcg"
    ML = "ml"
    L = "l"
    IU = "iu"
    MG_ML = "mg/ml"
    PERCENT = "%"
    MG_M2 = "mg/m2"




class OralMedicine(BaseModel):
    """Пероральный способ — требует дозу и единицу измерения."""
    intake_method: Literal["Oral"]
    dosage: float = Field(..., description="Дозировка препарата")
    unit: UnitEnum = Field(..., description="Одиница измерения (мг, мл и т.д.)")
    concentration: Optional[float] = None
    volume: Optional[float] = None





class OintmentMedicine(BaseModel):
    """Мази / свечи — требуют концентрацию."""
    intake_method: Literal["Ointment/suppositories"]
    concentration: float = Field(..., description="Концентрация активного вещества (%)")
    dosage: Optional[float] = None
    unit: Optional[UnitEnum] = None
    volume: Optional[float] = None




class SolutionMedicine(BaseModel):
    """Растворы, внутривенно, внутримышечно — требуют концентрацию и объем."""
    intake_method: Literal["Intravenous", "Intramuscularly", "Solutions"]
    concentration: float = Field(..., description="Концентрация раствора (%)")
    volume: float = Field(..., description="Объем раствора (мл)")
    dosage: Optional[float] = None
    unit: Optional[UnitEnum] = None






class MedicineBase(BaseModel):
    name: str = Field(..., description="Название препарата")
    active_substance: Optional[str] = Field(None, description="Действующее вещество")


    method_data: Union[OralMedicine, OintmentMedicine, SolutionMedicine]

    class Config:
        orm_mode = True






class MedicineCreate(MedicineBase):
    pass




class MedicineUpdate(MedicineBase):
    name: Optional[str] = None






class MedicineScheduleBase(BaseModel):
    start_date: date
    duration_days: Optional[int] = Field(None, description="Длительность приема")
    times_per_day: Optional[int] = Field(
        None, description="Кратность в день: 1 раз / 2 раза / 3 раза в день"
    )
    intake_times: Optional[List[time]] = Field(
        None, description="Список времён приёма: 21:00, 9:00 и т.д."
    )
    interval_minutes: Optional[int] = Field(
        None, description="Интервал между приёмами в минутах"
    )
    symptomatically: Optional[bool] = Field(False, description="Симптоматический приём")
    notes: Optional[str] = Field(None, description="Заметка")


    @field_validator("intake_times", mode="before")
    @classmethod
    def validate_intake_times(cls, v: Optional[List], info: ValidationInfo):
        if v is None:
            return v
        
        # Преобразуем строки в time объекты
        result = []
        for item in v:
            if isinstance(item, str):
                # Парсим строку формата "HH:MM", "HH:MM:SS" или "HH:MM:SS.microseconds[Z]"
                try:
                    # Убираем timezone marker (Z) если есть
                    time_str = item.rstrip('Z')
                    
                    # Разделяем по двоеточию
                    time_parts = time_str.split(":")
                    
                    if len(time_parts) == 2:
                        # Формат HH:MM
                        result.append(time(int(time_parts[0]), int(time_parts[1])))
                    elif len(time_parts) == 3:
                        # Формат HH:MM:SS или HH:MM:SS.microseconds
                        seconds_part = time_parts[2]
                        
                        # Проверяем, есть ли миллисекунды/микросекунды
                        if '.' in seconds_part:
                            seconds_str, microseconds_str = seconds_part.split('.')
                            seconds = int(seconds_str)
                            # Преобразуем миллисекунды в микросекунды (datetime.time принимает микросекунды)
                            # Если пришло "39.554", то это 554 миллисекунды = 554000 микросекунд
                            microseconds = int(microseconds_str.ljust(6, '0')[:6])
                            result.append(time(int(time_parts[0]), int(time_parts[1]), seconds, microseconds))
                        else:
                            # Простой формат HH:MM:SS
                            result.append(time(int(time_parts[0]), int(time_parts[1]), int(seconds_part)))
                    else:
                        raise ValueError(f"Неверный формат времени: {item}. Ожидается HH:MM, HH:MM:SS или HH:MM:SS.microseconds")
                except (ValueError, IndexError) as e:
                    raise ValueError(f"Не удалось распарсить время '{item}': {e}")
            elif isinstance(item, time):
                result.append(item)
            else:
                raise ValueError(f"Неверный тип времени: {type(item)}. Ожидается строка или time объект")
        
        data = info.data or {}  
        times_per_day = data.get("times_per_day")

        if times_per_day is not None and result is not None:
            if len(result) != times_per_day:
                raise ValueError(
                    f"Количество вхождений часов приема ({len(result)}) должно соответствовать количеству приёмов в день({times_per_day})"
                )

        # Если times_per_day не указано, но intake_times есть — выставляем автоматически
        if result is not None and times_per_day is None:
            data["times_per_day"] = len(result)

        return result


    @field_validator("times_per_day")
    @classmethod
    def validate_times_per_day(cls, v: Optional[int]):
        if v is not None and v <= 0:
            raise ValueError("Количество приемов должно быть больше нуля")
        return v

    @model_validator(mode="after")
    def validate_schedule_logic(self):
        if self.intake_times and self.interval_minutes:
            raise ValueError(
                "Нельзя одновременно указывать и времена приема, и интервал между ними"
            )
        if not self.intake_times and not self.interval_minutes:
            raise ValueError(
                "Нужно указать либо конкретные времена приема, либо интервал между ними"
            )
        return self




class MedicineScheduleCreate(MedicineScheduleBase):
    medicine_id: str




class MedicineScheduleUpdate(MedicineScheduleBase):
    pass



class MedicineScheduleResponse(BaseModel):
    id: str
    start_date: date
    duration_days: Optional[int] 
    times_per_day: Optional[int]
    intake_times: Optional[List[time]] 
    interval_minutes: Optional[int] 
    symptomatically: Optional[bool] 
    notes: Optional[str] 

    class Config:
        from_attributes = True




class MedicineIntakeBase(BaseModel):
    """Базовая схема приема медикамента"""
    planned_datetime: datetime = Field(..., description="Запланированное время приема")
    status: MedicineIntakeStatus = Field(
        default=MedicineIntakeStatus.PLANNED,
        description="Статус приема (запланирован/выполнен/пропущен/отложен)"
    )
    notes: Optional[str] = Field(None, description="Комментарий к приему")



class MedicineIntakeCreate(MedicineIntakeBase):
    """Схема для создания записи о приеме"""
    schedule_id: str = Field(..., description="ID расписания")
    user_cor_id: str = Field(..., description="ID пользователя")



class MedicineIntakeUpdate(BaseModel):
    """Схема для обновления записи о приеме"""
    status: MedicineIntakeStatus = Field(..., description="Новый статус приема")
    actual_datetime: Optional[datetime] = Field(None, description="Фактическое время приема")
    notes: Optional[str] = Field(None, description="Комментарий к приему")



class MedicineIntakeResponse(BaseModel):
    """Схема для ответа с информацией о приеме"""
    id: str
    schedule_id: str
    user_cor_id: str
    planned_datetime: datetime
    actual_datetime: Optional[datetime] = None
    status: MedicineIntakeStatus
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    name: str = Field(alias='medicine_name', description="Название лекарства")
    dosage: Optional[float] = Field(alias='medicine_dosage', description="Дозировка лекарства")
    unit: Optional[str] = Field(alias='medicine_unit', description="Единица измерения дозировки")
    intake_method: Optional[str] = Field(alias='medicine_intake_method', description="Способ приёма лекарства")
    # name: str
    # medicine_dosage: Optional[float] = None
    # medicine_unit: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)




class PaginatedMedicineIntakeResponse(BaseModel):
    """Схема для пагинированного списка приемов лекарств"""
    items: List[MedicineIntakeResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)




class GroupedMedicineIntake(BaseModel):
    """Группа приемов лекарств на одно время"""
    time: str = Field(..., description="Время приема (HH:MM)")
    planned_datetime: datetime = Field(..., description="Полная дата и время планового приема")
    medicines: List[MedicineIntakeResponse] = Field(default_factory=list, description="Список лекарств на это время")
    total_count: int = Field(..., description="Количество лекарств в группе")
    
    model_config = ConfigDict(from_attributes=True)




class DailyMedicineIntakes(BaseModel):
    """Приемы лекарств на конкретную дату, сгруппированные по времени"""
    intake_date: date = Field(..., description="Дата")
    day_name: str = Field(..., description="Название дня недели")
    time_groups: List[GroupedMedicineIntake] = Field(default_factory=list, description="Группы приемов по времени")
    total_intakes: int = Field(..., description="Общее количество приемов за день")
    
    model_config = ConfigDict(from_attributes=True)




class GroupedMedicineIntakesResponse(BaseModel):
    """Список приемов лекарств, сгруппированных по дням и времени"""
    days: List[DailyMedicineIntakes] = Field(default_factory=list, description="Приемы по дням")
    total_days: int = Field(..., description="Количество дней")
    date_range: dict = Field(..., description="Диапазон дат (start, end)")
    
    model_config = ConfigDict(from_attributes=True)




class MedicineScheduleWithIntakes(MedicineScheduleResponse):
    intakes: List[MedicineIntakeResponse] = []

    class Config:
        from_attributes = True




class MedicineScheduleWithIntakes(MedicineScheduleResponse):
    intakes: List[MedicineIntakeResponse] = []

    class Config:
        from_attributes = True




class MedicineScheduleRead(MedicineScheduleBase):
    id: str
    medicine_id: str
    # user_cor_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True




class MedicineRead(MedicineBase):
    id: str
    created_at: datetime
    updated_at: datetime
    schedules: Optional[List[MedicineScheduleResponse]] = []

    class Config:
        orm_mode = True




class FirstAidKitBase(BaseModel):
    name: str = Field(..., description="Название аптечки")
    description: Optional[str] = None





class FirstAidKitCreate(FirstAidKitBase):
    pass




class FirstAidKitUpdate(FirstAidKitBase):
    name: Optional[str] = None






class FirstAidKitItemBase(BaseModel):
    medicine_id: str
    quantity: Optional[int] = 1
    expiration_date: Optional[date] = None




class FirstAidKitItemCreate(FirstAidKitItemBase):
    # first_aid_kit_id: str
    pass




class FirstAidKitItemUpdate(FirstAidKitItemBase):
    pass




class FirstAidKitItemRead(FirstAidKitItemBase):
    id: str
    created_at: datetime
    medicine: Optional[MedicineRead]

    class Config:
        orm_mode = True



class FirstAidKitCreateResponse(FirstAidKitBase):
    id: str
    # user_id: str
    created_at: datetime
    # updated_at: datetime
    # medicines: Optional[List[FirstAidKitItemRead]] = []

    class Config:
        orm_mode = True




class FirstAidKitRead(FirstAidKitBase):
    id: str
    # user_id: str
    created_at: datetime
    updated_at: datetime
    # medicines: Optional[List[FirstAidKitItemRead]] = []

    class Config:
        orm_mode = True




class FirstAidKitItemAddRead(BaseModel):
    id: str
    quantity: int
    expiration_date: Optional[date] = None
    created_at: datetime
    medicine: MedicineRead
    first_aid_kit: FirstAidKitRead

    class Config:
        orm_mode = True



class OphthalmologicalPrescriptionBase(BaseModel):
    # Параметры правого глаза (OD)
    od_sph: Optional[float] = Field(None, description="Sph правого глаза")
    od_cyl: Optional[float] = Field(None, description="Cyl правого глаза")
    od_ax: Optional[float] = Field(None, description="Ax правого глаза")
    od_prism: Optional[float] = Field(None, description="Prism правого глаза")
    od_base: Optional[str] = Field(None, description="Base правого глаза (Up / Down / In / Out)")
    od_add: Optional[float] = Field(None, description="Add правого глаза")

    # Параметры левого глаза (OS)
    os_sph: Optional[float] = Field(None, description="Sph левого глаза")
    os_cyl: Optional[float] = Field(None, description="Cyl левого глаза")
    os_ax: Optional[float] = Field(None, description="Ax левого глаза")
    os_prism: Optional[float] = Field(None, description="Prism левого глаза")
    os_base: Optional[str] = Field(None, description="Base левого глаза (Up / Down / Medial / Lateral)")
    os_add: Optional[float] = Field(None, description="Add левого глаза")

    # Общие параметры
    glasses_purpose: Literal["glasses_for_reading", "glasses_for_distance", "glasses_for_constant_wear"]
    glasses_type: Literal["monofocal_glasses", "bifocal_glasses", "multifocal_glasses"]

    issue_date: Optional[datetime] = Field(...)
    term_months: Optional[int] = Field(None, description="Срок действия рецепта в месяцах")
    note: Optional[str] = Field(None, description="Заметки")

    @field_validator("od_base", "os_base")
    @classmethod
    def validate_base_direction(cls, v):
        allowed = {"Up", "Down", "Medial", "Lateral", None}
        if v not in allowed:
            raise ValueError("Base должен быть одним из: Up, Down, Medial, Lateral")
        return v





class OphthalmologicalPrescriptionCreate(OphthalmologicalPrescriptionBase):
    patient_id: str
    doctor_signature_id: Optional[str] = None




class OphthalmologicalPrescriptionUpdate(OphthalmologicalPrescriptionBase):
    pass




class OphthalmologicalPrescriptionRead(OphthalmologicalPrescriptionBase):
    id: str
    patient_id: str
    expires_at: Optional[datetime] = None
    doctor_signature_id: Optional[str] = None
    signed_at: Optional[datetime] = None
    issue_date: datetime

    class Config:
        orm_mode = True



class OphthalmologicalPrescriptionReadWithSigning(BaseModel):
    ophthalmological_prescription: OphthalmologicalPrescriptionRead
    doctor_signing_info: Optional["DoctorSignatureResponseWithName"] = None
    current_signings: Optional["StatusResponse"] = None



class PrescriptionFileBase(BaseModel):
    file_name: str = Field(..., description="Название файла рецепта")
    file_type: str = Field(..., description="Тип файла (image/jpeg, image/png, application/pdf)")
    file_size_kb: float = Field(..., description="Размер файла в килобайтах")
    issue_date: Optional[datetime] = Field(None, description="Дата выписки рецепта")



class PrescriptionFileRead(PrescriptionFileBase):
    id: str
    uploaded_at: datetime

    class Config:
        orm_mode = True
