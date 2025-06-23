import base64
import re
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import and_, distinct, func, literal_column, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from cor_pass.repository.patient import get_patient_by_corid
from cor_pass.schemas import (
    Case as CaseModelScheema,
    CaseFinalReportPageResponse,
    CaseIDReportPageResponse,
    CaseParametersScheema,
    CassetteForGlassPage,
    CassetteTestForGlassPage,
    DoctorResponseForSignature,
    FinalReportResponseSchema,
    FirstCaseTestGlassDetailsSchema,
    GlassTestModelScheema,
    PatientFinalReportPageResponse,
    PatientTestReportPageResponse,
    ReportCreateSchema,
    ReportResponseSchema,
    ReportSignatureSchema,
    ReportUpdateSchema,
    DoctorSignatureResponse,
    FirstCaseGlassDetailsSchema,
    LastCaseExcisionDetailsSchema,
    MicrodescriptionResponse,
    PathohistologicalConclusionResponse,
    PatientExcisionPageResponse,
    PatientGlassPageResponse,
    ReferralFileSchema,
    FirstCaseReferralDetailsSchema,
    PatientCasesWithReferralsResponse,
    ReferralCreate,
    Sample as SampleModelScheema,
    Cassette as CassetteModelScheema,
    Glass as GlassModelScheema,
    SampleForExcisionPage,
    SampleForGlassPage,
    SampleTestForGlassPage,
    SingleCaseExcisionPageResponse,
    SingleCaseGlassPageResponse,
    UpdateCaseCodeResponce,
    CaseCreate,
    UpdateMicrodescription,
    UpdatePathohistologicalConclusion,
)
from cor_pass.database import models as db_models
import uuid
from datetime import date, datetime
from cor_pass.services.cipher import decrypt_data
from cor_pass.services.logger import logger
from cor_pass.config.config import settings


async def generate_case_code(
    urgency_char: str, year_short: str, sample_type_char: str, next_number: int
) -> str:
    """Генератор коду кейса у форматі:
    1-й символ - срочність, 2-3 - рік, 4 - тип, 5-9 - порядковий номер.
    """
    formatted_number = f"{next_number:05d}"
    return f"{urgency_char}{year_short}{sample_type_char}{formatted_number}"


async def create_cases_with_initial_data(
    db: AsyncSession, body: CaseCreate
) -> Dict[str, Any]:
    """Асинхронно створює вказану кількість кейсів та пов'язані з ними початкові дані.
    Повертає список всіх створених кейсів та деталізацію першого з них.
    """
    created_cases_db: List[db_models.Case] = []
    now = datetime.now()
    year_short = now.strftime("%y")
    urgency_char = body.urgency.value[0].upper()
    material_type_char = body.material_type.value[0].upper()


    result = await db.execute(select(db_models.Case.case_code))
    all_existing_case_codes = result.scalars().all()

    max_sequential_number = 0
    for code in all_existing_case_codes:
        if len(code) == 9: 
            code_year_part = code[1:3] 
            
            if code_year_part == year_short: 
                try:
                    sequential_part = code[4:] 
                    sequential_number = int(sequential_part)
                    
                    if sequential_number > max_sequential_number:
                        max_sequential_number = sequential_number
                except ValueError:
                    continue
    
    next_number = max_sequential_number + 1

    for _ in range(body.num_cases):
        now = datetime.now()

        db_case = db_models.Case(
            id=str(uuid.uuid4()),
            patient_id=body.patient_cor_id,
            creation_date=now,
            bank_count=0,
            cassette_count=0,
            glass_count=0,
        )
        db_case.case_code = await generate_case_code(
            urgency_char, year_short, material_type_char, next_number
        )
        db.add(db_case)
        await db.commit()
        await db.refresh(db_case)
        next_number += 1


        db_sample = db_models.Sample(case_id=db_case.id, sample_number="A")
        db_case.bank_count += 1
        db.add(db_sample)
        await db.commit()
        await db.refresh(db_sample)
        await db.refresh(db_case)


        db_cassette = db_models.Cassette(
            sample_id=db_sample.id,
            cassette_number=f"{db_sample.sample_number}1",
            glass_count=0,
        )
        db.add(db_cassette)
        db_case.cassette_count += 1
        db_sample.cassette_count += 1
        await db.commit()
        await db.refresh(db_cassette)
        await db.refresh(db_case)
        await db.refresh(db_sample)


        db_glass = db_models.Glass(
            cassette_id=db_cassette.id,
            glass_number=0,
            staining=db_models.StainingType.HE,
        )
        db.add(db_glass)
        db_case.glass_count += 1
        db_sample.glass_count += 1
        db_cassette.glass_count += 1
        await db.commit()
        await db.refresh(db_glass)
        await db.refresh(db_case)
        await db.refresh(db_sample)
        await db.refresh(db_cassette)


        db_case_parameters = db_models.CaseParameters(
            case_id=db_case.id,
            urgency=body.urgency,
            material_type=body.material_type,
        )
        db.add(db_case_parameters)
        await db.commit()
        await db.refresh(db_case_parameters)
        await db.refresh(db_case)

        created_cases_db.append(db_case)

    all_cases = [
        CaseModelScheema.model_validate(case).model_dump() for case in created_cases_db
    ]
    first_case_details = None

    if created_cases_db:
        first_case_db = created_cases_db[0]


        samples_result = await db.execute(
            select(db_models.Sample)
            .where(db_models.Sample.case_id == first_case_db.id)
            .order_by(db_models.Sample.sample_number)
        )
        first_case_samples_db = samples_result.scalars().all()
        first_case_samples = []

        for i, sample_db in enumerate(first_case_samples_db):
            sample = SampleModelScheema.model_validate(sample_db).model_dump()
            sample["cassettes"] = []

            if i == 0 and sample_db:
                await db.refresh(sample_db, attribute_names=["cassette"])
                for cassette_db in sample_db.cassette:
                    await db.refresh(cassette_db, attribute_names=["glass"])
                    cassette = CassetteModelScheema.model_validate(
                        cassette_db
                    ).model_dump()
                    cassette["glasses"] = [
                        GlassModelScheema.model_validate(glass).model_dump()
                        for glass in cassette_db.glass
                    ]
                    sample["cassettes"].append(cassette)
            first_case_samples.append(sample)

        first_case_details = {
            "id": first_case_db.id,
            "case_code": first_case_db.case_code,
            "creation_date": first_case_db.creation_date,
            "samples": first_case_samples,
            "bank_count": first_case_db.bank_count,
            "cassette_count": first_case_db.cassette_count,
            "glass_count": first_case_db.glass_count,
            "grossing_status":first_case_db.grossing_status
        }

    return {"all_cases": all_cases, "first_case_details": first_case_details}


async def get_case(db: AsyncSession, case_id: str) -> Optional[Dict[str, Any]]:
    """Асинхронно получает информацию о кейсе по его ID, включая связанные банки и отсортированные кассеты первого семпла."""
    result = await db.execute(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    case_db = result.scalar_one_or_none()
    if not case_db:
        return None

    # 2. Получаем семплы первого кейса и связанные с ними кассеты и стекла с сортировкой
    samples_result = await db.execute(
        select(db_models.Sample)
        .where(db_models.Sample.case_id == case_db.id)
        .options(
            selectinload(db_models.Sample.cassette)
        )  # Предварительно загружаем кассеты
        .order_by(db_models.Sample.sample_number)
    )
    first_case_samples_db = samples_result.scalars().all()
    first_case_samples: List[Dict[str, Any]] = []

    for i, sample_db in enumerate(first_case_samples_db):
        sample = SampleModelScheema.model_validate(sample_db).model_dump()
        sample["cassettes"] = []

        # Если это первый семпл, загружаем связанные кассеты и стекла с сортировкой
        if i == 0 and sample_db:
            await db.refresh(sample_db, attribute_names=["cassette"])

            def sort_cassettes(cassette: db_models.Cassette):
                match = re.match(r"([A-Z]+)(\d+)", cassette.cassette_number)
                if match:
                    letter_part = match.group(1)
                    number_part = int(match.group(2))
                    return (letter_part, number_part)
                return (
                    cassette.cassette_number,
                    0,
                )  # Для случаев, если формат не совпадает

            sorted_cassettes_db = sorted(sample_db.cassette, key=sort_cassettes)

            for cassette_db in sorted_cassettes_db:
                await db.refresh(cassette_db, attribute_names=["glass"])
                cassette = CassetteModelScheema.model_validate(cassette_db).model_dump()
                cassette["glasses"] = sorted(
                    [
                        GlassModelScheema.model_validate(glass).model_dump()
                        for glass in cassette_db.glass
                    ],
                    key=lambda glass: glass["glass_number"],
                )
                sample["cassettes"].append(cassette)
        first_case_samples.append(sample)

    case_details = {
        "id": case_db.id,
        "case_code": case_db.case_code,
        "creation_date": case_db.creation_date,
        "bank_count": case_db.bank_count,
        "cassette_count": case_db.cassette_count,
        "glass_count": case_db.glass_count,
        "samples": first_case_samples,
        "grossing_status":case_db.grossing_status
    }

    return case_details


async def get_case_parameters(
    db: AsyncSession, case_id: str
) -> db_models.CaseParameters | None:
    """Асинхронно получает информацию о кейсе по его ID, включая связанные банки."""
    result = await db.execute(
        select(db_models.CaseParameters).where(
            db_models.CaseParameters.case_id == case_id
        )
    )
    case_db = result.scalar_one_or_none()
    if case_db:
        responce = CaseParametersScheema(
            case_id=case_db.case_id,
            macro_description=case_db.macro_description,
            container_count_actual=case_db.container_count_actual,
            urgency=case_db.urgency,
            material_type=case_db.material_type,
            macro_archive=case_db.macro_archive,
            decalcification=case_db.decalcification,
            sample_type=case_db.sample_type,
            fixation=case_db.fixation,
        )
        return responce
    else:
        return None


async def update_case_parameters(
    db: AsyncSession,
    case_id: str,
    macro_description: str,
    container_count_actual: int,
    urgency: db_models.UrgencyType, 
    material_type: db_models.SampleType, 
    macro_archive: db_models.MacroArchive = db_models.MacroArchive.ESS,
    decalcification: db_models.DecalcificationType = db_models.DecalcificationType.ABSENT,
    sample_type: db_models.SampleType = db_models.SampleType.NATIVE,
    fixation: db_models.FixationType = db_models.FixationType.NBF_10,
) -> CaseParametersScheema: 
    """
    Асинхронно обновляет параметры кейса.
    При смене urgency или material_type также обновляет соответствующий case_code.
    """
    result_params = await db.execute(
        select(db_models.CaseParameters).where(
            db_models.CaseParameters.case_id == case_id
        )
    )
    case_parameters_db = result_params.scalar_one_or_none()

    if not case_parameters_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Параметри для кейса з ID '{case_id}' не знайдено."
        )
    
    result_case = await db.execute(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    db_case = result_case.scalar_one_or_none()

    if not db_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Кейс з ID '{case_id}' не знайдено, неможливо оновити код."
        )

    old_urgency = case_parameters_db.urgency
    old_material_type = case_parameters_db.material_type

    case_parameters_db.macro_description = macro_description
    case_parameters_db.container_count_actual = container_count_actual
    case_parameters_db.urgency = urgency
    case_parameters_db.material_type = material_type
    case_parameters_db.macro_archive = macro_archive
    case_parameters_db.decalcification = decalcification
    case_parameters_db.sample_type = sample_type
    case_parameters_db.fixation = fixation

    if old_urgency != urgency or old_material_type != material_type:
        current_code = db_case.case_code

        if not current_code or len(current_code) != 9:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Некоректний формат коду кейса '{current_code}'. Оновлення неможливе."
            )
        year_part = current_code[1:3] 
        sequential_suffix = current_code[4:] 

        new_urgency_char = urgency.value[0].upper()
        new_material_type_char = material_type.value[0].upper()

        new_case_code = (
            f"{new_urgency_char}"
            f"{year_part}"
            f"{new_material_type_char}"
            f"{sequential_suffix}"
        )

        existing_codes_stmt = select(db_models.Case.case_code).where(
            db_models.Case.case_code == new_case_code, 
            db_models.Case.id != case_id 
        )
        existing_conflict = (await db.execute(existing_codes_stmt)).scalar_one_or_none()

        if existing_conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Новый код кейса '{new_case_code}' уже существует. "
                       "Измените порядковый номер для сохранения уникальности."
            )
        
        db_case.case_code = new_case_code
        db.add(db_case)

    db.add(case_parameters_db) 
    await db.commit()


    await db.refresh(case_parameters_db)
    if old_urgency != urgency or old_material_type != material_type:
        await db.refresh(db_case)

    responce = CaseParametersScheema(
        case_id=case_parameters_db.case_id,
        macro_description=case_parameters_db.macro_description,
        container_count_actual=case_parameters_db.container_count_actual,
        urgency=case_parameters_db.urgency,
        material_type=case_parameters_db.material_type,
        macro_archive=case_parameters_db.macro_archive,
        decalcification=case_parameters_db.decalcification,
        sample_type=case_parameters_db.sample_type,
        fixation=case_parameters_db.fixation,
    )
    return responce



