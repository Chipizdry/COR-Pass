from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.db import get_db
from cor_pass.schemas import (
    CreateSampleWithDetails,
    DeleteSampleRequest,
    DeleteSampleResponse,
    Sample,
    SampleCreate,
    UpdateSampleMacrodescription,
)
from cor_pass.repository import sample as sample_service

from cor_pass.services.access import doctor_access

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
    """Создаем указанное количество семплов"""
    return await sample_service.create_sample(
        db=db, case_id=body.case_id, num_samples=body.num_samples
    )


@router.get(
    "/{sample_id}", response_model=Sample, dependencies=[Depends(doctor_access)]
)
async def read_sample(sample_id: str, db: AsyncSession = Depends(get_db)):
    """Получаем данные о семпле"""
    db_sample = await sample_service.get_sample(db=db, sample_id=sample_id)
    if db_sample is None:
        raise HTTPException(status_code=404, detail="Sample not found")
    return db_sample


@router.put(
    "/archive/{sample_id}",
    response_model=Sample,
    dependencies=[Depends(doctor_access)],
)
async def archive(
    sample_id: str,
    archive: bool,
    db: AsyncSession = Depends(get_db),
):
    """
    Помечает образец как тот, что находится в архиве лаборатории

    """
    db_sample = await sample_service.archive_sample(
        db=db, sample_id=sample_id, archive=archive
    )
    if db_sample is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found"
        )
    return db_sample


@router.put(
    "/macrodescription/{sample_id}",
    response_model=Sample,
    dependencies=[Depends(doctor_access)],
)
async def update_sample_macrodescription(
    sample_id: str,
    body: UpdateSampleMacrodescription,
    db: AsyncSession = Depends(get_db),
):
    """
    Обновляет макроописание образца

    """
    db_sample = await sample_service.update_sample_macrodescription(
        db=db, sample_id=sample_id, body=body
    )
    if db_sample is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found"
        )
    return db_sample


@router.delete(
    "/delete",
    response_model=DeleteSampleResponse,
    dependencies=[Depends(doctor_access)],
    status_code=status.HTTP_200_OK,
)
async def delete_samples(
    request_body: DeleteSampleRequest, db: AsyncSession = Depends(get_db)
):
    """Удаляет массив семплов"""
    result = await sample_service.delete_samples(
        db=db, samples_ids=request_body.sample_ids
    )
    return result



@router.patch(
    "/{sample_id}/print_glasses",
    response_model=Sample,
    dependencies=[Depends(doctor_access)],
)
async def print_all_sample_glasses(
    sample_id: str,
    printing: bool=False,
    db: AsyncSession = Depends(get_db),
):
    """
    Печатает все стёкла семпла

    """
    db_sample = await sample_service.print_all_sample_glasses(
        db=db, sample_id=sample_id, printing=printing
    )
    if db_sample is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found"
        )
    return db_sample


@router.patch(
    "/{sample_id}/print_cassettes",
    response_model=Sample,
    dependencies=[Depends(doctor_access)],
)
async def print_all_sample_cassettes(
    sample_id: str,
    printing: bool=False,
    db: AsyncSession = Depends(get_db),
):
    """
    Печатает все кассеты семпла

    """
    db_sample = await sample_service.print_all_sample_cassettes(
        db=db, sample_id=sample_id, printing=printing
    )
    if db_sample is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found"
        )
    return db_sample