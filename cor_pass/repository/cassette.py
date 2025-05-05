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
from typing import List, Optional
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import selectinload
from cor_pass.database import models as db_models
from cor_pass.repository import case as repository_cases
from cor_pass.repository import sample as repository_samples


async def get_cassette(
    db: AsyncSession, cassette_id: str
) -> CassetteModelScheema | None:
    """Асинхронно получает информацию о кассете по её ID, включая связанные стекла."""
    cassette_result = await db.execute(
        select(db_models.Cassette)
        .where(db_models.Cassette.id == cassette_id)
        .options(selectinload(db_models.Cassette.glass))
    )
    cassette_db = cassette_result.scalar_one_or_none()

    if cassette_db:
        # Используем model_validate для преобразования Cassette SQLAlchemy-объекта в CassetteModelScheema
        cassette_schema = CassetteModelScheema.model_validate(cassette_db)
        cassette_schema.glasses = [
            GlassModelScheema.model_validate(glass) for glass in cassette_db.glass
        ]
        return cassette_schema
    return None


async def create_cassette(
    db: AsyncSession,
    sample_id: str,
    num_cassettes: int = 1,
    num_glasses_per_cassette: int = 1,
) -> Optional[SampleModelScheema]:
    """
    Асинхронно создает указанное количество кассет для существующего семпла
    и указанное количество стекол для каждой кассеты, обновляя счетчики.
    """
    # 1. Получаем текущий семпл
    # sample_result = await db.execute(
    #     select(db_models.Sample).where(db_models.Sample.id == sample_id).options(
    #         selectinload(db_models.Sample.case)
    #     )
    # )
    # db_sample = sample_result.scalar_one_or_none()

    db_sample = await repository_samples.get_single_sample(db=db, sample_id=sample_id)
    if not db_sample:
        raise ValueError(f"Семпл с ID {sample_id} не найден")

    db_case_id = db_sample.case_id
    db_case = await repository_cases.get_single_case(db=db, case_id=db_case_id)

    created_cassettes: List[db_models.Cassette] = []
    created_glasses_count = 0

    # 2. Создаем указанное количество кассет
    for i in range(num_cassettes):
        # next_cassette_number = db_sample.cassette_count + i + 1
        next_cassette_number = (
            f"{db_sample.sample_number}{db_sample.cassette_count + i + 1}"
        )
        db_cassette = db_models.Cassette(
            sample_id=db_sample.id, cassette_number=next_cassette_number
        )
        db.add(db_cassette)
        created_cassettes.append(db_cassette)
        db_sample.cassette_count += 1
        db_case.cassette_count += 1
        await db.commit()
        await db.refresh(db_cassette)

        # 3. Создаем указанное количество стекол для каждой кассеты
        for j in range(num_glasses_per_cassette):
            next_glass_number = db_cassette.glass_count + j
            db_glass = db_models.Glass(
                cassette_id=db_cassette.id,
                glass_number=next_glass_number,
                staining=db_models.StainingType.HE,
            )
            db.add(db_glass)
            db_sample.glass_count += 1
            db_case.glass_count += 1
            db_cassette.glass_count += 1
            await db.commit()
            await db.refresh(db_glass)

    await db.commit()

    # 4. Обновляем объекты в сессии, чтобы подгрузить связи и счетчики
    await db.refresh(db_sample)
    await db.refresh(db_case)
    for cassette in created_cassettes:
        await db.refresh(cassette)

    return created_cassettes
    # return CassetteModelScheema.model_validate(db_cassette)


async def delete_cassette(
    db: AsyncSession, cassette_id: str
) -> SampleModelScheema | None:
    """Асинхронно удаляет касетту."""
    result = await db.execute(
        select(db_models.Cassette).where(db_models.Cassette.id == cassette_id)
    )
    db_cassette = result.scalar_one_or_none()
    if db_cassette:
        await db.delete(db_cassette)
        await db.commit()
        return {"message": f"Кассета с ID {cassette_id} успешно удалена"}
    return None
