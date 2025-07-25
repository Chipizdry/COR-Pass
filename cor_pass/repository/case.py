import base64
from enum import Enum
import re
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request, UploadFile, status
from sqlalchemy import and_, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from cor_pass.repository.cassette import print_cassette_data
from cor_pass.repository.glass import print_glass_data
from cor_pass.repository.lawyer import get_doctor
from cor_pass.repository.patient import get_patient_by_corid
from cor_pass.schemas import (
    Case as CaseModelScheema,
    CaseCloseResponse,
    CaseDetailsResponse,
    CaseFinalReportPageResponse,
    CaseIDReportPageResponse,
    CaseOwnerResponse,
    CaseOwnershipResponse,
    CaseParametersScheema,
    CassetteForGlassPage,
    CassettePrinting,
    CassetteTestForGlassPage,
    DoctorDiagnosisSchema,
    DoctorResponseForSignature,
    FinalReportResponseSchema,
    FirstCaseTestGlassDetailsSchema,
    GeneralPrinting,
    GlassPrinting,
    GlassTestModelScheema,
    PatientFinalReportPageResponse,
    PatientTestReportPageResponse,
    ReportAndDiagnosisUpdateSchema,
    ReportResponseSchema,
    ReportSignatureSchema,
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
from loguru import logger
from cor_pass.config.config import settings
from string import ascii_uppercase


class ErrorCode(str, Enum):
    CASE_NOT_FOUND = "CASE_NOT_FOUND"
    NOT_CASE_OWNER = "NOT_CASE_OWNER"
    CASE_ALREADY_COMPLETED = "CASE_ALREADY_COMPLETED"
    REPORT_NOT_FOUND_FOR_CASE = "REPORT_NOT_FOUND_FOR_CASE"
    NO_DIAGNOSES_FOR_REPORT = "NO_DIAGNOSES_FOR_REPORT"
    DIAGNOSIS_NOT_SIGNED_BY_DOCTOR_NAME = (
        "DIAGNOSIS_NOT_SIGNED_BY_DOCTOR_NAME: {doctor_full_name}"
    )
    SIGNATURE_MISMATCH = "SIGNATURE_MISMATCH: Diagnosis by {diagnosis_doctor}, signed by {signature_doctor}"


async def _create_single_sample_with_dependencies(
    db: AsyncSession, case_id: str, sample_char: str
):
    """
    Создает один семпл, одну кассету и одно стекло.
    Возвращает созданный семпл.
    """
    db_case = await db.get(db_models.Case, case_id)

    db_sample = db_models.Sample(case_id=db_case.id, sample_number=sample_char)
    db.add(db_sample)
    db_case.bank_count += 1
    await db.flush()
    await db.refresh(db_sample)
    await db.refresh(db_case)

    db_cassette = db_models.Cassette(
        sample_id=db_sample.id, cassette_number=f"{sample_char}1"
    )
    db.add(db_cassette)
    db_case.cassette_count += 1
    db_sample.cassette_count += 1
    await db.flush()
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
    await db.flush()
    await db.refresh(db_glass)
    await db.refresh(db_case)
    await db.refresh(db_sample)
    await db.refresh(db_cassette)
    await _update_ancestor_statuses_from_cassette(db=db, cassette=db_cassette)
    await _update_ancestor_statuses_from_glass(db=db, glass=db_glass)

    return db_sample


async def _get_next_sample_char(db: AsyncSession, case_id: str):
    """Определяет следующий доступный буквенный номер семпла."""
    samples_result = await db.execute(
        select(db_models.Sample.sample_number)
        .where(db_models.Sample.case_id == case_id)
        .order_by(db_models.Sample.sample_number)
    )
    existing_sample_numbers = samples_result.scalars().all()

    if not existing_sample_numbers:
        return "A"

    last_sample_number = existing_sample_numbers[-1]
    if last_sample_number in ascii_uppercase:
        last_index = ascii_uppercase.index(last_sample_number)
        if last_index < len(ascii_uppercase) - 1:
            return ascii_uppercase[last_index + 1]

    return f"Z{len(existing_sample_numbers) + 1}"


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
    """
    Асинхронно создает указанное количество кейсов, семплов и связанные с ними данные.
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
        if len(code) == 9 and code[1:3] == year_short:
            try:
                sequential_number = int(code[4:])
                if sequential_number > max_sequential_number:
                    max_sequential_number = sequential_number
            except ValueError:
                continue
    next_number = max_sequential_number + 1
    for i in range(body.num_cases):
        db_case = db_models.Case(
            id=str(uuid.uuid4()),
            patient_id=body.patient_cor_id,
            creation_date=datetime.now(),
            bank_count=0,
            cassette_count=0,
            glass_count=0,
        )
        db_case.case_code = await generate_case_code(
            urgency_char, year_short, material_type_char, next_number
        )
        db.add(db_case)

        await db.flush()
        await db.refresh(db_case)
        next_number += 1

        for j in range(body.num_samples):
            sample_char = (
                ascii_uppercase[j]
                if j < len(ascii_uppercase)
                else f"Z{j - len(ascii_uppercase) + 1}"
            )

            await _create_single_sample_with_dependencies(db, db_case.id, sample_char)

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

    if created_cases_db:
        first_case_with_relations = await db.execute(
            select(db_models.Case)
            .options(
                selectinload(db_models.Case.samples)
                .selectinload(db_models.Sample.cassette)
                .selectinload(db_models.Cassette.glass)
            )
            .where(db_models.Case.id == created_cases_db[0].id)
        )
        first_case_db_full = first_case_with_relations.scalar_one_or_none()

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
            "grossing_status": first_case_db.grossing_status,
            "is_printed_cassette": first_case_db.is_printed_cassette,
            "is_printed_glass": first_case_db.is_printed_glass,
            "is_printed_qr": first_case_db.is_printed_qr,
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

    samples_result = await db.execute(
        select(db_models.Sample)
        .where(db_models.Sample.case_id == case_db.id)
        .options(selectinload(db_models.Sample.cassette))
        .order_by(db_models.Sample.sample_number)
    )
    first_case_samples_db = samples_result.scalars().all()
    first_case_samples: List[Dict[str, Any]] = []

    for i, sample_db in enumerate(first_case_samples_db):
        sample = SampleModelScheema.model_validate(sample_db).model_dump()
        sample["cassettes"] = []

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
        "is_printed_cassette": case_db.is_printed_cassette,
        "is_printed_glass": case_db.is_printed_glass,
        "is_printed_qr": case_db.is_printed_qr,
        "samples": first_case_samples,
        "grossing_status": case_db.grossing_status,
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
            detail=f"Параметри для кейса з ID '{case_id}' не знайдено.",
        )

    result_case = await db.execute(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    db_case = result_case.scalar_one_or_none()

    if not db_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Кейс з ID '{case_id}' не знайдено, неможливо оновити код.",
        )

    if db_case.grossing_status == db_models.Grossing_status.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"Запрещено редактировать закрытый кейс",
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
                detail=f"Некоректний формат коду кейса '{current_code}'. Оновлення неможливе.",
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
            db_models.Case.case_code == new_case_code, db_models.Case.id != case_id
        )
        existing_conflict = (await db.execute(existing_codes_stmt)).scalar_one_or_none()

        if existing_conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Новый код кейса '{new_case_code}' уже существует. "
                "Измените порядковый номер для сохранения уникальности.",
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


async def get_single_case_by_case_code(db: AsyncSession, case_code: str) -> db_models.Case | None:
    """Асинхронно получает информацию о кейсе по его case_code, включая связанные банки."""
    result = await db.execute(
        select(db_models.Case).where(db_models.Case.case_code == case_code)
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

        samples_result = await db.execute(
            select(db_models.Sample)
            .where(db_models.Sample.case_id == first_case_db.id)
            .options(selectinload(db_models.Sample.cassette))
            .order_by(db_models.Sample.sample_number)
        )
        first_case_samples_db = samples_result.scalars().all()
        first_case_samples: List[Dict[str, Any]] = []

        for i, sample_db in enumerate(first_case_samples_db):
            sample = SampleModelScheema.model_validate(sample_db).model_dump()
            sample["cassettes"] = []

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
                    )

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
            "grossing_status": first_case_db.grossing_status,
            "is_printed_cassette": first_case_db.is_printed_cassette,
            "is_printed_glass": first_case_db.is_printed_glass,
            "is_printed_qr": first_case_db.is_printed_qr,
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
            detail="Новый суффикс должен состоять из 5 цифровых символов.",
        )

    result = await db.execute(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    db_case = result.scalar_one_or_none()

    if not db_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Кейс с ID '{case_id}' не найден.",
        )
    if db_case.grossing_status == db_models.Grossing_status.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"Запрещено редактировать закрытый кейс",
        )

    current_code = db_case.case_code

    if len(current_code) < 9:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Текущий код кейса '{current_code}' слишком короткий.",
        )

    current_year_short = current_code[1:3]

    new_full_case_code = f"{current_code[:-5]}{new_suffix}"

    prefix_without_suffix = current_code[:-5]

    existing_codes_stmt = select(db_models.Case.case_code).where(
        db_models.Case.case_code.like(f"%{current_year_short}%"),
        db_models.Case.id != case_id,
    )
    existing_case_codes_in_current_year = (
        (await db.execute(existing_codes_stmt)).scalars().all()
    )

    if new_full_case_code in existing_case_codes_in_current_year:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Код кейса '{new_full_case_code}' уже существует в текущем году. Выбирите другой номер.",
        )

    db_case.case_code = new_full_case_code
    await db.commit()
    await db.refresh(db_case)

    return UpdateCaseCodeResponce.model_validate(db_case)


async def create_referral(
    db: AsyncSession, referral_in: ReferralCreate, case: db_models.Case
) -> db_models.Referral:
    db_referral = db_models.Referral(
        case_id=referral_in.case_id,
        case_number=case.case_code,
        biomaterial_date=referral_in.biomaterial_date,
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


async def update_referral(
    db: AsyncSession, db_referral: db_models.Referral, referral_in: ReferralCreate
) -> db_models.Referral:
    """
    Обновляет существующее направление в базе данных.
    """
    for field, value in referral_in.model_dump(exclude_unset=True).items():
        setattr(db_referral, field, value)

    await db.commit()
    await db.refresh(db_referral)
    return db_referral


async def upsert_referral(
    db: AsyncSession, referral_data: ReferralCreate, case: db_models.Case
) -> db_models.Referral:
    """
    Обновляет направление, если оно существует для данного case_id, иначе создает новое.
    """
    if case.grossing_status == db_models.Grossing_status.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"Запрещено редактировать закрытый кейс",
        )
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


async def get_referral(
    db: AsyncSession, referral_id: str
) -> Optional[db_models.Referral]:
    result = await db.execute(
        select(db_models.Referral).where(db_models.Referral.id == referral_id)
    )
    referral_db = result.scalars().unique().one_or_none()
    return referral_db


async def get_referral_by_case(
    db: AsyncSession, case_id: str
) -> Optional[db_models.Referral]:
    result = await db.execute(
        select(db_models.Referral).where(db_models.Referral.case_id == case_id)
    )
    referral_db = result.scalars().unique().one_or_none()
    return referral_db


async def get_referral_attachment(
    db: AsyncSession, attachment_id: str
) -> Optional[db_models.ReferralAttachment]:
    result = await db.execute(
        select(db_models.ReferralAttachment).where(
            db_models.ReferralAttachment.id == attachment_id
        )
    )
    return result.scalar_one_or_none()


async def upload_attachment(
    db: AsyncSession, referral_id: str, file: UploadFile
) -> db_models.ReferralAttachment:
    referral = await get_referral(db, referral_id)
    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Referral not found"
        )

    if len(referral.attachments) >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 5 attachments allowed per referral.",
        )
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
        file_data=file_data,
    )
    db.add(db_attachment)
    await db.commit()
    await db.refresh(db_attachment)
    return db_attachment


def generate_file_url(file_id: str, case_id: str) -> str:
    """Генерирует URL для скачивания/просмотра файла направления."""
    return f"/cases/attachments/{file_id}"


async def get_patient_cases_with_directions(
    db: AsyncSession, patient_id: str, current_doctor_id: str, case_id=Optional[str]
) -> PatientCasesWithReferralsResponse:
    """
    Асинхронно получает список всех кейсов пациента и детализацию первого из них:
    все семплы первого кейса, но кассеты и стекла загружаются только для первого семпла.
    Включает ссылки на файлы направлений для первого кейса.
    """

    cases_result = await db.execute(
        select(db_models.Case)
        .where(db_models.Case.patient_id == patient_id)
        .order_by(db_models.Case.creation_date.desc())
    )
    all_cases_db = cases_result.scalars().all()

    all_cases = [
        CaseModelScheema.model_validate(case).model_dump() for case in all_cases_db
    ]
    first_case_direction_details: Optional[FirstCaseReferralDetailsSchema] = None
    last_case_with_relations: Optional[db_models.Case] = None
    case_owner: Optional[CaseOwnerResponse] = None

    if all_cases_db:
        first_case_db = all_cases_db[0]
        if case_id:
            first_case_id = case_id
        else:
            first_case_id = first_case_db.id

        referral_db = await db.scalar(
            select(db_models.Referral).where(
                db_models.Referral.case_id == first_case_id
            )
        )
        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == first_case_id)
            .options(
                selectinload(db_models.Case.case_parameters),
                selectinload(db_models.Case.report).options(
                    selectinload(db_models.Report.doctor_diagnoses).options(
                        selectinload(db_models.DoctorDiagnosis.doctor),
                        selectinload(db_models.DoctorDiagnosis.signature).options(
                            selectinload(db_models.ReportSignature.doctor),
                            selectinload(db_models.ReportSignature.doctor_signature),
                        ),
                    )
                ),
                selectinload(db_models.Case.samples)
                .selectinload(db_models.Sample.cassette)
                .selectinload(db_models.Cassette.glass),
            )
        )
        last_case_with_relations = last_case_full_info_result.scalar_one_or_none()

        if referral_db:
            direction_files_result = await db.execute(
                select(db_models.ReferralAttachment).where(
                    db_models.ReferralAttachment.referral_id == referral_db.id
                )
            )
            direction_files_db = direction_files_result.scalars().all()

            attachments_for_response = []
            for file_db in direction_files_db:
                file_url = generate_file_url(file_db.id, last_case_with_relations.id)
                attachments_for_response.append(
                    ReferralFileSchema(
                        id=file_db.id,
                        file_name=file_db.filename,
                        file_type=file_db.content_type,
                        file_url=file_url,
                    )
                )

            first_case_direction_details = FirstCaseReferralDetailsSchema(
                id=last_case_with_relations.id,
                case_code=last_case_with_relations.case_code,
                creation_date=last_case_with_relations.creation_date,
                pathohistological_conclusion=last_case_with_relations.pathohistological_conclusion,
                microdescription=last_case_with_relations.microdescription,
                attachments=attachments_for_response,
                grossing_status=last_case_with_relations.grossing_status,
                patient_cor_id=last_case_with_relations.patient_id,
            )
    if last_case_with_relations:
        case_owner = await get_case_owner(
            db=db, case_id=last_case_with_relations.id, doctor_id=current_doctor_id
        )
    return PatientCasesWithReferralsResponse(
        all_cases=all_cases,
        case_details=last_case_with_relations,
        case_owner=case_owner,
        first_case_direction=first_case_direction_details,
    )


async def get_patient_case_details_for_glass_page(
    db: AsyncSession,
    patient_id: str,
    current_doctor_id: str,
    router: APIRouter,
    case_id=Optional[str],
) -> PatientGlassPageResponse:
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
    report_details = None
    case_owner: Optional[CaseOwnerResponse] = None
    last_case_with_relations: Optional[db_models.Case] = None

    if all_cases_db:
        first_case_db = all_cases_db[0]
        if case_id:
            first_case_id = case_id
        else:
            first_case_id = first_case_db.id
        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == first_case_id)
            .options(
                selectinload(db_models.Case.case_parameters),
                selectinload(db_models.Case.report).options(
                    selectinload(db_models.Report.doctor_diagnoses).options(
                        selectinload(db_models.DoctorDiagnosis.doctor),
                        selectinload(db_models.DoctorDiagnosis.signature).options(
                            selectinload(db_models.ReportSignature.doctor),
                            selectinload(db_models.ReportSignature.doctor_signature),
                        ),
                    )
                ),
                selectinload(db_models.Case.samples)
                .selectinload(db_models.Sample.cassette)
                .selectinload(db_models.Cassette.glass),
            )
        )
        last_case_with_relations = last_case_full_info_result.scalar_one_or_none()
        patient_db = await get_patient_by_corid(
            db=db, cor_id=last_case_with_relations.patient_id
        )
        referral_db = await get_referral_by_case(
            db=db, case_id=last_case_with_relations.id
        )

        report_details = await _format_final_report_response(
            db=db,
            db_report=last_case_with_relations.report,
            db_case_parameters=last_case_with_relations.case_parameters,
            router=router,
            patient_db=patient_db,
            referral_db=referral_db,
            case_db=last_case_with_relations,
            current_doctor_id=current_doctor_id,
        )
        samples_result = await db.execute(
            select(db_models.Sample)
            .where(db_models.Sample.case_id == last_case_with_relations.id)
            .options(
                selectinload(db_models.Sample.cassette).selectinload(
                    db_models.Cassette.glass
                )
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
                    cassette_db.glass, key=lambda glass: glass.glass_number
                )

                glasses_for_cassette = [
                    GlassModelScheema.model_validate(glass).model_dump()
                    for glass in sorted_glasses_db
                ]

                cassette_schematized = CassetteForGlassPage.model_validate(
                    cassette_db
                ).model_dump()
                cassette_schematized["glasses"] = glasses_for_cassette
                cassettes_for_sample.append(cassette_schematized)

            sample_schematized = SampleForGlassPage.model_validate(
                sample_db
            ).model_dump()
            sample_schematized["cassettes"] = cassettes_for_sample
            first_case_samples_schematized.append(sample_schematized)

        first_case_details_for_glass = FirstCaseGlassDetailsSchema(
            id=last_case_with_relations.id,
            case_code=last_case_with_relations.case_code,
            creation_date=last_case_with_relations.creation_date,
            pathohistological_conclusion=last_case_with_relations.pathohistological_conclusion,
            microdescription=last_case_with_relations.microdescription,
            samples=first_case_samples_schematized,
            grossing_status=last_case_with_relations.grossing_status,
            patient_cor_id=last_case_with_relations.patient_id,
            is_printed_cassette=last_case_with_relations.is_printed_cassette,
            is_printed_glass=last_case_with_relations.is_printed_glass,
            is_printed_qr=last_case_with_relations.is_printed_qr,
        )
    if last_case_with_relations:
        case_owner = await get_case_owner(
            db=db, case_id=last_case_with_relations.id, doctor_id=current_doctor_id
        )
    return PatientGlassPageResponse(
        all_cases=all_cases_schematized,
        first_case_details_for_glass=first_case_details_for_glass,
        case_owner=case_owner,
        report_details=report_details,
    )


async def get_current_cases_glass_details(
    db: AsyncSession,
    current_doctor_id: str,
    router: APIRouter,
    case_id=Optional[str],
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
    case_id_query = case_id
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
            db_models.Case.is_printed_cassette,
            db_models.Case.is_printed_glass,
            db_models.Case.is_printed_qr,
            literal_column("1").label("sort_priority"),
        ).where(
            and_(
                func.substr(db_models.Case.case_code, 1, 1).in_(["F", "U"]),
                db_models.Case.grossing_status
                != db_models.Grossing_status.COMPLETED.value,
            )
        )
    ).subquery("cases_fu")

    scanned_glass_exists_clause = (
        select(1)
        .select_from(db_models.Sample)
        .join(db_models.Cassette, db_models.Sample.id == db_models.Cassette.sample_id)
        .join(db_models.Glass, db_models.Cassette.id == db_models.Glass.cassette_id)
        .where(db_models.Sample.case_id == db_models.Case.id)
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
            db_models.Case.is_printed_cassette,
            db_models.Case.is_printed_glass,
            db_models.Case.is_printed_qr,
            literal_column("2").label("sort_priority"),
        ).where(
            and_(
                func.substr(db_models.Case.case_code, 1, 1) == "S",
                db_models.Case.grossing_status
                != db_models.Grossing_status.COMPLETED.value,
                scanned_glass_exists_clause,
            )
        )
    ).subquery("cases_s")

    combined_query_for_data = select(
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
        cases_fu_subquery.c.sort_priority,
        cases_fu_subquery.c.is_printed_cassette,
        cases_fu_subquery.c.is_printed_glass,
        cases_fu_subquery.c.is_printed_qr,
    ).union_all(
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
            cases_s_subquery.c.sort_priority,
            cases_s_subquery.c.is_printed_cassette,
            cases_s_subquery.c.is_printed_glass,
            cases_s_subquery.c.is_printed_qr,
        )
    )

    final_ordered_query = combined_query_for_data.order_by(
        combined_query_for_data.c.sort_priority.asc(),
        combined_query_for_data.c.creation_date.desc(),
    )

    paginated_results = await db.execute(final_ordered_query.offset(skip).limit(limit))
    all_current_cases_raw = paginated_results.all()

    current_cases_list: List[CaseModelScheema] = []
    first_case_details_for_glass: Optional[FirstCaseGlassDetailsSchema] = None
    report_details: Optional[FinalReportResponseSchema] = None
    case_owner: Optional[CaseOwnerResponse] = None
    last_case_with_relations: Optional[db_models.Case] = None

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
        is_printed_cassette = row.is_printed_cassette
        is_printed_glass = row.is_printed_glass
        is_printed_qr = row.is_printed_qr
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
                pathohistological_conclusion=pathohistological_conclusion,
                microdescription=microdescription,
                is_printed_cassette=is_printed_cassette,
                is_printed_glass=is_printed_glass,
                is_printed_qr=is_printed_qr,
            )
        )

    # !!!Детали последнего кейса!!!
    if all_current_cases_raw:
        first_case_db = all_current_cases_raw[0]
        if case_id_query:
            first_case_id = case_id_query
        else:
            first_case_id = first_case_db.id

        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == first_case_id)
            .options(
                selectinload(db_models.Case.case_parameters),
                selectinload(db_models.Case.report).options(
                    selectinload(db_models.Report.doctor_diagnoses).options(
                        selectinload(db_models.DoctorDiagnosis.doctor),
                        selectinload(db_models.DoctorDiagnosis.signature).options(
                            selectinload(db_models.ReportSignature.doctor),
                            selectinload(db_models.ReportSignature.doctor_signature),
                        ),
                    )
                ),
                selectinload(db_models.Case.samples)
                .selectinload(db_models.Sample.cassette)
                .selectinload(db_models.Cassette.glass),
            )
        )
        last_case_with_relations = last_case_full_info_result.scalar_one_or_none()
        patient_db = await get_patient_by_corid(
            db=db, cor_id=last_case_with_relations.patient_id
        )
        referral_db = await get_referral_by_case(
            db=db, case_id=last_case_with_relations.id
        )

        report_details = await _format_final_report_response(
            db=db,
            db_report=last_case_with_relations.report,
            db_case_parameters=last_case_with_relations.case_parameters,
            router=router,
            patient_db=patient_db,
            referral_db=referral_db,
            case_db=last_case_with_relations,
            current_doctor_id=current_doctor_id,
        )
        samples_result = await db.execute(
            select(db_models.Sample)
            .where(db_models.Sample.case_id == last_case_with_relations.id)
            .options(
                selectinload(db_models.Sample.cassette).selectinload(
                    db_models.Cassette.glass
                )
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
                    cassette_db.glass, key=lambda glass: glass.glass_number
                )

                glasses_for_cassette = [
                    GlassModelScheema.model_validate(glass).model_dump()
                    for glass in sorted_glasses_db
                ]

                cassette_schematized = CassetteForGlassPage.model_validate(
                    cassette_db
                ).model_dump()
                cassette_schematized["glasses"] = glasses_for_cassette
                cassettes_for_sample.append(cassette_schematized)

            sample_schematized = SampleForGlassPage.model_validate(
                sample_db
            ).model_dump()
            sample_schematized["cassettes"] = cassettes_for_sample
            first_case_samples_schematized.append(sample_schematized)

        first_case_details_for_glass = FirstCaseGlassDetailsSchema(
            id=last_case_with_relations.id,
            case_code=last_case_with_relations.case_code,
            creation_date=last_case_with_relations.creation_date,
            pathohistological_conclusion=last_case_with_relations.pathohistological_conclusion,
            microdescription=last_case_with_relations.microdescription,
            samples=first_case_samples_schematized,
            grossing_status=last_case_with_relations.grossing_status,
            patient_cor_id=last_case_with_relations.patient_id,
            is_printed_cassette=last_case_with_relations.is_printed_cassette,
            is_printed_glass=last_case_with_relations.is_printed_glass,
            is_printed_qr=last_case_with_relations.is_printed_qr,
        )
    if last_case_with_relations:
        case_owner = await get_case_owner(
            db=db, case_id=last_case_with_relations.id, doctor_id=current_doctor_id
        )
    return PatientGlassPageResponse(
        all_cases=current_cases_list,
        first_case_details_for_glass=first_case_details_for_glass,
        case_owner=case_owner,
        report_details=report_details,
    )


async def get_single_case_details_for_glass_page(
    db: AsyncSession, case_id: str, current_doctor_id: str, router: APIRouter
) -> SingleCaseGlassPageResponse:
    """
    Асинхронно получает список всех кейсов пациента и полную детализацию (включая все стёкла)
    для первого кейса, отсортированного по дате создания.
    Используется для вкладки "Стёкла" на странице врача.
    """
    result = await db.execute(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    case_db = result.scalar_one_or_none()
    if not case_db:
        return None

    first_case_details_for_glass: Optional[FirstCaseGlassDetailsSchema] = None
    report_details = None
    case_owner: Optional[CaseOwnerResponse] = None
    last_case_with_relations: Optional[db_models.Case] = None

    if case_db:
        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == case_db.id)
            .options(
                selectinload(db_models.Case.case_parameters),
                selectinload(db_models.Case.report).options(
                    selectinload(db_models.Report.doctor_diagnoses).options(
                        selectinload(db_models.DoctorDiagnosis.doctor),
                        selectinload(db_models.DoctorDiagnosis.signature).options(
                            selectinload(db_models.ReportSignature.doctor),
                            selectinload(db_models.ReportSignature.doctor_signature),
                        ),
                    )
                ),
                selectinload(db_models.Case.samples)
                .selectinload(db_models.Sample.cassette)
                .selectinload(db_models.Cassette.glass),
            )
        )
        last_case_with_relations = last_case_full_info_result.scalar_one_or_none()
        patient_db = await get_patient_by_corid(
            db=db, cor_id=last_case_with_relations.patient_id
        )
        referral_db = await get_referral_by_case(
            db=db, case_id=last_case_with_relations.id
        )

        report_details = await _format_final_report_response(
            db=db,
            db_report=last_case_with_relations.report,
            db_case_parameters=last_case_with_relations.case_parameters,
            router=router,
            patient_db=patient_db,
            referral_db=referral_db,
            case_db=last_case_with_relations,
            current_doctor_id=current_doctor_id,
        )

        samples_result = await db.execute(
            select(db_models.Sample)
            .where(db_models.Sample.case_id == case_db.id)
            .options(
                selectinload(db_models.Sample.cassette).selectinload(
                    db_models.Cassette.glass
                )
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
                    cassette_db.glass, key=lambda glass: glass.glass_number
                )

                glasses_for_cassette = [
                    GlassModelScheema.model_validate(glass).model_dump()
                    for glass in sorted_glasses_db
                ]

                cassette_schematized = CassetteForGlassPage.model_validate(
                    cassette_db
                ).model_dump()
                cassette_schematized["glasses"] = glasses_for_cassette
                cassettes_for_sample.append(cassette_schematized)

            sample_schematized = SampleForGlassPage.model_validate(
                sample_db
            ).model_dump()
            sample_schematized["cassettes"] = cassettes_for_sample
            first_case_samples_schematized.append(sample_schematized)

        first_case_details_for_glass = FirstCaseGlassDetailsSchema(
            id=case_db.id,
            case_code=case_db.case_code,
            creation_date=case_db.creation_date,
            samples=first_case_samples_schematized,
            grossing_status=case_db.grossing_status,
            patient_cor_id=case_db.patient_id,
            microdescription=case_db.microdescription,
            is_printed_cassette=case_db.is_printed_cassette,
            is_printed_glass=case_db.is_printed_glass,
            is_printed_qr=case_db.is_printed_qr,
        )
    if case_db:
        case_owner = await get_case_owner(
            db=db, case_id=case_db.id, doctor_id=current_doctor_id
        )
    return SingleCaseGlassPageResponse(
        single_case_for_glass_page=first_case_details_for_glass,
        case_owner=case_owner,
        report_details=report_details,
    )


async def update_case_pathohistological_conclusion(
    db: AsyncSession, case_id: str, body: UpdatePathohistologicalConclusion
) -> PathohistologicalConclusionResponse | None:
    """Асинхронно получает информацию о кейсе по его ID, включая связанные банки."""
    result = await db.execute(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    case_db = result.scalar_one_or_none()

    if case_db:
        if case_db.grossing_status == db_models.Grossing_status.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                detail=f"Запрещено редактировать закрытый кейс",
            )
        case_db.pathohistological_conclusion = body.pathohistological_conclusion
        await db.commit()
        await db.refresh(case_db)
        response = PathohistologicalConclusionResponse(
            pathohistological_conclusion=body.pathohistological_conclusion
        )
        return response
    else:
        return None


async def update_case_microdescription(
    db: AsyncSession, case_id: str, body: UpdateMicrodescription
) -> MicrodescriptionResponse | None:
    """Асинхронно получает информацию о кейсе по его ID, включая связанные банки."""
    result = await db.execute(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    case_db = result.scalar_one_or_none()
    if case_db:
        if case_db.grossing_status == db_models.Grossing_status.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                detail=f"Запрещено редактировать закрытый кейс",
            )
        case_db.microdescription = body.microdescription
        await db.commit()
        await db.refresh(case_db)
        response = MicrodescriptionResponse(microdescription=body.microdescription)
        return response
    else:
        return None


async def get_patient_case_details_for_excision_page(
    db: AsyncSession, patient_id: str, current_doctor_id: str, case_id=Optional[str]
) -> PatientExcisionPageResponse:  #
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
    case_owner: Optional[CaseOwnerResponse] = None

    if all_cases_db:
        last_case_db = all_cases_db[0]
        if case_id:
            first_case_id = case_id
        else:
            first_case_id = last_case_db.id
        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == first_case_id)
            .options(
                selectinload(db_models.Case.case_parameters),
                selectinload(db_models.Case.samples),
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
                last_case_with_relations.samples, key=lambda s: s.sample_number
            )

            for sample_db in sorted_samples:

                samples_for_excision_page.append(
                    SampleForExcisionPage(
                        id=sample_db.id,
                        sample_number=sample_db.sample_number,
                        is_archived=sample_db.archive,
                        macro_description=sample_db.macro_description,
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
                patient_cor_id=last_case_with_relations.patient_id,
                is_printed_cassette=last_case_with_relations.is_printed_cassette,
                is_printed_glass=last_case_with_relations.is_printed_glass,
                is_printed_qr=last_case_with_relations.is_printed_qr,
            )
    if last_case_details_for_excision:
        case_owner = await get_case_owner(
            db=db,
            case_id=last_case_details_for_excision.id,
            doctor_id=current_doctor_id,
        )
    return PatientExcisionPageResponse(
        all_cases=all_cases_schematized,
        last_case_details_for_excision=last_case_details_for_excision,
        case_owner=case_owner,
    )


async def get_single_case_details_for_excision_page(
    db: AsyncSession, case_id: str, current_doctor_id: str
) -> SingleCaseExcisionPageResponse:

    last_case_details_for_excision: Optional[LastCaseExcisionDetailsSchema] = None
    case_owner: Optional[CaseOwnerResponse] = None

    last_case_full_info_result = await db.execute(
        select(db_models.Case)
        .where(db_models.Case.id == case_id)
        .options(
            selectinload(db_models.Case.case_parameters),
            selectinload(db_models.Case.samples),
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
            last_case_with_relations.samples, key=lambda s: s.sample_number
        )

        for sample_db in sorted_samples:
            samples_for_excision_page.append(
                SampleForExcisionPage(
                    id=sample_db.id,
                    sample_number=sample_db.sample_number,
                    is_archived=sample_db.archive,
                    macro_description=sample_db.macro_description,
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
            patient_cor_id=last_case_with_relations.patient_id,
            is_printed_cassette=last_case_with_relations.is_printed_cassette,
            is_printed_glass=last_case_with_relations.is_printed_glass,
            is_printed_qr=last_case_with_relations.is_printed_qr,
        )
    if last_case_details_for_excision:
        case_owner = await get_case_owner(
            db=db,
            case_id=last_case_details_for_excision.id,
            doctor_id=current_doctor_id,
        )
    return SingleCaseExcisionPageResponse(
        case_details_for_excision=last_case_details_for_excision, case_owner=case_owner
    )


async def _format_report_response(
    db: AsyncSession,
    db_report: db_models.Report,
    router: APIRouter,
    case_db: db_models.Case,
) -> ReportResponseSchema:
    """
    Форматирует объект Report из базы данных в ReportResponseSchema.
    Теперь включает агрегированные диагнозы и их подписи,
    а также корректно обрабатывает перенос полей диагнозов в DoctorDiagnosis.
    """

    await db.refresh(
        db_report, attribute_names=["doctor_diagnoses", "attached_glass_ids"]
    )

    await db.execute(
        select(db_models.DoctorDiagnosis)
        .where(db_models.DoctorDiagnosis.report_id == db_report.id)
        .options(
            selectinload(db_models.DoctorDiagnosis.doctor),
            selectinload(db_models.DoctorDiagnosis.signature).selectinload(
                db_models.ReportSignature.doctor
            ),
            selectinload(db_models.DoctorDiagnosis.signature).selectinload(
                db_models.ReportSignature.doctor_signature
            ),
        )
    )

    macro_desc_from_params = (
        case_db.case_parameters.macro_description if case_db.case_parameters else None
    )

    attached_glasses_schematized: List[GlassModelScheema] = []
    if db_report.attached_glass_ids:
        attached_glasses_db_result = await db.execute(
            select(db_models.Glass).where(
                db_models.Glass.id.in_(db_report.attached_glass_ids)
            )
        )
        attached_glasses_db = attached_glasses_db_result.scalars().all()

        attached_glasses_schematized = [
            GlassModelScheema.model_validate(g) for g in attached_glasses_db
        ]

    doctor_diagnoses_schematized: List[DoctorDiagnosisSchema] = []
    if db_report:
        for dd_db in sorted(db_report.doctor_diagnoses, key=lambda x: x.created_at):
            doctor_data = (
                DoctorResponseForSignature.model_validate(dd_db.doctor)
                if dd_db.doctor
                else None
            )

            signature_data: Optional[ReportSignatureSchema] = None
            if dd_db.signature:
                signer_doctor_data = (
                    DoctorResponseForSignature.model_validate(dd_db.signature.doctor)
                    if dd_db.signature.doctor
                    else None
                )

                doctor_sig_response: Optional[DoctorSignatureResponse] = None
                if dd_db.signature.doctor_signature:
                    signature_url = None
                    if dd_db.signature.doctor_signature.signature_scan_data:
                        signature_url = router.url_path_for(
                            "get_signature_attachment",
                            signature_id=dd_db.signature.doctor_signature.id,
                        )

                    doctor_sig_response = DoctorSignatureResponse(
                        id=dd_db.signature.doctor_signature.id,
                        doctor_id=dd_db.signature.doctor_signature.doctor_id,
                        signature_name=dd_db.signature.doctor_signature.signature_name,
                        signature_scan_data=signature_url,
                        signature_scan_type=dd_db.signature.doctor_signature.signature_scan_type,
                        is_default=dd_db.signature.doctor_signature.is_default,
                        created_at=dd_db.signature.doctor_signature.created_at,
                    )
                signature_data = ReportSignatureSchema(
                    id=dd_db.signature.id,
                    doctor=signer_doctor_data,
                    signed_at=dd_db.signature.signed_at,
                    doctor_signature=doctor_sig_response,
                )

            doctor_diagnoses_schematized.append(
                DoctorDiagnosisSchema(
                    id=dd_db.id,
                    report_id=dd_db.report_id,
                    doctor=doctor_data,
                    created_at=dd_db.created_at,
                    immunohistochemical_profile=dd_db.immunohistochemical_profile,
                    molecular_genetic_profile=dd_db.molecular_genetic_profile,
                    pathomorphological_diagnosis=dd_db.pathomorphological_diagnosis,
                    icd_code=dd_db.icd_code,
                    comment=dd_db.comment,
                    report_macrodescription=dd_db.report_macrodescription,
                    report_microdescription=dd_db.report_microdescription,
                    signature=signature_data,
                )
            )

    return ReportResponseSchema(
        id=db_report.id,
        case_id=db_report.case_id if db_report else None,
        case_details=case_db,
        macro_description_from_case_params=macro_desc_from_params,
        microdescription_from_case=case_db.microdescription if case_db else None,
        doctor_diagnoses=doctor_diagnoses_schematized if db_report else None,
        attached_glasses=attached_glasses_schematized,
    )


async def get_report_by_case_id(
    db: AsyncSession, case_id: str, router: APIRouter, current_doctor_id: str
) -> CaseIDReportPageResponse:
    """
    Получает заключение для конкретного кейса. Если заключения нет, оно будет создано.
    Обновлено для работы с подписями, привязанными к DoctorDiagnosis.
    """
    case_db = await db.execute(
        select(db_models.Case)
        .where(db_models.Case.id == case_id)
        .options(
            selectinload(db_models.Case.case_parameters),
            selectinload(db_models.Case.report)
            .selectinload(db_models.Report.doctor_diagnoses)
            .options(
                selectinload(db_models.DoctorDiagnosis.doctor),
                selectinload(db_models.DoctorDiagnosis.signature).options(
                    selectinload(db_models.ReportSignature.doctor),
                    selectinload(db_models.ReportSignature.doctor_signature),
                ),
            ),
            selectinload(db_models.Case.samples)
            .selectinload(db_models.Sample.cassette)
            .selectinload(db_models.Cassette.glass),
        )
    )
    case_db = case_db.scalar_one_or_none()
    all_samples_for_last_case_schematized: List[SampleTestForGlassPage] = []
    report_details = None
    case_owner: Optional[CaseOwnerResponse] = None
    if case_db:
        last_case_for_report = CaseModelScheema.model_validate(case_db)

        if not case_db.report:
            new_report = db_models.Report(case_id=case_db.id)
            db.add(new_report)
            await db.commit()
            await db.refresh(new_report)
            case_db.report = new_report

        report_details = await _format_report_response(
            db=db, db_report=case_db.report, router=router, case_db=case_db
        )
        report_details.concatenated_macro_description = (
            f"{report_details.macro_description_from_case_params}"
            if report_details.macro_description_from_case_params
            else " "
        )

        for sample_db in case_db.samples:

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
                    cassette_db.glass, key=lambda glass: glass.glass_number
                )
                glasses_for_cassette: List[GlassTestModelScheema] = []
                for glass in sorted_glasses_db:
                    glass = GlassTestModelScheema(
                        id=glass.id,
                        glass_number=glass.glass_number,
                        cassette_id=glass.cassette_id,
                        staining=glass.staining,
                    )
                    glasses_for_cassette.append(glass)

                cassette_schematized = CassetteTestForGlassPage(
                    id=cassette_db.id,
                    cassette_number=cassette_db.cassette_number,
                    sample_id=cassette_db.sample_id,
                )
                cassette_schematized.glasses = glasses_for_cassette
                cassettes_for_sample.append(cassette_schematized)

            sample_schematized = SampleTestForGlassPage(
                id=sample_db.id,
                sample_number=sample_db.sample_number,
                case_id=sample_db.case_id,
                sample_macro_description=sample_db.macro_description,
            )
            report_details.concatenated_macro_description += (
                f"| {sample_db.macro_description}"
                if sample_db.macro_description
                else ""
            )
            sample_schematized.cassettes = cassettes_for_sample
            all_samples_for_last_case_schematized.append(sample_schematized)

        first_case_details_for_glass = FirstCaseTestGlassDetailsSchema(
            id=case_db.id,
            case_code=case_db.case_code,
            creation_date=case_db.creation_date,
            samples=all_samples_for_last_case_schematized,
            grossing_status=case_db.grossing_status,
        )
    if case_db:
        case_owner = await get_case_owner(
            db=db, case_id=case_db.id, doctor_id=current_doctor_id
        )
    general_response = CaseIDReportPageResponse(
        last_case_for_report=case_db,
        case_owner=case_owner,
        report_details=report_details,
        all_glasses_for_last_case=first_case_details_for_glass,
    )
    return general_response


async def get_patient_report_page_data(
    db: AsyncSession,
    patient_id: str,
    router: APIRouter,
    current_doctor_id: str,
    case_id=Optional[str],
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
    all_cases_schematized = [
        CaseModelScheema.model_validate(case) for case in all_cases_db
    ]

    last_case_for_report: Optional[CaseModelScheema] = None
    report_details: Optional[ReportResponseSchema] = None
    all_samples_for_last_case_schematized: List[SampleTestForGlassPage] = []
    first_case_details_for_glass: Optional[FirstCaseTestGlassDetailsSchema] = None
    case_owner: Optional[CaseOwnerResponse] = None

    if all_cases_db:
        last_case_db = all_cases_db[0]
        if case_id:
            first_case_id = case_id
        else:
            first_case_id = last_case_db.id

        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == first_case_id)
            .options(
                selectinload(db_models.Case.case_parameters),
                selectinload(db_models.Case.report)
                .selectinload(db_models.Report.doctor_diagnoses)
                .options(
                    selectinload(db_models.DoctorDiagnosis.doctor),
                    selectinload(db_models.DoctorDiagnosis.signature).options(
                        selectinload(db_models.ReportSignature.doctor),
                        selectinload(db_models.ReportSignature.doctor_signature),
                    ),
                ),
                selectinload(db_models.Case.samples)
                .selectinload(db_models.Sample.cassette)
                .selectinload(db_models.Cassette.glass),
            )
        )
        last_case_with_relations = last_case_full_info_result.scalar_one_or_none()

        if last_case_with_relations:
            last_case_for_report = CaseModelScheema.model_validate(
                last_case_with_relations
            )

            if not last_case_with_relations.report:
                new_report = db_models.Report(case_id=last_case_with_relations.id)
                db.add(new_report)
                await db.commit()
                await db.refresh(new_report)
                last_case_with_relations.report = new_report

            report_details = await _format_report_response(
                db=db,
                db_report=last_case_with_relations.report,
                router=router,
                case_db=last_case_with_relations,
            )
            report_details.concatenated_macro_description = (
                f"{report_details.macro_description_from_case_params}"
                if report_details.macro_description_from_case_params
                else " "
            )

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
                        cassette_db.glass, key=lambda glass: glass.glass_number
                    )
                    glasses_for_cassette: List[GlassTestModelScheema] = []
                    for glass in sorted_glasses_db:
                        glass = GlassTestModelScheema(
                            id=glass.id,
                            glass_number=glass.glass_number,
                            cassette_id=glass.cassette_id,
                            staining=glass.staining,
                        )
                        glasses_for_cassette.append(glass)

                    cassette_schematized = CassetteTestForGlassPage(
                        id=cassette_db.id,
                        cassette_number=cassette_db.cassette_number,
                        sample_id=cassette_db.sample_id,
                    )
                    cassette_schematized.glasses = glasses_for_cassette
                    cassettes_for_sample.append(cassette_schematized)

                sample_schematized = SampleTestForGlassPage(
                    id=sample_db.id,
                    sample_number=sample_db.sample_number,
                    case_id=sample_db.case_id,
                    sample_macro_description=sample_db.macro_description,
                )
                report_details.concatenated_macro_description += (
                    f"| {sample_db.macro_description}"
                    if sample_db.macro_description
                    else ""
                )
                sample_schematized.cassettes = cassettes_for_sample
                all_samples_for_last_case_schematized.append(sample_schematized)

            first_case_details_for_glass = FirstCaseTestGlassDetailsSchema(
                id=last_case_with_relations.id,
                case_code=last_case_with_relations.case_code,
                creation_date=last_case_with_relations.creation_date,
                samples=all_samples_for_last_case_schematized,
                grossing_status=last_case_with_relations.grossing_status,
            )
    if last_case_for_report:
        case_owner = await get_case_owner(
            db=db, case_id=last_case_for_report.id, doctor_id=current_doctor_id
        )
    return PatientTestReportPageResponse(
        all_cases=all_cases_schematized,
        last_case_for_report=last_case_for_report,
        case_owner=case_owner,
        report_details=report_details,
        all_glasses_for_last_case=first_case_details_for_glass,
    )


async def create_or_update_report_and_diagnosis(
    db: AsyncSession,
    case_id: str,
    router: APIRouter,
    update_data: ReportAndDiagnosisUpdateSchema,
    current_doctor_id: str,
) -> ReportResponseSchema:
    """
    Создает или обновляет отчет и/или запись диагноза доктора.
    - Владелец кейса может прикреплять/откреплять стекла и создавать/обновлять записи диагнозов.
    - Доктора, не являющиеся владельцами кейса, могут только создавать/обновлять свои записи диагнозов.
    """

    case_db = await db.scalar(
        select(db_models.Case)
        .where(db_models.Case.id == case_id)
        .options(selectinload(db_models.Case.case_parameters))
    )
    if not case_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Кейс с ID '{case_id}' не найден.",
        )
    if case_db.grossing_status == db_models.Grossing_status.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"Запрещено редактировать закрытый кейс",
        )
    report_result = await db.execute(
        select(db_models.Report)
        .where(db_models.Report.case_id == case_id)
        .options(
            selectinload(db_models.Report.doctor_diagnoses).options(
                selectinload(db_models.DoctorDiagnosis.doctor),
                selectinload(db_models.DoctorDiagnosis.signature).options(
                    selectinload(db_models.ReportSignature.doctor),
                    selectinload(db_models.ReportSignature.doctor_signature),
                ),
            )
        )
    )
    db_report = report_result.scalar_one_or_none()

    if not db_report:

        db_report = db_models.Report(case_id=case_id, attached_glass_ids=[])
        db.add(db_report)
        await db.flush()

    is_case_owner = False
    if case_db.case_owner == current_doctor_id:
        is_case_owner = True
    if is_case_owner:
        if update_data.attached_glass_ids is not None:
            db_report.attached_glass_ids = update_data.attached_glass_ids
        case_db.microdescription = (
            update_data.doctor_diagnosis_data.report_microdescription
            if update_data.doctor_diagnosis_data.report_microdescription
            else None
        )
        await db.commit()
        await db.refresh(case_db)
    else:
        if update_data.attached_glass_ids is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав для изменения прикрепленных стекол.",
            )

    if update_data.doctor_diagnosis_data:
        existing_diagnosis = await db.scalar(
            select(db_models.DoctorDiagnosis).where(
                db_models.DoctorDiagnosis.report_id == db_report.id,
                db_models.DoctorDiagnosis.doctor_id == current_doctor_id,
            )
        )

        diagnosis_data = update_data.doctor_diagnosis_data.model_dump(
            exclude_unset=True
        )

        if not any(diagnosis_data.values()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Должно быть предоставлено хотя бы одно поле диагноза (иммунопрофиль, молекулярно-генетический профиль, патоморфологический диагноз, микроописание, макроописание, icd_code или комментарий).",
            )

        if existing_diagnosis:

            for field, value in diagnosis_data.items():
                if value is not None:
                    setattr(existing_diagnosis, field, value)
            existing_diagnosis.updated_at = func.now()
        else:

            new_diagnosis_entry = db_models.DoctorDiagnosis(
                report_id=db_report.id,
                doctor_id=current_doctor_id,
                created_at=func.now(),
                **diagnosis_data,
            )
            db.add(new_diagnosis_entry)

    await db.commit()
    await db.refresh(db_report)

    return await _format_report_response(
        db=db, db_report=db_report, router=router, case_db=case_db
    )


async def add_diagnosis_signature(
    db: AsyncSession,
    diagnosis_entry_id: str,
    doctor_id: str,
    router: APIRouter,
    doctor_signature_id: Optional[str] = None,
) -> ReportResponseSchema:
    """
    Добавляет подпись доктора к конкретной записи диагноза.
    """

    diagnosis_entry_result = await db.execute(
        select(db_models.DoctorDiagnosis)
        .where(db_models.DoctorDiagnosis.id == diagnosis_entry_id)
        .options(
            selectinload(db_models.DoctorDiagnosis.doctor),
            selectinload(db_models.DoctorDiagnosis.report),
            selectinload(db_models.DoctorDiagnosis.signature),
        )
    )
    diagnosis_entry = diagnosis_entry_result.scalar_one_or_none()

    if not diagnosis_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Запись диагноза с ID '{diagnosis_entry_id}' не найдена.",
        )

    if diagnosis_entry.doctor_id != doctor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы можете подписать только собственный диагноз.",
        )

    if diagnosis_entry.signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Эта запись диагноза уже была подписана.",
        )

    doctor = await db.scalar(
        select(db_models.Doctor).where(db_models.Doctor.doctor_id == doctor_id)
    )
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Доктор с ID '{doctor_id}' не найден.",
        )

    target_doctor_signature: Optional[db_models.DoctorSignature] = None
    if doctor_signature_id:
        target_doctor_signature = await db.scalar(
            select(db_models.DoctorSignature).where(
                db_models.DoctorSignature.id == doctor_signature_id,
                db_models.DoctorSignature.doctor_id == doctor.id,
            )
        )
        if not target_doctor_signature:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Указанная подпись врача не найдена или принадлежит другому врачу.",
            )
    else:
        target_doctor_signature = await db.scalar(
            select(db_models.DoctorSignature).where(
                db_models.DoctorSignature.doctor_id == doctor.id,
                db_models.DoctorSignature.is_default == True,
            )
        )
        if not target_doctor_signature:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не найдена подпись по умолчанию для этого врача. Укажите ID подписи или загрузите подпись по умолчанию.",
            )
    new_signature = db_models.ReportSignature(
        diagnosis_entry_id=diagnosis_entry.id,
        doctor_id=doctor.id,
        doctor_signature_id=target_doctor_signature.id,
        signed_at=func.now(),
    )
    db.add(new_signature)

    await db.commit()
    await db.refresh(new_signature)
    await db.refresh(diagnosis_entry)

    case_db = await db.scalar(
        select(db_models.Case)
        .where(db_models.Case.id == diagnosis_entry.report.case_id)
        .options(selectinload(db_models.Case.case_parameters))
    )
    return await _format_report_response(
        db=db, db_report=diagnosis_entry.report, router=router, case_db=case_db
    )


async def get_patient_final_report_page_data(
    db: AsyncSession,
    patient_id: str,
    router: APIRouter,
    current_doctor_id: str,
    case_id=Optional[str],
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
    all_cases_schematized = [
        CaseModelScheema.model_validate(case) for case in all_cases_db
    ]

    report_details: Optional[ReportResponseSchema] = None
    last_case_details: Optional[CaseModelScheema] = None
    case_owner: Optional[CaseOwnerResponse] = None
    last_case_with_relations: Optional[db_models.Case] = None

    if all_cases_db:
        last_case_db_summary = all_cases_db[0]
        if case_id:
            first_case_id = case_id
        else:
            first_case_id = last_case_db_summary.id

        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == first_case_id)
            .options(
                selectinload(db_models.Case.case_parameters),
                selectinload(db_models.Case.report).options(
                    selectinload(db_models.Report.doctor_diagnoses).options(
                        selectinload(db_models.DoctorDiagnosis.doctor),
                        selectinload(db_models.DoctorDiagnosis.signature).options(
                            selectinload(db_models.ReportSignature.doctor),
                            selectinload(db_models.ReportSignature.doctor_signature),
                        ),
                    )
                ),
                selectinload(db_models.Case.samples)
                .selectinload(db_models.Sample.cassette)
                .selectinload(db_models.Cassette.glass),
            )
        )
        last_case_with_relations = last_case_full_info_result.scalar_one_or_none()

        if last_case_with_relations:
            last_case_details = CaseModelScheema.model_validate(
                last_case_with_relations
            )
            if not last_case_with_relations.report:
                new_report = db_models.Report(case_id=last_case_with_relations.id)
                db.add(new_report)
                await db.commit()
                await db.refresh(new_report)
                last_case_with_relations.report = new_report

            patient_db = await get_patient_by_corid(
                db=db, cor_id=last_case_with_relations.patient_id
            )
            referral_db = await get_referral_by_case(
                db=db, case_id=last_case_with_relations.id
            )

            report_details = await _format_final_report_response(
                db=db,
                db_report=last_case_with_relations.report,
                db_case_parameters=last_case_with_relations.case_parameters,
                router=router,
                patient_db=patient_db,
                referral_db=referral_db,
                case_db=last_case_with_relations,
                current_doctor_id=current_doctor_id,
            )
    if last_case_with_relations:
        case_owner = await get_case_owner(
            db=db, case_id=last_case_with_relations.id, doctor_id=current_doctor_id
        )
    return PatientFinalReportPageResponse(
        all_cases=all_cases_schematized,
        last_case_details=last_case_details,
        case_owner=case_owner,
        report_details=report_details,
    )


async def _format_final_report_response(
    db: AsyncSession,
    db_report: db_models.Report,
    router: APIRouter,
    patient_db: db_models.Patient,
    referral_db: db_models.Referral,
    case_db: db_models.Case,
    current_doctor_id: str,
    db_case_parameters: Optional[db_models.CaseParameters],
) -> ReportResponseSchema:
    """
    Форматирует объект db_models.Report в ReportResponseSchema для финального отчета.
    Эта функция должна быть обновлена для обработки doctor_diagnoses.
    """
    try:
        decoded_key = base64.b64decode(settings.aes_key)
        patient_surname = (
            await decrypt_data(patient_db.encrypted_surname, decoded_key)
            if patient_db.encrypted_surname
            else None
        )
        patient_first_name = (
            await decrypt_data(patient_db.encrypted_first_name, decoded_key)
            if patient_db.encrypted_first_name
            else None
        )
        patient_middle_name = (
            await decrypt_data(patient_db.encrypted_middle_name, decoded_key)
            if patient_db.encrypted_middle_name
            else None
        )
    except Exception as e:
        print(e)
    user_birth_year = patient_db.birth_date
    if user_birth_year is None and patient_db.patient_cor_id:
        cor_id_parts = patient_db.patient_cor_id.split("-")
        if len(cor_id_parts) > 1:
            year_part = cor_id_parts[1]
            numbers = re.findall(r"\d+", year_part)
            if numbers:
                try:
                    user_birth_year = numbers[0]
                except ValueError:
                    user_birth_year = None

    patient_age: Optional[int] = None
    if patient_db.birth_date:
        today = date.today()
        patient_age = (
            today.year
            - patient_db.birth_date.year
            - (
                (today.month, today.day)
                < (patient_db.birth_date.month, patient_db.birth_date.day)
            )
        )

    case_details_schema = None
    doctor_diagnoses_schematized: List[DoctorDiagnosisSchema] = []
    if case_db:
        case_details_schema = CaseModelScheema.model_validate(case_db)
    if db_report:
        await db.refresh(db_report, attribute_names=["doctor_diagnoses"])

        doctor_diagnoses_schematized: List[DoctorDiagnosisSchema] = []
        for dd_db in sorted(db_report.doctor_diagnoses, key=lambda x: x.created_at):
            doctor_data = (
                DoctorResponseForSignature.model_validate(dd_db.doctor)
                if dd_db.doctor
                else None
            )

            signature_data: Optional[ReportSignatureSchema] = None
            if dd_db.signature:
                signer_doctor_data = (
                    DoctorResponseForSignature.model_validate(dd_db.signature.doctor)
                    if dd_db.signature.doctor
                    else None
                )

                doctor_sig_response: Optional[DoctorSignatureResponse] = None
                if dd_db.signature.doctor_signature:
                    signature_url = None
                    if dd_db.signature.doctor_signature.signature_scan_data:
                        signature_url = router.url_path_for(
                            "get_signature_attachment",
                            signature_id=dd_db.signature.doctor_signature.id,
                        )

                    doctor_sig_response = DoctorSignatureResponse(
                        id=dd_db.signature.doctor_signature.id,
                        doctor_id=dd_db.signature.doctor_signature.doctor_id,
                        signature_name=dd_db.signature.doctor_signature.signature_name,
                        signature_scan_data=signature_url,
                        signature_scan_type=dd_db.signature.doctor_signature.signature_scan_type,
                        is_default=dd_db.signature.doctor_signature.is_default,
                        created_at=dd_db.signature.doctor_signature.created_at,
                    )
                signature_data = ReportSignatureSchema(
                    id=dd_db.signature.id,
                    doctor=signer_doctor_data,
                    signed_at=dd_db.signature.signed_at,
                    doctor_signature=doctor_sig_response,
                )

            doctor_diagnoses_schematized.append(
                DoctorDiagnosisSchema(
                    id=dd_db.id,
                    report_id=dd_db.report_id,
                    doctor=doctor_data,
                    created_at=dd_db.created_at,
                    immunohistochemical_profile=dd_db.immunohistochemical_profile,
                    molecular_genetic_profile=dd_db.molecular_genetic_profile,
                    pathomorphological_diagnosis=dd_db.pathomorphological_diagnosis,
                    icd_code=dd_db.icd_code,
                    comment=dd_db.comment,
                    report_macrodescription=dd_db.report_macrodescription,
                    report_microdescription=dd_db.report_microdescription,
                    signature=signature_data,
                )
            )
    if db_report:
        attached_glass_ids = (
            db_report.attached_glass_ids
            if db_report.attached_glass_ids is not None
            else []
        )
    else:
        attached_glass_ids = []
    attached_glasses_schemas: List[GlassModelScheema] = []
    glass_stainings = []
    if attached_glass_ids:
        glasses_db = await db.scalars(
            select(db_models.Glass).where(db_models.Glass.id.in_(attached_glass_ids))
        )
        for glass in glasses_db.all():
            attached_glasses_schemas.append(GlassModelScheema.model_validate(glass))
            glass_stainings.append(glass.staining)
    glass_stainings = set(glass_stainings)
    report = await get_report_by_case_id(
        db=db, case_id=case_db.id, router=router, current_doctor_id=current_doctor_id
    )
    concatenated_macro_description = (
        report.report_details.concatenated_macro_description
    )
    if db_report:
        report_date_new = (
            doctor_diagnoses_schematized[0].created_at.date()
            if db_report.doctor_diagnoses
            else None
        )
    else:
        report_date_new = None
    if referral_db:
        if referral_db.biomaterial_date:
            biomaterial_date = referral_db.biomaterial_date.date()
        else:
            biomaterial_date = None

    return FinalReportResponseSchema(
        id=db_report.id if db_report else None,
        case_id=case_db.id,
        case_code=case_db.case_code,
        biopsy_date=biomaterial_date if referral_db else None,
        arrival_date=case_db.creation_date.date() if case_db else None,
        report_date=case_db.closing_date.date() if case_db.closing_date else None,
        patient_cor_id=patient_db.patient_cor_id,
        patient_first_name=patient_first_name,
        patient_surname=patient_surname,
        patient_middle_name=patient_middle_name,
        patient_sex=patient_db.sex,
        patient_birth_date=patient_db.birth_date,
        patient_full_age=patient_age,
        patient_phone_number=patient_db.phone_number,
        patient_email=patient_db.email,
        concatenated_macro_description=concatenated_macro_description,
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
        doctor_diagnoses=doctor_diagnoses_schematized,
        attached_glasses=attached_glasses_schemas,
    )


async def get_final_report_by_case_id(
    db: AsyncSession, case_id: str, router: APIRouter, current_doctor_id: str
) -> CaseFinalReportPageResponse:
    """
    Получает заключение для конкретного кейса. Если заключения нет, оно будет создано.
    """
    report_details: Optional[ReportResponseSchema] = None
    last_case_details: Optional[CaseModelScheema] = None
    all_samples_for_last_case_schematized: List[SampleTestForGlassPage] = []
    case_owner: Optional[CaseOwnerResponse] = None
    last_case_full_info_result = await db.execute(
        select(db_models.Case)
        .where(db_models.Case.id == case_id)
        .options(
            selectinload(db_models.Case.case_parameters),
            selectinload(db_models.Case.report).options(
                selectinload(db_models.Report.doctor_diagnoses).options(
                    selectinload(db_models.DoctorDiagnosis.doctor),
                    selectinload(db_models.DoctorDiagnosis.signature).options(
                        selectinload(db_models.ReportSignature.doctor),
                        selectinload(db_models.ReportSignature.doctor_signature),
                    ),
                )
            ),
            selectinload(db_models.Case.samples)
            .selectinload(db_models.Sample.cassette)
            .selectinload(db_models.Cassette.glass),
        )
    )
    last_case_with_relations = last_case_full_info_result.scalar_one_or_none()

    if last_case_with_relations:
        last_case_details = CaseModelScheema.model_validate(last_case_with_relations)
        if not last_case_with_relations.report:
            new_report = db_models.Report(case_id=last_case_with_relations.id)
            db.add(new_report)
            await db.commit()
            await db.refresh(new_report)
            last_case_with_relations.report = new_report

        patient_db = await get_patient_by_corid(
            db=db, cor_id=last_case_with_relations.patient_id
        )
        referral_db = await get_referral_by_case(
            db=db, case_id=last_case_with_relations.id
        )

        report_details = await _format_final_report_response(
            db=db,
            db_report=last_case_with_relations.report,
            db_case_parameters=last_case_with_relations.case_parameters,
            router=router,
            patient_db=patient_db,
            referral_db=referral_db,
            case_db=last_case_with_relations,
            current_doctor_id=current_doctor_id,
        )
    if last_case_with_relations:
        case_owner = await get_case_owner(
            db=db, case_id=last_case_with_relations.id, doctor_id=current_doctor_id
        )
    return CaseFinalReportPageResponse(
        case_details=last_case_details,
        case_owner=case_owner,
        report_details=report_details,
    )


async def get_current_case_details_for_excision_page(
    db: AsyncSession,
    current_doctor_id: str,
    case_id=Optional[str],
    skip: int = 0,
    limit: int = 10,
) -> PatientExcisionPageResponse:
    """
    Асинхронно получает список всех кейсов пациента и полную детализацию
    по последнему кейсу (параметры, макроописание, инфо по семплам).
    Используется для вкладки "Excision" (удаление/макроописание) на странице врача.
    """
    case_id_query = case_id
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
            db_models.Case.is_printed_cassette,
            db_models.Case.is_printed_glass,
            db_models.Case.is_printed_qr,
            literal_column("1").label("sort_priority"),
        ).where(
            and_(
                func.substr(db_models.Case.case_code, 1, 1).in_(["F", "U"]),
                db_models.Case.grossing_status
                != db_models.Grossing_status.COMPLETED.value,
            )
        )
    ).subquery("cases_fu")

    scanned_glass_exists_clause = (
        select(1)
        .select_from(db_models.Sample)
        .join(db_models.Cassette, db_models.Sample.id == db_models.Cassette.sample_id)
        .join(db_models.Glass, db_models.Cassette.id == db_models.Glass.cassette_id)
        .where(db_models.Sample.case_id == db_models.Case.id)
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
            db_models.Case.is_printed_cassette,
            db_models.Case.is_printed_glass,
            db_models.Case.is_printed_qr,
            literal_column("2").label("sort_priority"),
        ).where(
            and_(
                func.substr(db_models.Case.case_code, 1, 1) == "S",
                db_models.Case.grossing_status
                != db_models.Grossing_status.COMPLETED.value,
                scanned_glass_exists_clause,
            )
        )
    ).subquery("cases_s")

    combined_query_for_data = select(
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
        cases_fu_subquery.c.is_printed_cassette,
        cases_fu_subquery.c.is_printed_glass,
        cases_fu_subquery.c.is_printed_qr,
        cases_fu_subquery.c.sort_priority,
    ).union_all(
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
            cases_s_subquery.c.is_printed_cassette,
            cases_s_subquery.c.is_printed_glass,
            cases_s_subquery.c.is_printed_qr,
            cases_s_subquery.c.sort_priority,
        )
    )

    final_ordered_query = combined_query_for_data.order_by(
        combined_query_for_data.c.sort_priority.asc(),
        combined_query_for_data.c.creation_date.desc(),
    )

    paginated_results = await db.execute(final_ordered_query.offset(skip).limit(limit))
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
        is_printed_cassette = row.is_printed_cassette
        is_printed_glass = row.is_printed_glass
        is_printed_qr = row.is_printed_qr

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
                pathohistological_conclusion=pathohistological_conclusion,
                microdescription=microdescription,
                is_printed_cassette=is_printed_cassette,
                is_printed_glass=is_printed_glass,
                is_printed_qr=is_printed_qr,
            )
        )

    last_case_details_for_excision: Optional[LastCaseExcisionDetailsSchema] = None
    case_owner: Optional[CaseOwnerResponse] = None

    if all_current_cases_raw:
        last_case_db = all_current_cases_raw[0]
        if case_id_query:
            first_case_id = case_id_query
        else:
            first_case_id = last_case_db.id
        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == first_case_id)
            .options(
                selectinload(db_models.Case.case_parameters),
                selectinload(db_models.Case.samples),
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
                last_case_with_relations.samples, key=lambda s: s.sample_number
            )

            for sample_db in sorted_samples:

                samples_for_excision_page.append(
                    SampleForExcisionPage(
                        id=sample_db.id,
                        sample_number=sample_db.sample_number,
                        is_archived=sample_db.archive,
                        macro_description=sample_db.macro_description,
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
                patient_cor_id=last_case_with_relations.patient_id,
                is_printed_cassette=last_case_with_relations.is_printed_cassette,
                is_printed_glass=last_case_with_relations.is_printed_glass,
                is_printed_qr=last_case_with_relations.is_printed_qr,
            )
    if last_case_with_relations:
        case_owner = await get_case_owner(
            db=db, case_id=last_case_with_relations.id, doctor_id=current_doctor_id
        )
    return PatientExcisionPageResponse(
        all_cases=current_cases_list,
        last_case_details_for_excision=last_case_details_for_excision,
        case_owner=case_owner,
    )


async def get_current_cases_report_page_data(
    db: AsyncSession,
    router: APIRouter,
    current_doctor_id: str,
    case_id=Optional[str],
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
    case_id_query = case_id
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
            db_models.Case.case_owner,
            db_models.Case.is_printed_cassette,
            db_models.Case.is_printed_glass,
            db_models.Case.is_printed_qr,
            literal_column("1").label("sort_priority"),
        ).where(
            and_(
                func.substr(db_models.Case.case_code, 1, 1).in_(["F", "U"]),
                db_models.Case.grossing_status
                != db_models.Grossing_status.COMPLETED.value,
            )
        )
    ).subquery("cases_fu")

    scanned_glass_exists_clause = (
        select(1)
        .select_from(db_models.Sample)
        .join(db_models.Cassette, db_models.Sample.id == db_models.Cassette.sample_id)
        .join(db_models.Glass, db_models.Cassette.id == db_models.Glass.cassette_id)
        .where(db_models.Sample.case_id == db_models.Case.id)
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
            db_models.Case.case_owner,
            db_models.Case.is_printed_cassette,
            db_models.Case.is_printed_glass,
            db_models.Case.is_printed_qr,
            literal_column("2").label("sort_priority"),
        ).where(
            and_(
                func.substr(db_models.Case.case_code, 1, 1) == "S",
                db_models.Case.grossing_status
                != db_models.Grossing_status.COMPLETED.value,
                scanned_glass_exists_clause,
            )
        )
    ).subquery("cases_s")

    combined_query_for_data = select(
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
        cases_fu_subquery.c.sort_priority,
        cases_fu_subquery.c.case_owner,
        cases_fu_subquery.c.is_printed_cassette,
        cases_fu_subquery.c.is_printed_glass,
        cases_fu_subquery.c.is_printed_qr,
    ).union_all(
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
            cases_s_subquery.c.sort_priority,
            cases_s_subquery.c.case_owner,
            cases_s_subquery.c.is_printed_cassette,
            cases_s_subquery.c.is_printed_glass,
            cases_s_subquery.c.is_printed_qr,
        )
    )

    final_ordered_query = combined_query_for_data.order_by(
        combined_query_for_data.c.sort_priority.asc(),
        combined_query_for_data.c.creation_date.desc(),
    )

    paginated_results = await db.execute(final_ordered_query.offset(skip).limit(limit))
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
        is_printed_cassette = row.is_printed_cassette
        is_printed_glass = row.is_printed_glass
        is_printed_qr = row.is_printed_qr

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
                pathohistological_conclusion=pathohistological_conclusion,
                microdescription=microdescription,
                is_printed_cassette=is_printed_cassette,
                is_printed_glass=is_printed_glass,
                is_printed_qr=is_printed_qr,
            )
        )

    last_case_for_report: Optional[CaseModelScheema] = None
    report_details: Optional[ReportResponseSchema] = None
    all_samples_for_last_case_schematized: List[SampleTestForGlassPage] = []
    first_case_details_for_glass: Optional[FirstCaseTestGlassDetailsSchema] = None
    case_owner: Optional[CaseOwnerResponse] = None

    if all_current_cases_raw:
        last_case_db_summary = all_current_cases_raw[0]
        if case_id_query:
            first_case_id = case_id_query
        else:
            first_case_id = last_case_db_summary.id

        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == first_case_id)
            .options(
                selectinload(db_models.Case.case_parameters),
                selectinload(db_models.Case.report).options(
                    selectinload(db_models.Report.doctor_diagnoses).options(
                        selectinload(db_models.DoctorDiagnosis.doctor),
                        selectinload(db_models.DoctorDiagnosis.signature).options(
                            selectinload(db_models.ReportSignature.doctor),
                            selectinload(db_models.ReportSignature.doctor_signature),
                        ),
                    )
                ),
                selectinload(db_models.Case.samples)
                .selectinload(db_models.Sample.cassette)
                .selectinload(db_models.Cassette.glass),
            )
        )
        last_case_with_relations = last_case_full_info_result.scalar_one_or_none()

        if last_case_with_relations:
            last_case_for_report = CaseModelScheema.model_validate(
                last_case_with_relations
            )

            if not last_case_with_relations.report:
                new_report = db_models.Report(case_id=last_case_with_relations.id)
                db.add(new_report)
                await db.commit()
                await db.refresh(new_report)
                last_case_with_relations.report = new_report

            report_details = await _format_report_response(
                db=db,
                db_report=last_case_with_relations.report,
                router=router,
                case_db=last_case_with_relations,
            )

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
                        cassette_db.glass, key=lambda glass: glass.glass_number
                    )
                    glasses_for_cassette: List[GlassTestModelScheema] = []
                    for glass in sorted_glasses_db:
                        glass_schematized = GlassTestModelScheema(
                            id=glass.id,
                            glass_number=glass.glass_number,
                            cassette_id=glass.cassette_id,
                            staining=glass.staining,
                        )
                        glasses_for_cassette.append(glass_schematized)

                    cassette_schematized = CassetteTestForGlassPage(
                        id=cassette_db.id,
                        cassette_number=cassette_db.cassette_number,
                        sample_id=cassette_db.sample_id,
                    )
                    cassette_schematized.glasses = glasses_for_cassette
                    cassettes_for_sample.append(cassette_schematized)

                sample_schematized = SampleTestForGlassPage(
                    id=sample_db.id,
                    sample_number=sample_db.sample_number,
                    case_id=sample_db.case_id,
                )
                sample_schematized.cassettes = cassettes_for_sample
                all_samples_for_last_case_schematized.append(sample_schematized)

            first_case_details_for_glass = FirstCaseTestGlassDetailsSchema(
                id=last_case_with_relations.id,
                case_code=last_case_with_relations.case_code,
                creation_date=last_case_with_relations.creation_date,
                samples=all_samples_for_last_case_schematized,
                grossing_status=last_case_with_relations.grossing_status,
            )
    if last_case_with_relations:
        case_owner = await get_case_owner(
            db=db, case_id=last_case_with_relations.id, doctor_id=current_doctor_id
        )
    return PatientTestReportPageResponse(
        all_cases=current_cases_list,
        last_case_for_report=last_case_for_report,
        case_owner=case_owner,
        report_details=report_details,
        all_glasses_for_last_case=first_case_details_for_glass,
    )


async def get_current_cases_with_directions(
    db: AsyncSession,
    current_doctor_id=str,
    case_id=Optional[str],
    skip: int = 0,
    limit: int = 10,
) -> PatientCasesWithReferralsResponse:
    """
    Асинхронно получает список всех кейсов пациента и детализацию первого из них:
    все семплы первого кейса, но кассеты и стекла загружаются только для первого семпла.
    Включает ссылки на файлы направлений для первого кейса.
    """
    case_id_query = case_id
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
            db_models.Case.is_printed_cassette,
            db_models.Case.is_printed_glass,
            db_models.Case.is_printed_qr,
            literal_column("1").label("sort_priority"),
        ).where(
            and_(
                func.substr(db_models.Case.case_code, 1, 1).in_(["F", "U"]),
                db_models.Case.grossing_status
                != db_models.Grossing_status.COMPLETED.value,
            )
        )
    ).subquery("cases_fu")

    scanned_glass_exists_clause = (
        select(1)
        .select_from(db_models.Sample)
        .join(db_models.Cassette, db_models.Sample.id == db_models.Cassette.sample_id)
        .join(db_models.Glass, db_models.Cassette.id == db_models.Glass.cassette_id)
        .where(db_models.Sample.case_id == db_models.Case.id)
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
            db_models.Case.is_printed_cassette,
            db_models.Case.is_printed_glass,
            db_models.Case.is_printed_qr,
            literal_column("2").label("sort_priority"),
        ).where(
            and_(
                func.substr(db_models.Case.case_code, 1, 1) == "S",
                db_models.Case.grossing_status
                != db_models.Grossing_status.COMPLETED.value,
                scanned_glass_exists_clause,
            )
        )
    ).subquery("cases_s")

    combined_query_for_data = select(
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
        cases_fu_subquery.c.sort_priority,
        cases_fu_subquery.c.is_printed_cassette,
        cases_fu_subquery.c.is_printed_glass,
        cases_fu_subquery.c.is_printed_qr,
    ).union_all(
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
            cases_s_subquery.c.sort_priority,
            cases_s_subquery.c.is_printed_cassette,
            cases_s_subquery.c.is_printed_glass,
            cases_s_subquery.c.is_printed_qr,
        )
    )

    final_ordered_query = combined_query_for_data.order_by(
        combined_query_for_data.c.sort_priority.asc(),
        combined_query_for_data.c.creation_date.desc(),
    )

    paginated_results = await db.execute(final_ordered_query.offset(skip).limit(limit))
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
        is_printed_cassette = row.is_printed_cassette
        is_printed_glass = row.is_printed_glass
        is_printed_qr = row.is_printed_qr
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
                pathohistological_conclusion=pathohistological_conclusion,
                microdescription=microdescription,
                is_printed_cassette=is_printed_cassette,
                is_printed_glass=is_printed_glass,
                is_printed_qr=is_printed_qr,
            )
        )

    first_case_direction_details: Optional[FirstCaseReferralDetailsSchema] = None
    case_details = None
    case_owner: Optional[CaseOwnerResponse] = None

    if all_current_cases_raw:
        first_case_db = all_current_cases_raw[0]
        if case_id_query:
            first_case_id = case_id_query
        else:
            first_case_id = first_case_db.id

        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == first_case_id)
            .options(
                selectinload(db_models.Case.case_parameters),
                selectinload(db_models.Case.report).options(
                    selectinload(db_models.Report.doctor_diagnoses).options(
                        selectinload(db_models.DoctorDiagnosis.doctor),
                        selectinload(db_models.DoctorDiagnosis.signature).options(
                            selectinload(db_models.ReportSignature.doctor),
                            selectinload(db_models.ReportSignature.doctor_signature),
                        ),
                    )
                ),
                selectinload(db_models.Case.samples)
                .selectinload(db_models.Sample.cassette)
                .selectinload(db_models.Cassette.glass),
            )
        )
        last_case_with_relations = last_case_full_info_result.scalar_one_or_none()
        referral_db = await db.scalar(
            select(db_models.Referral).where(
                db_models.Referral.case_id == first_case_id
            )
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
                file_url = generate_file_url(file_db.id, first_case_id)
                attachments_for_response.append(
                    ReferralFileSchema(
                        id=file_db.id,
                        file_name=file_db.filename,
                        file_type=file_db.content_type,
                        file_url=file_url,
                    )
                )

            first_case_direction_details = FirstCaseReferralDetailsSchema(
                id=last_case_with_relations.id,
                case_code=last_case_with_relations.case_code,
                creation_date=last_case_with_relations.creation_date,
                pathohistological_conclusion=last_case_with_relations.pathohistological_conclusion,
                microdescription=last_case_with_relations.microdescription,
                attachments=attachments_for_response,
                grossing_status=last_case_with_relations.grossing_status,
                patient_cor_id=last_case_with_relations.patient_id,
            )
    if last_case_with_relations:
        case_owner = await get_case_owner(
            db=db, case_id=last_case_with_relations.id, doctor_id=current_doctor_id
        )
    return PatientCasesWithReferralsResponse(
        all_cases=current_cases_list,
        case_details=last_case_with_relations,
        case_owner=case_owner,
        first_case_direction=first_case_direction_details,
    )


async def get_current_cases_final_report_page_data(
    db: AsyncSession,
    router: APIRouter,
    current_doctor_id=str,
    case_id=Optional[str],
    skip: int = 0,
    limit: int = 10,
) -> PatientFinalReportPageResponse:
    """
    Получает данные для вкладки "Заключение" на странице врача:
    - Все текущие (незавершенные) кейсы, отсортированные по приоритету.
    - Детали последнего (по приоритету и дате) кейса: сам кейс, его параметры,
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
            db_models.Case.is_printed_cassette,
            db_models.Case.is_printed_glass,
            db_models.Case.is_printed_qr,
            literal_column("1").label("sort_priority"),
        ).where(
            and_(
                func.substr(db_models.Case.case_code, 1, 1).in_(["F", "U"]),
                db_models.Case.grossing_status
                != db_models.Grossing_status.COMPLETED.value,
            )
        )
    ).subquery("cases_fu")

    scanned_glass_exists_clause = (
        select(1)
        .select_from(db_models.Sample)
        .join(db_models.Cassette, db_models.Sample.id == db_models.Cassette.sample_id)
        .join(db_models.Glass, db_models.Cassette.id == db_models.Glass.cassette_id)
        .where(db_models.Sample.case_id == db_models.Case.id)
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
            db_models.Case.is_printed_cassette,
            db_models.Case.is_printed_glass,
            db_models.Case.is_printed_qr,
            literal_column("2").label("sort_priority"),
        ).where(
            and_(
                func.substr(db_models.Case.case_code, 1, 1) == "S",
                db_models.Case.grossing_status
                != db_models.Grossing_status.COMPLETED.value,
                scanned_glass_exists_clause,
            )
        )
    ).subquery("cases_s")

    combined_query_for_data = select(
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
        cases_fu_subquery.c.is_printed_cassette,
        cases_fu_subquery.c.is_printed_glass,
        cases_fu_subquery.c.is_printed_qr,
        cases_fu_subquery.c.sort_priority,
    ).union_all(
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
            cases_s_subquery.c.is_printed_cassette,
            cases_s_subquery.c.is_printed_glass,
            cases_s_subquery.c.is_printed_qr,
            cases_s_subquery.c.sort_priority,
        )
    )

    final_ordered_query = combined_query_for_data.order_by(
        combined_query_for_data.c.sort_priority.asc(),
        combined_query_for_data.c.creation_date.desc(),
    )

    paginated_results = await db.execute(final_ordered_query.offset(skip).limit(limit))
    all_current_cases_raw = paginated_results.all()

    current_cases_list: List[CaseModelScheema] = []
    last_case_details: Optional[CaseModelScheema] = None
    report_details: Optional[FinalReportResponseSchema] = None
    all_samples_for_last_case_schematized: List[SampleTestForGlassPage] = []
    case_owner: Optional[CaseOwnerResponse] = None

    for row in all_current_cases_raw:
        current_cases_list.append(
            CaseModelScheema(
                id=str(row.id),
                case_code=row.case_code,
                creation_date=row.creation_date,
                patient_id=str(row.patient_id),
                grossing_status=db_models.Grossing_status(row.grossing_status),
                bank_count=row.bank_count,
                cassette_count=row.cassette_count,
                glass_count=row.glass_count,
                pathohistological_conclusion=row.pathohistological_conclusion,
                microdescription=row.microdescription,
                is_printed_cassette=row.is_printed_cassette,
                is_printed_glass=row.is_printed_glass,
                is_printed_qr=row.is_printed_qr,
            )
        )

    if all_current_cases_raw:
        if case_id:
            first_case_id = case_id
        else:
            first_case_id = all_current_cases_raw[0].id

        last_case_full_info_result = await db.execute(
            select(db_models.Case)
            .where(db_models.Case.id == first_case_id)
            .options(
                selectinload(db_models.Case.case_parameters),
                selectinload(db_models.Case.report).options(
                    selectinload(db_models.Report.doctor_diagnoses).options(
                        selectinload(db_models.DoctorDiagnosis.doctor),
                        selectinload(db_models.DoctorDiagnosis.signature).options(
                            selectinload(db_models.ReportSignature.doctor),
                            selectinload(db_models.ReportSignature.doctor_signature),
                        ),
                    )
                ),
                selectinload(db_models.Case.samples)
                .selectinload(db_models.Sample.cassette)
                .selectinload(db_models.Cassette.glass),
            )
        )
        last_case_with_relations = last_case_full_info_result.scalar_one_or_none()

        if last_case_with_relations:
            last_case_details = CaseModelScheema.model_validate(
                last_case_with_relations
            )

            if not last_case_with_relations.report:
                new_report = db_models.Report(case_id=last_case_with_relations.id)
                db.add(new_report)
                await db.commit()
                await db.refresh(new_report)
                last_case_with_relations.report = new_report

            patient_db = await get_patient_by_corid(
                db=db, cor_id=last_case_with_relations.patient_id
            )
            referral_db = await get_referral_by_case(
                db=db, case_id=last_case_with_relations.id
            )

            report_details = await _format_final_report_response(
                db=db,
                db_report=last_case_with_relations.report,
                db_case_parameters=last_case_with_relations.case_parameters,
                router=router,
                patient_db=patient_db,
                referral_db=referral_db,
                case_db=last_case_with_relations,
                current_doctor_id=current_doctor_id,
            )
    if last_case_with_relations:
        case_owner = await get_case_owner(
            db=db, case_id=last_case_with_relations.id, doctor_id=current_doctor_id
        )
    return PatientFinalReportPageResponse(
        all_cases=current_cases_list,
        last_case_details=last_case_details,
        case_owner=case_owner,
        report_details=report_details,
    )