async def get_single_case(db: AsyncSession, case_id: str) -> db_models.Case | None:
    """Асинхронно получает информацию о кейсе по его ID, включая связанные банки."""
    result = await db.execute(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    return result.scalar_one_or_none()


async def delete_cases(db: AsyncSession, case_ids: List[str]) -> Dict[str, Any]:
    """Асинхронно удаляет кейс."""
    deleted_count = 0
    not_found_ids: List[str] = []
    for case_id in case_ids:
        result = await db.execute(
            select(db_models.Case).where(db_models.Case.id == case_id)
        )
        db_case = result.scalar_one_or_none()

        if db_case:
            await db.delete(db_case)
            deleted_count += 1
            await db.commit()
        else:
            not_found_ids.append(case_id)

    response = {
        "deleted_count": deleted_count,
        "message": f"Успешно удалено {deleted_count} кейсов.",
    }
    if not_found_ids:
        response["message"] += f" Кейсы с ID {', '.join(not_found_ids)} не найдены."
    return response


async def get_patient_first_case_details(
    db: AsyncSession, patient_id: str
) -> Optional[Dict[str, Any]]:
    """
    Асинхронно получает список всех кейсов пациента и детализацию первого из них:
    все семплы первого кейса, но кассеты и стекла загружаются только для первого семпла.
    Использует model_validate и model_dump для работы с Pydantic моделями.
    """
    # 1. Получаем список всех кейсов пациента, отсортированных по дате создания
    cases_result = await db.execute(
        select(db_models.Case)
        .where(db_models.Case.patient_id == patient_id)
        .order_by(db_models.Case.creation_date.desc())
    )
    all_cases_db = cases_result.scalars().all()
    all_cases = [
        CaseModelScheema.model_validate(case).model_dump() for case in all_cases_db
    ]

    first_case_details = None
    if all_cases_db:
        first_case_db = all_cases_db[0]

        # 2. Получаем все семплы первого кейса, отсортированные по номеру
        samples_result = await db.execute(
            select(db_models.Sample)
            .where(db_models.Sample.case_id == first_case_db.id)
            .options(
                selectinload(db_models.Sample.cassette)
            )  # Предварительно загружаем кассеты
            .order_by(db_models.Sample.sample_number)
        )
        first_case_samples_db = samples_result.scalars().all()
        first_case_samples: List[Dict[str, Any]] = []

        for i, sample_db in enumerate(first_case_samples_db):
            sample = SampleModelScheema.model_validate(sample_db).model_dump()
            sample["cassettes"] = []

            # Если это первый семпл, загружаем связанные кассеты и стекла с сортировкой
            if i == 0 and sample_db:
                await db.refresh(sample_db, attribute_names=["cassette"])

                def sort_cassettes(cassette: db_models.Cassette):
                    match = re.match(r"([A-Z]+)(\d+)", cassette.cassette_number)
                    if match:
                        letter_part = match.group(1)
                        number_part = int(match.group(2))
                        return (letter_part, number_part)
                    return (
                        cassette.cassette_number,
                        0,
                    )  # Для случаев, если формат не совпадает

                sorted_cassettes_db = sorted(sample_db.cassette, key=sort_cassettes)

                for cassette_db in sorted_cassettes_db:
                    await db.refresh(cassette_db, attribute_names=["glass"])
                    cassette = CassetteModelScheema.model_validate(
                        cassette_db
                    ).model_dump()
                    cassette["glasses"] = sorted(
                        [
                            GlassModelScheema.model_validate(glass).model_dump()
                            for glass in cassette_db.glass
                        ],
                        key=lambda glass: glass["glass_number"],
                    )
                    sample["cassettes"].append(cassette)
            first_case_samples.append(sample)

        first_case_details = {
            "id": first_case_db.id,
            "case_code": first_case_db.case_code,
            "creation_date": first_case_db.creation_date,
            "grossing_status":first_case_db.grossing_status,
            "samples": first_case_samples,
        }

    return {"all_cases": all_cases, "first_case_details": first_case_details}


async def update_case_code_suffix(db: AsyncSession, case_id: str, new_suffix: str):
    """
    Асинхронно обновляет последние 5 символов кода кейса, с проверкой на уникальность нового порядкового номера в этом году.
    """
    if len(new_suffix) != 5 or not new_suffix.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Новый суффикс должен состоять из 5 цифровых символов."
        )

    result = await db.execute(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    db_case = result.scalar_one_or_none()

    if not db_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Кейс с ID '{case_id}' не найден."
        )

    current_code = db_case.case_code

    if len(current_code) < 9: 
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Текущий код кейса '{current_code}' слишком короткий."
        )

    current_year_short = current_code[1:3] 
    
    new_full_case_code = f"{current_code[:-5]}{new_suffix}"

    prefix_without_suffix = current_code[:-5]

    existing_codes_stmt = select(db_models.Case.case_code).where(
        db_models.Case.case_code.like(f"%{current_year_short}%"), 
        db_models.Case.id != case_id 
    )
    existing_case_codes_in_current_year = (await db.execute(existing_codes_stmt)).scalars().all()

    if new_full_case_code in existing_case_codes_in_current_year:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Код кейса '{new_full_case_code}' уже существует в текущем году. Выбирите другой номер."
        )
    
    db_case.case_code = new_full_case_code
    await db.commit()
    await db.refresh(db_case)
    
    return UpdateCaseCodeResponce.model_validate(db_case)



async def create_referral(db: AsyncSession, referral_in: ReferralCreate, case: db_models.Case) -> db_models.Referral:
    db_referral = db_models.Referral(
        case_id=referral_in.case_id,
        case_number=case.case_code,
        research_type=referral_in.research_type,
        container_count=referral_in.container_count,
        medical_card_number=referral_in.medical_card_number,
        clinical_data=referral_in.clinical_data,
        clinical_diagnosis=referral_in.clinical_diagnosis,
        medical_institution=referral_in.medical_institution,
        department=referral_in.department,
        attending_doctor=referral_in.attending_doctor,
        doctor_contacts=referral_in.doctor_contacts,
        medical_procedure=referral_in.medical_procedure,
        final_report_delivery=referral_in.final_report_delivery,
        issued_at=referral_in.issued_at,
    )
    db.add(db_referral)
    await db.commit()
    await db.refresh(db_referral)
    return db_referral

async def update_referral(db: AsyncSession, db_referral: db_models.Referral, referral_in: ReferralCreate) -> db_models.Referral:
        """
        Обновляет существующее направление в базе данных.
        """
        # Обновляем все поля из referral_in
        for field, value in referral_in.model_dump(exclude_unset=True).items(): # exclude_unset=True для частичного обновления (Pydantic v2)
        # Для Pydantic v1: referral_in.dict(exclude_unset=True).items()
            setattr(db_referral, field, value)
        
        await db.commit()
        await db.refresh(db_referral)
        return db_referral


async def upsert_referral(db: AsyncSession, referral_data: ReferralCreate, case: db_models.Case) -> db_models.Referral:
    """
    Обновляет направление, если оно существует для данного case_id, иначе создает новое.
    """
    existing_referral = await db.execute(
        select(db_models.Referral)
        .where(db_models.Referral.case_id == referral_data.case_id)
        .options(selectinload(db_models.Referral.attachments)) 
    )
    db_referral = existing_referral.scalars().first()

    if db_referral:
        print(f"Updating existing referral for case_id: {referral_data.case_id}")
        for field, value in referral_data.model_dump().items(): 
            setattr(db_referral, field, value)
        db_referral.case_number = case.case_code        
        await db.commit()
        await db.refresh(db_referral)
    else:
        print(f"Creating new referral for case_id: {referral_data.case_id}")
        db_referral = await create_referral(db=db, referral_in=referral_data, case=case)
    
    return db_referral

async def get_referral(db: AsyncSession, referral_id: str) -> Optional[db_models.Referral]:
    result = await db.execute(
        select(db_models.Referral).where(
            db_models.Referral.id == referral_id
        )
    )
    referral_db = result.scalars().unique().one_or_none()
    return referral_db


async def get_referral_by_case(db: AsyncSession, case_id: str) -> Optional[db_models.Referral]:
    result = await db.execute(
        select(db_models.Referral).where(
            db_models.Referral.case_id == case_id
        )
    )
    referral_db = result.scalars().unique().one_or_none()
    return referral_db




async def get_referral_attachment(db: AsyncSession, attachment_id: str) -> Optional[db_models.ReferralAttachment]:
    result = await db.execute(select(db_models.ReferralAttachment).where(db_models.ReferralAttachment.id == attachment_id))
    return result.scalar_one_or_none()


async def upload_attachment(db: AsyncSession, referral_id: str, file: UploadFile) -> db_models.ReferralAttachment:
    referral = await get_referral(db, referral_id)
    if not referral:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral not found")

    if len(referral.attachments) >= 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 5 attachments allowed per referral.")
    allowed_types = ["image/jpeg", "image/png", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Недопустимый тип файла. Разрешены только JPEG, PNG и PDF.",
        )

    file_data = await file.read()
    db_attachment = db_models.ReferralAttachment(
        referral_id=referral_id,
        filename=file.filename,
        content_type=file.content_type,
        file_data=file_data
    )
    db.add(db_attachment)
    await db.commit()
    await db.refresh(db_attachment)
    return db_attachment




def generate_file_url(file_id: str, case_id: str) -> str:
    """Генерирует URL для скачивания/просмотра файла направления."""
    return f"/cases/attachments/{file_id}"


async def get_patient_cases_with_directions(
    db: AsyncSession, patient_id: str
) -> PatientCasesWithReferralsResponse: # Указываем тип возвращаемого значения
    """
    Асинхронно получает список всех кейсов пациента и детализацию первого из них:
    все семплы первого кейса, но кассеты и стекла загружаются только для первого семпла.
    Включает ссылки на файлы направлений для первого кейса.
    """
    # 1. Получаем список всех кейсов пациента, отсортированных по дате создания
    cases_result = await db.execute(
        select(db_models.Case)
        .where(db_models.Case.patient_id == patient_id)
        .order_by(db_models.Case.creation_date.desc())
    )
    all_cases_db = cases_result.scalars().all()
    

    all_cases = [CaseModelScheema.model_validate(case).model_dump() for case in all_cases_db]

    first_case_direction_details: Optional[FirstCaseReferralDetailsSchema] = None

    if all_cases_db:
        first_case_db = all_cases_db[0]
        
        referral_db = await db.scalar(
            select(db_models.Referral).where(db_models.Referral.case_id == first_case_db.id)
        )

        if referral_db:
            direction_files_result = await db.execute(
                select(db_models.ReferralAttachment).where(
                    db_models.ReferralAttachment.referral_id == referral_db.id
                )
            )
            direction_files_db = direction_files_result.scalars().all()

            attachments_for_response = []
            for file_db in direction_files_db:
                file_url = generate_file_url(file_db.id, first_case_db.id)
                attachments_for_response.append(
                    ReferralFileSchema(
                        id=file_db.id,
                        file_name=file_db.filename,
                        file_type=file_db.content_type, 
                        file_url=file_url
                    )
                )
            
            first_case_direction_details = FirstCaseReferralDetailsSchema(
                id=first_case_db.id,
                case_code=first_case_db.case_code,
                creation_date=first_case_db.creation_date,
                pathohistological_conclusion=first_case_db.pathohistological_conclusion,
                microdescription=first_case_db.microdescription,
                attachments=attachments_for_response,
                grossing_status=first_case_db.grossing_status
            )

    return PatientCasesWithReferralsResponse(
        all_cases=all_cases,
        case_details=first_case_db,
        first_case_direction=first_case_direction_details
    )



