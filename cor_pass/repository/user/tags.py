from typing import Any, Dict, List

from sqlalchemy import select


from cor_pass.database.models import Tag
from cor_pass.schemas import TagModel, TagResponse
from sqlalchemy.ext.asyncio import AsyncSession


async def get_tags(skip: int, limit: int, db: AsyncSession) -> List[Dict[str, Any]]:
    """
    Асинхронно получает перечень тегов из базы данных.

    """
    stmt = select(Tag).offset(skip).limit(limit)
    result = await db.execute(stmt)
    tags = result.scalars().all()
    tag_dicts = [{"name": tag.name, "id": str(tag.id)} for tag in tags]
    return tag_dicts


async def get_tag(tag_id: int, db: AsyncSession) -> Tag | None:
    """
    Асинхронно получает тег из базы данных по его ID.

    """
    stmt = select(Tag).where(Tag.id == tag_id)
    result = await db.execute(stmt)
    tag = result.scalar_one_or_none()
    return tag


async def create_tag(body: TagModel, db: AsyncSession) -> TagResponse:
    """
    Асинхронно создает новый тэг в базе данных.

    """
    tag = Tag(name=body.name)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return TagResponse(id=tag.id, name=tag.name)


async def update_tag(tag_id: int, body: TagModel, db: AsyncSession) -> Tag | None:
    """
    Асинхронно обновляет существующий тэг в базе данных.

    """
    stmt = select(Tag).where(Tag.id == tag_id)
    result = await db.execute(stmt)
    tag = result.scalar_one_or_none()
    if tag:
        tag.name = body.name
        await db.commit()
        await db.refresh(tag)
        return tag
    return None


async def remove_tag(tag_id: int, db: AsyncSession) -> Tag | None:
    """
    Асинхронно удаляет тэг из базы данных.

    """
    stmt = select(Tag).where(Tag.id == tag_id)
    result = await db.execute(stmt)
    tag = result.scalar_one_or_none()
    if tag:
        await db.delete(tag)
        await db.commit()
        return tag
    return None
