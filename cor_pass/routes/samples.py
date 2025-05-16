from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.db import get_db
from cor_pass.schemas import CreateSampleWithDetails, GetSample, Sample, SampleCreate, Sample as SampleModelScheema
from cor_pass.repository import sample as sample_service
from typing import List

from cor_pass.services.access import user_access, doctor_access

router = APIRouter(prefix="/samples", tags=["Samples"])


@router.post(
    "/create",
    response_model=CreateSampleWithDetails,  
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_201_CREATED,
)
async def create_sample_for_case(
    body: SampleCreate, db: AsyncSession = Depends(get_db)
):
    return await sample_service.create_sample(db=db, case_id=body.case_id, num_samples=body.num_samples) 


@router.get(
    "/{sample_id}", response_model=Sample, dependencies=[Depends(doctor_access)]
)
async def read_sample(sample_id: str, db: AsyncSession = Depends(get_db)):
    db_sample = await sample_service.get_sample(db=db, sample_id=sample_id)
    if db_sample is None:
        raise HTTPException(status_code=404, detail="Sample not found")
    return db_sample


@router.delete(
    "/{sample_id}",
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_sample(sample_id: str, db: AsyncSession = Depends(get_db)):
    db_sample = await sample_service.delete_sample(db=db, sample_id=sample_id)
    if db_sample is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found")
    return