async def take_case_ownership(
    db: AsyncSession, case_id: str, doctor_id: str
) -> db_models.Case:
    """
    Позволяет доктору взять на себя владение кейсом.
    """
    case_db = await db.scalar(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    if not case_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Кейс с ID '{case_id}' не найден.",
        )
    if case_db.grossing_status == db_models.Grossing_status.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"Запрещено редактировать закрытый кейс",
        )

    doctor_db = await db.scalar(
        select(db_models.Doctor).where(db_models.Doctor.doctor_id == doctor_id)
    )
    if not doctor_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Доктор с ID '{doctor_id}' не найден.",
        )

    if case_db.case_owner == doctor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже являетесь владельцем этого кейса.",
        )

    if case_db.case_owner is not None and case_db.case_owner != doctor_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Кейс уже занят другим доктором.",
        )

    case_db.case_owner = doctor_id
    case_db.grossing_status = db_models.Grossing_status.PROCESSING
    await db.commit()
    await db.refresh(case_db)

    doctor = await get_doctor(db=db, doctor_id=case_db.case_owner)
    samples_result = await db.execute(
        select(db_models.Sample)
        .where(db_models.Sample.case_id == case_db.id)
        .options(selectinload(db_models.Sample.cassette))
        .order_by(db_models.Sample.sample_number)
    )
    first_case_samples_db = samples_result.scalars().all()
    first_case_samples: List[Dict[str, Any]] = []

    for i, sample_db in enumerate(first_case_samples_db):
        sample = SampleModelScheema.model_validate(sample_db).model_dump()
        sample["cassettes"] = []

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
                )

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
    response = CaseDetailsResponse(
        id=case_db.id,
        case_code=case_db.case_code,
        creation_date=case_db.creation_date,
        bank_count=case_db.bank_count,
        cassette_count=case_db.cassette_count,
        glass_count=case_db.glass_count,
        pathohistological_conclusion=case_db.pathohistological_conclusion,
        microdescription=case_db.microdescription,
        samples=first_case_samples,
    )
    case_owner_response = CaseOwnerResponse(
        id=doctor.id if case_db.case_owner else None,
        doctor_id=doctor.doctor_id if case_db.case_owner else None,
        work_email=doctor.work_email if case_db.case_owner else None,
        phone_number=doctor.phone_number if case_db.case_owner else None,
        first_name=doctor.first_name if case_db.case_owner else None,
        middle_name=doctor.middle_name if case_db.case_owner else None,
        last_name=doctor.last_name if case_db.case_owner else None,
        is_case_owner=True,
    )
    general_response = CaseOwnershipResponse(
        case_details=response, case_owner=case_owner_response
    )
    return general_response


