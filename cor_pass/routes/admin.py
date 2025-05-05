from typing import List
from fastapi import APIRouter, HTTPException, Depends, status
from cor_pass.database.db import get_db
from cor_pass.services.auth import auth_service
from cor_pass.database.models import User, Status
from cor_pass.services.access import admin_access
from cor_pass.schemas import UserDb
from cor_pass.repository import person
from pydantic import EmailStr
from cor_pass.database.redis_db import redis_client
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.services.logger import logger

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/get_all", response_model=List[UserDb], dependencies=[Depends(admin_access)]
)
async def get_all_users(
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    **Get a list of users. / Получение списка всех пользователей**\n
    This route allows to get a list of pagination-aware users.
    Level of Access:
    - Admin
    :param skip: int: Number of users to skip.
    :param limit: int: Maximum number of users to return.
    :param current_user: User: Current authenticated user (for dependency injection).
    :param db: AsyncSession: Database session.
    :return: List of users with their last activity.
    :rtype: List[UserDb]
    """

    list_users = await person.get_users(skip, limit, db)
    users_list_with_activity = []

    for user in list_users:
        oid = str(user.id)  # Convert UUID to string for Redis
        last_active = None
        if await redis_client.exists(oid):
            users_last_activity = await redis_client.get(oid)
            user_response = UserDb(
                id=user.id,
                cor_id=user.cor_id,
                email=user.email,
                account_status=user.account_status,
                is_active=user.is_active,
                last_password_change=user.last_password_change,
                user_sex=user.user_sex,
                birth=user.birth,
                user_index=user.user_index,
                created_at=user.created_at,
                last_active=users_last_activity,
            )
        else:
            user_response = UserDb(
                id=user.id,
                cor_id=user.cor_id,
                email=user.email,
                account_status=user.account_status,
                is_active=user.is_active,
                last_password_change=user.last_password_change,
                user_sex=user.user_sex,
                birth=user.birth,
                user_index=user.user_index,
                created_at=user.created_at,
            )

        users_list_with_activity.append(user_response)

    return users_list_with_activity


@router.patch("/asign_status/{account_status}", dependencies=[Depends(admin_access)])
async def assign_status(
    email: EmailStr, account_status: Status, db: AsyncSession = Depends(get_db)
):
    """
    **Assign a account_status to a user by email. / Применение нового статуса аккаунта пользователя**\n

    This route allows to assign the selected account_status to a user by their email.

    :param email: EmailStr: Email of the user to whom you want to assign the status.

    :param account_status: Status: The selected account_status for the assignment (Premium, Basic).

    :param db: AsyncSession: Database Session.

    :return: Message about successful status change.

    :rtype: dict
    """
    user = await person.get_user_by_email(email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if account_status == user.account_status:
        return {"message": "The account status has already been assigned"}
    else:
        await person.make_user_status(email, account_status, db)
        return {"message": f"{email} - {account_status.value}"}


@router.delete("/{email}", dependencies=[Depends(admin_access)])
async def delete_user(email: EmailStr, db: AsyncSession = Depends(get_db)):
    """
        **Delete user by email. / Удаление пользователя по имейлу**\n

    =
    """
    user = await person.get_user_by_email(email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    else:
        await person.delete_user_by_email(db=db, email=email)
        return {"message": f" user {email} - was deleted"}


@router.patch("/deactivate/{email}", dependencies=[Depends(admin_access)])
async def deactivate_user(email: EmailStr, db: AsyncSession = Depends(get_db)):
    """
    **Deactivate user by email. / Деактивация аккаунта пользователя**\n

    This route allows to deactivate a user account by their email.

    :param email: EmailStr: Email of the user to deactivate.

    :param db: AsyncSession: Database Session.

    :return: Message about successful deactivation.

    :rtype: dict
    """
    user = await person.get_user_by_email(email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if not user.is_active:
        return {"message": f"The {user.email} account is already deactivated"}
    else:
        await person.deactivate_user(email, db)
        return {"message": f"{user.email} - account is deactivated"}


@router.patch("/activate/{email}", dependencies=[Depends(admin_access)])
async def activate_user(email: EmailStr, db: AsyncSession = Depends(get_db)):
    """
    **Activate user by email. / Активация аккаунта пользователя**\n

    This route allows to activate a user account by their email.

    :param email: EmailStr: Email of the user to activate.

    :param db: AsyncSession: Database Session.

    :return: Message about successful activation.

    :rtype: dict
    """
    user = await person.get_user_by_email(email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if user.is_active:
        return {"message": f"The {user.email} account is already active"}
    else:
        await person.activate_user(email, db)
        return {"message": f"{user.email} - account is activated"}


@router.patch("/kickout/{email}", dependencies=[Depends(admin_access)])
async def kickout_user(email: EmailStr, db: AsyncSession = Depends(get_db)):
    """
    **Kickout user by email (delete refresh token). / Удаление рефреш токена пользователя**\n

    """
    user = await person.get_user_by_email(email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    else:
        new_token = None
        await person.update_token(user=user, token=new_token, db=db)
        return {"message": f"{email} - delete refresh token"}
