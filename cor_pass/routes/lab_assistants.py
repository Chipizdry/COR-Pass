from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy.exc import IntegrityError
from cor_pass.database.db import get_db
from cor_pass.repository.lab_assistant import create_lab_assistant
from cor_pass.repository.lawyer import get_doctor
from cor_pass.schemas import (
    LabAssistantCreate,
    LabAssistantResponse
)

from cor_pass.repository import person as repository_person
from cor_pass.services.access import doctor_access, lab_assistant_or_doctor_access
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger

router = APIRouter(prefix="/lab_assistant", tags=["LabAssistant"])




@router.post(
    "/signup_as_lab_assistant",
    response_model=LabAssistantResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(doctor_access)],
)
async def signup_user_as_lab_assistant(
    user_cor_id: str,
    lab_assistant_data: LabAssistantCreate = Body(...),
    db: AsyncSession = Depends(get_db),
):

    exist_doctor = await get_doctor(db=db, doctor_id=user_cor_id)
    if exist_doctor:
        logger.debug(f"{user_cor_id} user is doctor")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Doctor account already exists for this user"
        )
    user = await repository_person.get_user_by_corid(db=db, cor_id=user_cor_id)
    if not user:
        logger.debug(f"User not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    try:
        lab_assistant = await create_lab_assistant(
            lab_assistant_data=lab_assistant_data,
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
            detail="An unexpected error occurred during lab_assistant creation.",
        )
    # Сериализуем ответ
    lab_assistant_response = LabAssistantResponse(
        id=lab_assistant.id,
        lab_assistant_cor_id=lab_assistant.lab_assistant_cor_id,
        first_name=lab_assistant.first_name,
        surname=lab_assistant.surname,
        middle_name=lab_assistant.middle_name
    )

    return lab_assistant_response




@router.post(
    "/check_access",
    # response_model=LabAssistantResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(lab_assistant_or_doctor_access)],
)
async def check_access(
    db: AsyncSession = Depends(get_db),
):

    return "lab_assistant_response"

