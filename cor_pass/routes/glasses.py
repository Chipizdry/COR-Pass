from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.db import get_db
from cor_pass.schemas import (
    ChangeGlassStaining,
    DeleteGlassesRequest,
    DeleteGlassesResponse,
    Glass as GlassModelScheema,
    GlassCreate,
)
from cor_pass.repository import glass as glass_service
from typing import List

from cor_pass.services.access import doctor_access

router = APIRouter(prefix="/glasses", tags=["Glass"])


@router.post(
    "/create",
    dependencies=[Depends(doctor_access)],
    response_model=List[GlassModelScheema],
)
async def create_glass_for_cassette(
    body: GlassCreate,
    printing: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Создаем указанное количество стёкол"""
    return await glass_service.create_glass(
        db=db,
        cassette_id=body.cassette_id,
        num_glasses=body.num_glasses,
        staining_type=body.staining_type,
        printing=printing,
    )


@router.get(
    "/{glass_id}",
    response_model=GlassModelScheema,
    dependencies=[Depends(doctor_access)],
)
async def read_glass_info(glass_id: str, db: AsyncSession = Depends(get_db)):
    """Получаем информацию о стекле по его ID."""
    db_glass = await glass_service.get_glass(db=db, glass_id=glass_id)
    if db_glass is None:
        raise HTTPException(status_code=404, detail="Glass not found")
    return db_glass


@router.delete(
    "/delete",
    response_model=DeleteGlassesResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
)
async def delete_glasses_endpoint(
    request_body: DeleteGlassesRequest, db: AsyncSession = Depends(get_db)
):
    """Удаляет несколько стекол по их ID."""
    result = await glass_service.delete_glasses(db=db, glass_ids=request_body.glass_ids)
    return result


@router.patch(
    "/{glass_id}/staining",
    response_model=GlassModelScheema,
    dependencies=[Depends(doctor_access)],
)
async def change_glass_staining(
    glass_id: str, body: ChangeGlassStaining, db: AsyncSession = Depends(get_db)
):
    """Получаем информацию о стекле по его ID."""
    db_glass = await glass_service.change_staining(db=db, glass_id=glass_id, body=body)
    if db_glass is None:
        raise HTTPException(status_code=404, detail="Glass not found")
    return db_glass


@router.patch(
    "/{glass_id}/printed",
    response_model=GlassModelScheema,
    dependencies=[Depends(doctor_access)],
)
async def change_glass_printing_status(
    glass_id: str, printing: bool, db: AsyncSession = Depends(get_db)
):
    """Меняем статус печати стекла"""
    db_glass = await glass_service.change_printing_status(
        db=db, glass_id=glass_id, printing=printing
    )
    if db_glass is None:
        raise HTTPException(status_code=404, detail="Glass not found")
    return db_glass