async def get_patient_case_details_for_glass_page(
    db: AsyncSession, patient_id: str
) -> PatientGlassPageResponse: #
    """
    Асинхронно получает список всех кейсов пациента и полную детализацию (включая все стёкла)
    для первого кейса, отсортированного по дате создания.
    Используется для вкладки "Стёкла" на странице врача.
    """
    cases_result = await db.execute(
        select(db_models.Case)
        .where(db_models.Case.patient_id == patient_id)
        .order_by(db_models.Case.creation_date.desc())
    )
    all_cases_db = cases_result.scalars().all()
    
    all_cases_schematized = [
        CaseModelScheema.model_validate(case).model_dump() for case in all_cases_db
    ]

    first_case_details_for_glass: Optional[FirstCaseGlassDetailsSchema] = None

    if all_cases_db:
        first_case_db = all_cases_db[0]

        samples_result = await db.execute(
            select(db_models.Sample)
            .where(db_models.Sample.case_id == first_case_db.id)
            .options(
                selectinload(db_models.Sample.cassette).selectinload(db_models.Cassette.glass)
            ) 
            .order_by(db_models.Sample.sample_number)
        )
        first_case_samples_db = samples_result.scalars().all()


        first_case_samples_schematized: List[SampleForGlassPage] = []

        for sample_db in first_case_samples_db:

            def sort_cassettes(cassette: db_models.Cassette):
                match = re.match(r"([A-Z]+)(\d+)", cassette.cassette_number)
                if match:
                    letter_part = match.group(1)
                    number_part = int(match.group(2))
                    return (letter_part, number_part)
                return (cassette.cassette_number, 0) 


            sorted_cassettes_db = sorted(sample_db.cassette, key=sort_cassettes)
            
            cassettes_for_sample = []
            for cassette_db in sorted_cassettes_db:
                sorted_glasses_db = sorted(
                    cassette_db.glass,
                    key=lambda glass: glass.glass_number 
                )
                
                glasses_for_cassette = [
                    GlassModelScheema.model_validate(glass).model_dump()
                    for glass in sorted_glasses_db
                ]
                
                cassette_schematized = CassetteForGlassPage.model_validate(cassette_db).model_dump()
                cassette_schematized["glasses"] = glasses_for_cassette 
                cassettes_for_sample.append(cassette_schematized)

            sample_schematized = SampleForGlassPage.model_validate(sample_db).model_dump()
            sample_schematized["cassettes"] = cassettes_for_sample 
            first_case_samples_schematized.append(sample_schematized)


        first_case_details_for_glass = FirstCaseGlassDetailsSchema(
            id=first_case_db.id,
            case_code=first_case_db.case_code,
            creation_date=first_case_db.creation_date,
            pathohistological_conclusion=first_case_db.pathohistological_conclusion,
            microdescription=first_case_db.microdescription,
            samples=first_case_samples_schematized,
            grossing_status=first_case_db.grossing_status 
        )

    return PatientGlassPageResponse(
        all_cases=all_cases_schematized,
        first_case_details_for_glass=first_case_details_for_glass,
    )


async def get_current_cases_glass_details(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 10,
) -> PatientGlassPageResponse:
    """
    Получает список "текущих кейсов + стёкла" для страницы "Текущие кейсы" вкладка "Стёкла".

    Условия включения кейса:
    - Маркировка "F" или "U": grossing_status не "Завершено".
    - Маркировка "S": grossing_status не "Завершено" И есть хотя бы одно отсканированное стекло.

    Сортировка:
    - Сначала кейсы "F"/"U" (по creation_date DESC).
    - Затем кейсы "S" (по creation_date DESC).
    """

    cases_fu_subquery = (
        select(
            db_models.Case.id,
            db_models.Case.case_code,
            db_models.Case.creation_date,
            db_models.Case.patient_id,
            db_models.Case.grossing_status,
            db_models.Case.bank_count,     
            db_models.Case.cassette_count, 
            db_models.Case.glass_count,
            db_models.Case.pathohistological_conclusion,
            db_models.Case.microdescription,
            literal_column("1").label("sort_priority")
        )
        .where( 
            and_(
                func.substr(db_models.Case.case_code, 1, 1).in_(['F', 'U']),
                db_models.Case.grossing_status != db_models.Grossing_status.COMPLETED.value
            )
        )
    ).subquery("cases_fu")

    scanned_glass_exists_clause = (
        select(1)
        .select_from(db_models.Sample)
        .join(db_models.Cassette, db_models.Sample.id == db_models.Cassette.sample_id)
        .join(db_models.Glass, db_models.Cassette.id == db_models.Glass.cassette_id)
        .where(
            db_models.Sample.case_id == db_models.Case.id
        )
        .exists()
    )

    cases_s_subquery = (
        select(
            db_models.Case.id,
            db_models.Case.case_code,
            db_models.Case.creation_date,
            db_models.Case.patient_id,
            db_models.Case.grossing_status,
            db_models.Case.bank_count,    
            db_models.Case.cassette_count,
            db_models.Case.glass_count,
            db_models.Case.pathohistological_conclusion,
            db_models.Case.microdescription,
            literal_column("2").label("sort_priority")
        )
        .where( 
            and_(
                func.substr(db_models.Case.case_code, 1, 1) == 'S',

                db_models.Case.grossing_status != db_models.Grossing_status.COMPLETED.value,
                scanned_glass_exists_clause 
            )
        )
    ).subquery("cases_s")

    combined_query_for_data = (
        select(
            cases_fu_subquery.c.id,
            cases_fu_subquery.c.case_code,
            cases_fu_subquery.c.creation_date,
            cases_fu_subquery.c.patient_id,
            cases_fu_subquery.c.grossing_status,
            cases_fu_subquery.c.bank_count,    
            cases_fu_subquery.c.cassette_count, 
            cases_fu_subquery.c.glass_count,
            cases_fu_subquery.c.pathohistological_conclusion,
            cases_fu_subquery.c.microdescription,
            cases_fu_subquery.c.sort_priority
        )
        .union_all(
            select(
                cases_s_subquery.c.id,
                cases_s_subquery.c.case_code,
                cases_s_subquery.c.creation_date,
                cases_s_subquery.c.patient_id,
                cases_s_subquery.c.grossing_status,
                cases_s_subquery.c.bank_count,     
                cases_s_subquery.c.cassette_count, 
                cases_s_subquery.c.glass_count,
                cases_s_subquery.c.pathohistological_conclusion,
                cases_s_subquery.c.microdescription,
                cases_s_subquery.c.sort_priority
            )
        )
    )

    final_ordered_query = combined_query_for_data.order_by(
        combined_query_for_data.c.sort_priority.asc(),
        combined_query_for_data.c.creation_date.desc()
    )

    paginated_results = await db.execute(
        final_ordered_query.offset(skip).limit(limit)
    )
    all_current_cases_raw = paginated_results.all()

    current_cases_list: List[CaseModelScheema] = []
    first_case_details_for_glass: Optional[FirstCaseGlassDetailsSchema] = None

    for row in all_current_cases_raw:
        case_id = row.id
        case_code = row.case_code
        creation_date = row.creation_date
        patient_id = row.patient_id
        bank_count = row.bank_count
        cassette_count = row.cassette_count
        glass_count = row.glass_count
        grossing_status = db_models.Grossing_status(row.grossing_status)
        pathohistological_conclusion = row.pathohistological_conclusion
        microdescription = row.microdescription
        current_cases_list.append(
            CaseModelScheema(
                id=case_id,
                case_code=case_code,
                creation_date=creation_date,
                patient_id=patient_id,
                grossing_status=grossing_status,
                bank_count=bank_count,
                cassette_count=cassette_count,
                glass_count=glass_count,
                pathohistological_conclusion = pathohistological_conclusion,
                microdescription = microdescription
            )
        )

    # !!!Детали последнего кейса!!!
    if all_current_cases_raw:
        first_case_db = all_current_cases_raw[0]

        samples_result = await db.execute(
            select(db_models.Sample)
            .where(db_models.Sample.case_id == first_case_db.id)
            .options(
                selectinload(db_models.Sample.cassette).selectinload(db_models.Cassette.glass)
            )
            .order_by(db_models.Sample.sample_number)
        )
        first_case_samples_db = samples_result.scalars().all()

        first_case_samples_schematized: List[SampleForGlassPage] = []
        for sample_db in first_case_samples_db:

            def sort_cassettes(cassette: db_models.Cassette):
                match = re.match(r"([A-Z]+)(\d+)", cassette.cassette_number)
                if match:
                    letter_part = match.group(1)
                    number_part = int(match.group(2))
                    return (letter_part, number_part)
                return (cassette.cassette_number, 0)

            sorted_cassettes_db = sorted(sample_db.cassette, key=sort_cassettes)

            cassettes_for_sample = []
            for cassette_db in sorted_cassettes_db:
                sorted_glasses_db = sorted(
                    cassette_db.glass,
                    key=lambda glass: glass.glass_number
                )

                glasses_for_cassette = [
                    GlassModelScheema.model_validate(glass).model_dump()
                    for glass in sorted_glasses_db
                ]

                cassette_schematized = CassetteForGlassPage.model_validate(cassette_db).model_dump()
                cassette_schematized["glasses"] = glasses_for_cassette
                cassettes_for_sample.append(cassette_schematized)

            sample_schematized = SampleForGlassPage.model_validate(sample_db).model_dump()
            sample_schematized["cassettes"] = cassettes_for_sample
            first_case_samples_schematized.append(sample_schematized)

        first_case_details_for_glass = FirstCaseGlassDetailsSchema(
            id=first_case_db.id,
            case_code=first_case_db.case_code,
            creation_date=first_case_db.creation_date,
            pathohistological_conclusion=first_case_db.pathohistological_conclusion,
            microdescription=first_case_db.microdescription,
            samples=first_case_samples_schematized,
            grossing_status=first_case_db.grossing_status,
            patient_cor_id=first_case_db.patient_id
        )

    return PatientGlassPageResponse(
        all_cases=current_cases_list,
        first_case_details_for_glass=first_case_details_for_glass,
    )
       

async def get_single_case_details_for_glass_page(
    db: AsyncSession, case_id:str
) -> SingleCaseGlassPageResponse: 
    """
    Асинхронно получает список всех кейсов пациента и полную детализацию (включая все стёкла)
    для первого кейса, отсортированного по дате создания.
    Используется для вкладки "Стёкла" на странице врача.
    """
    result = await db.execute(
        select(db_models.Case)
        .where(db_models.Case.id == case_id)
    )
    case_db = result.scalar_one_or_none()
    if not case_db:
        return None
    
    first_case_details_for_glass: Optional[FirstCaseGlassDetailsSchema] = None

    if case_db:
        
        samples_result = await db.execute(
            select(db_models.Sample)
            .where(db_models.Sample.case_id == case_db.id)
            .options(
                selectinload(db_models.Sample.cassette).selectinload(db_models.Cassette.glass)
            ) 
            .order_by(db_models.Sample.sample_number)
        )
        first_case_samples_db = samples_result.scalars().all()


        first_case_samples_schematized: List[SampleForGlassPage] = []

        for sample_db in first_case_samples_db:

            def sort_cassettes(cassette: db_models.Cassette):
                match = re.match(r"([A-Z]+)(\d+)", cassette.cassette_number)
                if match:
                    letter_part = match.group(1)
                    number_part = int(match.group(2))
                    return (letter_part, number_part)
                return (cassette.cassette_number, 0) 


            sorted_cassettes_db = sorted(sample_db.cassette, key=sort_cassettes)
            
            cassettes_for_sample = []
            for cassette_db in sorted_cassettes_db:
                sorted_glasses_db = sorted(
                    cassette_db.glass,
                    key=lambda glass: glass.glass_number 
                )
                
                glasses_for_cassette = [
                    GlassModelScheema.model_validate(glass).model_dump()
                    for glass in sorted_glasses_db
                ]
                
                cassette_schematized = CassetteForGlassPage.model_validate(cassette_db).model_dump()
                cassette_schematized["glasses"] = glasses_for_cassette 
                cassettes_for_sample.append(cassette_schematized)

            sample_schematized = SampleForGlassPage.model_validate(sample_db).model_dump()
            sample_schematized["cassettes"] = cassettes_for_sample 
            first_case_samples_schematized.append(sample_schematized)


        first_case_details_for_glass = FirstCaseGlassDetailsSchema(
            id=case_db.id,
            case_code=case_db.case_code,
            creation_date=case_db.creation_date,
            samples=first_case_samples_schematized,
            grossing_status=case_db.grossing_status,
            patient_cor_id = case_db.patient_id
        )

    return SingleCaseGlassPageResponse(
        single_case_for_glass_page=first_case_details_for_glass,
    )








