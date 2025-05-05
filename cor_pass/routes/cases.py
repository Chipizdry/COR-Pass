from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.db import get_db
from cor_pass.repository.patient import get_patient_by_corid
from cor_pass.schemas import Case, CaseCreate, CaseParametersScheema, Sample
from cor_pass.database import models as db_models
from cor_pass.repository import case as case_service

from cor_pass.services.access import user_access, doctor_access

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post(
    "/",
    dependencies=[Depends(doctor_access)],
    #  response_model=Case
)
async def create_case(
    case_in: CaseCreate,
    db: AsyncSession = Depends(get_db),
    num_cases: int = 1,
    urgency: db_models.UrgencyType = Query(
        db_models.UrgencyType.S, description="Срочность"
    ),
    material_type: db_models.MaterialType = Query(
        db_models.MaterialType.R, description="Тип исследования"
    ),
):

    patient = await get_patient_by_corid(db=db, cor_id=case_in.patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )
    case = await case_service.create_cases_with_initial_data(
        db=db,
        case_in=case_in,
        num_cases=num_cases,
        urgency=urgency,
        material_type=material_type,
    )
    return case




@router.get(
    "/{case_id}",
    dependencies=[Depends(doctor_access)]
    # response_model=Case
)
async def read_case(case_id: str, db: AsyncSession = Depends(get_db)):
    db_case = await case_service.get_case(db, case_id)
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return db_case


@router.get(
    "/{case_id}/case_parameters",
    dependencies=[Depends(doctor_access)],
    # response_model=Case
)
async def read_case_parameters(case_id: str, db: AsyncSession = Depends(get_db)):
    db_case_parameters = await case_service.get_case_parameters(db, case_id)
    if db_case_parameters is None:
        raise HTTPException(status_code=404, detail="Case parameters not found")
    return db_case_parameters


@router.patch(
    "/{case_id}/case_parameters",
    dependencies=[Depends(doctor_access)],
    # response_model=Case
)
async def update_case_parameters(
    case_id: str,
    body: CaseParametersScheema,
    db: AsyncSession = Depends(get_db),
):
    db_case_parameters = await case_service.update_case_parameters(
        db,
        case_id,
        body.macro_description,
        body.container_count_actual,
        body.urgency,
        body.material_type,
        body.macro_archive,
        body.decalcification,
        body.sample_type,
        body.fixation,
    )
    if db_case_parameters is None:
        raise HTTPException(status_code=404, detail="Case parameters not found")
    return db_case_parameters


@router.delete(
    "/{case_id}",
    dependencies=[Depends(doctor_access)],
    #    response_model=Case
)
async def delete_case(case_id: str, db: AsyncSession = Depends(get_db)):
    db_case = await case_service.delete_case(db, case_id)
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return db_case


@router.get("/patients/{patient_id}/overview", dependencies=[Depends(doctor_access)])
async def read_patient_overview_details(
    patient_id: str, db: AsyncSession = Depends(get_db)
):
    """
    Возвращает список всех кейсов пациента и детализацию первого из них:
    семплы, кассеты первого семпла и стекла этих кассет.
    """
    overview_data = await case_service.get_patient_first_case_details(db, patient_id)
    if overview_data is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return overview_data


@router.patch("/cases/{case_id}/code", dependencies=[Depends(doctor_access)]
            #   response_model=CaseModelScheema
              )
async def update_case_code(
    case_id: str,
    update_data: str,
    db: AsyncSession = Depends(get_db),
):
    """Редагує останні 5 символів коду кейса."""
    try:
        updated_case = await case_service.update_case_code_suffix(db, case_id, update_data)
        if updated_case:
            return updated_case
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Кейс з ID {case_id} не знайдено")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))