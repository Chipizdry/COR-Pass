from typing import List
from sqlalchemy import and_, select


from cor_pass.database.models import User, Record, Tag
from cor_pass.schemas import CreateRecordModel, UpdateRecordModel
from cor_pass.services.cipher import encrypt_data, decrypt_data, decrypt_user_key

from sqlalchemy.ext.asyncio import AsyncSession


async def create_record(
    body: CreateRecordModel, db: AsyncSession, user: User
) -> Record:
    if not user:
        raise Exception("User not found")
    new_record = Record(
        record_name=body.record_name,
        user_id=user.id,
        website=body.website,
        username=await encrypt_data(
            data=body.username, key=await decrypt_user_key(user.unique_cipher_key)
        ),
        password=await encrypt_data(
            data=body.password, key=await decrypt_user_key(user.unique_cipher_key)
        ),
        notes=body.notes,
    )
    if body.tag_names:
        for tag_name in body.tag_names:
            tag_stmt = select(Tag).where(Tag.name == tag_name)
            tag_result = await db.execute(tag_stmt)
            tag = tag_result.scalar_one_or_none()
            if not tag:
                tag = Tag(name=tag_name)
            new_record.tags.append(tag)

    db.add(new_record)
    await db.commit()
    await db.refresh(new_record)
    return new_record


async def get_record_by_id(user: User, db: AsyncSession, record_id: int):
    """
    Асинхронно получает запись по ID, проверяя принадлежность пользователю, и дешифрует данные.
    """
    stmt = (
        select(Record)
        .join(User, Record.user_id == User.id)
        .where(and_(Record.record_id == record_id, User.id == user.id))
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if record:
        record.password = await decrypt_data(
            encrypted_data=record.password,
            key=await decrypt_user_key(user.unique_cipher_key),
        )
        record.username = await decrypt_data(
            encrypted_data=record.username,
            key=await decrypt_user_key(user.unique_cipher_key),
        )
    return record


async def get_all_user_records(
    db: AsyncSession, user_id: str, skip: int, limit: int
) -> List[Record]:
    """
    Асинхронно получает все записи конкретного пользователя из базы данных с учетом пагинации.
    """
    stmt = select(Record).where(Record.user_id == user_id).offset(skip).limit(limit)
    result = await db.execute(stmt)
    records = result.scalars().all()
    return list(records)


async def update_record(
    record_id: int, body: UpdateRecordModel, user: User, db: AsyncSession
):
    """
    Асинхронно обновляет существующую запись, проверяя ее принадлежность пользователю.
    """
    stmt = (
        select(Record)
        .join(User, Record.user_id == User.id)
        .where(and_(Record.record_id == record_id, User.id == user.id))
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if record:
        record.record_name = body.record_name
        record.website = body.website
        record.username = await encrypt_data(
            data=body.username, key=await decrypt_user_key(user.unique_cipher_key)
        )
        record.password = await encrypt_data(
            data=body.password, key=await decrypt_user_key(user.unique_cipher_key)
        )
        record.notes = body.notes

        await db.commit()
        await db.refresh(record)
        return record
    return None


async def make_favorite(
    record_id: int, is_favorite: bool, user: User, db: AsyncSession
):
    """
    Асинхронно изменяет статус для записи.
    """
    stmt = (
        select(Record)
        .join(User, Record.user_id == User.id)
        .where(and_(Record.record_id == record_id, User.id == user.id))
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if record:
        record.is_favorite = is_favorite
        await db.commit()
        await db.refresh(record)
        return record
    return None


async def delete_record(user: User, db: AsyncSession, record_id: int):
    """
    Асинхронно удаляет запись, проверяя ее принадлежность пользователю.
    """
    stmt = (
        select(Record)
        .join(User, Record.user_id == User.id)
        .where(and_(Record.record_id == record_id, Record.user_id == user.id))
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        return None

    await db.delete(record)
    await db.commit()
    print("Record deleted")
    return record