async def update_case_pathohistological_conclusion(db: AsyncSession, case_id: str, body: UpdatePathohistologicalConclusion) -> PathohistologicalConclusionResponse | None:
    """Асинхронно получает информацию о кейсе по его ID, включая связанные банки."""
    result = await db.execute(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    case_db = result.scalar_one_or_none()
    if case_db:
        case_db.pathohistological_conclusion = body.pathohistological_conclusion
        await db.commit()
        await db.refresh(case_db)
        response = PathohistologicalConclusionResponse(pathohistological_conclusion=body.pathohistological_conclusion)
        return response
    else:
        return None
    

async def update_case_microdescription(db: AsyncSession, case_id: str, body: UpdateMicrodescription) -> MicrodescriptionResponse | None:
    """Асинхронно получает информацию о кейсе по его ID, включая связанные банки."""
    result = await db.execute(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    case_db = result.scalar_one_or_none()
    if case_db:
        case_db.microdescription = body.microdescription
        await db.commit()
        await db.refresh(case_db)
        response = MicrodescriptionResponse(pathohistological_conclusion=body.microdescription)
        return response
    else:
        return None
    






async def get_patient_case_details_for_excision_page(
    db: AsyncSession, patient_id: str
) -> PatientExcisionPageResponse: #
    """
    Асинхронно получает список всех кейсов пациента и полную детализацию
    по последнему кейсу (параметры, макроописание, инфо по семплам).
    Используется для вкладки "Excision" (удаление/макроописание) на странице врача.
    """
    cases_result = await db.execute(
        select(db_models.Case)
        .where(db_models.Case.patient_id == patient_id)
        .order_by(db_models.Case.creation_date.desc()) 
    )
    all_cases_db = cases_result.scalars().all()
    

    all_cases_schematized = [
        CaseModelScheema.model_validate(case).model_dump() for case in all_cases_db
    ]

    last_case_details_for_excision: Optional[LastCaseExcisionDetailsSchema] = None

    if all_cases_db:
        last_case_db = all_cases_db[0] 
        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == last_case_db.id)
            .options(
                selectinload(db_models.Case.case_parameters), 
                selectinload(db_models.Case.samples) 
            )
        )
        last_case_with_relations = last_case_full_info_result.scalar_one_or_none()

        if last_case_with_relations:

            case_parameters_schematized: Optional[CaseParametersScheema] = None
            if last_case_with_relations.case_parameters:
                case_parameters_schematized = CaseParametersScheema.model_validate(
                    last_case_with_relations.case_parameters
                ).model_dump()
            

            samples_for_excision_page: List[SampleForExcisionPage] = []
            

            sorted_samples = sorted(
                last_case_with_relations.samples,
                key=lambda s: s.sample_number 
            )

            for sample_db in sorted_samples:

                samples_for_excision_page.append(
                    SampleForExcisionPage(
                        id=sample_db.id,
                        sample_number=sample_db.sample_number,
                        is_archived=sample_db.archive, 
                        macro_description=sample_db.macro_description 
                    )
                )


            last_case_details_for_excision = LastCaseExcisionDetailsSchema(
                id=last_case_db.id,
                case_code=last_case_db.case_code,
                creation_date=last_case_db.creation_date,
                pathohistological_conclusion=last_case_db.pathohistological_conclusion,
                microdescription=last_case_db.microdescription,
                case_parameters=case_parameters_schematized,
                samples=samples_for_excision_page,
                grossing_status=last_case_db.grossing_status
            )


    return PatientExcisionPageResponse(
        all_cases=all_cases_schematized,
        last_case_details_for_excision=last_case_details_for_excision,
    )





async def get_single_case_details_for_excision_page(
    db: AsyncSession, case_id:str
) -> SingleCaseExcisionPageResponse: 

    last_case_details_for_excision: Optional[LastCaseExcisionDetailsSchema] = None

    last_case_full_info_result = await db.execute(
        select(db_models.Case)
        .where(db_models.Case.id == case_id)
        .options(
            selectinload(db_models.Case.case_parameters), 
            selectinload(db_models.Case.samples) 
        )
    )
    last_case_with_relations = last_case_full_info_result.scalar_one_or_none()

    if last_case_with_relations:
        case_parameters_schematized: Optional[CaseParametersScheema] = None
        if last_case_with_relations.case_parameters:
            case_parameters_schematized = CaseParametersScheema.model_validate(
                last_case_with_relations.case_parameters
            ).model_dump()
        
        samples_for_excision_page: List[SampleForExcisionPage] = []
        
        sorted_samples = sorted(
            last_case_with_relations.samples,
            key=lambda s: s.sample_number 
        )

        for sample_db in sorted_samples:
            samples_for_excision_page.append(
                SampleForExcisionPage(
                    id=sample_db.id,
                    sample_number=sample_db.sample_number,
                    is_archived=sample_db.archive, 
                    macro_description=sample_db.macro_description 
                )
            )

        last_case_details_for_excision = LastCaseExcisionDetailsSchema(
            id=last_case_with_relations.id,
            case_code=last_case_with_relations.case_code,
            creation_date=last_case_with_relations.creation_date,
            pathohistological_conclusion=last_case_with_relations.pathohistological_conclusion,
            microdescription=last_case_with_relations.microdescription,
            case_parameters=case_parameters_schematized,
            samples=samples_for_excision_page,
            grossing_status=last_case_with_relations.grossing_status,
            patient_cor_id = last_case_with_relations.patient_id
        )

    return SingleCaseExcisionPageResponse(
        case_details_for_excision=last_case_details_for_excision,
    )

async def _format_report_response(
    db: AsyncSession, 
    db_report: db_models.Report,
    router: APIRouter,
    case_db: Optional[db_models.Case],
    db_case_parameters: Optional[db_models.CaseParameters]
) -> ReportResponseSchema:
    """Вспомогательная функция для форматирования объекта Report в ReportResponseSchema."""

    macro_desc_from_params = db_case_parameters.macro_description if db_case_parameters else None

    attached_glasses_schematized: List[GlassModelScheema] = []
    if db_report.attached_glass_ids:
        attached_glasses_db_result = await db.execute(
            select(db_models.Glass).where(db_models.Glass.id.in_(db_report.attached_glass_ids))
        )
        attached_glasses_db = attached_glasses_db_result.scalars().all()
        attached_glasses_schematized = []
        for g in attached_glasses_db:
            g = GlassModelScheema(
                glass_number=g.glass_number,
                staining=g.staining,
                id=g.id,
                cassette_id=g.cassette_id
            )
            attached_glasses_schematized.append(g)

    signatures_schematized: List[ReportSignatureSchema] = []
    await db.refresh(db_report, attribute_names=['signatures'])
    for signature_db in db_report.signatures:
        await db.refresh(signature_db, attribute_names=['doctor', 'doctor_signature']) 
        doctor_sig_type = None
        doctor_sig_response = None
        if signature_db.doctor_signature:
            if signature_db.doctor_signature.signature_scan_data:
                signature_data=router.url_path_for("get_signature_attachment", signature_id=signature_db.doctor_signature_id)
            doctor_sig_type = signature_db.doctor_signature.signature_scan_type
            doctor_sig_response = DoctorSignatureResponse(
                id=signature_db.doctor_signature.id,
                doctor_id=signature_db.doctor_signature.doctor_id,
                signature_name=signature_db.doctor_signature.signature_name,
                signature_scan_data=signature_data,
                signature_scan_type=doctor_sig_type,
                is_default=signature_db.doctor_signature.is_default,
                created_at=signature_db.doctor_signature.created_at
            )

        signatures_schematized.append(
            ReportSignatureSchema(
                id=signature_db.id,
                doctor=DoctorResponseForSignature.model_validate(signature_db.doctor),
                signed_at=signature_db.signed_at,
                doctor_signature=doctor_sig_response
            )
        )
    signatures_schematized.sort(key=lambda s: s.signed_at)

    return ReportResponseSchema(
        id=db_report.id,
        case_id=db_report.case_id,
        case_details=case_db,
        macro_description_from_case_params=macro_desc_from_params,
        microdescription_from_case=case_db.microdescription,
        immunohistochemical_profile=db_report.immunohistochemical_profile,
        molecular_genetic_profile=db_report.molecular_genetic_profile,
        pathomorphological_diagnosis=db_report.pathomorphological_diagnosis,
        icd_code=db_report.icd_code,
        comment=db_report.comment,
        signatures=signatures_schematized,
        attached_glasses=attached_glasses_schematized
    )


async def get_report_by_case_id(
    db: AsyncSession, case_id: str, router: APIRouter
) -> CaseIDReportPageResponse:
    """
    Получает заключение для конкретного кейса. Если заключения нет, оно будет создано.
    """
    case_db = await db.scalar(
        select(db_models.Case)
        .where(db_models.Case.id == case_id)
        .options(
            selectinload(db_models.Case.case_parameters),
            selectinload(db_models.Case.report).selectinload(db_models.Report.signatures).selectinload(db_models.ReportSignature.doctor),
            selectinload(db_models.Case.report).selectinload(db_models.Report.signatures).selectinload(db_models.ReportSignature.doctor_signature)
        )
    )
    if not case_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Кейс с ID '{case_id}' не найден.")

    if not case_db.report:
        new_report = db_models.Report(
            case_id=case_db.id,
        )
        db.add(new_report)
        await db.commit()
        await db.refresh(new_report)
        case_db.report = new_report 

    last_case_for_report: Optional[CaseModelScheema] = None
    report_details: Optional[ReportResponseSchema] = None
    all_samples_for_last_case_schematized: List[SampleTestForGlassPage] = []
    first_case_details_for_glass: Optional[FirstCaseTestGlassDetailsSchema] = None

    report_response =  await _format_report_response(db=db, db_report=case_db.report, db_case_parameters=case_db.case_parameters, router=router, case_db=case_db)
    last_case_db = case_db

    last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == last_case_db.id)
            .options(
                selectinload(db_models.Case.case_parameters),
                selectinload(db_models.Case.report).selectinload(db_models.Report.signatures).selectinload(db_models.ReportSignature.doctor),
                selectinload(db_models.Case.report).selectinload(db_models.Report.signatures).selectinload(db_models.ReportSignature.doctor_signature),
                selectinload(db_models.Case.samples).selectinload(db_models.Sample.cassette).selectinload(db_models.Cassette.glass)
            )
        )
    last_case_with_relations = last_case_full_info_result.scalar_one_or_none()


    if last_case_with_relations:
        last_case_for_report = CaseModelScheema.model_validate(last_case_with_relations)

        if not last_case_with_relations.report:
            new_report = db_models.Report(case_id=last_case_with_relations.id)
            db.add(new_report)
            await db.commit()
            await db.refresh(new_report)
            last_case_with_relations.report = new_report

        # report_details = await _format_report_response(db=db, db_report=last_case_with_relations.report, db_case_parameters=last_case_with_relations.case_parameters, router=router, case_db=last_case_db)

        for sample_db in last_case_with_relations.samples:
            def sort_cassettes(cassette: db_models.Cassette):
                match = re.match(r"([A-Z]+)(\d+)", cassette.cassette_number)
                if match:
                    letter_part = match.group(1)
                    number_part = int(match.group(2))
                    return (letter_part, number_part)
                return (cassette.cassette_number, 0)

            sorted_cassettes_db = sorted(sample_db.cassette, key=sort_cassettes)

            cassettes_for_sample: List[CassetteTestForGlassPage] = []
            for cassette_db in sorted_cassettes_db:
                sorted_glasses_db = sorted(
                    cassette_db.glass,
                    key=lambda glass: glass.glass_number
                )
                glasses_for_cassette: List[GlassTestModelScheema] = []
                for glass in sorted_glasses_db:
                    glass = GlassTestModelScheema(id=glass.id,
                                                    glass_number=glass.glass_number,
                                                    cassette_id=glass.cassette_id,
                                                    staining=glass.staining
                                                    )
                    glasses_for_cassette.append(glass)
                    
                cassette_schematized = CassetteTestForGlassPage(id=cassette_db.id,
                                                                cassette_number=cassette_db.cassette_number,
                                                                sample_id=cassette_db.sample_id
                                                                )
                cassette_schematized.glasses = glasses_for_cassette 
                cassettes_for_sample.append(cassette_schematized)

            sample_schematized = SampleTestForGlassPage(id=sample_db.id,
                                                        sample_number=sample_db.sample_number,
                                                        case_id=sample_db.case_id)
            sample_schematized.cassettes = cassettes_for_sample
            all_samples_for_last_case_schematized.append(sample_schematized)


        first_case_details_for_glass = FirstCaseTestGlassDetailsSchema(
            id=last_case_with_relations.id,
            case_code=last_case_with_relations.case_code,
            creation_date=last_case_with_relations.creation_date,
            samples=all_samples_for_last_case_schematized,
            grossing_status=last_case_with_relations.grossing_status 
        )

    general_response = CaseIDReportPageResponse(
        last_case_for_report = case_db,
        report_details = report_response,
        all_glasses_for_last_case= first_case_details_for_glass
    )
    return general_response


