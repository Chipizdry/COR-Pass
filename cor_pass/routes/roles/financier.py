from sqlite3 import IntegrityError
from typing import List, Optional
from fastapi import APIRouter, Body, HTTPException, Depends, Query, status
from fastapi.responses import StreamingResponse

from cor_pass.database.db import get_db


from cor_pass.services.shared.access import financier_access, admin_access
from cor_pass.schemas import (
    FinancierCreate,
    FinancierResponse
)
from cor_pass.repository.roles import financier as repository_financier
from cor_pass.repository.user import person as repository_person
import base64
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

router = APIRouter(prefix="/financier", tags=["Financier"])


@router.post(
    "/signup_as_financier",
    response_model=FinancierResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(admin_access)],
    tags=["Admin"],
)
async def signup_user_as_financier(
    user_cor_id: str,
    financier_data: FinancierCreate = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """
    **Создание финансиста**\n
    Этот маршрут позволяет создать финансиста на основе существующего пользователя.
    
    Уровень доступа:
    - Только администраторы
    
    :param user_cor_id: COR ID пользователя, которого нужно назначить финансистом
    :param financier_data: Данные финансиста (имя, фамилия, отчество)
    :return: Данные созданного финансиста
    """
    user = await repository_person.get_user_by_corid(db=db, cor_id=user_cor_id)
    if not user:
        logger.debug(f"User not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    
    # Проверяем, не является ли пользователь уже финансистом
    existing_financier = await repository_financier.get_financier(user_cor_id, db)
    if existing_financier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail="User is already a financier"
        )
    
    try:
        financier = await repository_financier.create_financier(
            financier_data=financier_data,
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
            detail="An unexpected error occurred during financier creation.",
        )
    
    financier_response = FinancierResponse(
        id=financier.id,
        financier_cor_id=financier.financier_cor_id,
        first_name=financier.first_name,
        last_name=financier.surname,
        middle_name=financier.middle_name,
    )

    return financier_response


@router.get(
    "/all_financiers",
    response_model=List[FinancierResponse],
    dependencies=[Depends(admin_access)],
    tags=["Admin"],
)
async def get_all_financiers(
    skip: int = Query(0, description="Количество записей для пропуска"),
    limit: int = Query(10, description="Максимальное количество записей для возврата"),
    db: AsyncSession = Depends(get_db),
):
    """
    **Получение списка всех финансистов**\n
    Этот маршрут позволяет получить список всех финансистов с пагинацией.
    
    Уровень доступа:
    - Только администраторы
    
    :param skip: int: Количество записей для пропуска.
    :param limit: int: Максимальное количество записей для возврата.
    :return: List[FinancierResponse]: Список финансистов.
    """
    financiers = await repository_financier.get_all_financiers(
        skip=skip,
        limit=limit,
        db=db,
    )
    
    return [
        FinancierResponse(
            id=financier.id,
            financier_cor_id=financier.financier_cor_id,
            first_name=financier.first_name,
            last_name=financier.surname,
            middle_name=financier.middle_name,
        )
        for financier in financiers
    ]
