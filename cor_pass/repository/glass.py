from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.schemas import Glass as GlassModelScheema
from typing import Any, Dict, List
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


async def create_glass(
    db: AsyncSession,
    cassette_id: str,
    staining_type: db_models.StainingType = db_models.StainingType.HE,
    num_glasses: int = 1,
) -> List[GlassModelScheema]:
    """
    Асинхронно создает указанное количество стекол для существующей кассеты,
    обеспечивая последовательную нумерацию даже после удаления стекол.
    Обновляет счетчики стекол в кассете, семпле и кейсе.
    """

    # 1. Получаем текущую кассету и связанные с ней семпл и кейс
    cassette_result = await db.execute(
        select(db_models.Cassette)
        .where(db_models.Cassette.id == cassette_id)
        .options(
            selectinload(db_models.Cassette.sample).selectinload(db_models.Sample.case)
        )
    )
    db_cassette = cassette_result.scalar_one_or_none()
    if not db_cassette:
        raise ValueError(f"Кассету с ID {cassette_id} не найдено")

    db_sample = await db.get(db_models.Sample, db_cassette.sample_id)
    if not db_sample:
        raise ValueError(f"Семпл с ID {db_cassette.sample_id} не найден")

    db_case = await db.get(db_models.Case, db_sample.case_id)

    created_glasses: List[db_models.Glass] = []

    # 2. Получаем существующие номера стекол для кассеты
    existing_glasses_result = await db.execute(
        select(db_models.Glass.glass_number)
        .where(db_models.Glass.cassette_id == db_cassette.id)
        .order_by(db_models.Glass.glass_number)
    )
    existing_glass_numbers = {
        result[0] for result in existing_glasses_result.fetchall()
    }

    # 3. Создаем указанное количество стекол
    next_glass_number = 0
    for _ in range(num_glasses):
        while next_glass_number in existing_glass_numbers:
            next_glass_number += 1

        db_glass = db_models.Glass(
            cassette_id=db_cassette.id,
            glass_number=next_glass_number,
            staining=staining_type,
        )
        db.add(db_glass)
        created_glasses.append(db_glass)
        existing_glass_numbers.add(next_glass_number)
        next_glass_number += 1

        # 4. Обновляем счетчики стекол
        db_cassette.glass_count += 1
        db_sample.glass_count += 1
        db_case.glass_count += 1

    await db.commit()

    # 5. Обновляем объекты в сессии
    await db.refresh(db_cassette)
    await db.refresh(db_sample)
    await db.refresh(db_case)
    for glass in created_glasses:
        await db.refresh(glass)

    return [
        GlassModelScheema.model_validate(glass).model_dump()
        for glass in created_glasses
    ]


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
            # 1. Отримуємо поточну касету, а також пов'язані з нею семпл та кейс
            cassette_result = await db.execute(
                select(db_models.Cassette)
                .where(db_models.Cassette.id == db_glass.cassette_id)
                .options(
                    selectinload(db_models.Cassette.sample).selectinload(
                        db_models.Sample.case
                    )
                )
            )
            db_cassette = cassette_result.scalar_one_or_none()
            if not db_cassette:
                raise ValueError(f"Касету з ID {db_glass.cassette_id} не знайдено")

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
            await db.delete(db_glass)
            deleted_count += 1
            # 3. Оновлюємо лічильники скелець
            db_cassette.glass_count -= 1
            db_sample.glass_count -= 1
            db_case.glass_count -= 1
            await db.commit()
            await db.refresh(db_cassette)
            await db.refresh(db_sample)
            await db.refresh(db_case)
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
