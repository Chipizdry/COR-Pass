import re
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
from typing import Any, Dict, List
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import selectinload
from cor_pass.database import models as db_models
from cor_pass.repository import case as repository_cases


async def get_sample(db: AsyncSession, sample_id: str) -> SampleModelScheema | None:
    """Асинхронно получает информацию о семпле по ID, включая связанные кассеты и стекла с корректной сортировкой."""
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
        sample_schema = SampleModelScheema.model_validate(sample_db)
        sample_schema.cassettes = []

        def sort_cassettes(cassette):
            match = re.match(r'([A-Z]+)(\d+)', cassette.cassette_number)
            if match:
                letter_part = match.group(1)
                number_part = int(match.group(2))
                return (letter_part, number_part)
            return (cassette.cassette_number, 0)  # Для случаев, если формат не совпадает

        sorted_cassettes = sorted(sample_db.cassette, key=sort_cassettes)

        for cassette_db in sorted_cassettes:
            cassette_schema = CassetteModelScheema.model_validate(cassette_db)
            cassette_schema.glasses = sorted(
                [GlassModelScheema.model_validate(glass) for glass in cassette_db.glass],
                key=lambda glass_schema: glass_schema.glass_number
            )
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


# async def create_sample(
#     db: AsyncSession, case_id: str, num_samples: int = 1
# ) -> List[SampleModelScheema]:
#     """
#     Асинхронно создает указанное количество новых банок для указанного кейса,
#     нумеруя их последовательными буквами, и автоматически создает первую кассету и стекло.
#     """
#     db_case = await repository_cases.get_single_case(db=db, case_id=case_id)
#     if not db_case:
#         raise ValueError(f"Кейс с ID {case_id} не найден")

#     created_samples: List[db_models.Sample] = []

#     # 1. Получаем все семплы текущего кейса для определения начального номера
#     samples_result = await db.execute(
#         select(db_models.Sample.sample_number)
#         .where(db_models.Sample.case_id == db_case.id)
#         .order_by(db_models.Sample.sample_number)
#     )
#     existing_sample_numbers = samples_result.scalars().all()

#     next_sample_char = "A"
#     if existing_sample_numbers:
#         last_sample_number = existing_sample_numbers[-1]
#         try:
#             last_index = ascii_uppercase.index(last_sample_number)
#             if last_index < len(ascii_uppercase) - 1:
#                 next_sample_char = ascii_uppercase[last_index + 1]
#             else:
#                 # Обработка ситуации, когда закончились буквы
#                 next_sample_char = f"Z{len(existing_sample_numbers) + 1 - len(ascii_uppercase)}"
#         except ValueError:
#             # Обработка некорректного формата номера семпла
#             next_sample_char = "A"  # Начинаем с начала

#     # 2. Создаем указанное количество семплов
#     for i in range(num_samples):
#         sample_number = next_sample_char
#         db_sample = db_models.Sample(case_id=db_case.id, sample_number=sample_number)
#         db.add(db_sample)
#         created_samples.append(db_sample)
#         db_case.bank_count += 1
#         # db_case.sample_count += 1  # Обновляем счетчик семплов в кейсе
#         await db.commit()
#         await db.refresh(db_sample)
#         await db.refresh(db_case)

#         # 3. Автоматически создаем одну кассету для каждого семпла
#         db_cassette = db_models.Cassette(
#             sample_id=db_sample.id, cassette_number=f"{sample_number}1"
#         )
#         db.add(db_cassette)
#         db_case.cassette_count += 1
#         db_sample.cassette_count += 1
#         await db.commit()
#         await db.refresh(db_sample)
#         await db.refresh(db_case)
#         await db.refresh(db_cassette)

#         # 4. Автоматически создаем одно стекло для каждой кассеты
#         db_glass = db_models.Glass(
#             cassette_id=db_cassette.id, glass_number=0, staining=db_models.StainingType.HE
#         )
#         db.add(db_glass)
#         db_case.glass_count += 1
#         db_sample.glass_count += 1

#         await db.commit()
#         await db.refresh(db_sample)
#         await db.refresh(db_cassette)
#         await db.refresh(db_glass)
#         await db.refresh(db_case)

#         # Определяем номер следующего семпла
#         try:
#             last_index = ascii_uppercase.index(next_sample_char)
#             if last_index < len(ascii_uppercase) - 1:
#                 next_sample_char = ascii_uppercase[last_index + 1]
#             else:
#                 next_sample_char = f"Z{len(existing_sample_numbers) + 1 + i + 1 - len(ascii_uppercase)}"
#         except ValueError:
#             next_sample_char = f"A{i + 2}" # Если формат не буква, продолжаем нумерацию

#     return [SampleModelScheema.model_validate(sample) for sample in created_samples]