async def release_case_ownership(
    db: AsyncSession, case_id: str, doctor_id: str
) -> CaseOwnershipResponse:
    """
    Позволяет доктору отказаться от владения кейсом.
    """
    case_db = await db.scalar(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    if not case_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Кейс с ID '{case_id}' не найден.",
        )
    if case_db.grossing_status == db_models.Grossing_status.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"Запрещено редактировать закрытый кейс",
        )
    if case_db.case_owner != doctor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы не являетесь владельцем этого кейса и не можете его освободить.",
        )

    case_db.case_owner = None
    case_db.grossing_status = db_models.Grossing_status.CREATED
    await db.commit()
    await db.refresh(case_db)

    await db.commit()
    await db.refresh(case_db)
    doctor = await get_doctor(db=db, doctor_id=case_db.case_owner)

    samples_result = await db.execute(
        select(db_models.Sample)
        .where(db_models.Sample.case_id == case_db.id)
        .options(selectinload(db_models.Sample.cassette))
        .order_by(db_models.Sample.sample_number)
    )
    first_case_samples_db = samples_result.scalars().all()
    first_case_samples: List[Dict[str, Any]] = []

    for i, sample_db in enumerate(first_case_samples_db):
        sample = SampleModelScheema.model_validate(sample_db).model_dump()
        sample["cassettes"] = []

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
                )

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
    response = CaseDetailsResponse(
        id=case_db.id,
        case_code=case_db.case_code,
        creation_date=case_db.creation_date,
        bank_count=case_db.bank_count,
        cassette_count=case_db.cassette_count,
        glass_count=case_db.glass_count,
        pathohistological_conclusion=case_db.pathohistological_conclusion,
        microdescription=case_db.microdescription,
        samples=first_case_samples,
    )
    case_owner_response = CaseOwnerResponse(
        id=doctor.id if case_db.case_owner else None,
        doctor_id=doctor.doctor_id if case_db.case_owner else None,
        work_email=doctor.work_email if case_db.case_owner else None,
        phone_number=doctor.phone_number if case_db.case_owner else None,
        first_name=doctor.first_name if case_db.case_owner else None,
        middle_name=doctor.middle_name if case_db.case_owner else None,
        last_name=doctor.last_name if case_db.case_owner else None,
        is_case_owner=False,
    )
    general_response = CaseOwnershipResponse(
        case_details=response, case_owner=case_owner_response
    )
    return general_response


