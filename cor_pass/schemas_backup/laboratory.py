"""Laboratory domain schemas"""
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
    from .doctor import DoctorDiagnosisInputSchema, DoctorDiagnosisSchema, DoctorResponseForSignature
    from .shared import StatusResponse

# AUTH MODELS


class CaseOwnerResponse(BaseModel):
    id: Optional[str] = Field(None, description="ID врача")
    doctor_id: Optional[str] = Field(None, description="COR-ID врача")
    work_email: Optional[EmailStr] = Field(None, description="Рабочий имейл")
    phone_number: Optional[str] = Field(None, description="Номер телефона")
    first_name: Optional[str] = Field(None, description="Имя врача")
    middle_name: Optional[str] = Field(None, description="Отчество врача")
    last_name: Optional[str] = Field(None, description="Фамилия врача")
    is_case_owner: Optional[bool] = Field(False, description="Владелец кейса")




class GlassBase(BaseModel):
    glass_number: int
    staining: Optional[str] = None




class GlassCreate(BaseModel):
    cassette_id: str
    staining_type: StainingType = Field(
        ...,
        description="Тип окрашивания для стекла",
        example=StainingType.HE,
    )
    num_glasses: int = Field(default=1, description="Количество создаваемых стекол")




class ChangeGlassStaining(BaseModel):
    staining_type: StainingType = Field(
        ...,
        description="Тип окрашивания для стекла",
        example=StainingType.HE,
    )




class Glass(GlassBase):
    id: str
    cassette_id: str
    is_printed: Optional[bool]
    preview_url: Optional[str]

    class Config:
        from_attributes = True




class GlassForGlassPage(GlassBase):
    id: str
    # cassette_id: str

    class Config:
        from_attributes = True




class DeleteGlassesRequest(BaseModel):
    glass_ids: List[str]




class DeleteGlassesResponse(BaseModel):
    deleted_count: int
    message: str
    not_found_ids: List[str] | None = None




class GetSample(BaseModel):
    sample_id: str




class SampleBase(BaseModel):
    sample_number: str
    archive: bool = False
    cassette_count: int = 0
    glass_count: int = 0




class SampleCreate(BaseModel):
    case_id: str
    num_samples: int = 1




class CassetteBase(BaseModel):
    cassette_number: str
    comment: Optional[str] = None




class CassetteCreate(BaseModel):
    sample_id: str
    num_cassettes: int = 1




class CassetteUpdateComment(BaseModel):
    comment: Optional[str] = None




class Cassette(CassetteBase):
    id: str
    sample_id: str
    glasses: List["Glass"] = []

    class Config:
        from_attributes = True


class Cassette(CassetteBase):
    id: str
    sample_id: str
    is_printed: Optional[bool]
    glasses: List[Glass] = []

    class Config:
        from_attributes = True




class Cassette(CassetteBase):
    id: str
    sample_id: str
    glasses: List["Glass"] = []

    class Config:
        from_attributes = True


class Cassette(CassetteBase):
    id: str
    sample_id: str
    is_printed: Optional[bool]
    glasses: List[Glass] = []

    class Config:
        from_attributes = True




class CassetteForGlassPage(BaseModel):
    # id: str
    # sample_id: str
    cassette_number: str
    glasses: List[Glass] = []

    class Config:
        from_attributes = True




class DeleteCassetteRequest(BaseModel):
    cassette_ids: List[str]




class DeleteCassetteResponse(BaseModel):
    deleted_count: int
    message: str




class Sample(SampleBase):
    id: str
    case_id: str
    macro_description: Optional[str] = None
    is_printed_cassette: Optional[bool]
    is_printed_glass: Optional[bool]
    cassettes: List[Cassette] = []

    class Config:
        from_attributes = True




class SampleForGlassPage(BaseModel):
    # id: str
    # case_id: str
    # macro_description: Optional[str] = None
    sample_number: str
    cassettes: List[CassetteForGlassPage] = []

    class Config:
        from_attributes = True




class UpdateSampleMacrodescription(BaseModel):
    macro_description: str




class DeleteSampleRequest(BaseModel):
    sample_ids: List[str]




class DeleteSampleResponse(BaseModel):
    deleted_count: int
    message: str




class DeleteCasesRequest(BaseModel):
    case_ids: List[str]




class DeleteCasesResponse(BaseModel):
    deleted_count: int
    message: str