async def create_sample(
    db: AsyncSession, case_id: str, num_samples: int = 1
) -> Dict[str, Any]:
    """
    Асинхронно создает указанное количество новых семплов для указанного кейса,
    нумеруя их последовательными буквами, и автоматически создает первую кассету и стекло.
    Возвращает список всех созданных семплов и детализацию первого созданного семпла.
    """
    db_case = await db.get(db_models.Case, case_id)
    if not db_case:
        raise ValueError(f"Кейс с ID {case_id} не найден")

    created_samples_db: List[db_models.Sample] = []

    # 1. Получаем все семплы текущего кейса для определения начального номера
    samples_result = await db.execute(
        select(db_models.Sample.sample_number)
        .where(db_models.Sample.case_id == db_case.id)
        .order_by(db_models.Sample.sample_number)
    )
    existing_sample_numbers = samples_result.scalars().all()

    next_sample_char = "A"
    if existing_sample_numbers:
        last_sample_number = existing_sample_numbers[-1]
        try:
            last_index = ascii_uppercase.index(last_sample_number)
            if last_index < len(ascii_uppercase) - 1:
                next_sample_char = ascii_uppercase[last_index + 1]
            else:
                # Обработка ситуации, когда закончились буквы
                next_sample_char = f"Z{len(existing_sample_numbers) + 1 - len(ascii_uppercase)}"
        except ValueError:
            # Обработка некорректного формата номера семпла
            next_sample_char = "A"  # Начинаем с начала

    first_created_sample_id = None

    # 2. Создаем указанное количество семплов
    for i in range(num_samples):
        sample_number = next_sample_char
        db_sample = db_models.Sample(case_id=db_case.id, sample_number=sample_number)
        db.add(db_sample)
        created_samples_db.append(db_sample)
        db_case.bank_count += 1
        await db.commit()
        await db.refresh(db_sample)
        await db.refresh(db_case)

        if i == 0:
            first_created_sample_id = db_sample.id

        # 3. Автоматически создаем одну кассету для каждого семпла
        db_cassette = db_models.Cassette(
            sample_id=db_sample.id, cassette_number=f"{sample_number}1"
        )
        db.add(db_cassette)
        db_case.cassette_count += 1
        db_sample.cassette_count += 1
        await db.commit()
        await db.refresh(db_sample)
        await db.refresh(db_case)
        await db.refresh(db_cassette)

        # 4. Автоматически создаем одно стекло для каждой кассеты
        db_glass = db_models.Glass(
            cassette_id=db_cassette.id, glass_number=0, staining=db_models.StainingType.HE
        )
        db.add(db_glass)
        db_case.glass_count += 1
        db_sample.glass_count += 1

        await db.commit()
        await db.refresh(db_sample)
        await db.refresh(db_cassette)
        await db.refresh(db_glass)
        await db.refresh(db_case)

        # Определяем номер следующего семпла
        try:
            last_index = ascii_uppercase.index(next_sample_char)
            if last_index < len(ascii_uppercase) - 1:
                next_sample_char = ascii_uppercase[last_index + 1]
            else:
                next_sample_char = f"Z{len(existing_sample_numbers) + 1 + i + 1 - len(ascii_uppercase)}"
        except ValueError:
            next_sample_char = f"A{i + 2}" # Если формат не буква, продолжаем нумерацию

    created_samples = [SampleModelScheema.model_validate(sample).model_dump() for sample in created_samples_db]
    first_sample_details = None

    if first_created_sample_id:
        first_sample_details_db = await db.get(db_models.Sample, first_created_sample_id)
        if first_sample_details_db:
            first_sample_details_schema = SampleModelScheema.model_validate(first_sample_details_db)
            first_sample_details_schema.cassettes = []

            await db.refresh(first_sample_details_db, attribute_names=["cassette"])

            def sort_cassettes(cassette):
                match = re.match(r'([A-Z]+)(\d+)', cassette.cassette_number)
                if match:
                    letter_part = match.group(1)
                    number_part = int(match.group(2))
                    return (letter_part, number_part)
                return (cassette.cassette_number, 0)  # Для случаев, если формат не совпадает

            sorted_cassettes = sorted(first_sample_details_db.cassette, key=sort_cassettes)

            for cassette_db in sorted_cassettes:
                await db.refresh(cassette_db, attribute_names=["glass"])
                cassette_schema = CassetteModelScheema.model_validate(cassette_db)
                cassette_schema.glasses = sorted(
                    [GlassModelScheema.model_validate(glass) for glass in cassette_db.glass],
                    key=lambda glass_schema: glass_schema.glass_number
                )
                first_sample_details_schema.cassettes.append(cassette_schema)

            first_sample_details = first_sample_details_schema.model_dump()

    return {"created_samples": created_samples, "first_sample_details": first_sample_details}


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
