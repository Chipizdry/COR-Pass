from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.schemas import (
    Case as CaseModelScheema,
    CaseBase as CaseBaseScheema,
    Sample as SampleModelScheema,
    Cassette as CassetteModelScheema,
    Glass as GlassModelScheema,
)
from cor_pass.database import models as db_models
import uuid
from datetime import datetime
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import selectinload
from cor_pass.services.logger import logger


async def generate_case_code(urgency_char: str, year_short: str, sample_type_char: str, next_number: int) -> str:
    """Генератор коду кейса у форматі:
    1-й символ - срочність, 2-3 - рік, 4 - тип, 5-9 - порядковий номер.
    """
    formatted_number = f"{next_number:05d}"
    return f"{urgency_char}{year_short}{sample_type_char}{formatted_number}"


async def create_cases_with_initial_data(
    db: AsyncSession,
    case_in: CaseBaseScheema,
    num_cases: int = 1,
    urgency: db_models.UrgencyType = db_models.UrgencyType.S,
    material_type: db_models.SampleType = db_models.MaterialType.R,
) -> List[CaseModelScheema]:
    """Асинхронно створює вказану кількість кейсів та пов'язані з ними початкові дані."""
    created_cases: List[db_models.Case] = []
    now = datetime.now()
    year_short = now.strftime("%y")
    urgency_char = urgency.value[0].upper()
    material_type_char = material_type.value[0].upper()

    result = await db.execute(
            select(db_models.Case).where(
                db_models.Case.patient_id == case_in.patient_id
            )
        )
    cases_for_patient = result.scalars().all()
    next_number = len(cases_for_patient) + 1 if cases_for_patient else 1

    for _ in range(num_cases):
        now = datetime.now()

        db_case = db_models.Case(
            id=str(uuid.uuid4()),
            patient_id=case_in.patient_id,
            creation_date=now,
            bank_count=0,
            cassette_count=0,
            glass_count=0,
            # grossing_status=case_in.grossing_status
        )
        db_case.case_code = await generate_case_code(urgency_char, year_short, material_type_char, next_number)
        db.add(db_case)
        await db.commit()
        await db.refresh(db_case)

        # Автоматично створюємо одну банку
        db_sample = db_models.Sample(case_id=db_case.id, sample_number="A")
        db_case.bank_count += 1
        db.add(db_sample)
        await db.commit()
        await db.refresh(db_sample)
        await db.refresh(db_case)

        # Автоматично створюємо одну касету
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

        # Автоматично створюємо одне скло
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

        # Автоматично створюємо параметри кейса
        db_case_parameters = db_models.CaseParameters(
            case_id=db_case.id,
            urgency=urgency,
            material_type=material_type,
        )
        db.add(db_case_parameters)
        await db.commit()
        await db.refresh(db_case_parameters)
        await db.refresh(db_case)

        created_cases.append(db_case)

    return created_cases