class CaseBase(BaseModel):
    patient_cor_id: str
    # case_code: Optional[str] = None
    # grossing_status: str = Field(default="processing")




class CaseCreate(BaseModel):
    patient_cor_id: str
    num_cases: int = 1
    urgency: UrgencyType = Field(
        ...,
        description="Срочность иссследования",
        example=UrgencyType.S,
    )
    material_type: MaterialType = Field(
        ...,
        description="Тип исследования",
        example=MaterialType.R,
    )
    num_samples: int = Field(
        1, ge=1, description="Количество семплов для создания в каждом кейсе"
    )




class CaseCreateResponse(BaseModel):
    id: str
    case_code: str
    patient_id: str
    grossing_status: str
    creation_date: datetime
    cassette_count: int
    bank_count: int
    glass_count: int




class UpdateCaseCode(BaseModel):
    case_id: str
    update_data: str = Field(
        min_length=5,
        max_length=5,
        description="Последние 5 целочисельных символлов кода кейса",
    )




class Case(BaseModel):
    id: str
    creation_date: datetime
    patient_id: str
    case_code: str
    bank_count: int
    cassette_count: int
    glass_count: int
    pathohistological_conclusion: Optional[str] = None
    microdescription: Optional[str] = None
    grossing_status: Optional[str] = None
    is_printed_cassette: Optional[bool]
    is_printed_glass: Optional[bool]
    is_printed_qr: Optional[bool]


    class Config:
        from_attributes = True



class CaseWithOwner(Case):
    is_case_owner: Optional[bool]

    class Config:
        from_attributes = True




class UpdateCaseCodeResponce(BaseModel):
    id: str
    patient_id: str
    creation_date: datetime
    case_code: str
    bank_count: int
    cassette_count: int
    glass_count: int

    class Config:
        from_attributes = True




class FirstCaseDetailsSchema(BaseModel):
    id: str
    case_code: str
    creation_date: datetime
    is_printed_cassette: Optional[bool]
    is_printed_glass: Optional[bool]
    is_printed_qr: Optional[bool]
    samples: List[Sample]




class PatientFirstCaseDetailsResponse(BaseModel):
    all_cases: List[Case]
    first_case_details: Optional[FirstCaseDetailsSchema] = None




class CaseParametersScheema(BaseModel):
    case_id: str
    macro_archive: MacroArchive
    decalcification: DecalcificationType
    sample_type: SampleType
    material_type: MaterialType
    urgency: UrgencyType
    container_count_actual: Optional[int]
    fixation: FixationType
    macro_description: Optional[str]

    class Config:
        from_attributes = True




class SampleWithoutCassettesSchema(BaseModel):
    id: str
    sample_number: str
    case_id: str
    archive: bool
    cassette_count: int
    glass_count: int
    cassettes: List = []  # Для остальных семплов список кассет будет пустой




class CaseDetailsResponse(BaseModel):
    id: str
    case_code: str
    creation_date: datetime
    bank_count: int
    cassette_count: int
    glass_count: int
    pathohistological_conclusion: Optional[str] = None
    microdescription: Optional[str] = None
    is_printed_cassette: Optional[bool]
    is_printed_glass: Optional[bool]
    is_printed_qr: Optional[bool]
    samples: List[SampleWithoutCassettesSchema | Sample]
    # case_owner: Optional["DoctorResponseForSignature"] = None

    class Config:
        from_attributes = True




class SimpleCaseResponse(BaseModel):
    id: str
    case_code: str
    creation_date: datetime
    bank_count: int
    cassette_count: int
    glass_count: int
    pathohistological_conclusion: Optional[str] = None
    microdescription: Optional[str] = None




class CaseListResponse(BaseModel):
    items: List[Union[CaseDetailsResponse, SimpleCaseResponse]]




class CreateSampleWithDetails(BaseModel):
    created_samples: List[Sample]
    first_sample_details: Optional[Sample] = None




class ReferralAttachmentResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    file_url: Optional[str] = Field(None, description="URL файла")

    class Config:
        from_attributes = True




class ReferralAttachmentCreate(BaseModel):
    filename: str
    content_type: str
    file_data: bytes




