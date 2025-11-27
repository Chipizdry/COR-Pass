from datetime import date, datetime
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from cor_pass.database.models import FirstAidKit, FirstAidKitItem, Medicine, User

from cor_pass.schemas import (
    FirstAidKitCreate,
    FirstAidKitUpdate,
    FirstAidKitItemCreate,
    FirstAidKitItemUpdate,
)


async def create_first_aid_kit(
    db: AsyncSession, body: FirstAidKitCreate, user: User
) -> FirstAidKit:
    """
    Создает новую аптечку для пользователя.
    """
    new_kit = FirstAidKit(
        name=body.name,
        description=body.description,
        user_cor_id=user.cor_id,
    )
    db.add(new_kit)
    await db.commit()
    await db.refresh(new_kit)
    return new_kit


async def get_user_first_aid_by_name(db: AsyncSession, user: User, kit_name: str) -> List[FirstAidKit]:
    """
    Возвращает аптечку по названию.
    """
    result = await db.execute(
        select(FirstAidKit).where(FirstAidKit.user_cor_id == user.cor_id).where(FirstAidKit.name == kit_name)
    )
    return result.scalar_one_or_none()

async def get_user_first_aid_kits(db: AsyncSession, user: User) -> List[FirstAidKit]:
    """
    Возвращает все аптечки пользователя.
    """
    result = await db.execute(
        select(FirstAidKit).where(FirstAidKit.user_cor_id == user.cor_id).order_by(FirstAidKit.created_at.desc())
    )
    return result.scalars().all()


async def get_first_aid_kit_by_id(db: AsyncSession, kit_id: str, user: User) -> Optional[FirstAidKit]:
    """
    Возвращает аптечку по ID, принадлежащую пользователю.
    """
    result = await db.execute(
        select(FirstAidKit)
        .where(FirstAidKit.id == kit_id)
        .where(FirstAidKit.user_cor_id == user.cor_id)
    )
    return result.scalar_one_or_none()


async def update_first_aid_kit(
    db: AsyncSession, kit: FirstAidKit, body: FirstAidKitUpdate
) -> FirstAidKit:
    """
    Обновляет аптечку пользователя.
    """
    for field, value in body.dict(exclude_unset=True).items():
        setattr(kit, field, value)
    await db.commit()
    await db.refresh(kit)
    return kit


async def delete_first_aid_kit(db: AsyncSession, kit: FirstAidKit):
    """
    Удаляет аптечку вместе с содержимым.
    """
    await db.delete(kit)
    await db.commit()



async def add_item_to_first_aid_kit(
    db: AsyncSession, body: FirstAidKitItemCreate, kit_id: str
) -> FirstAidKitItem:
    """
    Добавляет медикамент в аптечку.
    """
    new_item = FirstAidKitItem(
        first_aid_kit_id=kit_id,
        medicine_id=body.medicine_id,
        quantity=body.quantity,
        expiration_date=body.expiration_date,
    )

    db.add(new_item)
    await db.commit()

    # Обновляем объект и подгружаем связи (medicine + first_aid_kit)
    await db.refresh(new_item)
    await db.refresh(new_item, ["medicine", "first_aid_kit"])

    return new_item


async def get_items_by_kit(db: AsyncSession, kit_id: str) -> List[FirstAidKitItem]:
    """
    Возвращает список медикаментов в аптечке с подгруженными данными.
    """
    result = await db.execute(
        select(FirstAidKitItem)
        .options(
            selectinload(FirstAidKitItem.first_aid_kit),
            selectinload(FirstAidKitItem.medicine)
            .selectinload(Medicine.schedules),  
        )
        .where(FirstAidKitItem.first_aid_kit_id == kit_id)
        .order_by(FirstAidKitItem.created_at.desc())
    )
    return result.scalars().all()


async def update_item_in_first_aid_kit(db: AsyncSession, body: FirstAidKitItemUpdate, kit_id: str):
    """
    Обновляет медикамент в аптечке
    """

    result = await db.execute(
        select(FirstAidKitItem)
        .options(
            selectinload(FirstAidKitItem.first_aid_kit),
            selectinload(FirstAidKitItem.medicine)
            .selectinload(Medicine.schedules),  
        )
        .where(
            FirstAidKitItem.id == body.medicine_id,
            FirstAidKitItem.first_aid_kit_id == kit_id,
        )
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Медикамент не найден в аптечке")

    if body.quantity is not None:
        item.quantity = body.quantity
    if body.expiration_date is not None:
        item.expiration_date = body.expiration_date

    await db.commit()
    await db.refresh(item, ["medicine", "first_aid_kit"])
    return item


async def delete_item_from_first_aid_kit(db: AsyncSession, item_id: str, kit_id: str):
    """
    Удаляет медикамент из аптечки.
    """
    result = await db.execute(
        select(FirstAidKitItem).where(
            FirstAidKitItem.id == item_id,
            FirstAidKitItem.first_aid_kit_id == kit_id,
        )
    )
    item = result.scalar_one_or_none()
    await db.delete(item)
    await db.commit()
    return None