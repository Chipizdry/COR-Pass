from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy.exc import IntegrityError
from cor_pass.database.db import get_db
from cor_pass.repository.energy_manager import create_energy_manager
from cor_pass.schemas import (
    EnergyManagerCreate,
    EnergyManagerResponse
)

from cor_pass.repository import person as repository_person
from cor_pass.services.access import admin_access
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger


router = APIRouter(prefix="/energy_managers", tags=["EnergyManager"])


@router.post(
    "/signup_as_energy_manager",
    response_model=EnergyManagerResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(admin_access)],
    tags=["Admin"]
)
async def signup_user_as_energy_manager(
    user_cor_id: str,
    energy_manager_data: EnergyManagerCreate = Body(...),
    db: AsyncSession = Depends(get_db),
):

    user = await repository_person.get_user_by_corid(db=db, cor_id=user_cor_id)
    if not user:
        logger.debug(f"User not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    try:
        energy_manager = await create_energy_manager(
            energy_manager_data=energy_manager_data,
            db=db,
            user=user,
        )
    except IntegrityError as e:
        logger.error(f"Database integrity error: {e}")
        await db.rollback()
        detail = "Database error occurred. Please check the data for duplicates or invalid entries."
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during energy_manager creation.",
        )
    # Сериализуем ответ
    energy_manager_response = EnergyManagerResponse(
        id=energy_manager.id,
        energy_manager_cor_id=energy_manager.energy_manager_cor_id,
        first_name=energy_manager.first_name,
        surname=energy_manager.surname,
        middle_name=energy_manager.middle_name
    )

    return energy_manager_response

