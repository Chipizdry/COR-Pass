from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.database import db
from cor_pass.database.models import Doctor, Doctor_Status, User
from cor_pass.services.auth import auth_service
from cor_pass.config.config import settings


class UserRoleChecker:
    async def is_active(self, user: User = Depends(auth_service.get_current_user)):
        return user.is_active

class AdminRoleChecker:
    async def is_admin(self, user: User = Depends(auth_service.get_current_user)):
        return user.email in settings.admin_accounts

class LawyerRoleChecker:
    async def is_lawyer(self, user: User = Depends(auth_service.get_current_user)):
        return user.email in settings.lawyer_accounts

class DoctorRoleChecker:
    async def is_doctor(
        self,
        user: User = Depends(auth_service.get_current_user),
        db: AsyncSession = Depends(db.get_db),
    ):
        query = select(Doctor).where(Doctor.doctor_id == user.cor_id)
        result = await db.execute(query)
        doctor = result.scalar_one_or_none()
        return doctor is not None and doctor.status == Doctor_Status.approved

class CorIntRoleChecker:
    async def is_cor_int(self, user: User = Depends(auth_service.get_current_user)):
        """
        Проверяет, принадлежит ли пользователь к роли cor-int.
        """
        return user.email.endswith("@cor-int.com")

user_role_checker = UserRoleChecker()
admin_role_checker = AdminRoleChecker()
lawyer_role_checker = LawyerRoleChecker()
doctor_role_checker = DoctorRoleChecker()
cor_int_role_checker = CorIntRoleChecker()