async def close_case_service(
    db: AsyncSession, case_id: str, current_doctor: db_models.Doctor
) -> CaseCloseResponse:
    """
    Закрывает кейс, меняя его grossing_status на COMPLETED.
    Требует, чтобы текущий врач был владельцем кейса и чтобы
    все DoctorDiagnosis имели соответствующие подписи.
    """
    case_result = await db.execute(
        select(db_models.Case)
        .where(db_models.Case.id == case_id)
        .options(
            selectinload(db_models.Case.owner_obj),
            selectinload(db_models.Case.report).options(
                selectinload(db_models.Report.doctor_diagnoses).options(
                    selectinload(db_models.DoctorDiagnosis.doctor),
                    selectinload(db_models.DoctorDiagnosis.signature),
                )
            ),
        )
    )
    case_to_close = case_result.scalar_one_or_none()

    if not case_to_close:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.CASE_NOT_FOUND
        )

    if str(case_to_close.case_owner) != str(current_doctor.doctor_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=ErrorCode.NOT_CASE_OWNER
        )

    if case_to_close.grossing_status == db_models.Grossing_status.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.CASE_ALREADY_COMPLETED,
        )

    if not case_to_close.report:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.REPORT_NOT_FOUND_FOR_CASE,
        )

    if not case_to_close.report.doctor_diagnoses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.NO_DIAGNOSES_FOR_REPORT,
        )

    for diagnosis in case_to_close.report.doctor_diagnoses:
        if not diagnosis.signature:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorCode.DIAGNOSIS_NOT_SIGNED_BY_DOCTOR_NAME.format(
                    doctor_full_name=(
                        f"{diagnosis.doctor.first_name} {diagnosis.doctor.last_name}"
                        if diagnosis.doctor
                        else "N/A"
                    )
                ),
            )
    case_to_close.grossing_status = db_models.Grossing_status.COMPLETED
    case_to_close.closing_date = datetime.now()

    db.add(case_to_close)
    await db.commit()
    await db.refresh(case_to_close)

    return CaseCloseResponse(
        message="Case closed successfully.",
        case_id=str(case_to_close.id),
        new_status=case_to_close.grossing_status.value,
    )