async def get_patient_report_page_data(
    db: AsyncSession, patient_id: str, router: APIRouter
) -> PatientTestReportPageResponse:
    """
    Получает данные для вкладки "Заключение" на странице врача:
    - Все кейсы пациента.
    - Детали последнего кейса: сам кейс (включая micro_description), его параметры (для macro_description),
      и его заключение (если есть). Если заключения нет, оно будет создано.
    - Все стёкла последнего кейса (для выбора, какие прикрепить).
    """
    cases_result = await db.execute(
        select(db_models.Case)
        .where(db_models.Case.patient_id == patient_id)
        .order_by(db_models.Case.creation_date.desc())
    )
    all_cases_db = cases_result.scalars().all()
    all_cases_schematized = [CaseModelScheema.model_validate(case) for case in all_cases_db]

    last_case_for_report: Optional[CaseModelScheema] = None
    report_details: Optional[ReportResponseSchema] = None
    all_samples_for_last_case_schematized: List[SampleTestForGlassPage] = []
    first_case_details_for_glass: Optional[FirstCaseTestGlassDetailsSchema] = None

    if all_cases_db:
        last_case_db = all_cases_db[0]

        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == last_case_db.id)
            .options(
                selectinload(db_models.Case.case_parameters),
                selectinload(db_models.Case.report).selectinload(db_models.Report.signatures).selectinload(db_models.ReportSignature.doctor),
                selectinload(db_models.Case.report).selectinload(db_models.Report.signatures).selectinload(db_models.ReportSignature.doctor_signature),
                selectinload(db_models.Case.samples).selectinload(db_models.Sample.cassette).selectinload(db_models.Cassette.glass)
            )
        )
        last_case_with_relations = last_case_full_info_result.scalar_one_or_none()

        if last_case_with_relations:
            last_case_for_report = CaseModelScheema.model_validate(last_case_with_relations)

            if not last_case_with_relations.report:
                new_report = db_models.Report(case_id=last_case_with_relations.id)
                db.add(new_report)
                await db.commit()
                await db.refresh(new_report)
                last_case_with_relations.report = new_report

            report_details = await _format_report_response(db=db, db_report=last_case_with_relations.report, db_case_parameters=last_case_with_relations.case_parameters, router=router, case_db=last_case_db)

            for sample_db in last_case_with_relations.samples:
                def sort_cassettes(cassette: db_models.Cassette):
                    match = re.match(r"([A-Z]+)(\d+)", cassette.cassette_number)
                    if match:
                        letter_part = match.group(1)
                        number_part = int(match.group(2))
                        return (letter_part, number_part)
                    return (cassette.cassette_number, 0)

                sorted_cassettes_db = sorted(sample_db.cassette, key=sort_cassettes)

                cassettes_for_sample: List[CassetteTestForGlassPage] = []
                for cassette_db in sorted_cassettes_db:
                    sorted_glasses_db = sorted(
                        cassette_db.glass,
                        key=lambda glass: glass.glass_number
                    )
                    glasses_for_cassette: List[GlassTestModelScheema] = []
                    for glass in sorted_glasses_db:
                        glass = GlassTestModelScheema(id=glass.id,
                                                      glass_number=glass.glass_number,
                                                      cassette_id=glass.cassette_id,
                                                      staining=glass.staining
                                                      )
                        glasses_for_cassette.append(glass)
                        
                    cassette_schematized = CassetteTestForGlassPage(id=cassette_db.id,
                                                                    cassette_number=cassette_db.cassette_number,
                                                                    sample_id=cassette_db.sample_id
                                                                    )
                    cassette_schematized.glasses = glasses_for_cassette 
                    cassettes_for_sample.append(cassette_schematized)

                sample_schematized = SampleTestForGlassPage(id=sample_db.id,
                                                            sample_number=sample_db.sample_number,
                                                            case_id=sample_db.case_id)
                sample_schematized.cassettes = cassettes_for_sample
                all_samples_for_last_case_schematized.append(sample_schematized)


            first_case_details_for_glass = FirstCaseTestGlassDetailsSchema(
                id=last_case_with_relations.id,
                case_code=last_case_with_relations.case_code,
                creation_date=last_case_with_relations.creation_date,
                samples=all_samples_for_last_case_schematized,
                grossing_status=last_case_with_relations.grossing_status 
            )

    return PatientTestReportPageResponse(
        all_cases=all_cases_schematized,
        last_case_for_report=last_case_for_report,
        report_details=report_details,
        all_glasses_for_last_case=first_case_details_for_glass 
    )


async def create_or_update_report(
    db: AsyncSession, case_id: str, router: APIRouter, report_data: Union[ReportCreateSchema, ReportUpdateSchema]
) -> ReportResponseSchema:
    """
    Создает новое заключение для кейса или обновляет существующее.
    """
    case_db = await db.scalar(
        select(db_models.Case)
        .where(db_models.Case.id == case_id)
        .options(selectinload(db_models.Case.case_parameters)),
    )
    if not case_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Кейс з ID '{case_id}' не знайдено.")

    result = await db.execute(
        select(db_models.Report)
        .where(db_models.Report.case_id == case_id)
        .options(
            selectinload(db_models.Report.signatures)
            .selectinload(db_models.ReportSignature.doctor),
            selectinload(db_models.Report.signatures)
            .selectinload(db_models.ReportSignature.doctor_signature)
        )
    )
    db_report = result.scalar_one_or_none()

    if db_report:
        for field, value in report_data.model_dump(exclude_unset=True).items():
            if field == "attached_glass_ids":
                db_report.attached_glass_ids = value if value is not None else []
            else:
                setattr(db_report, field, value)
    else:
        report_dict = report_data.model_dump()
        report_dict['case_id'] = case_id
        if 'attached_glass_ids' not in report_dict or report_dict['attached_glass_ids'] is None:
            report_dict['attached_glass_ids'] = []
            
        db_report = db_models.Report(**report_dict)
        db.add(db_report)

    await db.commit()
    await db.refresh(db_report)

    # patient_db = await get_patient_by_corid(db=db, cor_id=case_db.patient_id)
    # referral_db = await get_referral_by_case(db=db, case_id=case_db.id)
    return await _format_report_response(db=db, db_report=db_report, db_case_parameters=case_db.case_parameters, router=router, case_db=case_db)


async def add_report_signature(
    db: AsyncSession, case_id: str, doctor_id: str, router: APIRouter, doctor_signature_id: Optional[str] = None
) -> ReportResponseSchema:
    """
    Добавляет подпись доктора к заключению кейса, используя существующую подпись доктора.
    Если doctor_signature_id не предоставлен, попытается использовать подпись доктора по умолчанию.
    """
    report_result = await db.execute(
        select(db_models.Report)
        .where(db_models.Report.case_id == case_id)
        .options(
            selectinload(db_models.Report.signatures)
            .selectinload(db_models.ReportSignature.doctor),
            selectinload(db_models.Report.signatures)
            .selectinload(db_models.ReportSignature.doctor_signature) 
        )
    )
    db_report = report_result.scalar_one_or_none()

    if not db_report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Заключение для кейса '{case_id}' не найдено.")

    target_doctor_signature: Optional[db_models.DoctorSignature] = None
    if doctor_signature_id:
        target_doctor_signature = await db.scalar(
            select(db_models.DoctorSignature)
            .where(db_models.DoctorSignature.id == doctor_signature_id, db_models.DoctorSignature.doctor_id == doctor_id)
        )
        if not target_doctor_signature:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Указанная подпись врача не найдена или принадлежит другому врачу.")
    else:
        target_doctor_signature = await db.scalar(
            select(db_models.DoctorSignature)
            .where(db_models.DoctorSignature.doctor_id == doctor_id, db_models.DoctorSignature.is_default == True)
        )
        if not target_doctor_signature:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не найдена подпись по умолчанию для этого врача. Укажите ID подписи или загрузите подпись по умолчанию.")

    existing_signature_by_doctor = await db.scalar(
        select(db_models.ReportSignature)
        .where(
            db_models.ReportSignature.report_id == db_report.id,
            db_models.ReportSignature.doctor_id == doctor_id,
            db_models.ReportSignature.doctor_signature_id == target_doctor_signature.id
        )
    )
    if existing_signature_by_doctor:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Этот врач уже подписал данное заключение с использованием этой подписи.")

    new_signature = db_models.ReportSignature(
        report_id=db_report.id,
        doctor_id=doctor_id,
        doctor_signature_id=target_doctor_signature.id, 
        signed_at=func.now()
    )
    db.add(new_signature)
    
    await db.commit()
    await db.refresh(new_signature)
    await db.refresh(db_report) 

    case_db = await db.scalar(
        select(db_models.Case)
        .where(db_models.Case.id == case_id)
        .options(selectinload(db_models.Case.case_parameters))
    )
    case_db.grossing_status = db_models.Grossing_status.COMPLETED
    await db.commit()
    await db.refresh(case_db)
    macro_desc_from_params = case_db.case_parameters.macro_description if case_db.case_parameters else None

    attached_glasses_schematized: List[GlassModelScheema] = []
    if db_report.attached_glass_ids:
        attached_glasses_db_result = await db.execute(
            select(db_models.Glass).where(db_models.Glass.id.in_(db_report.attached_glass_ids))
        )
        attached_glasses_db = attached_glasses_db_result.scalars().all()
        attached_glasses_schematized = [GlassModelScheema.model_validate(g).model_dump() for g in attached_glasses_db]

    signatures_schematized: List[ReportSignatureSchema] = []
    await db.refresh(db_report, attribute_names=['signatures']) 
    for signature_db in db_report.signatures: 
        await db.refresh(signature_db, attribute_names=['doctor', 'doctor_signature'])
        doctor_sig_type = None
        doctor_sig_response = None
        if signature_db.doctor_signature:
            if signature_db.doctor_signature.signature_scan_data:
                signature_data=router.url_path_for("get_signature_attachment", signature_id=new_signature.doctor_signature_id)
            doctor_sig_type = signature_db.doctor_signature.signature_scan_type
            doctor_sig_response = DoctorSignatureResponse(
                id=signature_db.doctor_signature.id,
                doctor_id=signature_db.doctor_signature.doctor_id,
                signature_name=signature_db.doctor_signature.signature_name,
                signature_scan_data=signature_data,
                signature_scan_type=doctor_sig_type,
                is_default=signature_db.doctor_signature.is_default,
                created_at=signature_db.doctor_signature.created_at
            )

        signatures_schematized.append(
            ReportSignatureSchema(
                id=signature_db.id,
                doctor=DoctorResponseForSignature.model_validate(signature_db.doctor).model_dump(),
                signed_at=signature_db.signed_at,
                doctor_signature=doctor_sig_response
            )
        )
    signatures_schematized.sort(key=lambda s: s.signed_at)

    return ReportResponseSchema(
        id=db_report.id,
        case_id=db_report.case_id,
        case_details=case_db,
        macro_description_from_case_params=macro_desc_from_params,
        immunohistochemical_profile=db_report.immunohistochemical_profile,
        molecular_genetic_profile=db_report.molecular_genetic_profile,
        pathomorphological_diagnosis=db_report.pathomorphological_diagnosis,
        icd_code=db_report.icd_code,
        comment=db_report.comment,
        signatures=signatures_schematized,
        attached_glasses=attached_glasses_schematized
    )