class ReferralCreate(BaseModel):
    case_id: str = Field(..., description="ID связанного кейса")
    biomaterial_date: Optional[date] = Field(
        None, description="Дата забора биоматериала"
    )
    research_type: Optional[StudyType] = Field(None, description="Вид исследования")
    container_count: Optional[int] = Field(
        None, description="Фактическое количество контейнеров"
    )
    medical_card_number: Optional[str] = Field(None, description="Номер медкарты")
    clinical_data: Optional[str] = Field(None, description="Клинические данные")
    clinical_diagnosis: Optional[str] = Field(None, description="Клинический диагноз")
    medical_institution: Optional[str] = Field(
        None, description="Медицинское учреждение"
    )
    department: Optional[str] = Field(None, description="Отделение")
    attending_doctor: Optional[str] = Field(None, description="Лечащий врач")
    doctor_contacts: Optional[str] = Field(None, description="Контакты врача")
    medical_procedure: Optional[str] = Field(None, description="Медицинская процедура")
    final_report_delivery: Optional[str] = Field(
        None, description="Финальный репорт отправить"
    )
    issued_at: Optional[date] = Field(None, description="Выдано (дата)")




class ReferralResponse(BaseModel):
    id: str
    case_id: str
    case_number: str
    created_at: datetime
    biomaterial_date: Optional[date]
    research_type: Optional[StudyType]
    container_count: Optional[int]
    medical_card_number: Optional[str]
    clinical_data: Optional[str]
    clinical_diagnosis: Optional[str]
    medical_institution: Optional[str]
    department: Optional[str]
    attending_doctor: Optional[str]
    doctor_contacts: Optional[str]
    medical_procedure: Optional[str]
    final_report_delivery: Optional[str]
    issued_at: Optional[date]
    attachments: List[ReferralAttachmentResponse] = []

    class Config:
        from_attributes = True




class ReferralUpdate(BaseModel):
    case_number: Optional[str] = None
    research_type: Optional[str] = None
    container_count: Optional[int] = None
    medical_card_number: Optional[str] = None
    clinical_data: Optional[str] = None
    clinical_diagnosis: Optional[str] = None
    medical_institution: Optional[str] = None
    department: Optional[str] = None
    attending_doctor: Optional[str] = None
    doctor_contacts: Optional[str] = None
    medical_procedure: Optional[str] = None
    final_report_delivery: Optional[str] = None
    issued_at: Optional[date] = None

    class Config:
        from_attributes = True




class ReferralFileSchema(BaseModel):
    id: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_url: Optional[str] = None

    class Config:
        from_attributes = True




class FirstCaseReferralDetailsSchema(BaseModel):
    id: str
    case_code: str
    creation_date: datetime
    pathohistological_conclusion: Optional[str] = None
    microdescription: Optional[str] = None
    general_macrodescription: Optional[str] = None
    grossing_status: Optional[str] = None
    patient_cor_id: Optional[str] = None

    attachments: Optional[List[ReferralFileSchema]] = None

    class Config:
        from_attributes = True



class FirstCaseReferralDetailsWithOwner(FirstCaseReferralDetailsSchema):
    is_case_owner: Optional[bool]

    class Config:
        from_attributes = True



class ReportBaseSchema(BaseModel):
    immunohistochemical_profile: Optional[str] = None
    molecular_genetic_profile: Optional[str] = None
    pathomorphological_diagnosis: Optional[str] = None
    icd_code: Optional[str] = None
    comment: Optional[str] = None

    attached_glass_ids: Optional[List[str]] = None




class ReportCreateSchema(ReportBaseSchema):
    pass




class ReportUpdateSchema(ReportBaseSchema):
    pass



class FinalReportResponseSchema(BaseModel):
    id: Optional[str] = None
    case_id: str
    case_code: str

    biopsy_date: Optional[date] = None
    arrival_date: Optional[date] = None
    report_date: Optional[date] = None

    patient_cor_id: Optional[str] = None
    patient_first_name: Optional[str] = None
    patient_surname: Optional[str] = None
    patient_middle_name: Optional[str] = None
    patient_sex: Optional[str] = None
    patient_birth_date: Optional[date] = None
    patient_full_age: Optional[int] = None
    patient_phone_number: Optional[str] = None
    patient_email: Optional[str] = None

    concatenated_macro_description: Optional[str] = None

    medical_card_number: Optional[str] = None
    medical_institution: Optional[str] = None
    medical_department: Optional[str] = None
    attending_doctor: Optional[str] = None
    clinical_data: Optional[str] = None
    clinical_diagnosis: Optional[str] = None

    painting: Optional[List[StainingType]] = None

    macroarchive: Optional[MacroArchive] = None
    decalcification: Optional[DecalcificationType] = None
    fixation: Optional[FixationType] = None
    num_blocks: Optional[int] = None
    containers_recieved: Optional[int] = None
    containers_actual: Optional[int] = None

    doctor_diagnoses: List["DoctorDiagnosisSchema"] = []

    # attached_glass_ids: List[str] = []
    attached_glasses: List[Glass] = []

    class Config:
        from_attributes = True




