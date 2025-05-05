from string import ascii_uppercase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.schemas import (
    Case as CaseModelScheema,
    CaseBase as CaseBaseScheema,
    Sample as SampleModelScheema,
    Cassette as CassetteModelScheema,
    Glass as GlassModelScheema,
    SampleCreate,
)
from typing import List
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import selectinload
from cor_pass.database import models as db_models
from cor_pass.repository import case as repository_cases


async def get_sample(db: AsyncSession, sample_id: str) -> SampleModelScheema | None:
    """Асинхронно получает информацию о семпле по ID, включая связанные кассеты и стекла."""
    sample_result = await db.execute(
        select(db_models.Sample)
        .where(db_models.Sample.id == sample_id)
        .options(
            selectinload(db_models.Sample.cassette).selectinload(
                db_models.Cassette.glass
            )
        )
    )
    sample_db = sample_result.scalar_one_or_none()

    if sample_db:
        # Используем model_validate для преобразования Sample SQLAlchemy-объекта в SampleModelScheema
        sample_schema = SampleModelScheema.model_validate(sample_db)
        sample_schema.cassettes = []
        for cassette_db in sample_db.cassette:
            cassette_schema = CassetteModelScheema.model_validate(cassette_db)
            cassette_schema.glasses = [
                GlassModelScheema.model_validate(glass) for glass in cassette_db.glass
            ]
            sample_schema.cassettes.append(cassette_schema)
        return sample_schema
    return None


async def get_single_sample(db: AsyncSession, sample_id: str) -> db_models.Case | None:
    """Асинхронно получает информацию о кейсе по его ID, включая связанные банки."""
    sample_result = await db.execute(
        select(db_models.Sample)
        .where(db_models.Sample.id == sample_id)
        .options(selectinload(db_models.Sample.case))
    )
    return sample_result.scalar_one_or_none()


async def create_sample(
    db: AsyncSession, case_id: str, sample_in: SampleCreate
) -> SampleModelScheema:
    """Асинхронно создает новую банку для указанного кейса, нумеруя ее следующей буквой."""

    # 1. Получаем текущий кейс
    db_case = await repository_cases.get_single_case(db=db, case_id=case_id)
    if not db_case:
        # Обработка случая, если кейс не найден
        raise ValueError(f"Кейс с ID {case_id} не найден")

    # 2. Получаем все семплы текущего кейса, чтобы определить следующий номер
    samples_result = await db.execute(
        select(db_models.Sample.sample_number)
        .where(db_models.Sample.case_id == db_case.id)
        .order_by(
            db_models.Sample.sample_number
        )  # Важно для определения последнего номера
    )
    existing_sample_numbers = samples_result.scalars().all()

    next_sample_number = "A"
    if existing_sample_numbers:
        last_sample_number = existing_sample_numbers[-1]
        try:
            last_index = ascii_uppercase.index(last_sample_number)
            if last_index < len(ascii_uppercase) - 1:
                next_sample_number = ascii_uppercase[last_index + 1]
            else:
                # Обработка ситуации, когда закончились буквы (можно расширить логику при необходимости)
                next_sample_number = (
                    f"Z{len(existing_sample_numbers) + 1 - len(ascii_uppercase)}"
                )
        except ValueError:
            # Обработка случая, если номер семпла не является латинской буквой (например, если были ошибки в данных)
            # В этом случае просто присваиваем следующую букву после 'A'
            next_sample_number = "B"

    # 3. Создаем новую банку
    db_sample = db_models.Sample(case_id=db_case.id, sample_number=next_sample_number)
    db_case.bank_count += 1
    db.add(db_sample)
    await db.commit()
    await db.refresh(db_sample)
    await db.refresh(db_case)

    # 4. Автоматически создаем одну кассету
    db_cassette = db_models.Cassette(
        sample_id=db_sample.id, cassette_number=f"{db_sample.sample_number}1"
    )
    db.add(db_cassette)
    db_case.cassette_count += 1
    db_sample.cassette_count += 1
    await db.commit()
    await db.refresh(db_cassette)
    await db.refresh(db_case)
    await db.refresh(db_sample)

    # 5. Автоматически создаем одно стекло
    db_glass = db_models.Glass(
        cassette_id=db_cassette.id, glass_number=0, staining=db_models.StainingType.HE
    )
    db.add(db_glass)
    db_case.glass_count += 1
    db_sample.glass_count += 1
    await db.commit()
    await db.refresh(db_glass)
    await db.refresh(db_case)
    await db.refresh(db_sample)

    return SampleModelScheema.model_validate(db_sample)


async def delete_sample(db: AsyncSession, sample_id: str) -> SampleModelScheema | None:
    """Асинхронно удаляет банку."""
    result = await db.execute(
        select(db_models.Sample).where(db_models.Sample.id == sample_id)
    )
    db_sample = result.scalar_one_or_none()
    if db_sample:
        await db.delete(db_sample)
        await db.commit()
        return {"message": f"Семпл с ID {sample_id} успешно удалён"}
    return None
