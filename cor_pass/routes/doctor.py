from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

from cor_pass.database.db import get_db
from cor_pass.database.models import (
    PatientClinicStatus,
    PatientStatus,
    User,
)
from cor_pass.repository.doctor import (
    create_doctor,
    create_doctor_service,
    create_doctor_signature,
    delete_doctor_signature,
    get_doctor_signatures,
    get_doctor_single_patient_without_doctor_status,
    get_patients_with_optional_status,
    get_signature_data,
    set_default_doctor_signature,
    upload_certificate_service,
    upload_diploma_service,
    upload_doctor_photo_service,
    upload_reserv_data_service,
)
from cor_pass.repository.lawyer import get_doctor
from cor_pass.repository.patient import (
    create_patient_and_user_by_email,
    create_patient_linked_to_user,
    create_standalone_patient,
    find_patient,
    get_single_patient_by_corid

)
from cor_pass.schemas import (
    CaseCloseResponse,
    CaseCreate,
    CaseFinalReportPageResponse,
    CaseIDReportPageResponse,
    ExistingPatientRegistration,
    GetAllPatientsResponce,
    PatientCreationResponse,
    PatientFinalReportPageResponse,
    PatientTestReportPageResponse,
    ReportAndDiagnosisUpdateSchema,
    ReportResponseSchema,
    DoctorCreate,
    DoctorCreateResponse,
    DoctorSignatureResponse,
    ExistingPatientAdd,
    MicrodescriptionResponse,
    NewPatientRegistration,
    PathohistologicalConclusionResponse,
    PatientCasesWithReferralsResponse,
    PatientDecryptedResponce,
    PatientExcisionPageResponse,
    PatientGlassPageResponse,
    ReferralAttachmentResponse,
    ReferralResponseForDoctor,
    SearchResultCaseDetails,
    SearchResultPatientOverview,
    SignReportRequest,
    SingleCaseExcisionPageResponse,
    SingleCaseGlassPageResponse,
    UnifiedSearchResponse,
    UpdateMicrodescription,
    UpdatePathohistologicalConclusion,
)
from cor_pass.routes.cases import router as cases_router
from cor_pass.repository import case as case_service
from cor_pass.repository import person as repository_person
from cor_pass.services.auth import auth_service
from cor_pass.services.access import user_access, doctor_access, lab_assistant_or_doctor_access
from cor_pass.services.auth import auth_service
from cor_pass.services.document_validation import validate_document_file
from cor_pass.services.image_validation import validate_image_file
from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger

from cor_pass.services.search_token_generator import generate_ngrams

router = APIRouter(prefix="/doctor", tags=["Doctor"])


