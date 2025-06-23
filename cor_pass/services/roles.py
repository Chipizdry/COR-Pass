from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.database import db
from cor_pass.database.models import Doctor, Doctor_Status, EnergyManager, Lawyer, User, LabAssistant
from cor_pass.services.auth import auth_service
from cor_pass.config.config import settings


class UserRoleChecker:
    async def is_active(self, user: User = Depends(auth_service.get_current_user)):
        return user.is_active


class AdminRoleChecker:
    async def is_admin(self, user: User = Depends(auth_service.get_current_user)):
        return user.email in settings.admin_accounts


class LawyerRoleChecker:
    async def is_lawyer(self, 
                        user: User = Depends(auth_service.get_current_user),
                        db: AsyncSession = Depends(db.get_db)):
        is_lawyer = False
        if user.email in settings.lawyer_accounts:
            is_lawyer = True
        query = select(Lawyer).where(Lawyer.lawyer_cor_id == user.cor_id)
        result = await db.execute(query)
        lawyer = result.scalar_one_or_none()
        if lawyer:
           is_lawyer = True 
        return is_lawyer


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


class LabAssistantRoleChecker:
    async def is_lab_assistant(
        self,
        user: User = Depends(auth_service.get_current_user),
        db: AsyncSession = Depends(db.get_db),
    ):
        lab_assistant_query = select(LabAssistant).where(LabAssistant.lab_assistant_cor_id == user.cor_id)
        lab_assistant = await db.scalar(lab_assistant_query)

        if lab_assistant:
            return lab_assistant 

class EnergyManagerRoleChecker:
    async def is_energy_manager(
        self,
        user: User = Depends(auth_service.get_current_user),
        db: AsyncSession = Depends(db.get_db),
    ):
        energy_manager_query = select(EnergyManager).where(EnergyManager.energy_manager_cor_id == user.cor_id)
        energy_manager = await db.scalar(energy_manager_query)

        if energy_manager:
            return energy_manager


user_role_checker = UserRoleChecker()
admin_role_checker = AdminRoleChecker()
lawyer_role_checker = LawyerRoleChecker()
doctor_role_checker = DoctorRoleChecker()
cor_int_role_checker = CorIntRoleChecker()
lab_assistant_role_checker = LabAssistantRoleChecker()
energy_manager_role_checker = EnergyManagerRoleChecker()
