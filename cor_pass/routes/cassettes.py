from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.db import get_db
from cor_pass.schemas import Cassette, CassetteCreate, Sample, SampleCreate
from cor_pass.repository import sample as sample_service
from cor_pass.repository import cassette as cassette_service
from typing import List

from cor_pass.services.access import user_access, doctor_access

router = APIRouter(prefix="/cassettes", tags=["Cassette"])


@router.post(
    "/samples/{sample_id}/cassette",
    dependencies=[Depends(doctor_access)],
    #  response_model=Cassette
)
async def create_cassette_for_sample(
    sample_id: str,
    num_cassettes: int = 1,
    num_glasses_per_cassette: int = 1,
    db: AsyncSession = Depends(get_db),
):
    return await cassette_service.create_cassette(
        db=db,
        sample_id=sample_id,
        num_cassettes=num_cassettes,
        num_glasses_per_cassette=num_glasses_per_cassette,
    )


@router.get(
    "/{cassette_id}", response_model=Cassette, dependencies=[Depends(doctor_access)]
)
async def read_cassette(cassette_id: str, db: AsyncSession = Depends(get_db)):
    db_cassette = await cassette_service.get_cassette(db, cassette_id)
    if db_cassette is None:
        raise HTTPException(status_code=404, detail="Cassette not found")
    return db_cassette


@router.delete(
    "/{cassette_id}",
    dependencies=[Depends(doctor_access)],
    #    response_model=Cassette
)
async def delete_cassette(cassette_id: str, db: AsyncSession = Depends(get_db)):
    db_cassette = await cassette_service.delete_cassette(db, cassette_id)
    if db_cassette is None:
        raise HTTPException(status_code=404, detail="Cassette not found")
    return db_cassette
