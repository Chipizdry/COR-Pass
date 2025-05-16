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
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import selectinload
from cor_pass.database import models as db_models
from cor_pass.repository import case as repository_cases


async def get_glass(db: AsyncSession, glass_id: int) -> GlassModelScheema | None:
    """Асинхронно получает конкретное стекло, связанное с кассетой по её ID и номеру."""
    result = await db.execute(
        select(db_models.Glass).where(db_models.Glass.id == glass_id)
    )
    glass_db = result.scalar_one_or_none()
    if glass_db:
        return GlassModelScheema.model_validate(glass_db)
        # return glass_db
    return None


# async def create_glass(
#     db: AsyncSession,
#     cassette_id: str,
#     num_glasses: int = 1,
# ) -> Optional[SampleModelScheema]:
#     """
#     Асинхронно создает указанное количество кассет для существующего семпла
#     и указанное количество стекол для каждой кассеты, обновляя счетчики.
#     """
#     # 1. Получаем текущий семпл
#     sample_result = await db.execute(
#         select(db_models.Sample).where(db_models.Sample.id == sample_id).options(
#             selectinload(db_models.Sample.case)
#         )
#     )
#     db_sample = sample_result.scalar_one_or_none()
#     if not db_sample:
#         raise ValueError(f"Семпл с ID {sample_id} не найден")

#     db_case_id = db_sample.case_id
#     db_case = await repository_cases.get_single_case(db=db, case_id=db_case_id)

#     created_cassettes: List[db_models.Cassette] = []
#     created_glasses_count = 0

#     # 2. Создаем указанное количество кассет
#     for i in range(num_cassettes):
#         next_cassette_number = db_sample.cassette_count + i + 1
#         db_cassette = db_models.Cassette(sample_id=db_sample.id, cassette_number=next_cassette_number)
#         db.add(db_cassette)
#         created_cassettes.append(db_cassette)
#         db_sample.cassette_count += 1
#         db_case.cassette_count += 1
#         await db.commit()
#         await db.refresh(db_cassette)

#         # 3. Создаем указанное количество стекол для каждой кассеты
#         for j in range(num_glasses_per_cassette):
#             next_glass_number = j
#             db_glass = db_models.Glass(cassette_id=db_cassette.id, glass_number=next_glass_number)
#             db.add(db_glass)
#             db_sample.glass_count += 1
#             db_case.glass_count += 1
#             created_glasses_count += 1
#             await db.commit()
#             await db.refresh(db_glass)

#     await db.commit()

#     # 4. Обновляем объекты в сессии, чтобы подгрузить связи и счетчики
#     await db.refresh(db_sample)
#     await db.refresh(db_case)
#     for cassette in created_cassettes:
#         await db.refresh(cassette)

#     return created_cassettes
#     # return CassetteModelScheema.model_validate(db_cassette)


async def create_glass(
    db: AsyncSession,
    cassette_id: str,
    staining_type: db_models.StainingType = db_models.StainingType.HE,
    num_glasses: int = 1,
) -> list[db_models.Glass]:
    """
    Асинхронно створює вказану кількість скелець для існуючої касети
    та оновлює лічильники скелець у касеті, семплі та кейсі.
    """

    # 1. Отримуємо поточну касету, а також пов'язані з нею семпл та кейс
    cassette_result = await db.execute(
        select(db_models.Cassette)
        .where(db_models.Cassette.id == cassette_id)
        .options(
            selectinload(db_models.Cassette.sample).selectinload(db_models.Sample.case)
        )
    )
    db_cassette = cassette_result.scalar_one_or_none()
    if not db_cassette:
        raise ValueError(f"Касету з ID {cassette_id} не знайдено")

    # Получаем текущий семпл
    sample_result = await db.execute(
        select(db_models.Sample)
        .where(db_models.Sample.id == db_cassette.sample_id)
        .options(selectinload(db_models.Sample.case))
    )
    db_sample = sample_result.scalar_one_or_none()
    if not db_sample:
        raise ValueError(f"Семпл с ID {db_cassette.sample_id} не найден")

    db_case_id = db_sample.case_id
    db_case = await repository_cases.get_single_case(db=db, case_id=db_case_id)

    db_sample = db_sample
    db_case = db_case

    created_glasses: List[db_models.Glass] = []

    # 2. Створюємо вказану кількість скелець для касети
    for i in range(num_glasses):
        next_glass_number = db_cassette.glass_count + 1
        db_glass = db_models.Glass(
            cassette_id=db_cassette.id,
            glass_number=next_glass_number,
            staining=staining_type,
        )
        db.add(db_glass)
        created_glasses.append(db_glass)

        # 3. Оновлюємо лічильники скелець
        db_cassette.glass_count += 1
        db_sample.glass_count += 1
        db_case.glass_count += 1

    await db.commit()

    # 4. Оновлюємо об'єкти в сесії, щоб підвантажити всі зміни
    await db.refresh(db_cassette)
    await db.refresh(db_sample)
    await db.refresh(db_case)
    for glass in created_glasses:
        await db.refresh(glass)

    # return created_glasses
    return [GlassModelScheema.model_validate(glass) for glass in created_glasses]


async def delete_glasses(db: AsyncSession, glass_ids: List[str]) -> Dict[str, Any]:
    """Асинхронно удаляет несколько стекол по их ID."""
    deleted_count = 0
    not_found_ids: List[str] = []

    for glass_id in glass_ids:
        result = await db.execute(
            select(db_models.Glass).where(db_models.Glass.id == glass_id)
        )
        db_glass = result.scalar_one_or_none()
        if db_glass:
            await db.delete(db_glass)
            deleted_count += 1
        else:
            not_found_ids.append(glass_id)

    await db.commit()

    response = {"deleted_count": deleted_count}
    if not_found_ids:
        response["not_found_ids"] = not_found_ids
    response["message"] = f"Успешно удалено {deleted_count} стекол."
    if not_found_ids:
        response["message"] += f" Стекла с ID {', '.join(not_found_ids)} не найдены."

    return response