@router.post(
    "/signup",
    response_model=DoctorCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_access)],
)
async def signup_doctor(
    doctor_data: DoctorCreate = Body(...),
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Создание врача со всеми связанными данными**\n
    Этот маршрут позволяет создать врача вместе с дипломами, сертификатами и привязками к клиникам.
    Уровень доступа:
    - Текущий авторизованный пользователь
    :param doctor_data: str: Данные для создания врача в формате JSON.
    :param db: AsyncSession: Сессия базы данных.
    :return: Созданный врач.
    :rtype: DoctorResponse
    """

    exist_doctor = await get_doctor(db=db, doctor_id=current_user.cor_id)
    if exist_doctor:
        logger.debug(f"{current_user.cor_id} doctor already exist")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Doctor account already exists"
        )

    try:
        doctor = await create_doctor(
            doctor_data=doctor_data,
            db=db,
            user=current_user,
        )
        cer, dip, clin = await create_doctor_service(
            doctor_data=doctor_data, db=db, doctor=doctor
        )
    except IntegrityError as e:
        logger.error(f"Database integrity error: {e}")
        await db.rollback()
        detail = "Database error occurred. Please check the data for duplicates or invalid entries."
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during doctor creation.",
        )
    # Сериализуем ответ
    doctor_response = DoctorCreateResponse(
        id=doctor.id,
        doctor_cor_id=doctor.doctor_id,
        work_email=doctor.work_email,
        phone_number=doctor.phone_number,
        first_name=doctor.first_name,
        middle_name=doctor.middle_name,
        last_name=doctor.last_name,
        scientific_degree=doctor.scientific_degree,
        date_of_last_attestation=doctor.date_of_last_attestation,
        status=doctor.status,
        diploma_id=dip,
        certificates_id=cer,
        clinic_affiliations_id=clin,
        place_of_registration=doctor.place_of_registration,
        passport_code=doctor.passport_code,
        taxpayer_identification_number=doctor.taxpayer_identification_number,
    )

    return doctor_response


@router.post("/doctors/{doctor_cor_id}/photo", dependencies=[Depends(user_access)])
async def upload_doctor_photo(
    doctor_cor_id: str,
    file: UploadFile = Depends(validate_image_file),
    db: AsyncSession = Depends(get_db),
):
    return await upload_doctor_photo_service(doctor_cor_id, file, db)


@router.post("/doctors/{doctor_cor_id}/reserv", dependencies=[Depends(user_access)])
async def upload_doctor_reserv_data(
    doctor_cor_id: str,
    file: UploadFile = Depends(validate_document_file),
    db: AsyncSession = Depends(get_db),
):
    return await upload_reserv_data_service(doctor_cor_id, file, db)


@router.post("/diploma/{diploma_id}", dependencies=[Depends(user_access)])
async def upload_diploma(
    document_id: str,
    file: UploadFile = Depends(validate_document_file),
    db: AsyncSession = Depends(get_db),
):
    return await upload_diploma_service(document_id, file, db)


@router.post("/certificate/{certificate_id}", dependencies=[Depends(user_access)])
async def upload_certificate(
    document_id: str,
    file: UploadFile = Depends(validate_document_file),
    db: AsyncSession = Depends(get_db),
):
    return await upload_certificate_service(document_id, file, db)


@router.get(
    "/patients",
    dependencies=[Depends(doctor_access)],
    response_model=GetAllPatientsResponce,
)
async def get_doctor_patients(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
    doctor_patient_status: Optional[str] = Query(
        None,
        description="Фильтрация по статусу у врача (скорее всего отпадет) (варианты: registered, diagnosed, under_treatment, hospitalized, discharged, died, in_process, referred_for_additional_consultation)",
    ),
    clinic_patient_status: Optional[str] = Query(
        None,
        description="Фильтр поо статусу в клинике (варианты: registered, diagnosed, under_treatment, hospitalized, discharged, died, in_process, referred_for_additional_consultation, awaiting_report, completed, error)",
    ),
    current_doctor: Optional[bool] = Query(
        False, description="Фильтр по текущему врачу (бул)"
    ),
    sex: Optional[str] = Query(None, description="Фильтр по полу (варианты:'M','F')"),
    sort_by: Optional[str] = Query(
        "change_date",
        description="Сортировка по полю (варианты: change_date, birth_date)",
    ),
    sort_order: Optional[str] = Query("desc", description="Сортировка (asc или desc)"),
    skip: int = Query(1, ge=1, description="Страницы (1-based index)"),
    limit: int = Query(10, ge=1, le=100, description="К-ство на страницу"),
):
    doctor = None
    if current_doctor:
        doctor = await get_doctor(db=db, doctor_id=current_user.cor_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found"
            )

    doctor_status_filters = None
    if doctor_patient_status:
        try:
            doctor_status_filters = [PatientStatus(doctor_patient_status)]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid doctor patient status value: '{doctor_patient_status}'. Allowed values are: {[e.value for e in PatientStatus]}",
            )

    clinic_status_filters = None
    if clinic_patient_status:
        try:
            clinic_status_filters = [PatientClinicStatus(clinic_patient_status)]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid clinic patient status value: '{clinic_patient_status}'. Allowed values are: {[e.value for e in PatientClinicStatus]}",
            )

    response = await get_patients_with_optional_status(
        db=db,
        doctor=doctor,
        doctor_status_filters=doctor_status_filters,
        clinic_status_filters=clinic_status_filters,
        sex_filters=sex,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=limit
    )
    return response


@router.get(
    "/patients/{patient_cor_id}",
    dependencies=[Depends(doctor_access)],
    response_model=PatientDecryptedResponce,
)
async def get_single_patient(
    patient_cor_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    doctor = await get_doctor(db=db, doctor_id=current_user.cor_id)
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found"
        )

    patient = await get_doctor_single_patient_without_doctor_status(
        db=db, patient_cor_id=patient_cor_id, doctor=doctor
    )

    return patient


@router.post(
    "/patients/register-new",
    response_model=PatientCreationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(doctor_access)],
)
async def add_new_patient_to_doctor(
    body: NewPatientRegistration,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    """
    Добавить нового пациента к врачу.
    """
    doctor = await get_doctor(current_user.cor_id, db)
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found"
        )
    if current_user.cor_id != doctor.doctor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to add patients to this doctor",
        )
    new_patient_info = body
    if new_patient_info.email:
        exist_user = await repository_person.get_user_by_email(
            new_patient_info.email, db
        )
        if exist_user:
            logger.debug(
                f"{new_patient_info.email} user already exists, please create patient by cor-id"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Account already exists"
            )
        try:
            return await create_patient_and_user_by_email(
                db=db, patient_data=body, doctor=doctor
            )
        except HTTPException as e:
            raise e
        except Exception as e:

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create new user and patient: {e}",
            )
    else:
        try:
            return await create_standalone_patient(
                db=db, patient_data=body, doctor=doctor
            )
        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create standalone patient: {e}",
            )


@router.post(
    "/patients/add-existing",
    response_model=PatientCreationResponse,
    dependencies=[Depends(doctor_access)],
)
async def add_existing_patient_to_doctor(
    patient_data: ExistingPatientAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    """
    Добавить существующего пациента к врачу.
    """
    doctor = await get_doctor(doctor_id=current_user.cor_id, db=db)
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found"
        )
    user = await repository_person.get_user_by_corid(cor_id=patient_data.cor_id, db=db)
    new_patient_data = ExistingPatientRegistration(
        email=user.email,
        birth_date=user.birth,
        sex=user.user_sex,
    )
    patient = await create_patient_linked_to_user(
        db=db,
        doctor=doctor,
        user_cor_id=patient_data.cor_id,
        patient_data=new_patient_data,
    )
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )

    return patient


@router.get(
    "/patients/{patient_id}/glass-details",
    response_model=PatientGlassPageResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Получение кейсов и стёкол для страницы 'Стёкла'",
    tags=["DoctorPage"],
)
async def get_patient_glass_page_data(
    patient_id: str,
    case_id=Query(None, description="Опциональный параметр case_id"),
    user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PatientGlassPageResponse:
    """
    Возвращает список всех кейсов пациента и все стёкла первого кейса
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    glass_page_data = await case_service.get_patient_case_details_for_glass_page(
        db=db,
        patient_id=patient_id,
        current_doctor_id=doctor.doctor_id,
        router=router,
        case_id=case_id,
    )

    return glass_page_data


@router.get(
    "/cases/{case_id}/glass-details",
    response_model=SingleCaseGlassPageResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Cтёкла конкретного кейса для страницы 'Стёкла'",
    tags=["DoctorPage"],
)
async def get_single_case_details_for_glass_page(
    case_id: str,
    user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SingleCaseGlassPageResponse:
    """
    Возвращает стёкла конкретного кейса
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    glass_page_data = await case_service.get_single_case_details_for_glass_page(
        db=db, case_id=case_id, current_doctor_id=doctor.doctor_id, router=router
    )

    return glass_page_data


@router.get(
    "/patients/{patient_cor_id}/referral_page",
    response_model=PatientCasesWithReferralsResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Получение кейсов и вывод файлов направления по первому кейсу",
    tags=["DoctorPage"],
)
async def get_patient_cases_for_doctor(
    patient_cor_id: str,
    case_id=Query(None, description="Опциональный параметр case_id"),
    user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PatientCasesWithReferralsResponse:
    """
    Возвращает список всех кейсов конкретного пациента, а также детали первого кейса, включая ссылку на файлы его направлений
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    patient_cases_data = await case_service.get_patient_cases_with_directions(
        db=db,
        patient_id=patient_cor_id,
        current_doctor_id=doctor.doctor_id,
        case_id=case_id,
    )
    if not patient_cases_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кейси пацієнта або направлення не знайдено.",
        )

    return patient_cases_data


@router.get(
    "/patients/referrals/{case_id}",
    response_model=ReferralResponseForDoctor,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Вывод файлов направления по id кейса для доктора",
    tags=["DoctorPage"],
)
async def get_single_referral(
    case_id: str,
    user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает ссылки на прикрепленные файлы направлений конкретного кейса.
    """
    referral = await case_service.get_referral_by_case(db=db, case_id=case_id)
    if not referral:
        referral = None
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)

    if referral:
        attachments_response = [
            ReferralAttachmentResponse(
                id=att.id,
                filename=att.filename,
                content_type=att.content_type,
                file_url=cases_router.url_path_for(
                    "get_referral_attachment", attachment_id=att.id
                ),
            )
            for att in referral.attachments
        ]

    case_db = await case_service.get_single_case(db=db, case_id=case_id)
    case_owner = await case_service.get_case_owner(
        db=db, case_id=case_db.id, doctor_id=doctor.doctor_id
    )
    response = ReferralResponseForDoctor(
        case_details=case_db,
        case_owner=case_owner,
        referral_id=referral.id if referral else None,
        attachments=attachments_response if referral else None,
    )
    return response


@router.put(
    "/pathohistological_conclusion/{case_id}",
    response_model=PathohistologicalConclusionResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Обновляет патогистологическое заключение кейса",
    tags=["DoctorPage"],
)
async def update_pathohistological_conclusion(
    case_id: str,
    body: UpdatePathohistologicalConclusion,
    db: AsyncSession = Depends(get_db),
):
    """
    Обновляет патогистологическое заключение кейса

    """
    db_case = await case_service.update_case_pathohistological_conclusion(
        db=db, case_id=case_id, body=body
    )
    if db_case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Case not found"
        )
    return db_case


@router.put(
    "/microdescription/{case_id}",
    response_model=MicrodescriptionResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Обновляет микроописание кейса",
    tags=["DoctorPage"],
)
async def update_microdescription(
    case_id: str,
    body: UpdateMicrodescription,
    db: AsyncSession = Depends(get_db),
):
    """
    Обновляет микроописание кейса

    """
    db_case = await case_service.update_case_microdescription(
        db=db, case_id=case_id, body=body
    )
    if db_case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Case not found"
        )
    return db_case


@router.get(
    "/patients/{patient_id}/excision-details",
    response_model=PatientExcisionPageResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Получение кейсов и нужных данных для страницы 'Вырезка'",
    tags=["DoctorPage"],
)
async def get_patient_excision_page_data(
    patient_id: str,
    case_id=Query(None, description="Опциональный параметр case_id"),
    user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PatientExcisionPageResponse:
    """
    Возвращает все кейсы и данные вырезки по последнему кейсу
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    excision_page_data = await case_service.get_patient_case_details_for_excision_page(
        db=db,
        patient_id=patient_id,
        current_doctor_id=doctor.doctor_id,
        case_id=case_id,
    )

    return excision_page_data


@router.get(
    "/cases/{case_id}/excision-details",
    response_model=SingleCaseExcisionPageResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Данные вырезки конкретного кейса для страницы 'Вырезка'",
    tags=["DoctorPage"],
)
async def get_single_case_details_for_excision_page(
    case_id: str,
    user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SingleCaseExcisionPageResponse:
    """
    Возвращает данные вырезки конкретного кейса
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    excision_page_data = await case_service.get_single_case_details_for_excision_page(
        db=db, case_id=case_id, current_doctor_id=doctor.doctor_id
    )

    return excision_page_data


# --- Маршруты для управления подписями доктора ---
@router.post(
    "/signatures/create",
    response_model=DoctorSignatureResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_201_CREATED,
    summary="Создать новую подпись врача",
    tags=["Doctor Signatures"],
)
async def upload_doctor_signature(
    signature_scan_file: UploadFile = File(...),  # Файл обязателен
    signature_name: Optional[str] = Form(
        None
    ),  # Имя подписи опционально, как Form-поле
    is_default: bool = Form(False),  # Дефолтность, как Form-поле
    db: AsyncSession = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
) -> DoctorSignatureResponse:
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    return await create_doctor_signature(
        db=db,
        doctor_id=doctor.id,
        signature_name=signature_name,
        signature_scan_file=signature_scan_file,
        is_default=is_default,
        router=router,
    )


@router.get(
    "/signatures/all",
    response_model=List[DoctorSignatureResponse],
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Получить все подписи врача",
    tags=["Doctor Signatures"],
)
async def get_all_doctor_signatures(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
) -> List[DoctorSignatureResponse]:
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    return await get_doctor_signatures(db=db, doctor_id=doctor.id, router=router)


@router.put(
    "/signatures/{signature_id}/set-default",
    response_model=List[DoctorSignatureResponse],
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Установить подпись по умолчанию",
    tags=["Doctor Signatures"],
)
async def set_default_signature(
    signature_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
) -> List[DoctorSignatureResponse]:
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    return await set_default_doctor_signature(
        db=db, doctor_id=doctor.id, signature_id=signature_id, router=router
    )


@router.delete(
    "/signatures/{signature_id}/delete",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(doctor_access)],
    summary="Удалить подпись врача",
    tags=["Doctor Signatures"],
)
async def delete_signature(
    signature_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
):
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    return await delete_doctor_signature(
        db=db, doctor_id=doctor.id, signature_id=signature_id
    )


@router.get(
    "/patients/{patient_id}/report-page-data",
    response_model=PatientTestReportPageResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Получить все кейсы и данные заключения",
    tags=["DoctorPage"],
)
async def get_patient_report_full_page_data_route(
    patient_id: str,
    case_id=Query(None, description="Опциональный параметр case_id"),
    user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PatientTestReportPageResponse:
    """
    Этот маршрут возвращает список всех кейсов пациента, детали последнего кейса
    (включая его параметры и заключения) и все стекла последнего кейса
    для выбора для прикрепления к заключению. Если заключение для последнего кейса
    отсутствует, оно будет автоматически создано с пустыми полями.
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    return await case_service.get_patient_report_page_data(
        db=db,
        patient_id=patient_id,
        router=router,
        current_doctor_id=doctor.doctor_id,
        case_id=case_id,
    )


@router.get(
    "/cases/{case_id}/report",
    response_model=CaseIDReportPageResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Получить заключение конкретного кейса",
    tags=["DoctorPage"],
)
async def get_case_report_route(
    case_id: str,
    user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseIDReportPageResponse:
    """
    Этот маршрут возвращает подробности заключения для указанного кейса.
    Если заключение для этого кейса отсутствует, оно будет автоматически создано с пустыми полями.
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    return await case_service.get_report_by_case_id(
        db=db, case_id=case_id, router=router, current_doctor_id=doctor.doctor_id
    )


@router.put("/cases/{case_id}/report/upsert", response_model=ReportResponseSchema)
async def handle_report_and_diagnosis(
    case_id: str,
    update_data: ReportAndDiagnosisUpdateSchema = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
):
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    return await case_service.create_or_update_report_and_diagnosis(
        db=db,
        case_id=case_id,
        router=router,
        update_data=update_data,
        current_doctor_id=doctor.doctor_id,
    )


@router.post(
    "/diagnosis/{diagnosis_entry_id}/report/sign",
    response_model=ReportResponseSchema,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Подписать заключение",
    tags=["DoctorPage"],
)
async def add_signature_to_report_route(
    diagnosis_entry_id: str,
    request: SignReportRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
) -> ReportResponseSchema:
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    return await case_service.add_diagnosis_signature(
        db=db,
        diagnosis_entry_id=diagnosis_entry_id,
        doctor_id=doctor.doctor_id,
        doctor_signature_id=request.doctor_signature_id,
        router=router,
    )


@router.get(
    "/signatures/{signature_id}/attachment", dependencies=[Depends(doctor_access)]
)
async def get_signature_attachment(
    signature_id: str, db: AsyncSession = Depends(get_db)
):
    """
    **Получение содержимого прикрепленного файла**\n
    Позволяет получить бинарные данные (фото/PDF) прикрепленного файла по его ID.
    """
    attachment = await get_signature_data(db=db, signature_id=signature_id)
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found"
        )

    # Потоковая передача данных из базы данных
    async def file_data_stream():
        yield attachment.signature_scan_data

    return StreamingResponse(
        file_data_stream(), media_type=attachment.signature_scan_type
    )


@router.get(
    "/patients/{patient_id}/final-report-page-data",
    response_model=PatientFinalReportPageResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Получить все кесы и данные для финального репорта по последнему кейсу",
    tags=["DoctorPage"],
)
async def get_patient_final_report_full_page_data_route(
    patient_id: str,
    case_id=Query(None, description="Опциональный параметр case_id"),
    user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PatientFinalReportPageResponse:
    """
    Этот маршрут возвращает список всех кейсов пациента и данные для формирования финального заключения по последнему кейсу
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    return await case_service.get_patient_final_report_page_data(
        db=db,
        patient_id=patient_id,
        router=router,
        current_doctor_id=doctor.doctor_id,
        case_id=case_id,
    )


@router.get(
    "/cases/{case_id}/final-report",
    response_model=CaseFinalReportPageResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Получить данные для финального заключения конкретного кейса",
    tags=["DoctorPage"],
)
async def get_case_final_report_route(
    case_id: str,
    user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseFinalReportPageResponse:
    """
    Этот маршрут возвращает данные для финального заключения для указанного кейса
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    return await case_service.get_final_report_by_case_id(
        db=db, case_id=case_id, router=router, current_doctor_id=doctor.doctor_id
    )


# Текущие кейсы


@router.get(
    "/current_cases/report-page-data",
    response_model=PatientTestReportPageResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Получить все кейсы и данные заключения",
    tags=["Current Cases"],
)
async def get_current_cases_report_full_page_data_route(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
    case_id=Query(None, description="Опциональный параметр case_id"),
    skip: int = Query(0, description="Количество записей для пропуска"),
    limit: int = Query(10, description="Максимальное количество записей для возврата"),
) -> PatientTestReportPageResponse:
    """
    Этот маршрут возвращает список всех кейсов пациента, детали последнего кейса
    (включая его параметры и заключения) и все стекла последнего кейса
    для выбора для прикрепления к заключению. Если заключение для последнего кейса
    отсутствует, оно будет автоматически создано с пустыми полями.
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    return await case_service.get_current_cases_report_page_data(
        db=db,
        router=router,
        skip=skip,
        limit=limit,
        current_doctor_id=doctor.doctor_id,
        case_id=case_id,
    )


@router.get(
    "/current_cases/referral_page",
    response_model=PatientCasesWithReferralsResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Получение кейсов и вывод файлов направления по первому кейсу",
    tags=["Current Cases"],
)
async def get_current_cases_with_directions_for_doctor(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
    case_id=Query(None, description="Опциональный параметр case_id"),
    skip: int = Query(0, description="Количество записей для пропуска"),
    limit: int = Query(10, description="Максимальное количество записей для возврата"),
) -> PatientCasesWithReferralsResponse:
    """
    Возвращает список всех кейсов конкретного пациента, а также детали первого кейса, включая ссылку на файлы его направлений
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    patient_cases_data = await case_service.get_current_cases_with_directions(
        db=db,
        skip=skip,
        limit=limit,
        current_doctor_id=doctor.doctor_id,
        case_id=case_id,
    )
    if not patient_cases_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кейси пацієнта або направлення не знайдено.",
        )

    return patient_cases_data


@router.get(
    "/current_cases/excision-details",
    response_model=PatientExcisionPageResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Получение кейсов и нужных данных для страницы 'Вырезка'",
    tags=["Current Cases"],
)
async def get_patient_excision_page_data(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
    case_id=Query(None, description="Опциональный параметр case_id"),
    skip: int = Query(0, description="Количество записей для пропуска"),
    limit: int = Query(10, description="Максимальное количество записей для возврата"),
) -> PatientExcisionPageResponse:
    """
    Возвращает все кейсы и данные вырезки по последнему кейсу
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    excision_page_data = await case_service.get_current_case_details_for_excision_page(
        db=db,
        skip=skip,
        limit=limit,
        current_doctor_id=doctor.doctor_id,
        case_id=case_id,
    )

    return excision_page_data


@router.get(
    "/current_cases/glass-details",
    response_model=PatientGlassPageResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Получение кейсов и стёкол для страницы 'Текущие кейсы' (вкладка Стёкла)",
    tags=["Current Cases"],
)
async def get_current_cases_glass_page_data(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
    case_id=Query(None, description="Опциональный параметр case_id"),
    skip: int = Query(0, description="Количество записей для пропуска"),
    limit: int = Query(10, description="Максимальное количество записей для возврата"),
) -> PatientGlassPageResponse:
    """
    Возвращает список всех текущих кейсов и все стёкла первого кейса
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    glass_page_data = await case_service.get_current_cases_glass_details(
        db=db,
        skip=skip,
        limit=limit,
        current_doctor_id=doctor.doctor_id,
        router=router,
        case_id=case_id,
    )

    return glass_page_data


@router.get(
    "/current_cases/final-report-page-data",
    response_model=PatientFinalReportPageResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
    summary="Получить все кейсы и данные для финального репорта по последнему кейсу",
    tags=["Current Cases"],
)
async def get_current_cases_final_report_full_page_data_route(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
    case_id=Query(None, description="Опциональный параметр case_id"),
    skip: int = Query(0, description="Количество записей для пропуска"),
    limit: int = Query(10, description="Максимальное количество записей для возврата"),
) -> PatientFinalReportPageResponse:
    """
    Этот маршрут возвращает список всех кейсов пациента и данные для формирования финального заключения по последнему кейсу
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    return await case_service.get_current_cases_final_report_page_data(
        db=db,
        router=router,
        skip=skip,
        limit=limit,
        current_doctor_id=doctor.doctor_id,
        case_id=case_id,
    )


@router.put(
    "/cases/{case_id}/close",
    response_model=CaseCloseResponse,
    summary="Закрыть кейс",
    description="Закрывает кейс, устанавливая grossing_status в COMPLETED. Доступно только владельцу кейса при наличии всех необходимых подписей под диагнозами.",
    status_code=status.HTTP_200_OK,
)
async def close_case_endpoint(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
) -> CaseCloseResponse:
    """
    Эндпоинт для закрытия кейса.
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    return await case_service.close_case_service(
        db=db, case_id=case_id, current_doctor=doctor
    )



async def _get_and_return_case_details(db: AsyncSession, patient_id: str, case_id: str, doctor_id: str, router):
    case_details_response = await case_service.get_patient_case_details_for_glass_page(
        db=db,
        patient_id=patient_id,
        current_doctor_id=doctor_id,
        router=router,
        case_id=case_id,
    )
    if case_details_response is None:
        raise HTTPException(status_code=404, detail="Детали кейса не найдены по этому коду.")
    return UnifiedSearchResponse(data=SearchResultCaseDetails(**case_details_response.model_dump()))

async def _get_and_return_patient_overview(db: AsyncSession, patient_cor_id: str):
    patient_overview_response = await case_service.get_patient_first_case_details(
        db=db, patient_id=patient_cor_id
    )
    if patient_overview_response is None:
        raise HTTPException(status_code=404, detail="Обзор пациента не найден.")
    return UnifiedSearchResponse(data=SearchResultPatientOverview(**patient_overview_response))



@router.get(
    "/search",
    response_model=UnifiedSearchResponse,
    dependencies=[Depends(lab_assistant_or_doctor_access)],
    summary="Поиск пациента по ФИО или коду кейса",
    description="Поиск может выполняться по ФИО пациента или cor-id (возвращает get_patient_first_case_details) "
                "или по коду кейса / id кейса (возвращает get_patient_case_details_for_glass_page). "
)
async def unified_search(
    query: str = Query(..., min_length=2, description="ФИО / cor-id пациента или код / id кейса"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    doctor = await get_doctor(doctor_id=current_user.cor_id, db=db)
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    case_db = await case_service.get_single_case(db=db, case_id=query)
    if case_db:
        return await _get_and_return_case_details(db, str(case_db.patient_id), str(case_db.id), doctor.doctor_id, router)
    
    case_db_by_code = await case_service.get_single_case_by_case_code(db=db, case_code=query)
    if case_db_by_code:
        return await _get_and_return_case_details(db, str(case_db_by_code.patient_id), str(case_db_by_code.id), doctor.doctor_id, router)


    search_ngrams = generate_ngrams(query, n=2)
    search_ngrams.extend(generate_ngrams(query, n=3))
    search_ngrams_joined = " ".join(sorted(list(set(search_ngrams))))

    found_patient_by_cor_id = await get_single_patient_by_corid(db=db, cor_id=query)
    if found_patient_by_cor_id:
        return await _get_and_return_patient_overview(db, found_patient_by_cor_id.patient_cor_id)
    
    found_patient = await find_patient(db=db, search_ngrams_joined=search_ngrams_joined)
    if found_patient:
        return await _get_and_return_patient_overview(db, found_patient.patient_cor_id)
            
    raise HTTPException(status_code=404, detail="Patient or Case not found.")