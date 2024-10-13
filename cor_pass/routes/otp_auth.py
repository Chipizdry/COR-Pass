from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import List

from cor_pass.repository import records as repository_record
from cor_pass.repository import otp_auth as repository_otp_auth
from cor_pass.database.db import get_db
from cor_pass.schemas import (
    CreateOTPRecordModel,
    OTPRecordResponse,
    UpdateOTPRecordModel,
)
from cor_pass.database.models import User
from cor_pass.config.config import settings
from cor_pass.services.auth import auth_service
from cor_pass.services.logger import logger
from cor_pass.services.access import user_access
from cor_pass.services import cor_otp


router = APIRouter(prefix="/otp_auth", tags=["OTP-Authentication"])
encryption_key = settings.encryption_key


@router.get(
    "/all", response_model=List[OTPRecordResponse], dependencies=[Depends(user_access)]
)
async def read_otp_records(
    skip: int = 0,
    limit: int = 150,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Get a list of otp_records. / Получение всех otp записей пользователя** \n

    :param skip: The number of otp records to skip (for pagination). Default is 0.
    :type skip: int
    :param limit: The maximum number of otp records to retrieve. Default is 150.
    :type limit: int
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: A list of OTPRecordResponse objects representing the records.
    :rtype: List[OTPRecordResponse]
    """
    try:
        otp_records = await repository_otp_auth.get_all_user_otp_records(
            db, user.id, skip, limit
        )
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    otp_records_with_codes = []
    for record in otp_records:
        otp_password, remaining_time = cor_otp.generate_and_verify_otp(
            record.private_key
        )
        otp_record_response = OTPRecordResponse(
            record_id=record.record_id,
            record_name=record.record_name,
            username=record.username,
            otp_password=otp_password,
            remaining_time=remaining_time,
        )
        otp_records_with_codes.append(otp_record_response)

    return otp_records_with_codes


@router.get(
    "/{otp_record_id}",
    response_model=OTPRecordResponse,
    dependencies=[Depends(user_access)],
)
async def read_otp_record(
    otp_record_id: int,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Get a specific otp_record by ID. / Получение данных одной конкретной otp записи пользователя** \n

    :param otp_record_id: The ID of the otp record.
    :type otp_record_id: int
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: The OTPRecordResponse object representing the record.
    :rtype: OTPRecordResponse
    :raises HTTPException 404: If the otp record with the specified ID does not exist.
    """
    otp_record = await repository_otp_auth.get_otp_record_by_id(user, db, otp_record_id)
    if otp_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    otp_password, remaining_time = cor_otp.generate_and_verify_otp(
        otp_record.private_key
    )

    return OTPRecordResponse(
        record_id=otp_record.record_id,
        record_name=otp_record.record_name,
        username=otp_record.username,
        otp_password=otp_password,
        remaining_time=remaining_time,
    )


@router.post(
    "/create",
    response_model=OTPRecordResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_access)],
)
async def create_otp_record(
    body: CreateOTPRecordModel,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Create a new otp record. / Создание записи** \n

    :param body: The request body containing the record data.
    :type body: CreateOTPRecordModel
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: The created OTPRecordResponse object representing the new otp record.
    :rtype: OTPRecordResponse
    """
    otp_record = await repository_otp_auth.create_otp_record(body, db, user)
    otp_password, remaining_time = cor_otp.generate_and_verify_otp(
        otp_record.private_key
    )

    return OTPRecordResponse(
        record_id=otp_record.record_id,
        record_name=otp_record.record_name,
        username=otp_record.username,
        otp_password=otp_password,
        remaining_time=remaining_time,
    )


"""
Маршрут обновления otp записи
"""


@router.put(
    "/{otp_record_id}",
    response_model=OTPRecordResponse,
    dependencies=[Depends(user_access)],
)
async def update_otp_record(
    otp_record_id: int,
    body: UpdateOTPRecordModel,
    db: Session = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
):
    """
    **Update an existing otp record. / Обновление данных otp записи** \n

    :param record_id: The ID of the record to update.
    :type record_id: int
    :param body: The request body containing the updated record data.
    :type body: UpdateOTPRecordModel
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: The updated ResponseRecord object representing the updated record.
    :rtype: OTPRecordResponse
    :raises HTTPException 404: If the record with the specified ID does not exist.
    """
    otp_record = await repository_otp_auth.update_otp_record(
        otp_record_id, body, user, db
    )
    if otp_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    otp_password, remaining_time = cor_otp.generate_and_verify_otp(
        otp_record.private_key
    )

    return OTPRecordResponse(
        record_id=otp_record.record_id,
        record_name=otp_record.record_name,
        username=otp_record.username,
        otp_password=otp_password,
        remaining_time=remaining_time,
    )


@router.delete("/{otp_record_id}")
async def remove_otp_record(
    otp_record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
):
    """
    **Remove a record. / Удаление записи** \n

    :param record_id: The ID of the record to remove.
    :type record_id: int
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: The removed RecordModel object representing the removed record.
    :rtype: RecordModel
    :raises HTTPException 404: If the record with the specified ID does not exist.
    """
    otp_record = await repository_otp_auth.delete_otp_record(user, db, otp_record_id)
    if otp_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    return otp_record