class PatientFinalReportPageResponse(BaseModel):
    all_cases: Optional[List[CaseWithOwner]] = None
    last_case_details: Optional[CaseWithOwner] = None
    case_owner: Optional[CaseOwnerResponse]
    report_details: Optional[FinalReportResponseSchema]
    current_signings: Optional["StatusResponse"] = None

    class Config:
        from_attributes = True




class CaseFinalReportPageResponse(BaseModel):
    case_details: CaseWithOwner
    case_owner: Optional[CaseOwnerResponse]
    report_details: Optional[FinalReportResponseSchema]
    current_signings: Optional["StatusResponse"] = None

    class Config:
        from_attributes = True




class PatientCasesWithReferralsResponse(BaseModel):
    all_cases: List[CaseWithOwner]
    case_details: Optional[CaseWithOwner]
    case_owner: Optional[CaseOwnerResponse]
    first_case_direction: Optional[FirstCaseReferralDetailsWithOwner] = None

    class Config:
        from_attributes = True




class FirstCaseGlassDetailsSchema(BaseModel):
    id: str
    case_code: str
    creation_date: datetime
    pathohistological_conclusion: Optional[str] = None
    microdescription: Optional[str] = None
    general_macrodescription: Optional[str] = None
    grossing_status: Optional[str] = None
    patient_cor_id: Optional[str] = None
    is_printed_cassette: Optional[bool]
    is_printed_glass: Optional[bool]
    is_printed_qr: Optional[bool]

    samples: List[SampleForGlassPage]

    class Config:
        from_attributes = True



class FirstCaseGlassDetailsSchemaWithOwner(FirstCaseGlassDetailsSchema):
    is_case_owner: Optional[bool]

    class Config:
        from_attributes = True




class PatientGlassPageResponse(BaseModel):
    all_cases: List[CaseWithOwner]
    first_case_details_for_glass: Optional[FirstCaseGlassDetailsSchemaWithOwner] = None
    case_owner: Optional[CaseOwnerResponse]
    report_details: Optional[FinalReportResponseSchema]

    class Config:
        from_attributes = True




class SingleCaseGlassPageResponse(BaseModel):
    single_case_for_glass_page: Optional[FirstCaseGlassDetailsSchema] = None
    case_owner: Optional[CaseOwnerResponse]
    report_details: Optional[FinalReportResponseSchema]




class PathohistologicalConclusionResponse(BaseModel):
    pathohistological_conclusion: Optional[str] = None




class UpdatePathohistologicalConclusion(BaseModel):
    pathohistological_conclusion: str




class MicrodescriptionResponse(BaseModel):
    microdescription: Optional[str] = None




class UpdateMicrodescription(BaseModel):
    microdescription: str




class SampleForExcisionPage(BaseModel):
    id: str
    sample_number: str
    is_archived: bool = False
    macro_description: Optional[str] = None

    class Config:
        from_attributes = True




class LastCaseExcisionDetailsSchema(BaseModel):
    id: str
    case_code: str
    creation_date: datetime
    pathohistological_conclusion: Optional[str] = None
    microdescription: Optional[str] = None
    case_parameters: Optional[CaseParametersScheema] = None
    grossing_status: Optional[str] = None
    patient_cor_id: Optional[str] = None
    is_printed_cassette: Optional[bool]
    is_printed_glass: Optional[bool]
    is_printed_qr: Optional[bool]

    samples: List[SampleForExcisionPage]

    class Config:
        from_attributes = True



class LastCaseExcisionDetailsSchemaWithOwner(LastCaseExcisionDetailsSchema):
    is_case_owner: Optional[bool]

    class Config:
        from_attributes = True



class PatientExcisionPageResponse(BaseModel):
    all_cases: List[CaseWithOwner]
    last_case_details_for_excision: Optional[LastCaseExcisionDetailsSchemaWithOwner] = None
    case_owner: Optional[CaseOwnerResponse]

    class Config:
        from_attributes = True