async def get_case_owner(
    db: AsyncSession, case_id: str, doctor_id: str
) -> CaseOwnerResponse:
    """
    Позволяет доктору взять на себя владение кейсом.
    """

    is_case_owner = False
    case_db = await db.scalar(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    if not case_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Кейс с ID '{case_id}' не найден.",
        )

    doctor_db = await db.scalar(
        select(db_models.Doctor).where(db_models.Doctor.doctor_id == doctor_id)
    )
    if not doctor_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Доктор с ID '{doctor_id}' не найден.",
        )

    if case_db.case_owner == doctor_id:
        is_case_owner = True

    doctor_db = await get_doctor(db=db, doctor_id=case_db.case_owner)

    response = CaseOwnerResponse(
        id=doctor_db.id if case_db.case_owner else None,
        doctor_id=doctor_db.doctor_id if case_db.case_owner else None,
        work_email=doctor_db.work_email if case_db.case_owner else None,
        phone_number=doctor_db.phone_number if case_db.case_owner else None,
        first_name=doctor_db.first_name if case_db.case_owner else None,
        middle_name=doctor_db.middle_name if case_db.case_owner else None,
        last_name=doctor_db.last_name if case_db.case_owner else None,
        is_case_owner=is_case_owner,
    )
    return response



async def print_all_case_glasses(
    db: AsyncSession, case_id: str, printing: bool, data: GeneralPrinting, request: Request
) -> Optional[Dict[str, Any]]:
    """
    Печатает все стёкла кейса, используя жадную загрузку для всех уровней.
    Возвращает полную информацию о кейсе в виде Pydantic-схемы.
    """
    case_result = await db.execute(
        select(db_models.Case)
        .where(db_models.Case.id == case_id)
        .options(
            selectinload(db_models.Case.samples)
            .selectinload(db_models.Sample.cassette)
            .selectinload(db_models.Cassette.glass)
        )
    )
    case_db = case_result.scalar_one_or_none()
    if not case_db:
        return None
    case_db.is_printed_glass = printing

    glasses_to_update: List[db_models.Glass] = []

    for sample_db in case_db.samples:

        sample_db.is_printed_glass = printing

        for cassette_db in sample_db.cassette:
            for glass_db in cassette_db.glass:
                glasses_to_update.append(glass_db)

    for glass_db in glasses_to_update:
        glass_data = GlassPrinting(
            printer_ip=data.printer_ip,
            model_id=data.model_id,
            clinic_name=data.clinic_name,
            hooper=data.hooper,
            glass_id=glass_db.id,
            printing=printing
        )
        await print_glass_data(db=db, data=glass_data, request=request)
        glass_db.is_printed = printing

    # def sort_cassettes(cassette: db_models.Cassette):
    #     match = re.match(r"([A-Z]+)(\d+)", cassette.cassette_number)
    #     if match:
    #         letter_part = match.group(1)
    #         number_part = int(match.group(2))
    #         return (letter_part, number_part)
    #     return (cassette.cassette_number, 0)

    # case_schema = CaseDetailsResponse.model_validate(case_db)

    # for sample_schema in case_schema.samples:
    #     sorted_cassettes_schemas = sorted(sample_schema.cassettes, key=sort_cassettes)
    #     sample_schema.cassettes = sorted_cassettes_schemas

    #     for cassette_schema in sample_schema.cassettes:
    #         cassette_schema.glasses.sort(key=lambda glass_s: glass_s.glass_number)

    await db.commit()
    await db.refresh(case_db)

    case_response = await get_case(db=db, case_id=case_id)
    return case_response



