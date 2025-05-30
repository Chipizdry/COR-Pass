from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.database import db
from cor_pass.database.models import Doctor, Doctor_Status, User
from cor_pass.services.auth import auth_service
from cor_pass.config.config import settings


class UserAccess:
    def __init__(self, active_user):
        self.active_user = active_user

    async def __call__(self, user: User = Depends(auth_service.get_current_user)):
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden operation"
            )


class AdminAccess:
    def __init__(self, email):
        self.email = email

    async def __call__(self, user: User = Depends(auth_service.get_current_user)):
        if not user.email in settings.admin_accounts:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden operation"
            )


class LawyerAccess:
    def __init__(self, email):
        self.email = email

    async def __call__(self, user: User = Depends(auth_service.get_current_user)):
        has_access = False
        if user.email in settings.admin_accounts:
            has_access = True
        if user.email in settings.lawyer_accounts:
            has_access = True

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для выполнения этой операции.",
            )


class DoctorAccess:
    def __init__(self, email):
        self.email = email

    async def __call__(
        self,
        user: User = Depends(auth_service.get_current_user),
        db: AsyncSession = Depends(db.get_db),
    ):
        query = select(Doctor).where(Doctor.doctor_id == user.cor_id)
        result = await db.execute(query)
        doctor = result.scalar_one_or_none()
        if not doctor or doctor.status != Doctor_Status.approved:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctor access required and status is not approved",
            )
        return doctor


user_access = UserAccess([User.is_active])
admin_access = AdminAccess([User.email])
lawyer_access = LawyerAccess([User.email])
doctor_access = DoctorAccess([User.email])