class SingleCaseExcisionPageResponse(BaseModel):

    case_details_for_excision: Optional[LastCaseExcisionDetailsSchemaWithOwner] = None
    case_owner: Optional[CaseOwnerResponse]

    class Config:
        from_attributes = True




class GlassTestModelScheema(BaseModel):
    id: str
    glass_number: int
    cassette_id: str
    staining: Optional[str] = None
    preview_url: Optional[str]




class CassetteTestForGlassPage(BaseModel):
    id: str
    cassette_number: str
    sample_id: str

    glasses: List[GlassTestModelScheema] = []




class SampleTestForGlassPage(BaseModel):
    id: str
    sample_number: str
    case_id: str
    sample_macro_description: Optional[str] = None

    cassettes: List[CassetteTestForGlassPage] = []




class FirstCaseTestGlassDetailsSchema(BaseModel):
    id: str
    case_code: str
    creation_date: datetime
    grossing_status: Optional[str] = None
    samples: List[SampleTestForGlassPage]

    class Config:
        from_attributes = True




class ReportResponseSchema(BaseModel):
    id: str
    case_id: str
    case_details: Optional[Case] = None
    macro_description_from_case_params: Optional[str] = None
    microdescription_from_case: Optional[str] = None
    concatenated_macro_description: Optional[str] = None

    doctor_diagnoses: List["DoctorDiagnosisSchema"] = []

    attached_glasses: List[Glass] = []

    class Config:
        from_attributes = True




class PatientReportPageResponse(BaseModel):
    all_cases: List[Case]

    last_case_for_report: Optional[Case] = None
    report_details: Optional[ReportResponseSchema] = None

    all_glasses_for_last_case: List[FirstCaseGlassDetailsSchema] = []

    class Config:
        from_attributes = True




class SignReportRequest(BaseModel):
    doctor_signature_id: Optional[str] = None




class PatientTestReportPageResponse(BaseModel):
    all_cases: List[CaseWithOwner]
    last_case_for_report: Optional[CaseWithOwner]
    case_owner: Optional[CaseOwnerResponse]
    report_details: Optional[ReportResponseSchema]
    all_glasses_for_last_case: Optional[FirstCaseTestGlassDetailsSchema] = None

    class Config:
        from_attributes = True




class CaseIDReportPageResponse(BaseModel):
    last_case_for_report: Optional[Case] = None
    case_owner: Optional[CaseOwnerResponse]
    report_details: Optional[ReportResponseSchema] = None
    all_glasses_for_last_case: Optional[FirstCaseTestGlassDetailsSchema] = None

    class Config:
        from_attributes = True




class ReportAndDiagnosisUpdateSchema(BaseModel):

    attached_glass_ids: Optional[List[str]] = None
    doctor_diagnosis_data: Optional["DoctorDiagnosisInputSchema"] = None




class CaseCloseResponse(BaseModel):
    message: str
    case_id: str
    new_status: str




class CaseOwnershipResponse(BaseModel):
    case_details: Optional[CaseDetailsResponse]
    case_owner: Optional[CaseOwnerResponse]




class SearchResultCaseDetails(PatientGlassPageResponse): 
    search_type: Literal["case_details"] = "case_details"



class SearchCaseDetailsSimple(BaseModel):
    search_type: Literal["case_details"] = "case_details"
    case_id: str
    patient_id: str



class GlassPrinting(BaseModel):
    printer_ip: Optional[str] = None
    model_id: Optional[str] = None
    clinic_name: Optional[str] = None
    hooper: Optional[str] = None
    glass_id: str
    printing: bool



class GlassResponseForPrinting(BaseModel):

    case_code: str
    sample_number: str
    cassette_number: str
    glass_number: int
    staining: str
    patient_cor_id: str



class CassettePrinting(BaseModel):
    printer_ip: Optional[str] = None
    number_models_id: Optional[int] = None
    clinic_name: Optional[str] = None
    hooper: Optional[str] = None
    cassete_id: str
    printing: bool



class CassetteResponseForPrinting(BaseModel):

    case_code: Optional[str] = None
    sample_number: str
    cassette_number: str
    patient_cor_id: Optional[str] = None





class UploadGlassSVSResponse(BaseModel):
    preview_url: str
    scan_url: str



class SupportReportScheema(BaseModel):
    product_name: str = Field(...,min_length=2,max_length=20, description="Название продукта")
    report_text: str = Field(...,min_length=2,max_length=800, description="Текст ошибки")
