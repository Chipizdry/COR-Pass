from typing import List, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.db import get_db
from cor_pass.repository.patient import get_patient_by_corid
from cor_pass.schemas import Case as CaseModelScheema, CaseCreate, CaseCreateResponse, CaseDetailsResponse, CaseListResponse, CaseParametersScheema, PatientFirstCaseDetailsResponse, UpdateCaseCode, UpdateCaseCodeResponce
from cor_pass.database import models as db_models
from cor_pass.repository import case as case_service

from cor_pass.services.access import user_access, doctor_access

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post(
    "/",
    dependencies=[Depends(doctor_access)],
    # response_model=List[CaseCreateResponse]
    response_model=PatientFirstCaseDetailsResponse
)
async def create_case(
    body: CaseCreate,
    db: AsyncSession = Depends(get_db),

):
    """
    Создает указанное количество кейсов и по 1 вложенной сущности
    """
    patient = await get_patient_by_corid(db=db, cor_id=body.patient_cor_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )
    case = await case_service.create_cases_with_initial_data(
        db=db,
        body=body
    )
    return case



@router.get(
    "/{case_id}",
    dependencies=[Depends(doctor_access)],
    response_model=CaseDetailsResponse
)
async def read_case(case_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получаем конкретный кейс и вложенные в него сущности 
    """
    db_case = await case_service.get_case(db, case_id)
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return db_case


@router.get(
    "/{case_id}/case_parameters",
    dependencies=[Depends(doctor_access)],
    response_model=CaseParametersScheema
)
async def read_case_parameters(case_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получение параметров кейса
    """
    db_case_parameters = await case_service.get_case_parameters(db, case_id)
    if db_case_parameters is None:
        raise HTTPException(status_code=404, detail="Case parameters not found")
    return db_case_parameters


@router.patch(
    "/case_parameters",
    dependencies=[Depends(doctor_access)],
    response_model=CaseParametersScheema
)
async def update_case_parameters(
    body: CaseParametersScheema,
    db: AsyncSession = Depends(get_db),
):
    """
    Обновляет параметры кейса
    """
    db_case_parameters = await case_service.update_case_parameters(
        db,
        body.case_id,
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
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_case(case_id: str, db: AsyncSession = Depends(get_db)):
    """
    Удаляет кейс и все вложенные в него сущности
    """
    db_case = await case_service.delete_case(db, case_id)
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return


@router.get("/patients/{patient_cor_id}/overview", dependencies=[Depends(doctor_access)], response_model=PatientFirstCaseDetailsResponse,)
async def read_patient_overview_details(
    patient_cor_id: str, db: AsyncSession = Depends(get_db)
):
    """
    Возвращает список всех кейсов пациента и детализацию первого из них:
    семплы, кассеты первого семпла и стекла этих кассет.
    """
    overview_data = await case_service.get_patient_first_case_details(db=db, patient_id=patient_cor_id)
    if overview_data is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return overview_data


@router.patch("/case_code", dependencies=[Depends(doctor_access)],
              response_model=UpdateCaseCodeResponce
              )
async def update_case_code(
    body: UpdateCaseCode,
    db: AsyncSession = Depends(get_db),
):
    """Изменяет последние 5 символов кейса"""
    try:
        updated_case = await case_service.update_case_code_suffix(db=db, case_id=body.case_id, new_suffix=body.update_data)
        if updated_case:
            return updated_case
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Кейс з ID {body.case_id} не знайдено")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))