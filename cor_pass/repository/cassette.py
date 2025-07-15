from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.schemas import (
    CassetteUpdateComment,
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
            key=lambda glass_schema: glass_schema.glass_number,
        )
        return cassette_schema
    return None


async def create_cassette(
    db: AsyncSession,
    sample_id: str,
    num_cassettes: int = 1,
    printing: bool = False
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
        next_cassette_number = (
            f"{db_sample.sample_number}{db_sample.cassette_count + 1}"
        )
        db_cassette = db_models.Cassette(
            sample_id=db_sample.id, cassette_number=next_cassette_number, is_printed = printing
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
            is_printed=False
        )
        db.add(db_glass)
        db_sample.glass_count += 1
        db_case.glass_count += 1
        db_cassette.glass_count += 1
        await db.commit()
        await db.refresh(db_glass)
        await repository_cases._update_ancestor_statuses_from_glass(db=db, glass=db_glass)

    await db.refresh(db_sample)
    await db.refresh(db_case)

    created_cassettes_with_glasses = []
    for cassette_db in created_cassettes_db:
        await db.refresh(cassette_db, attribute_names=["glass"])
        cassette_schema = CassetteModelScheema.model_validate(cassette_db)
        cassette_schema.glasses = sorted(
            [GlassModelScheema.model_validate(glass) for glass in cassette_db.glass],
            key=lambda glass_schema: glass_schema.glass_number,
        )
        created_cassettes_with_glasses.append(cassette_schema.model_dump())

        await repository_cases._update_ancestor_statuses_from_cassette(db=db, cassette=cassette_db)
    return created_cassettes_with_glasses


async def update_cassette_comment(
    db: AsyncSession, cassette_id: str, comment_update: CassetteUpdateComment
) -> Optional[CassetteModelScheema]:
    """Асинхронно обновляет комментарий кассеты по ID."""
    result = await db.execute(
        select(db_models.Cassette).where(db_models.Cassette.id == cassette_id)
    )
    cassette_db = result.scalar_one_or_none()
    if cassette_db:
        if comment_update.comment is not None:
            cassette_db.comment = comment_update.comment
        await db.commit()
        await db.refresh(cassette_db)
        return CassetteModelScheema.model_validate(cassette_db)
    return None


async def delete_cassettes(
    db: AsyncSession, cassettes_ids: List[str]
) -> Dict[str, Any]:
    """Асинхронно удаляет несколько кассет по их ID и корректно обновляет счетчики."""
    deleted_count = 0
    not_found_ids: List[str] = []

    for cassette_id in cassettes_ids:
        result = await db.execute(
            select(db_models.Cassette)
            .where(db_models.Cassette.id == cassette_id)
            .options(
                selectinload(db_models.Cassette.glass)
            )  
        )
        db_cassette = result.scalar_one_or_none()
        if db_cassette:
            
            sample_result = await db.execute(
                select(db_models.Sample)
                .where(db_models.Sample.id == db_cassette.sample_id)
                .options(selectinload(db_models.Sample.case))
            )
            db_sample = sample_result.scalar_one_or_none()
            if not db_sample:
                raise ValueError(f"Семпл с ID {db_cassette.sample_id} не найден")

            db_case = await db.get(db_models.Case, db_sample.case_id)

            
            num_glasses_to_decrement = len(db_cassette.glass)
            await repository_cases._update_ancestor_statuses_from_cassette(db=db, cassette=db_cassette)

            await db.delete(db_cassette)
            deleted_count += 1

            
            db_sample.glass_count -= num_glasses_to_decrement
            db_sample.cassette_count -= 1

            db_case.glass_count -= num_glasses_to_decrement
            db_case.cassette_count -= 1

            await db.commit()

            await db.refresh(db_sample)
            await db.refresh(db_case)

        else:
            not_found_ids.append(cassette_id)

    response = {"deleted_count": deleted_count}
    if not_found_ids:
        response["message"] = (
            f"Успешно удалено {deleted_count} кассет. Не найдены ID: {not_found_ids}"
        )
    else:
        response["message"] = f"Успешно удалено {deleted_count} кассет."

    return response



async def change_printing_status(
    db: AsyncSession, cassette_id: str, printing: bool
) -> Optional[CassetteModelScheema]:
    """Меняем статус печати кассеты """
    result = await db.execute(
        select(db_models.Cassette).where(db_models.Cassette.id == cassette_id)
    )
    cassette_db = result.scalar_one_or_none()
    if cassette_db:
        cassette_db.is_printed = printing
        await db.commit()
        await db.refresh(cassette_db)
        await repository_cases._update_ancestor_statuses_from_cassette(db=db, cassette=cassette_db)
        return CassetteModelScheema.model_validate(cassette_db)
    return None