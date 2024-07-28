from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import List

from cor_pass.repository import records as repository_record
from cor_pass.database.db import get_db
from cor_pass.schemas import CreateRecordModel, RecordResponse
from cor_pass.database.models import User
from cor_pass.config.config import settings
from cor_pass.services.auth import auth_service
from cor_pass.services.logger import logger
from cor_pass.services.access import user_access
from cor_pass.repository import users as repository_users

router = APIRouter(prefix="/records", tags=["Records"])
encryption_key = settings.encryption_key



"""
Маршрут получения всех записей пользователя
"""


@router.get(
    "/", response_model=List[RecordResponse], dependencies=[Depends(user_access)]
)
async def read_records(
    skip: int = 0,
    limit: int = 50,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a list of records.

    :param skip: The number of records to skip (for pagination). Default is 0.
    :type skip: int
    :param limit: The maximum number of records to retrieve. Default is 50.
    :type limit: int
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: A list of RecordModel objects representing the records.
    :rtype: List[RecordModel]
    """
    try:
        records = await repository_record.get_all_user_records(db, user.id, skip, limit)
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    return records



"""
Маршрут получения конкретной записи пользователя
"""

@router.get(
    "/{record_id}", response_model=RecordResponse, dependencies=[Depends(user_access)]
)
async def read_record(
    record_id: int,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a specific record by ID.

    :param record_id: The ID of the record.
    :type record_id: int
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: The RecordModel object representing the record.
    :rtype: RecordModel
    :raises HTTPException 404: If the record with the specified ID does not exist.
    """
    record = await repository_record.get_record_by_id(user, db, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    return record



"""
Маршрут создания записи
"""

@router.post(
    "/",
    response_model=RecordResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_access)],
)
async def create_record(
    body: CreateRecordModel,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new record.

    :param body: The request body containing the record data.
    :type body: CreateRecordModel
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: The created ResponseRecord object representing the new record.
    :rtype: ResponseRecord
    """
    record = await repository_record.create_record(body, db, user)
    return record




"""
Маршрут обновления записи
"""

@router.put(
    "/{record_id}", response_model=RecordResponse, dependencies=[Depends(user_access)]
)
async def update_record(
    record_id: int,
    body: CreateRecordModel,
    db: Session = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
):
    """
    Update an existing record.

    :param record_id: The ID of the record to update.
    :type record_id: int
    :param body: The request body containing the updated record data.
    :type body: CreateRecordModel
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: The updated ResponseRecord object representing the updated record.
    :rtype: ResponseRecord
    :raises HTTPException 404: If the record with the specified ID does not exist.
    """
    record = await repository_record.update_record(record_id, body, user, db)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    return record




"""
Маршрут удаления записи
"""

@router.delete("/{record_id}", response_model=RecordResponse)
async def remove_record(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
):
    """
    Remove a record.

    :param record_id: The ID of the record to remove.
    :type record_id: int
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: The removed RecordModel object representing the removed record.
    :rtype: RecordModel
    :raises HTTPException 404: If the record with the specified ID does not exist.
    """
    record = await repository_record.delete_record(user, db, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    return record
