from click import File
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.db import get_db
from cor_pass.database.models import User
from cor_pass.repository.lawyer import get_doctor
from cor_pass.repository.patient import get_patient_by_corid
from cor_pass.schemas import (
    CaseCreate,
    CaseDetailsResponse,
    CaseOwnershipResponse,
    CaseParametersScheema,
    DeleteCasesRequest,
    DeleteCasesResponse,
    GeneralPrinting,
    PatientFirstCaseDetailsResponse,
    ReferralAttachmentResponse,
    ReferralCreate,
    ReferralResponse,
    UpdateCaseCode,
    UpdateCaseCodeResponce,
)
from cor_pass.repository import case as case_service

from cor_pass.services.access import doctor_access
from cor_pass.services.auth import auth_service
from cor_pass.services.document_validation import validate_document_file

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post(
    "/create",
    dependencies=[Depends(doctor_access)],
    response_model=PatientFirstCaseDetailsResponse,
)
async def create_case(
    body: CaseCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Создает указанное количество кейсов и по 1 вложенной сущности
    """
    patient = await get_patient_by_corid(db=db, cor_id=body.patient_cor_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )
    case = await case_service.create_cases_with_initial_data(db=db, body=body)
    return case


@router.get(
    "/{case_id}",
    dependencies=[Depends(doctor_access)],
    response_model=CaseDetailsResponse,
)
async def read_case(case_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получаем конкретный кейс и вложенные в него сущности
    """
    db_case = await case_service.get_case(db, case_id)
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return db_case


@router.get(
    "/{case_id}/case_parameters",
    dependencies=[Depends(doctor_access)],
    response_model=CaseParametersScheema,
)
async def read_case_parameters(case_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получение параметров кейса
    """
    db_case_parameters = await case_service.get_case_parameters(db, case_id)
    if db_case_parameters is None:
        raise HTTPException(status_code=404, detail="Case parameters not found")
    return db_case_parameters


@router.patch(
    "/case_parameters",
    dependencies=[Depends(doctor_access)],
    response_model=CaseParametersScheema,
)
async def update_case_parameters(
    body: CaseParametersScheema,
    db: AsyncSession = Depends(get_db),
):
    """
    Обновляет параметры кейса
    """
    db_case_parameters = await case_service.update_case_parameters(
        db,
        body.case_id,
        body.macro_description,
        body.container_count_actual,
        body.urgency,
        body.material_type,
        body.macro_archive,
        body.decalcification,
        body.sample_type,
        body.fixation,
    )
    if db_case_parameters is None:
        raise HTTPException(status_code=404, detail="Case parameters not found")
    return db_case_parameters


@router.delete(
    "/delete",
    response_model=DeleteCasesResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
)
async def delete_cases(
    request_body: DeleteCasesRequest, db: AsyncSession = Depends(get_db)
):
    """
    Удаляет кейс и все вложенные в него сущности
    """
    result = await case_service.delete_cases(db=db, case_ids=request_body.case_ids)
    return result


@router.get(
    "/patients/{patient_cor_id}/overview",
    dependencies=[Depends(doctor_access)],
    response_model=PatientFirstCaseDetailsResponse,
)
async def read_patient_overview_details(
    patient_cor_id: str, db: AsyncSession = Depends(get_db)
):
    """
    Возвращает список всех кейсов пациента и детализацию первого из них:
    семплы, кассеты первого семпла и стекла этих кассет.
    """
    overview_data = await case_service.get_patient_first_case_details(
        db=db, patient_id=patient_cor_id
    )
    if overview_data is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return overview_data


@router.patch(
    "/case_code",
    dependencies=[Depends(doctor_access)],
    response_model=UpdateCaseCodeResponce,
)
async def update_case_code(
    body: UpdateCaseCode,
    db: AsyncSession = Depends(get_db),
):
    """Изменяет последние 5 символов кейса"""
    try:
        updated_case = await case_service.update_case_code_suffix(
            db=db, case_id=body.case_id, new_suffix=body.update_data
        )
        if updated_case:
            return updated_case
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Кейс з ID {body.case_id} не знайдено",
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/referrals/upsert",
    response_model=ReferralResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(doctor_access)],
)
async def upsert_referral_endpoint(
    referral_data: ReferralCreate, db: AsyncSession = Depends(get_db)
):
    """
    **Создание или обновление направления для кейса (Upsert)**\n
    Если для данного `case_id` направление уже существует, оно будет обновлено.
    В противном случае будет создано новое направление.
    """
    case = await case_service.get_single_case(db=db, case_id=referral_data.case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Associated Case not found"
        )
    db_referral = await case_service.upsert_referral(
        db=db, referral_data=referral_data, case=case
    )

    attachments_response = [
        ReferralAttachmentResponse(
            id=att.id,
            filename=att.filename,
            content_type=att.content_type,
            file_url=router.url_path_for(
                "get_referral_attachment", attachment_id=att.id
            ),
        )
        for att in db_referral.attachments
    ]

    # Создаем и возвращаем объект ReferralResponse
    referral_response_obj = ReferralResponse.model_validate(
        db_referral
    )  # ИЛИ .from_orm для Pydantic v1.x
    referral_response_obj.attachments = attachments_response

    return referral_response_obj


@router.get(
    "/referrals/{case_id}",
    response_model=ReferralResponse,
    dependencies=[Depends(doctor_access)],
)
async def get_single_referral(case_id: str, db: AsyncSession = Depends(get_db)):
    """
    **Получение информации о направлении по case_id**\n
    Возвращает полную информацию о направлении, включая ссылки на прикрепленные файлы.
    """
    referral = await case_service.get_referral_by_case(db=db, case_id=case_id)
    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Referral not found"
        )

    # Генерируем URL для каждого прикрепленного файла
    attachments_response = [
        ReferralAttachmentResponse(
            id=att.id,
            filename=att.filename,
            content_type=att.content_type,
            file_url=router.url_path_for(
                "get_referral_attachment", attachment_id=att.id
            ),
        )
        for att in referral.attachments
    ]

    referral_response_obj = ReferralResponse.model_validate(referral)

    referral_response_obj.attachments = attachments_response

    return referral_response_obj


@router.post(
    "/{referral_id}/attachments",
    response_model=ReferralAttachmentResponse,
    dependencies=[Depends(doctor_access)],
)
async def upload_referral_attachment(
    referral_id: str,
    file: UploadFile = Depends(validate_document_file),
    db: AsyncSession = Depends(get_db),
):
    """
    **Загрузка прикрепленного файла для направления**\n
    Позволяет загрузить до 5 файлов (PDF/изображения) к существующему направлению.
    """
    db_attachment = await case_service.upload_attachment(db, referral_id, file)
    return ReferralAttachmentResponse(
        id=db_attachment.id,
        filename=db_attachment.filename,
        content_type=db_attachment.content_type,
        file_url=router.url_path_for(
            "get_referral_attachment", attachment_id=db_attachment.id
        ),
    )


@router.get("/attachments/{attachment_id}", dependencies=[Depends(doctor_access)])
async def get_referral_attachment(
    attachment_id: str, db: AsyncSession = Depends(get_db)
):
    """
    **Получение содержимого прикрепленного файла**\n
    Позволяет получить бинарные данные (фото/PDF) прикрепленного файла по его ID.
    """
    attachment = await case_service.get_referral_attachment(db, attachment_id)
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found"
        )

    # Потоковая передача данных из базы данных
    async def file_data_stream():
        yield attachment.file_data

    return StreamingResponse(file_data_stream(), media_type=attachment.content_type)


@router.post(
    "/{case_id}/take", response_model=CaseOwnershipResponse, summary="Взять кейс себе"
)
async def take_case(
    case_id: str,
    user: User = Depends(auth_service.get_current_user),  # Получаем ID текущего доктора
    db: AsyncSession = Depends(get_db),
):
    """
    Позволяет авторизованному доктору взять на себя владение указанным кейсом.
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    try:
        response = await case_service.take_case_ownership(
            db=db, case_id=case_id, doctor_id=doctor.doctor_id
        )
        return response
    except HTTPException as e:
        raise e


@router.post(
    "/{case_id}/release",
    response_model=CaseOwnershipResponse,
    summary="Убрать кейс с себя",
)
async def release_case(
    case_id: str,
    user: User = Depends(auth_service.get_current_user),  # Получаем ID текущего доктора
    db: AsyncSession = Depends(get_db),
):
    """
    Позволяет авторизованному доктору отказаться от владения указанным кейсом.
    """
    doctor = await get_doctor(doctor_id=user.cor_id, db=db)
    try:
        response = await case_service.release_case_ownership(
            db=db, case_id=case_id, doctor_id=doctor.doctor_id
        )
        return response
    except HTTPException as e:
        raise e


@router.patch(
    "/{case_id}/print_glasses",
    dependencies=[Depends(doctor_access)],
    response_model=CaseDetailsResponse,
)
async def print_all_case_glasses(
    case_id: str, data: GeneralPrinting,
    request: Request, printing: bool = False, db: AsyncSession = Depends(get_db)
):
    """
    Печатает все стёкла кейса
    """
    db_case = await case_service.print_all_case_glasses(
        db=db, case_id=case_id, printing=printing, data=data, request=request
    )
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return db_case


@router.patch(
    "/{case_id}/print_cassettes",
    dependencies=[Depends(doctor_access)],
    response_model=CaseDetailsResponse,
)
async def print_all_case_cassettes(
    case_id: str, data: GeneralPrinting,
    request: Request, printing: bool = False, db: AsyncSession = Depends(get_db)
):
    """
    Печатает все кассеты кейса
    """
    db_case = await case_service.print_all_case_cassette(
        db=db, case_id=case_id, printing=printing, data=data, request=request
    )
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return db_case


@router.patch(
    "/{case_id}/print_qr",
    dependencies=[Depends(doctor_access)],
    response_model=CaseDetailsResponse,
)
async def print_case_qr(
    case_id: str, printing: bool = False, db: AsyncSession = Depends(get_db)
):
    """
    Печатает все кассеты кейса
    """
    db_case = await case_service.print_case_qr(
        db=db, case_id=case_id, printing=printing
    )
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return db_case