async def get_patient_final_report_page_data(
    db: AsyncSession, patient_id: str, router: APIRouter
) -> PatientFinalReportPageResponse:
    """
    Получает данные для вкладки "Заключение" на странице врача:
    - Все кейсы пациента.
    - Детали последнего кейса: сам кейс (включая micro_description), его параметры (для macro_description),
      и его заключение (если есть). Если заключения нет, оно будет создано.
    - Все стёкла последнего кейса (для выбора, какие прикрепить).
    """
    cases_result = await db.execute(
        select(db_models.Case)
        .where(db_models.Case.patient_id == patient_id)
        .order_by(db_models.Case.creation_date.desc())
    )
    all_cases_db = cases_result.scalars().all()
    all_cases_schematized = [CaseModelScheema.model_validate(case) for case in all_cases_db]

    report_details: Optional[ReportResponseSchema] = None
    all_samples_for_last_case_schematized: List[SampleTestForGlassPage] = []
    last_case_details = None


    if all_cases_db:
        last_case_db = all_cases_db[0]
        last_case_details = CaseModelScheema.model_validate(last_case_db)

        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == last_case_db.id)
            .options(
                selectinload(db_models.Case.case_parameters),
                selectinload(db_models.Case.report).selectinload(db_models.Report.signatures).selectinload(db_models.ReportSignature.doctor),
                selectinload(db_models.Case.report).selectinload(db_models.Report.signatures).selectinload(db_models.ReportSignature.doctor_signature),
                selectinload(db_models.Case.samples).selectinload(db_models.Sample.cassette).selectinload(db_models.Cassette.glass)
            )
        )
        last_case_with_relations = last_case_full_info_result.scalar_one_or_none()

        if last_case_with_relations:
            if not last_case_with_relations.report:
                new_report = db_models.Report(case_id=last_case_with_relations.id)
                db.add(new_report)
                await db.commit()
                await db.refresh(new_report)
                last_case_with_relations.report = new_report

            patient_db = await get_patient_by_corid(db=db, cor_id=last_case_db.patient_id)
            referral_db = await get_referral_by_case(db=db, case_id=last_case_db.id)
            report_details = await _format_final_report_response(db=db, db_report=last_case_with_relations.report, db_case_parameters=last_case_with_relations.case_parameters, router=router, patient_db=patient_db, referral_db=referral_db, case_db=last_case_with_relations)

            for sample_db in last_case_with_relations.samples:
                def sort_cassettes(cassette: db_models.Cassette):
                    match = re.match(r"([A-Z]+)(\d+)", cassette.cassette_number)
                    if match:
                        letter_part = match.group(1)
                        number_part = int(match.group(2))
                        return (letter_part, number_part)
                    return (cassette.cassette_number, 0)

                sorted_cassettes_db = sorted(sample_db.cassette, key=sort_cassettes)

                cassettes_for_sample: List[CassetteTestForGlassPage] = []
                for cassette_db in sorted_cassettes_db:
                    sorted_glasses_db = sorted(
                        cassette_db.glass,
                        key=lambda glass: glass.glass_number
                    )
                    glasses_for_cassette: List[GlassTestModelScheema] = []
                    for glass in sorted_glasses_db:
                        glass = GlassTestModelScheema(id=glass.id,
                                                      glass_number=glass.glass_number,
                                                      cassette_id=glass.cassette_id
                                                      )
                        glasses_for_cassette.append(glass)
                        
                    cassette_schematized = CassetteTestForGlassPage(id=cassette_db.id,
                                                                    cassette_number=cassette_db.cassette_number,
                                                                    sample_id=cassette_db.sample_id
                                                                    )
                    cassette_schematized.glasses = glasses_for_cassette 
                    cassettes_for_sample.append(cassette_schematized)

                sample_schematized = SampleTestForGlassPage(id=sample_db.id,
                                                            sample_number=sample_db.sample_number,
                                                            case_id=sample_db.case_id)
                sample_schematized.cassettes = cassettes_for_sample
                all_samples_for_last_case_schematized.append(sample_schematized)


    return PatientFinalReportPageResponse(
        all_cases=all_cases_schematized,
        last_case_details=last_case_details,
        report_details=report_details
    )




async def _format_final_report_response(
    db: AsyncSession, 
    db_report: db_models.Report,
    case_db: db_models.Case,
    patient_db: db_models.Patient,
    referral_db: db_models.Referral,
    router: APIRouter,
    db_case_parameters: Optional[db_models.CaseParameters]
) -> FinalReportResponseSchema:
    """Вспомогательная функция для форматирования объекта Report в ReportResponseSchema."""

    try:
        decoded_key = base64.b64decode(settings.aes_key)
        patient_surname = await decrypt_data(patient_db.encrypted_surname, decoded_key)if patient_db.encrypted_surname else None
        patient_first_name = await decrypt_data(patient_db.encrypted_first_name, decoded_key)if patient_db.encrypted_first_name else None
        patient_middle_name = await decrypt_data(patient_db.encrypted_middle_name, decoded_key)if patient_db.encrypted_middle_name else None
    except Exception as e:
        print(e)
    user_birth_year = patient_db.birth_date
    if user_birth_year is None and patient_db.patient_cor_id:
        cor_id_parts = patient_db.patient_cor_id.split('-')
        if len(cor_id_parts) > 1:
            year_part = cor_id_parts[1]
            numbers = re.findall(r'\d+', year_part)
            if numbers:
                try:
                    user_birth_year = (numbers[0])
                except ValueError:
                    user_birth_year = None

    patient_age: Optional[int] = None
    if patient_db.birth_date:
        today = date.today()
        patient_age = today.year - patient_db.birth_date.year - \
                        ((today.month, today.day) < (patient_db.birth_date.month, patient_db.birth_date.day))




    # Прикрепление стёкол
    attached_glasses_schematized: List[GlassModelScheema] = []
    glass_stainings = []
    if db_report.attached_glass_ids:
        attached_glasses_db_result = await db.execute(
            select(db_models.Glass).where(db_models.Glass.id.in_(db_report.attached_glass_ids))
        )
        attached_glasses_db = attached_glasses_db_result.scalars().all()
        attached_glasses_schematized = []
        for g in attached_glasses_db:
            g = GlassModelScheema(
                glass_number=g.glass_number,
                staining=g.staining,
                id=g.id,
                cassette_id=g.cassette_id
            )
            glass_stainings.append(g.staining)
            attached_glasses_schematized.append(g)

    # Прикрепление подписей
    glass_stainings = set(glass_stainings)
    signatures_schematized: List[ReportSignatureSchema] = []
    await db.refresh(db_report, attribute_names=['signatures'])
    for signature_db in db_report.signatures:
        await db.refresh(signature_db, attribute_names=['doctor', 'doctor_signature']) 
        doctor_sig_type = None
        doctor_sig_response = None
        if signature_db.doctor_signature:
            if signature_db.doctor_signature.signature_scan_data:
                signature_data=router.url_path_for("get_signature_attachment", signature_id=signature_db.doctor_signature_id)
            doctor_sig_type = signature_db.doctor_signature.signature_scan_type
            doctor_sig_response = DoctorSignatureResponse(
                id=signature_db.doctor_signature.id,
                doctor_id=signature_db.doctor_signature.doctor_id,
                signature_name=signature_db.doctor_signature.signature_name,
                signature_scan_data=signature_data,
                signature_scan_type=doctor_sig_type,
                is_default=signature_db.doctor_signature.is_default,
                created_at=signature_db.doctor_signature.created_at
            )

        signatures_schematized.append(
            ReportSignatureSchema(
                id=signature_db.id,
                doctor=DoctorResponseForSignature.model_validate(signature_db.doctor),
                signed_at=signature_db.signed_at,
                doctor_signature=doctor_sig_response
            )
        )
    signatures_schematized.sort(key=lambda s: s.signed_at)

    return FinalReportResponseSchema(
        id=db_report.id,
        case_id=case_db.id,
        case_code=case_db.case_code,

        biopsy_date=case_db.creation_date.date(),
        arrival_date=referral_db.issued_at if referral_db else None,

        report_date=signature_db.doctor_signature.created_at.date() if db_report.signatures else None,
        
        patient_cor_id=patient_db.patient_cor_id,
        patient_first_name=patient_first_name,
        patient_surname=patient_surname,
        patient_middle_name=patient_middle_name,
        patient_sex=patient_db.sex,
        patient_birth_date=patient_db.birth_date,
        patient_full_age=patient_age,
        patient_phone_number=patient_db.phone_number,
        patient_email=patient_db.email,

        medical_card_number=referral_db.medical_card_number if referral_db else None,
        medical_institution=referral_db.medical_institution if referral_db else None,
        medical_department=referral_db.department if referral_db else None,
        attending_doctor=referral_db.attending_doctor if referral_db else None,
        clinical_data=referral_db.clinical_data if referral_db else None,
        clinical_diagnosis=referral_db.clinical_diagnosis if referral_db else None,

        painting=glass_stainings,


        macroarchive=db_case_parameters.macro_archive,
        decalcification=db_case_parameters.decalcification,
        fixation=db_case_parameters.fixation,
        num_blocks=case_db.cassette_count,

        containers_recieved=case_db.bank_count,

        containers_actual=db_case_parameters.container_count_actual,
        macrodescription=db_case_parameters.macro_description,

        microdescription=case_db.microdescription,

        pathomorphological_diagnosis=db_report.pathomorphological_diagnosis,
        immunohistochemical_profile=db_report.immunohistochemical_profile,
        molecular_genetic_profile=db_report.molecular_genetic_profile,
        comment=db_report.comment,
        icd_code=db_report.icd_code,
        signatures=signatures_schematized,
        attached_glasses=attached_glasses_schematized
    )


async def get_final_report_by_case_id(
    db: AsyncSession, case_id: str, router: APIRouter
) -> CaseFinalReportPageResponse:
    """
    Получает заключение для конкретного кейса. Если заключения нет, оно будет создано.
    """
    case_db = await db.scalar(
        select(db_models.Case)
        .where(db_models.Case.id == case_id)
        .options(
            selectinload(db_models.Case.case_parameters),
            selectinload(db_models.Case.report).selectinload(db_models.Report.signatures).selectinload(db_models.ReportSignature.doctor),
            selectinload(db_models.Case.report).selectinload(db_models.Report.signatures).selectinload(db_models.ReportSignature.doctor_signature)
        )
    )
    if not case_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Кейс с ID '{case_id}' не найден.")
    
    
    case_schematized = CaseModelScheema.model_validate(case_db)

    if not case_db.report:
        new_report = db_models.Report(
            case_id=case_db.id,
        )
        db.add(new_report)
        await db.commit()
        await db.refresh(new_report)
        case_db.report = new_report 


    patient_db = await get_patient_by_corid(db=db, cor_id=case_db.patient_id)

    referral_db = await get_referral_by_case(db=db, case_id=case_db.id)

    report_details =  await _format_final_report_response(db=db, db_report=case_db.report, db_case_parameters=case_db.case_parameters, router=router, patient_db=patient_db, referral_db=referral_db, case_db=case_db)
    return CaseFinalReportPageResponse(
        case_details=case_schematized,
        report_details=report_details,
    )

