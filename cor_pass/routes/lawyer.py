from typing import List
from fastapi import APIRouter, File, HTTPException, Depends, UploadFile, status
from sqlalchemy.orm import Session
from cor_pass.database.db import get_db
from cor_pass.services.auth import auth_service
from cor_pass.database.models import (
    Certificate,
    ClinicAffiliation,
    Diploma,
    DoctorStatus,
    User,
    Status,
    Doctor,
)
from cor_pass.services.access import admin_access, lawyer_access
from cor_pass.schemas import (
    CertificateResponse,
    ClinicAffiliationResponse,
    DiplomaResponse,
    DoctorCreate,
    DoctorResponse,
    DoctorWithRelationsResponse,
    UserDb,
)
from cor_pass.repository import person
from cor_pass.repository import lawyer
from pydantic import EmailStr
from cor_pass.database.redis_db import redis_client
import base64

from cor_pass.services.logger import logger

router = APIRouter(prefix="/lawyer", tags=["Lawyer"])


@router.get(
    "/get_all_doctors",
    response_model=List[DoctorResponse],
    dependencies=[Depends(lawyer_access)],
)
async def get_all_doctors(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
):

    list_doctors = await lawyer.get_doctors(skip=skip, limit=limit, db=db)

    if not list_doctors:
        return []

    doctors_response = [
        DoctorResponse(
            id=doctor.id,
            doctor_id=doctor.doctor_id,
            work_email=doctor.work_email,
            first_name=doctor.first_name,
            surname=doctor.surname,
            last_name=doctor.last_name,
            scientific_degree=doctor.scientific_degree,
            date_of_last_attestation=doctor.date_of_last_attestation,
            status=doctor.status,
        )
        for doctor in list_doctors
    ]
    return doctors_response

    # Функция для преобразования бинарных данных в base64
def bytes_to_base64(binary_data: bytes):
    if binary_data is None:
        return None
    return base64.b64encode(binary_data).decode('utf-8')




@router.get(
    "/get_doctor_info/{doctor_id}",
    response_model=DoctorWithRelationsResponse,
    dependencies=[Depends(lawyer_access)],
)
async def get_doctor_with_relations(
    doctor_id: str,
    db: Session = Depends(get_db),
):

    doctor = await lawyer.get_all_doctor_info(doctor_id=doctor_id, db=db)

    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    # Серіалізуємо дані у відповідну схему
    doctor_response = DoctorWithRelationsResponse(
        id=doctor.id,
        doctor_id=doctor.doctor_id,
        work_email=doctor.work_email,
        first_name=doctor.first_name,
        surname=doctor.surname,
        last_name=doctor.last_name,
        scientific_degree=doctor.scientific_degree,
        date_of_last_attestation=doctor.date_of_last_attestation,
        status=doctor.status,
        diplomas=[
            DiplomaResponse(
                id=diploma.id,
                date=diploma.date,
                series=diploma.series,
                number=diploma.number,
                university=diploma.university,
                scan=bytes_to_base64(diploma.scan)
            )
            for diploma in doctor.diplomas
        ],
        certificates=[
            CertificateResponse(
                id=certificate.id,
                date=certificate.date,
                series=certificate.series,
                number=certificate.number,
                university=certificate.university,
            )
            for certificate in doctor.certificates
        ],
        clinic_affiliations=[
            ClinicAffiliationResponse(
                id=affiliation.id,
                clinic_name=affiliation.clinic_name,
                department=affiliation.department,
                position=affiliation.position,
                specialty=affiliation.specialty,
            )
            for affiliation in doctor.clinic_affiliations
        ],
    )

    return doctor_response


@router.patch("/asign_status/{doctor_id}", dependencies=[Depends(lawyer_access)])
async def assign_status(
    doctor_id: str, doctor_status: DoctorStatus, db: Session = Depends(get_db)
):
    """
    **Assign a doctor_status to a doctor by doctor_id. / Применение нового статуса доктора (подтвержден / на рассмотрении)**\n

    :param doctor_id: str: doctor_id of the user to whom you want to assign the status.

    :param doctor_status: DoctorStatus: The selected doctor_status for the assignment (pending, approved).

    :param db: Session: Database Session.

    :return: Message about successful status change.

    :rtype: str
    """
    doctor = await lawyer.get_doctor(doctor_id=doctor_id, db=db)

    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if doctor_status == doctor.status:
        return {"message": "The acount status has already been assigned"}
    else:
        await lawyer.approve_doctor(doctor=doctor, db=db, status=doctor_status)
        return {
            "message": f"{doctor.first_name} {doctor.last_name}'s status - {doctor_status.value}"
        }



@router.delete("/delete_doctor/{doctor_id}", dependencies=[Depends(lawyer_access)])
async def delete_user(doctor_id: str, db: Session = Depends(get_db)):
    """
    
        **Delete doctor by doctor_id. / Удаление врача по doctor_id**\n

    """
    doctor = await lawyer.get_doctor(doctor_id=doctor_id, db=db)
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    else:
        await lawyer.delete_doctor_by_doctor_id(db=db, doctor_id=doctor_id)
        return {"message": f" doctor {doctor.first_name} {doctor.last_name} - was deleted"}