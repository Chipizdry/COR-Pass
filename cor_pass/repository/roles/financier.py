from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy import asc, desc, select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Query as SQLAQuery

from cor_pass.database.models import (
    Financier,
    User
)
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.schemas import FinancierCreate


async def create_financier(
    financier_data: FinancierCreate,
    db: AsyncSession,
    user: User,
) -> Financier:
    """
    Асинхронная сервисная функция по созданию финансиста.
    """
    financier = Financier(
        financier_cor_id=user.cor_id,
        first_name=financier_data.first_name,
        surname=financier_data.last_name,
        middle_name=financier_data.middle_name,
    )

    db.add(financier)

    await db.commit()
    await db.refresh(financier)

    return financier

async def get_financier(financier_cor_id: str, db: AsyncSession) -> Financier | None:
    """
    Асинхронно получает финансиста по его cor_id.
    """
    stmt = select(Financier).where(Financier.financier_cor_id == financier_cor_id)
    result = await db.execute(stmt)
    financier = result.scalar_one_or_none()
    return financier


async def get_all_financiers(
    skip: int,
    limit: int,
    db: AsyncSession,
) -> List[Financier]:
    """
    Асинхронно возвращает список всех финансистов с пагинацией.
    """
    stmt = select(Financier).offset(skip).limit(limit)
    result = await db.execute(stmt)
    financiers = result.scalars().all()
    return list(financiers)