async def print_all_case_cassette(
    db: AsyncSession, case_id: str, printing: bool, data: GeneralPrinting, request: Request
) -> Optional[Dict[str, Any]]:
    """
    Печатает все кассеты кейса, используя жадную загрузку для всех уровней.
    Возвращает полную информацию о кейсе в виде Pydantic-схемы.
    """
    case_result = await db.execute(
        select(db_models.Case)
        .where(db_models.Case.id == case_id)
        .options(
            selectinload(db_models.Case.samples)
            .selectinload(db_models.Sample.cassette)
            .selectinload(db_models.Cassette.glass)
        )
    )
    case_db = case_result.scalar_one_or_none()
    if not case_db:
        return None
    case_db.is_printed_cassette = printing
    cassettes_to_update = []
    for sample_db in case_db.samples:
        sample_db.is_printed_cassette = printing
        cassettes_to_update = list(sample_db.cassette) if sample_db.cassette else []

        for cassette_db in cassettes_to_update:
            cassette_data = CassettePrinting(
            printer_ip=data.printer_ip,
            model_id=data.model_id,
            clinic_name=data.clinic_name,
            hooper=data.hooper,
            cassete_id=cassette_db.id,
            printing=printing
        )
            await print_cassette_data(db=db, data=cassette_data, request=request)
            cassette_db.is_printed = printing

    await db.commit()
    await db.refresh(case_db)

    case_response = await get_case(db=db, case_id=case_id)
    return case_response


