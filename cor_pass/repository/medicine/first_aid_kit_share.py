from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cor_pass.database.models import (
    FirstAidKit,
    FirstAidKitItem,
    FirstAidKitShare,
    FirstAidKitShareStatus,
    User,
)

DEFAULT_EXPIRES_HOURS = 72


async def get_share_by_id(db: AsyncSession, share_id: str) -> Optional[FirstAidKitShare]:
    result = await db.execute(select(FirstAidKitShare).where(FirstAidKitShare.id == share_id))
    return result.scalar_one_or_none()


async def get_share_by_token(
    db: AsyncSession,
    token: str,
    with_kit: bool = False,
) -> Optional[FirstAidKitShare]:
    stmt = select(FirstAidKitShare).where(FirstAidKitShare.token == token)
    if with_kit:
        stmt = stmt.options(
            selectinload(FirstAidKitShare.kit)
            .selectinload(FirstAidKit.medicines)
        )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_share(
    db: AsyncSession,
    *,
    kit: FirstAidKit,
    from_user: User,
    to_user_cor_id: Optional[str] = None,
    to_email: Optional[str] = None,
    expires_hours: int = DEFAULT_EXPIRES_HOURS,
    context: Optional[dict] = None,
) -> FirstAidKitShare:
    token = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours or DEFAULT_EXPIRES_HOURS)

    share = FirstAidKitShare(
        kit_id=kit.id,
        from_user_cor_id=from_user.cor_id,
        to_user_cor_id=to_user_cor_id,
        to_email=to_email,
        token=token,
        status=FirstAidKitShareStatus.PENDING,
        expires_at=expires_at,
        context=context,
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)
    return share


async def revoke_share(db: AsyncSession, *, share: FirstAidKitShare, current_user: User) -> FirstAidKitShare:
    if share.from_user_cor_id != current_user.cor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to revoke this share")
    if share.status != FirstAidKitShareStatus.PENDING:
        return share

    share.status = FirstAidKitShareStatus.REVOKED
    await db.commit()
    await db.refresh(share)
    return share


async def accept_share(db: AsyncSession, *, share: FirstAidKitShare, current_user: User) -> FirstAidKit:
    now = datetime.now(timezone.utc)

    if share.status != FirstAidKitShareStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation is not pending")

    if share.expires_at <= now:
        share.status = FirstAidKitShareStatus.EXPIRED
        await db.commit()
        await db.refresh(share)
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invitation expired")

    if share.to_user_cor_id and share.to_user_cor_id != current_user.cor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invitation is addressed to another user")

    target_cor_id = share.to_user_cor_id or current_user.cor_id

    # Ensure kit and items are loaded
    if not share.kit:
        result = await db.execute(
            select(FirstAidKit)
            .options(selectinload(FirstAidKit.medicines))
            .where(FirstAidKit.id == share.kit_id)
        )
        share.kit = result.scalar_one_or_none()

    if not share.kit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared kit not found")

    # Create copy of kit (non-primary by default)
    new_kit = FirstAidKit(
        name=share.kit.name,
        description=share.kit.description,
        user_cor_id=target_cor_id,
        is_primary=False,
    )
    db.add(new_kit)
    await db.flush()  # to get new_kit.id

    # Copy items
    for item in share.kit.medicines:
        db.add(
            FirstAidKitItem(
                first_aid_kit_id=new_kit.id,
                medicine_id=item.medicine_id,
                quantity=item.quantity,
                expiration_date=item.expiration_date,
            )
        )

    share.status = FirstAidKitShareStatus.ACCEPTED
    share.accepted_at = now
    share.to_user_cor_id = target_cor_id

    await db.commit()
    await db.refresh(new_kit)
    await db.refresh(share)
    return new_kit