async def get_case(db: AsyncSession, case_id: str) -> db_models.Case | None:
    """Асинхронно получает информацию о кейсе по его ID, включая связанные банки."""
    result = await db.execute(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    case_db = result.scalar_one_or_none()
    # 2. Получаем семплы первого кейса и связанные с ними кассеты и стекла
    samples_result = await db.execute(
        select(db_models.Sample)
        .where(db_models.Sample.case_id == case_db.id)
        .options(
            selectinload(db_models.Sample.cassette).selectinload(
                db_models.Cassette.glass
            )
        )
    )
    first_case_samples_db = samples_result.scalars().all()
    first_case_samples = []
    for sample_db in first_case_samples_db:
        sample = SampleModelScheema.model_validate(sample_db).model_dump()
        sample["cassettes"] = []
        for cassette_db in sample_db.cassette:
            cassette = CassetteModelScheema.model_validate(cassette_db).model_dump()
            cassette["glasses"] = [
                GlassModelScheema.model_validate(glass).model_dump()
                for glass in cassette_db.glass
            ]
            sample["cassettes"].append(cassette)
        first_case_samples.append(sample)

    first_case_details = {
        "id": case_db.id,
        "case_code": case_db.case_code,
        "creation_date": case_db.creation_date,
        "samples": first_case_samples,
    }

    return {"case_details": first_case_details}


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

    return {f"case {case_id} parameters": case_db}


async def update_case_parameters(
    db: AsyncSession,
    case_id: str,
    macro_description: str,
    container_count_actual: int,
    urgency: db_models.UrgencyType = db_models.UrgencyType.S,
    material_type: db_models.SampleType = db_models.MaterialType.R,
    macro_archive: db_models.MacroArchive = db_models.MacroArchive.ESS,
    decalcification: db_models.DecalcificationType = db_models.DecalcificationType.ABSENT,
    sample_type: db_models.SampleType = db_models.SampleType.NATIVE,
    fixation: db_models.FixationType = db_models.FixationType.NBF_10,
) -> db_models.CaseParameters | None:
    """Асинхронно получает информацию о кейсе по его ID, включая связанные банки."""
    result = await db.execute(
        select(db_models.CaseParameters).where(
            db_models.CaseParameters.case_id == case_id
        )
    )
    case_parameters_db = result.scalar_one_or_none()
    if case_parameters_db:
        case_parameters_db.macro_description = macro_description
        case_parameters_db.container_count_actual = container_count_actual
        case_parameters_db.urgency = urgency
        case_parameters_db.material_type = material_type
        case_parameters_db.macro_archive = macro_archive
        case_parameters_db.decalcification = decalcification
        case_parameters_db.sample_type = sample_type
        case_parameters_db.fixation = fixation
        await db.commit()
        await db.refresh(case_parameters_db)

    return {f"case {case_id} parameters updated": case_parameters_db}


async def get_single_case(db: AsyncSession, case_id: str) -> db_models.Case | None:
    """Асинхронно получает информацию о кейсе по его ID, включая связанные банки."""
    result = await db.execute(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    return result.scalar_one_or_none()


async def delete_case(db: AsyncSession, case_id: str) -> db_models.Case | None:
    """Асинхронно удаляет кейс."""
    result = await db.execute(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    db_case = result.scalar_one_or_none()
    if db_case:
        await db.delete(db_case)
        await db.commit()
        return {"message": f"Кейс с ID {case_id} успешно удалён"}
    return None


async def get_patient_first_case_details(
    db: AsyncSession, patient_id: str
) -> dict | None:
    """
    Асинхронно получает список всех кейсов пациента и детализацию первого из них:
    семплы, кассеты первого семпла и стекла этих кассет (оптимизированная загрузка).
    Использует model_validate вместо устаревшего from_orm.
    """
    # 1. Получаем список всех кейсов пациента
    cases_result = await db.execute(
        select(db_models.Case).where(db_models.Case.patient_id == patient_id)
    )
    all_cases_db = cases_result.scalars().all()
    all_cases = all_cases_db

    first_case_details = None
    if all_cases_db:
        first_case_db = all_cases_db[0]

        # 2. Получаем семплы первого кейса и связанные с ними кассеты и стекла
        samples_result = await db.execute(
            select(db_models.Sample)
            .where(db_models.Sample.case_id == first_case_db.id)
            .options(
                selectinload(db_models.Sample.cassette).selectinload(
                    db_models.Cassette.glass
                )
            )
        )
        first_case_samples_db = samples_result.scalars().all()
        first_case_samples = []
        for sample_db in first_case_samples_db:
            sample = SampleModelScheema.model_validate(sample_db).model_dump()
            sample["cassettes"] = []
            for cassette_db in sample_db.cassette:
                cassette = CassetteModelScheema.model_validate(cassette_db).model_dump()
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
        }

    return {"all_cases": all_cases, "first_case_details": first_case_details}

async def update_case_code_suffix(db: AsyncSession, case_id: str, new_suffix: str):
    """Асинхронно оновлює останні 5 символів коду кейса."""
    if len(new_suffix) != 5 or not new_suffix.isdigit():
        raise ValueError("Новий суфікс повинен складатися з 5 цифрових символів.")

    result = await db.execute(
        select(db_models.Case).where(db_models.Case.id == case_id)
    )
    db_case = result.scalar_one_or_none()

    if db_case:
        current_code = db_case.case_code
        if len(current_code) >= 4:
            new_case_code = f"{current_code[:-5]}{new_suffix}"
            db_case.case_code = new_case_code
            await db.commit()
            await db.refresh(db_case)
            return db_case
        else:
            raise ValueError(f"Поточний код кейса '{current_code}' занадто короткий для оновлення суфікса.")
    return None