async def print_case_qr(
    db: AsyncSession, case_id: str, printing: bool
) -> Optional[Dict[str, Any]]:
    """
    Печатает куар кейса
    """
    case_result = await db.execute(
        select(db_models.Case)
        .where(db_models.Case.id == case_id)
        .options(
            selectinload(db_models.Case.samples)
            .selectinload(db_models.Sample.cassette)
            .selectinload(db_models.Cassette.glass)
        )
    )
    case_db = case_result.scalar_one_or_none()
    if not case_db:
        return None
    case_db.is_printed_qr = printing

    await db.commit()
    await db.refresh(case_db)

    case_response = await get_case(db=db, case_id=case_id)
    return case_response


# --- Вспомогательные функции для обновления статусов ---


async def _update_sample_glass_status(db: AsyncSession, sample: db_models.Sample):
    """
    Обновляет is_printed_glass для Sample на основе статусов всех его Glass.
    Статус True, если ВСЕ стекла напечатаны. False, если хотя бы одно не напечатано.
    """
    all_glasses_in_sample_result = await db.execute(
        select(db_models.Glass).where(
            db_models.Glass.cassette.has(db_models.Cassette.sample_id == sample.id)
        )
    )
    all_glasses_in_sample = all_glasses_in_sample_result.scalars().all()

    new_sample_glass_status = (
        all(g.is_printed for g in all_glasses_in_sample)
        if all_glasses_in_sample
        else True
    )

    if sample.is_printed_glass != new_sample_glass_status:
        sample.is_printed_glass = new_sample_glass_status
        db.add(sample)


