from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.db import get_db
from cor_pass.schemas import Cassette as CassetteModelScheema, CassetteCreate, Sample, SampleCreate
from cor_pass.repository import sample as sample_service
from cor_pass.repository import cassette as cassette_service
from typing import List

from cor_pass.services.access import user_access, doctor_access

router = APIRouter(prefix="/cassettes", tags=["Cassette"])


@router.post(
    "/create",
    dependencies=[Depends(doctor_access)],
    response_model=List[CassetteModelScheema],
)
async def create_cassette_for_sample(
    body: CassetteCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Создаем заданное количество стёкол и кассет для конкретного семпла
    """
    return await cassette_service.create_cassette(
        db=db,
        sample_id=body.sample_id,
        num_cassettes=body.num_cassettes,
        
    )


@router.get(
    "/{cassette_id}", response_model=CassetteModelScheema, dependencies=[Depends(doctor_access)]
)
async def read_cassette(cassette_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получаем данные кассеты и вложеных сущностей
    """
    db_cassette = await cassette_service.get_cassette(db, cassette_id)
    if db_cassette is None:
        raise HTTPException(status_code=404, detail="Cassette not found")
    return db_cassette


@router.delete(
    "/{cassette_id}",
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_cassette(cassette_id: str, db: AsyncSession = Depends(get_db)):
    """
    Удаляет кассету
    """
    db_cassette = await cassette_service.delete_cassette(db, cassette_id)
    if db_cassette is None:
        raise HTTPException(status_code=404, detail="Cassette not found")
    return 
