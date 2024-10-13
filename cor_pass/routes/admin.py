from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from cor_pass.database.db import get_db
from cor_pass.services.auth import auth_service
from cor_pass.database.models import User, Status
from cor_pass.services.access import user_access, admin_access
from cor_pass.schemas import UserDb
from cor_pass.repository import person
from pydantic import EmailStr


router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/get_all", response_model=list[UserDb], dependencies=[Depends(admin_access)])
async def get_all_users(
    skip: int = 0,
    limit: int = 10,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Get a list of users. / Получение списка всех пользователей**\n
    This route allows to get a list of pagination-aware users.
    Level of Access:
    - Current authorized user
    :param skip: int: Number of users to skip.
    :param limit: int: Maximum number of users to return.
    :param current_user: User: Current authenticated user.
    :param db: Session: Database session.
    :return: List of users.
    :rtype: List[UserDb]
    """
    list_users = await person.get_users(skip, limit, db)
    return list_users


@router.patch("/asign_status/{account_status}", dependencies=[Depends(admin_access)])
async def assign_status(
    email: EmailStr, account_status: Status, db: Session = Depends(get_db)
):
    """
    **Assign a account_status to a user by email. / Применение нового статуса аккаунта пользователя**\n

    This route allows to assign the selected account_status to a user by their email.

    :param email: EmailStr: Email of the user to whom you want to assign the status.

    :param account_status: Status: The selected account_status for the assignment (Premium, Basic).

    :param db: Session: Database Session.

    :return: Message about successful status change.

    :rtype: dict
    """
    user = await person.get_user_by_email(email, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    if account_status == user.account_status:
        return {"message": "The acount status has already been assigned"}
    else:
        await person.make_user_status(email, account_status, db)
        return {"message": f"{email} - {account_status.value}"}
    

@router.delete("/{email}", dependencies=[Depends(admin_access)])
async def delete_user(
    email: EmailStr, db: Session = Depends(get_db)
):
    """
    **Delete user by email. / Удаление пользователя по имейлу**\n

=
    """
    user = await person.get_user_by_email(email, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    else:
        await person.delete_user_by_email(db=db, email=email)
        return {"message": f" user {email} - was deleted"}