async def _update_sample_cassette_status(db: AsyncSession, sample: db_models.Sample):
    """
    Обновляет is_printed_cassette для Sample на основе статусов всех его Cassette.
    Статус True, если ВСЕ кассеты напечатаны. False, если хотя бы одна не напечатана.
    """
    all_cassettes_in_sample_result = await db.execute(
        select(db_models.Cassette).where(db_models.Cassette.sample_id == sample.id)
    )
    all_cassettes_in_sample = all_cassettes_in_sample_result.scalars().all()

    new_sample_cassette_status = (
        all(c.is_printed for c in all_cassettes_in_sample)
        if all_cassettes_in_sample
        else True
    )

    if sample.is_printed_cassette != new_sample_cassette_status:
        sample.is_printed_cassette = new_sample_cassette_status
        db.add(sample)


async def _update_case_glass_status(db: AsyncSession, case: db_models.Case):
    """
    Обновляет is_printed_glass для Case на основе is_printed_glass статусов всех его Sample.
    Статус True, если is_printed_glass всех семплов True. False, если хотя бы у одного False.
    """
    all_samples_in_case_result = await db.execute(
        select(db_models.Sample).where(db_models.Sample.case_id == case.id)
    )
    all_samples_in_case = all_samples_in_case_result.scalars().all()

    new_case_glass_status = (
        all(s.is_printed_glass for s in all_samples_in_case)
        if all_samples_in_case
        else True
    )

    if case.is_printed_glass != new_case_glass_status:
        case.is_printed_glass = new_case_glass_status
        db.add(case)


async def _update_case_cassette_status(db: AsyncSession, case: db_models.Case):
    """
    Обновляет is_printed_cassette для Case на основе is_printed_cassette статусов всех его Sample.
    Статус True, если is_printed_cassette всех семплов True. False, если хотя бы у одного False.
    """
    all_samples_in_case_result = await db.execute(
        select(db_models.Sample).where(db_models.Sample.case_id == case.id)
    )
    all_samples_in_case = all_samples_in_case_result.scalars().all()

    new_case_cassette_status = (
        all(s.is_printed_cassette for s in all_samples_in_case)
        if all_samples_in_case
        else True
    )

    if case.is_printed_cassette != new_case_cassette_status:
        case.is_printed_cassette = new_case_cassette_status
        db.add(case)


async def _update_ancestor_statuses_from_glass(
    db: AsyncSession, glass: db_models.Glass
):
    """
    Основная функция, вызываемая при изменении статуса `is_printed` у Glass.
    Запускает цепочку обновлений вверх по иерархии: Glass -> Cassette -> Sample -> Case.
    """

    cassette = await db.get(db_models.Cassette, glass.cassette_id)
    if not cassette:
        return

    # all_glasses_in_cassette_result = await db.execute(
    #     select(db_models.Glass).where(db_models.Glass.cassette_id == cassette.id)
    # )
    # all_glasses_in_cassette = all_glasses_in_cassette_result.scalars().all()

    # new_cassette_is_printed_status = all(g.is_printed for g in all_glasses_in_cassette) if all_glasses_in_cassette else True

    # if cassette.is_printed != new_cassette_is_printed_status:
    #     cassette.is_printed = new_cassette_is_printed_status
    #     db.add(cassette)

    sample = await db.get(db_models.Sample, cassette.sample_id)
    if not sample:
        return

    await _update_sample_glass_status(db, sample)

    # await _update_sample_cassette_status(db, sample)

    case = await db.get(db_models.Case, sample.case_id)
    if not case:
        return

    await _update_case_glass_status(db, case)

    # await _update_case_cassette_status(db, case)

    await db.commit()
    await db.refresh(glass)
    await db.refresh(cassette)
    await db.refresh(sample)
    await db.refresh(case)


async def _update_ancestor_statuses_from_cassette(
    db: AsyncSession, cassette: db_models.Cassette
):
    """
    Основная функция, вызываемая при изменении статуса `is_printed` у Cassette.
    Запускает цепочку обновлений вверх по иерархии: Cassette -> Sample -> Case.
    """

    sample = await db.get(db_models.Sample, cassette.sample_id)
    if not sample:
        return

    await _update_sample_cassette_status(db, sample)

    case = await db.get(db_models.Case, sample.case_id)
    if not case:

        return

    await _update_case_cassette_status(db, case)

    await db.commit()
    await db.refresh(cassette)
    await db.refresh(sample)
    await db.refresh(case)
