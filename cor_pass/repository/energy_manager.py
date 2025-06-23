
from cor_pass.database.models import (
    EnergyManager,
    User
)
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.repository.patient import get_patient_by_corid
from cor_pass.repository.person import get_user_by_corid
from cor_pass.schemas import EnergyManagerCreate, EnergyManagerResponse



async def create_energy_manager(
    energy_manager_data: EnergyManagerCreate,
    db: AsyncSession,
    user: User,
) -> EnergyManager:
    """
    Асинхронная сервисная функция по созданию energy_manager.
    """
    energy_manager = EnergyManager(
        energy_manager_cor_id=user.cor_id,
        first_name = energy_manager_data.first_name,
        surname = energy_manager_data.last_name,
        middle_name = energy_manager_data.middle_name
    )

    db.add(energy_manager)

    await db.commit()
    await db.refresh(energy_manager)

    return energy_manager