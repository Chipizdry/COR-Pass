from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.schemas import (
    Sample as SampleModelScheema,
    Cassette as CassetteModelScheema,
    Glass as GlassModelScheema,
)
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import selectinload
from cor_pass.database import models as db_models
from cor_pass.repository import case as repository_cases
from cor_pass.repository import sample as repository_samples


async def get_cassette(
    db: AsyncSession, cassette_id: str
) -> CassetteModelScheema | None:
    """Асинхронно получает информацию о кассете по её ID, включая связанные стекла с сортировкой."""
    cassette_result = await db.execute(
        select(db_models.Cassette)
        .where(db_models.Cassette.id == cassette_id)
        .options(selectinload(db_models.Cassette.glass))
    )
    cassette_db = cassette_result.scalar_one_or_none()

    if cassette_db:
        cassette_schema = CassetteModelScheema.model_validate(cassette_db)
        # Сортируем стекла по glass_number
        cassette_schema.glasses = sorted(
            [GlassModelScheema.model_validate(glass) for glass in cassette_db.glass],
            key=lambda glass_schema: glass_schema.glass_number
        )
        return cassette_schema
    return None


# async def create_cassette(
#     db: AsyncSession,
#     sample_id: str,
#     num_cassettes: int = 1,
#     num_glasses_per_cassette: int = 1,
# ) -> Optional[SampleModelScheema]:
#     """
#     Асинхронно создает указанное количество кассет для существующего семпла
#     и указанное количество стекол для каждой кассеты, обновляя счетчики.
#     Корректная последовательная нумерация кассет при многократном вызове.
#     """

#     db_sample = await repository_samples.get_single_sample(db=db, sample_id=sample_id)
#     if not db_sample:
#         raise ValueError(f"Семпл с ID {sample_id} не найден")

#     db_case_id = db_sample.case_id
#     db_case = await repository_cases.get_single_case(db=db, case_id=db_case_id)

#     created_cassettes: List[db_models.Cassette] = []

#     # 2. Создаем указанное количество кассет
#     for i in range(num_cassettes):
#         # Получаем актуальное количество кассет перед созданием новой
#         await db.refresh(db_sample)
#         next_cassette_number = f"{db_sample.sample_number}{db_sample.cassette_count + 1}"
#         db_cassette = db_models.Cassette(
#             sample_id=db_sample.id, cassette_number=next_cassette_number
#         )
#         db.add(db_cassette)
#         created_cassettes.append(db_cassette)
#         db_sample.cassette_count += 1
#         db_case.cassette_count += 1
#         await db.commit()
#         await db.refresh(db_cassette)

#         # 3. Создаем указанное количество стекол для каждой кассеты
#         for j in range(num_glasses_per_cassette):
#             next_glass_number = j
#             db_glass = db_models.Glass(
#                 cassette_id=db_cassette.id,
#                 glass_number=next_glass_number,
#                 staining=db_models.StainingType.HE,
#             )
#             db.add(db_glass)
#             db_sample.glass_count += 1
#             db_case.glass_count += 1
#             db_cassette.glass_count += 1
#             await db.commit()
#             await db.refresh(db_glass)

#     await db.commit()

#     # 4. Обновляем объекты в сессии
#     await db.refresh(db_sample)
#     await db.refresh(db_case)
#     for cassette in created_cassettes:
#         await db.refresh(cassette)

#     return [CassetteModelScheema.model_validate(cassette) for cassette in created_cassettes]

async def create_cassette(
    db: AsyncSession,
    sample_id: str,
    num_cassettes: int = 1,
) -> Dict[str, Any]:
    """
    Асинхронно создает указанное количество кассет для существующего семпла
    и возвращает список всех созданных кассет с их стеклами.
    """

    db_sample = await db.get(db_models.Sample, sample_id)
    if not db_sample:
        raise ValueError(f"Семпл с ID {sample_id} не найден")

    db_case = await db.get(db_models.Case, db_sample.case_id)

    created_cassettes_db: List[db_models.Cassette] = []

    for i in range(num_cassettes):
        await db.refresh(db_sample)
        next_cassette_number = f"{db_sample.sample_number}{db_sample.cassette_count + 1}"
        db_cassette = db_models.Cassette(
            sample_id=db_sample.id, cassette_number=next_cassette_number
        )
        db.add(db_cassette)
        created_cassettes_db.append(db_cassette)
        db_sample.cassette_count += 1
        db_case.cassette_count += 1
        await db.commit()
        await db.refresh(db_cassette)

        # Автоматически создаем одно стекло для каждой кассеты
        db_glass = db_models.Glass(
            cassette_id=db_cassette.id,
            glass_number=0,
            staining=db_models.StainingType.HE,
        )
        db.add(db_glass)
        db_sample.glass_count += 1
        db_case.glass_count += 1
        db_cassette.glass_count += 1
        await db.commit()
        await db.refresh(db_glass)

    await db.refresh(db_sample)
    await db.refresh(db_case)
    for cassette in created_cassettes_db:
        await db.refresh(cassette, attribute_names=["glass"])

    created_cassettes_with_glasses = []
    for cassette_db in created_cassettes_db:
        cassette_schema = CassetteModelScheema.model_validate(cassette_db)
        cassette_schema.glasses = sorted(
            [GlassModelScheema.model_validate(glass) for glass in cassette_db.glass],
            key=lambda glass_schema: glass_schema.glass_number
        )
        created_cassettes_with_glasses.append(cassette_schema.model_dump())

    return created_cassettes_with_glasses


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