async def get_current_case_details_for_excision_page(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 10,
) -> PatientExcisionPageResponse: #
    """
    Асинхронно получает список всех кейсов пациента и полную детализацию
    по последнему кейсу (параметры, макроописание, инфо по семплам).
    Используется для вкладки "Excision" (удаление/макроописание) на странице врача.
    """
    cases_fu_subquery = (
        select(
            db_models.Case.id,
            db_models.Case.case_code,
            db_models.Case.creation_date,
            db_models.Case.patient_id,
            db_models.Case.grossing_status,
            db_models.Case.bank_count,     
            db_models.Case.cassette_count, 
            db_models.Case.glass_count,
            db_models.Case.pathohistological_conclusion,
            db_models.Case.microdescription,
            literal_column("1").label("sort_priority")
        )
        .where( 
            and_(
                func.substr(db_models.Case.case_code, 1, 1).in_(['F', 'U']),
                db_models.Case.grossing_status != db_models.Grossing_status.COMPLETED.value
            )
        )
    ).subquery("cases_fu")

    scanned_glass_exists_clause = (
        select(1)
        .select_from(db_models.Sample)
        .join(db_models.Cassette, db_models.Sample.id == db_models.Cassette.sample_id)
        .join(db_models.Glass, db_models.Cassette.id == db_models.Glass.cassette_id)
        .where(
            db_models.Sample.case_id == db_models.Case.id
        )
        .exists()
    )

    cases_s_subquery = (
        select(
            db_models.Case.id,
            db_models.Case.case_code,
            db_models.Case.creation_date,
            db_models.Case.patient_id,
            db_models.Case.grossing_status,
            db_models.Case.bank_count,    
            db_models.Case.cassette_count,
            db_models.Case.glass_count,
            db_models.Case.pathohistological_conclusion,
            db_models.Case.microdescription,
            literal_column("2").label("sort_priority")
        )
        .where( 
            and_(
                func.substr(db_models.Case.case_code, 1, 1) == 'S',

                db_models.Case.grossing_status != db_models.Grossing_status.COMPLETED.value,
                scanned_glass_exists_clause 
            )
        )
    ).subquery("cases_s")

    combined_query_for_data = (
        select(
            cases_fu_subquery.c.id,
            cases_fu_subquery.c.case_code,
            cases_fu_subquery.c.creation_date,
            cases_fu_subquery.c.patient_id,
            cases_fu_subquery.c.grossing_status,
            cases_fu_subquery.c.bank_count,    
            cases_fu_subquery.c.cassette_count, 
            cases_fu_subquery.c.glass_count,
            cases_fu_subquery.c.pathohistological_conclusion,
            cases_fu_subquery.c.microdescription,
            cases_fu_subquery.c.sort_priority
        )
        .union_all(
            select(
                cases_s_subquery.c.id,
                cases_s_subquery.c.case_code,
                cases_s_subquery.c.creation_date,
                cases_s_subquery.c.patient_id,
                cases_s_subquery.c.grossing_status,
                cases_s_subquery.c.bank_count,     
                cases_s_subquery.c.cassette_count, 
                cases_s_subquery.c.glass_count,
                cases_s_subquery.c.pathohistological_conclusion,
                cases_s_subquery.c.microdescription,
                cases_s_subquery.c.sort_priority
            )
        )
    )

    final_ordered_query = combined_query_for_data.order_by(
        combined_query_for_data.c.sort_priority.asc(),
        combined_query_for_data.c.creation_date.desc()
    )

    paginated_results = await db.execute(
        final_ordered_query.offset(skip).limit(limit)
    )
    all_current_cases_raw = paginated_results.all()
    

    current_cases_list: List[CaseModelScheema] = []

    for row in all_current_cases_raw:
        case_id = row.id
        case_code = row.case_code
        creation_date = row.creation_date
        patient_id = row.patient_id
        bank_count = row.bank_count
        cassette_count = row.cassette_count
        glass_count = row.glass_count
        grossing_status = db_models.Grossing_status(row.grossing_status)
        pathohistological_conclusion = row.pathohistological_conclusion
        microdescription = row.microdescription

        current_cases_list.append(
            CaseModelScheema(
                id=case_id,
                case_code=case_code,
                creation_date=creation_date,
                patient_id=patient_id,
                grossing_status=grossing_status,
                bank_count=bank_count,
                cassette_count=cassette_count,
                glass_count=glass_count,
                pathohistological_conclusion = pathohistological_conclusion,
                microdescription = microdescription
            )
        )

    last_case_details_for_excision: Optional[LastCaseExcisionDetailsSchema] = None

    if all_current_cases_raw:
        last_case_db = all_current_cases_raw[0] 
        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == last_case_db.id)
            .options(
                selectinload(db_models.Case.case_parameters), 
                selectinload(db_models.Case.samples) 
            )
        )
        last_case_with_relations = last_case_full_info_result.scalar_one_or_none()

        if last_case_with_relations:

            case_parameters_schematized: Optional[CaseParametersScheema] = None
            if last_case_with_relations.case_parameters:
                case_parameters_schematized = CaseParametersScheema.model_validate(
                    last_case_with_relations.case_parameters
                ).model_dump()
            

            samples_for_excision_page: List[SampleForExcisionPage] = []
            

            sorted_samples = sorted(
                last_case_with_relations.samples,
                key=lambda s: s.sample_number 
            )

            for sample_db in sorted_samples:

                samples_for_excision_page.append(
                    SampleForExcisionPage(
                        id=sample_db.id,
                        sample_number=sample_db.sample_number,
                        is_archived=sample_db.archive, 
                        macro_description=sample_db.macro_description 
                    )
                )


            last_case_details_for_excision = LastCaseExcisionDetailsSchema(
                id=last_case_db.id,
                case_code=last_case_db.case_code,
                creation_date=last_case_db.creation_date,
                pathohistological_conclusion=last_case_db.pathohistological_conclusion,
                microdescription=last_case_db.microdescription,
                case_parameters=case_parameters_schematized,
                samples=samples_for_excision_page,
                grossing_status=last_case_db.grossing_status,
                patient_cor_id=last_case_db.patient_id
            )


    return PatientExcisionPageResponse(
        all_cases=current_cases_list,
        last_case_details_for_excision=last_case_details_for_excision,
    )



async def get_current_cases_report_page_data(
    db: AsyncSession,
    router: APIRouter, 
    skip: int = 0,
    limit: int = 10, 
    
) -> PatientTestReportPageResponse:
    """
    Получает данные для вкладки "Заключение" на странице врача:
    - Все кейсы пациента.
    - Детали последнего кейса: сам кейс (включая micro_description), его параметры (для macro_description),
      и его заключение (если есть). Если заключения нет, оно будет создано.
    - Все стёкла последнего кейса (для выбора, какие прикрепить).
    """
    cases_fu_subquery = (
        select(
            db_models.Case.id,
            db_models.Case.case_code,
            db_models.Case.creation_date,
            db_models.Case.patient_id,
            db_models.Case.grossing_status,
            db_models.Case.bank_count,     
            db_models.Case.cassette_count, 
            db_models.Case.glass_count,
            db_models.Case.pathohistological_conclusion,
            db_models.Case.microdescription,
            literal_column("1").label("sort_priority")
        )
        .where( 
            and_(
                func.substr(db_models.Case.case_code, 1, 1).in_(['F', 'U']),
                db_models.Case.grossing_status != db_models.Grossing_status.COMPLETED.value
            )
        )
    ).subquery("cases_fu")

    scanned_glass_exists_clause = (
        select(1)
        .select_from(db_models.Sample)
        .join(db_models.Cassette, db_models.Sample.id == db_models.Cassette.sample_id)
        .join(db_models.Glass, db_models.Cassette.id == db_models.Glass.cassette_id)
        .where(
            db_models.Sample.case_id == db_models.Case.id
        )
        .exists()
    )

    cases_s_subquery = (
        select(
            db_models.Case.id,
            db_models.Case.case_code,
            db_models.Case.creation_date,
            db_models.Case.patient_id,
            db_models.Case.grossing_status,
            db_models.Case.bank_count,    
            db_models.Case.cassette_count,
            db_models.Case.glass_count,
            db_models.Case.pathohistological_conclusion,
            db_models.Case.microdescription,
            literal_column("2").label("sort_priority")
        )
        .where( 
            and_(
                func.substr(db_models.Case.case_code, 1, 1) == 'S',

                db_models.Case.grossing_status != db_models.Grossing_status.COMPLETED.value,
                scanned_glass_exists_clause 
            )
        )
    ).subquery("cases_s")

    combined_query_for_data = (
        select(
            cases_fu_subquery.c.id,
            cases_fu_subquery.c.case_code,
            cases_fu_subquery.c.creation_date,
            cases_fu_subquery.c.patient_id,
            cases_fu_subquery.c.grossing_status,
            cases_fu_subquery.c.bank_count,    
            cases_fu_subquery.c.cassette_count, 
            cases_fu_subquery.c.glass_count,
            cases_fu_subquery.c.pathohistological_conclusion,
            cases_fu_subquery.c.microdescription,
            cases_fu_subquery.c.sort_priority
        )
        .union_all(
            select(
                cases_s_subquery.c.id,
                cases_s_subquery.c.case_code,
                cases_s_subquery.c.creation_date,
                cases_s_subquery.c.patient_id,
                cases_s_subquery.c.grossing_status,
                cases_s_subquery.c.bank_count,     
                cases_s_subquery.c.cassette_count, 
                cases_s_subquery.c.glass_count,
                cases_s_subquery.c.pathohistological_conclusion,
                cases_s_subquery.c.microdescription,
                cases_s_subquery.c.sort_priority
            )
        )
    )

    final_ordered_query = combined_query_for_data.order_by(
        combined_query_for_data.c.sort_priority.asc(),
        combined_query_for_data.c.creation_date.desc()
    )

    paginated_results = await db.execute(
        final_ordered_query.offset(skip).limit(limit)
    )
    all_current_cases_raw = paginated_results.all()
    

    current_cases_list: List[CaseModelScheema] = []

    for row in all_current_cases_raw:
        case_id = row.id
        case_code = row.case_code
        creation_date = row.creation_date
        patient_id = row.patient_id
        bank_count = row.bank_count
        cassette_count = row.cassette_count
        glass_count = row.glass_count
        grossing_status = db_models.Grossing_status(row.grossing_status)
        pathohistological_conclusion = row.pathohistological_conclusion
        microdescription = row.microdescription
        current_cases_list.append(
            CaseModelScheema(
                id=case_id,
                case_code=case_code,
                creation_date=creation_date,
                patient_id=patient_id,
                grossing_status=grossing_status,
                bank_count=bank_count,
                cassette_count=cassette_count,
                glass_count=glass_count,
                pathohistological_conclusion = pathohistological_conclusion,
                microdescription =microdescription
            )
        )

    last_case_for_report: Optional[CaseModelScheema] = None
    report_details: Optional[ReportResponseSchema] = None
    all_samples_for_last_case_schematized: List[SampleTestForGlassPage] = []
    first_case_details_for_glass: Optional[FirstCaseTestGlassDetailsSchema] = None

    if all_current_cases_raw:
        last_case_db = all_current_cases_raw[0]

        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == last_case_db.id)
            .options(
                selectinload(db_models.Case.case_parameters),
                selectinload(db_models.Case.report).selectinload(db_models.Report.signatures).selectinload(db_models.ReportSignature.doctor),
                selectinload(db_models.Case.report).selectinload(db_models.Report.signatures).selectinload(db_models.ReportSignature.doctor_signature),
                selectinload(db_models.Case.samples).selectinload(db_models.Sample.cassette).selectinload(db_models.Cassette.glass)
            )
        )
        last_case_with_relations = last_case_full_info_result.scalar_one_or_none()

        if last_case_with_relations:
            last_case_for_report = CaseModelScheema.model_validate(last_case_with_relations)

            if not last_case_with_relations.report:
                new_report = db_models.Report(case_id=last_case_with_relations.id)
                db.add(new_report)
                await db.commit()
                await db.refresh(new_report)
                last_case_with_relations.report = new_report

            report_details = await _format_report_response(db=db, db_report=last_case_with_relations.report, db_case_parameters=last_case_with_relations.case_parameters, router=router, case_db=last_case_db)

            for sample_db in last_case_with_relations.samples:
                def sort_cassettes(cassette: db_models.Cassette):
                    match = re.match(r"([A-Z]+)(\d+)", cassette.cassette_number)
                    if match:
                        letter_part = match.group(1)
                        number_part = int(match.group(2))
                        return (letter_part, number_part)
                    return (cassette.cassette_number, 0)

                sorted_cassettes_db = sorted(sample_db.cassette, key=sort_cassettes)

                cassettes_for_sample: List[CassetteTestForGlassPage] = []
                for cassette_db in sorted_cassettes_db:
                    sorted_glasses_db = sorted(
                        cassette_db.glass,
                        key=lambda glass: glass.glass_number
                    )
                    glasses_for_cassette: List[GlassTestModelScheema] = []
                    for glass in sorted_glasses_db:
                        glass = GlassTestModelScheema(id=glass.id,
                                                      glass_number=glass.glass_number,
                                                      cassette_id=glass.cassette_id,
                                                      staining=glass.staining
                                                      )
                        glasses_for_cassette.append(glass)
                        
                    cassette_schematized = CassetteTestForGlassPage(id=cassette_db.id,
                                                                    cassette_number=cassette_db.cassette_number,
                                                                    sample_id=cassette_db.sample_id
                                                                    )
                    cassette_schematized.glasses = glasses_for_cassette 
                    cassettes_for_sample.append(cassette_schematized)

                sample_schematized = SampleTestForGlassPage(id=sample_db.id,
                                                            sample_number=sample_db.sample_number,
                                                            case_id=sample_db.case_id)
                sample_schematized.cassettes = cassettes_for_sample
                all_samples_for_last_case_schematized.append(sample_schematized)


            first_case_details_for_glass = FirstCaseTestGlassDetailsSchema(
                id=last_case_with_relations.id,
                case_code=last_case_with_relations.case_code,
                creation_date=last_case_with_relations.creation_date,
                samples=all_samples_for_last_case_schematized,
                grossing_status=last_case_with_relations.grossing_status 
            )

    return PatientTestReportPageResponse(
        all_cases=current_cases_list,
        last_case_for_report=last_case_for_report,
        report_details=report_details,
        all_glasses_for_last_case=first_case_details_for_glass 
    )


