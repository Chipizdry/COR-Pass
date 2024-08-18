from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from cor_pass.database.db import get_db
from cor_pass.services.auth import auth_service
from cor_pass.database.models import User, Status
from cor_pass.services.access import user_access
from cor_pass.schemas import UserDb, ResponseCorIdModel, CreateCorIdModel
from cor_pass.repository import cor_id as repository_cor_id
from pydantic import EmailStr

router = APIRouter(prefix="/medical/cor_id", tags=["Cor-Id"])





"""
Маршрут просмотра cor-id
"""

@router.get(
    "/my_core_id", response_model=ResponseCorIdModel, dependencies=[Depends(user_access)]
)
async def read_cor_id(
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    
    cor_id = await repository_cor_id.get_cor_id(user, db)
    if cor_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="COR-Id not found"
        )
    return cor_id


"""
Маршрут создания cor-id
"""

@router.post(
    "/create",
    # response_model=ResponseCorIdModel,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_access)],
)
async def create_cor_id(
    body: CreateCorIdModel,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):

    if not user.cor_id:
        cor_id = await repository_cor_id.create_cor_id(body, db, user)
        return cor_id
    else:
        return {"message": "cor-id already exist",
                "cor_id": user.cor_id}