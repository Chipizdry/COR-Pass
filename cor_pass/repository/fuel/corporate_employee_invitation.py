"""
Repository for Corporate Employee Invitations
"""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.models.corporate_employee_invitation import CorporateEmployeeInvitation


async def create_employee_invitation(
    db: AsyncSession,
    email: str,
    first_name: str,
    last_name: str,
    phone_number: str,
    company_id: int,
    account_id: int,
    limit_amount: float,
    limit_period: str,
    invited_by_user_id: str,
) -> CorporateEmployeeInvitation:
    """
    Создаёт приглашение для добавления сотрудника в компанию
    """
    invitation = CorporateEmployeeInvitation(
        email=email.lower(),
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        company_id=company_id,
        account_id=account_id,
        limit_amount=limit_amount or 0,
        limit_period=limit_period or "day",
        invited_by=invited_by_user_id,
        is_used=0,
    )
    db.add(invitation)
    await db.flush()
    await db.commit()
    return invitation


async def get_invitation_by_email_and_company(
    db: AsyncSession,
    email: str,
    company_id: int,
) -> CorporateEmployeeInvitation:
    """
    Получает неиспользованное приглашение по email и company_id
    """
    stmt = select(CorporateEmployeeInvitation).where(
        CorporateEmployeeInvitation.email == email.lower(),
        CorporateEmployeeInvitation.company_id == company_id,
        CorporateEmployeeInvitation.is_used == 0,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_all_invitations_by_email(
    db: AsyncSession,
    email: str,
) -> list[CorporateEmployeeInvitation]:
    """
    Получает все неиспользованные приглашения по email
    """
    stmt = select(CorporateEmployeeInvitation).where(
        CorporateEmployeeInvitation.email == email.lower(),
        CorporateEmployeeInvitation.is_used == 0,
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_invitations_by_company(
    db: AsyncSession,
    company_id: int,
) -> list[CorporateEmployeeInvitation]:
    """
    Возвращает все неиспользованные приглашения по company_id
    """
    stmt = select(CorporateEmployeeInvitation).where(
        CorporateEmployeeInvitation.company_id == company_id,
        CorporateEmployeeInvitation.is_used == 0,
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def mark_invitation_as_used(
    db: AsyncSession,
    invitation_id: str,
    cor_id: str,
) -> CorporateEmployeeInvitation:
    """
    Помечает приглашение как использованное после регистрации пользователя
    """
    stmt = select(CorporateEmployeeInvitation).where(
        CorporateEmployeeInvitation.id == invitation_id
    )
    result = await db.execute(stmt)
    invitation = result.scalar_one_or_none()
    
    if invitation:
        invitation.is_used = 1
        invitation.created_cor_id = cor_id
        invitation.used_at = datetime.utcnow()
        await db.commit()
    
    return invitation


async def delete_pending_invitation(
    db: AsyncSession,
    invitation_id: str,
) -> bool:
    """
    Удаляет приглашение, если оно ещё не использовано.
    Возвращает True если удалено.
    """
    stmt = select(CorporateEmployeeInvitation).where(
        CorporateEmployeeInvitation.id == invitation_id,
        CorporateEmployeeInvitation.is_used == 0,
    )
    result = await db.execute(stmt)
    invitation = result.scalar_one_or_none()
    if not invitation:
        return False

    await db.delete(invitation)
    await db.commit()
    return True