async def get_current_cases_with_directions(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 10  
) -> PatientCasesWithReferralsResponse: 
    """
    Асинхронно получает список всех кейсов пациента и детализацию первого из них:
    все семплы первого кейса, но кассеты и стекла загружаются только для первого семпла.
    Включает ссылки на файлы направлений для первого кейса.
    """
    cases_fu_subquery = (
        select(
            db_models.Case.id,
            db_models.Case.case_code,
            db_models.Case.creation_date,
            db_models.Case.patient_id,
            db_models.Case.grossing_status,
            db_models.Case.bank_count,     
            db_models.Case.cassette_count, 
            db_models.Case.glass_count,
            db_models.Case.pathohistological_conclusion,
            db_models.Case.microdescription,
            literal_column("1").label("sort_priority")
        )
        .where( 
            and_(
                func.substr(db_models.Case.case_code, 1, 1).in_(['F', 'U']),
                db_models.Case.grossing_status != db_models.Grossing_status.COMPLETED.value
            )
        )
    ).subquery("cases_fu")

    scanned_glass_exists_clause = (
        select(1)
        .select_from(db_models.Sample)
        .join(db_models.Cassette, db_models.Sample.id == db_models.Cassette.sample_id)
        .join(db_models.Glass, db_models.Cassette.id == db_models.Glass.cassette_id)
        .where(
            db_models.Sample.case_id == db_models.Case.id
        )
        .exists()
    )

    cases_s_subquery = (
        select(
            db_models.Case.id,
            db_models.Case.case_code,
            db_models.Case.creation_date,
            db_models.Case.patient_id,
            db_models.Case.grossing_status,
            db_models.Case.bank_count,    
            db_models.Case.cassette_count,
            db_models.Case.glass_count,
            db_models.Case.pathohistological_conclusion,
            db_models.Case.microdescription,
            literal_column("2").label("sort_priority")
        )
        .where( 
            and_(
                func.substr(db_models.Case.case_code, 1, 1) == 'S',

                db_models.Case.grossing_status != db_models.Grossing_status.COMPLETED.value,
                scanned_glass_exists_clause 
            )
        )
    ).subquery("cases_s")

    combined_query_for_data = (
        select(
            cases_fu_subquery.c.id,
            cases_fu_subquery.c.case_code,
            cases_fu_subquery.c.creation_date,
            cases_fu_subquery.c.patient_id,
            cases_fu_subquery.c.grossing_status,
            cases_fu_subquery.c.bank_count,    
            cases_fu_subquery.c.cassette_count, 
            cases_fu_subquery.c.glass_count,
            cases_fu_subquery.c.pathohistological_conclusion,
            cases_fu_subquery.c.microdescription,
            cases_fu_subquery.c.sort_priority
        )
        .union_all(
            select(
                cases_s_subquery.c.id,
                cases_s_subquery.c.case_code,
                cases_s_subquery.c.creation_date,
                cases_s_subquery.c.patient_id,
                cases_s_subquery.c.grossing_status,
                cases_s_subquery.c.bank_count,     
                cases_s_subquery.c.cassette_count, 
                cases_s_subquery.c.glass_count,
                cases_s_subquery.c.pathohistological_conclusion,
                cases_s_subquery.c.microdescription,
                cases_s_subquery.c.sort_priority
            )
        )
    )

    final_ordered_query = combined_query_for_data.order_by(
        combined_query_for_data.c.sort_priority.asc(),
        combined_query_for_data.c.creation_date.desc()
    )

    paginated_results = await db.execute(
        final_ordered_query.offset(skip).limit(limit)
    )
    all_current_cases_raw = paginated_results.all()
    

    current_cases_list: List[CaseModelScheema] = []

    for row in all_current_cases_raw:
        case_id = row.id
        case_code = row.case_code
        creation_date = row.creation_date
        patient_id = row.patient_id
        bank_count = row.bank_count
        cassette_count = row.cassette_count
        glass_count = row.glass_count
        grossing_status = db_models.Grossing_status(row.grossing_status)
        pathohistological_conclusion = row.pathohistological_conclusion
        microdescription = row.microdescription
        current_cases_list.append(
            CaseModelScheema(
                id=case_id,
                case_code=case_code,
                creation_date=creation_date,
                patient_id=patient_id,
                grossing_status=grossing_status,
                bank_count=bank_count,
                cassette_count=cassette_count,
                glass_count=glass_count,
                pathohistological_conclusion = pathohistological_conclusion,
                microdescription = microdescription
            )
        )

    first_case_direction_details: Optional[FirstCaseReferralDetailsSchema] = None
    case_details = None

    if all_current_cases_raw:
        first_case_db = all_current_cases_raw[0]
        
        referral_db = await db.scalar(
            select(db_models.Referral).where(db_models.Referral.case_id == first_case_db.id)
        )

        if referral_db:
            direction_files_result = await db.execute(
                select(db_models.ReferralAttachment).where(
                    db_models.ReferralAttachment.referral_id == referral_db.id
                )
            )
            direction_files_db = direction_files_result.scalars().all()

            attachments_for_response = []
            for file_db in direction_files_db:
                file_url = generate_file_url(file_db.id, first_case_db.id)
                attachments_for_response.append(
                    ReferralFileSchema(
                        id=file_db.id,
                        file_name=file_db.filename,
                        file_type=file_db.content_type, 
                        file_url=file_url
                    )
                )
            
            first_case_direction_details = FirstCaseReferralDetailsSchema(
                id=first_case_db.id,
                case_code=first_case_db.case_code,
                creation_date=first_case_db.creation_date,
                pathohistological_conclusion=first_case_db.pathohistological_conclusion,
                microdescription=first_case_db.microdescription,
                attachments=attachments_for_response,
                grossing_status=first_case_db.grossing_status,
                patient_cor_id = first_case_db.patient_id
            )

    return PatientCasesWithReferralsResponse(
        all_cases=current_cases_list,
        case_details=first_case_db,
        first_case_direction=first_case_direction_details
    )



async def get_current_cases_final_report_page_data(
    db: AsyncSession, 
    router: APIRouter,
    skip: int = 0,
    limit: int = 10 

) -> PatientFinalReportPageResponse:
    """
    Получает данные для вкладки "Заключение" на странице врача:
    - Все кейсы пациента.
    - Детали последнего кейса: сам кейс (включая micro_description), его параметры (для macro_description),
      и его заключение (если есть). Если заключения нет, оно будет создано.
    - Все стёкла последнего кейса (для выбора, какие прикрепить).
    """
    cases_fu_subquery = (
        select(
            db_models.Case.id,
            db_models.Case.case_code,
            db_models.Case.creation_date,
            db_models.Case.patient_id,
            db_models.Case.grossing_status,
            db_models.Case.bank_count,     
            db_models.Case.cassette_count, 
            db_models.Case.glass_count,
            db_models.Case.pathohistological_conclusion,
            db_models.Case.microdescription,
            literal_column("1").label("sort_priority")
        )
        .where( 
            and_(
                func.substr(db_models.Case.case_code, 1, 1).in_(['F', 'U']),
                db_models.Case.grossing_status != db_models.Grossing_status.COMPLETED.value
            )
        )
    ).subquery("cases_fu")

    scanned_glass_exists_clause = (
        select(1)
        .select_from(db_models.Sample)
        .join(db_models.Cassette, db_models.Sample.id == db_models.Cassette.sample_id)
        .join(db_models.Glass, db_models.Cassette.id == db_models.Glass.cassette_id)
        .where(
            db_models.Sample.case_id == db_models.Case.id
        )
        .exists()
    )

    cases_s_subquery = (
        select(
            db_models.Case.id,
            db_models.Case.case_code,
            db_models.Case.creation_date,
            db_models.Case.patient_id,
            db_models.Case.grossing_status,
            db_models.Case.bank_count,    
            db_models.Case.cassette_count,
            db_models.Case.glass_count,
            db_models.Case.pathohistological_conclusion,
            db_models.Case.microdescription,
            literal_column("2").label("sort_priority")
        )
        .where( 
            and_(
                func.substr(db_models.Case.case_code, 1, 1) == 'S',

                db_models.Case.grossing_status != db_models.Grossing_status.COMPLETED.value,
                scanned_glass_exists_clause 
            )
        )
    ).subquery("cases_s")

    combined_query_for_data = (
        select(
            cases_fu_subquery.c.id,
            cases_fu_subquery.c.case_code,
            cases_fu_subquery.c.creation_date,
            cases_fu_subquery.c.patient_id,
            cases_fu_subquery.c.grossing_status,
            cases_fu_subquery.c.bank_count,    
            cases_fu_subquery.c.cassette_count, 
            cases_fu_subquery.c.glass_count,
            cases_fu_subquery.c.pathohistological_conclusion,
            cases_fu_subquery.c.microdescription,
            cases_fu_subquery.c.sort_priority
        )
        .union_all(
            select(
                cases_s_subquery.c.id,
                cases_s_subquery.c.case_code,
                cases_s_subquery.c.creation_date,
                cases_s_subquery.c.patient_id,
                cases_s_subquery.c.grossing_status,
                cases_s_subquery.c.bank_count,     
                cases_s_subquery.c.cassette_count, 
                cases_s_subquery.c.glass_count,
                cases_s_subquery.c.pathohistological_conclusion,
                cases_s_subquery.c.microdescription,
                cases_s_subquery.c.sort_priority
            )
        )
    )

    final_ordered_query = combined_query_for_data.order_by(
        combined_query_for_data.c.sort_priority.asc(),
        combined_query_for_data.c.creation_date.desc()
    )

    paginated_results = await db.execute(
        final_ordered_query.offset(skip).limit(limit)
    )
    all_current_cases_raw = paginated_results.all()
    

    current_cases_list: List[CaseModelScheema] = []
    last_case_details = None

    for row in all_current_cases_raw:
        case_id = row.id
        case_code = row.case_code
        creation_date = row.creation_date
        patient_id = row.patient_id
        bank_count = row.bank_count
        cassette_count = row.cassette_count
        glass_count = row.glass_count
        grossing_status = db_models.Grossing_status(row.grossing_status)
        pathohistological_conclusion = row.pathohistological_conclusion
        microdescription = row.microdescription
        current_cases_list.append(
            CaseModelScheema(
                id=case_id,
                case_code=case_code,
                creation_date=creation_date,
                patient_id=patient_id,
                grossing_status=grossing_status,
                bank_count=bank_count,
                cassette_count=cassette_count,
                glass_count=glass_count,
                pathohistological_conclusion = pathohistological_conclusion,
                microdescription = microdescription
            )
        )
    report_details: Optional[ReportResponseSchema] = None
    all_samples_for_last_case_schematized: List[SampleTestForGlassPage] = []


    if all_current_cases_raw:
        last_case_db = all_current_cases_raw[0]
        last_case_details = CaseModelScheema.model_validate(last_case_db)

        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == last_case_db.id)
            .options(
                selectinload(db_models.Case.case_parameters),
                selectinload(db_models.Case.report).selectinload(db_models.Report.signatures).selectinload(db_models.ReportSignature.doctor),
                selectinload(db_models.Case.report).selectinload(db_models.Report.signatures).selectinload(db_models.ReportSignature.doctor_signature),
                selectinload(db_models.Case.samples).selectinload(db_models.Sample.cassette).selectinload(db_models.Cassette.glass)
            )
        )
        last_case_with_relations = last_case_full_info_result.scalar_one_or_none()

        if last_case_with_relations:
            if not last_case_with_relations.report:
                new_report = db_models.Report(case_id=last_case_with_relations.id)
                db.add(new_report)
                await db.commit()
                await db.refresh(new_report)
                last_case_with_relations.report = new_report

            patient_db = await get_patient_by_corid(db=db, cor_id=last_case_db.patient_id)
            referral_db = await get_referral_by_case(db=db, case_id=last_case_db.id)
            report_details = await _format_final_report_response(db=db, db_report=last_case_with_relations.report, db_case_parameters=last_case_with_relations.case_parameters, router=router, patient_db=patient_db, referral_db=referral_db, case_db=last_case_with_relations)

            for sample_db in last_case_with_relations.samples:
                def sort_cassettes(cassette: db_models.Cassette):
                    match = re.match(r"([A-Z]+)(\d+)", cassette.cassette_number)
                    if match:
                        letter_part = match.group(1)
                        number_part = int(match.group(2))
                        return (letter_part, number_part)
                    return (cassette.cassette_number, 0)

                sorted_cassettes_db = sorted(sample_db.cassette, key=sort_cassettes)

                cassettes_for_sample: List[CassetteTestForGlassPage] = []
                for cassette_db in sorted_cassettes_db:
                    sorted_glasses_db = sorted(
                        cassette_db.glass,
                        key=lambda glass: glass.glass_number
                    )
                    glasses_for_cassette: List[GlassTestModelScheema] = []
                    for glass in sorted_glasses_db:
                        glass = GlassTestModelScheema(id=glass.id,
                                                      glass_number=glass.glass_number,
                                                      cassette_id=glass.cassette_id
                                                      )
                        glasses_for_cassette.append(glass)
                        
                    cassette_schematized = CassetteTestForGlassPage(id=cassette_db.id,
                                                                    cassette_number=cassette_db.cassette_number,
                                                                    sample_id=cassette_db.sample_id
                                                                    )
                    cassette_schematized.glasses = glasses_for_cassette 
                    cassettes_for_sample.append(cassette_schematized)

                sample_schematized = SampleTestForGlassPage(id=sample_db.id,
                                                            sample_number=sample_db.sample_number,
                                                            case_id=sample_db.case_id)
                sample_schematized.cassettes = cassettes_for_sample
                all_samples_for_last_case_schematized.append(sample_schematized)


    return PatientFinalReportPageResponse(
        all_cases=current_cases_list,
        last_case_details=last_case_details,
        report_details=report_details
    )