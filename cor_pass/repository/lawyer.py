from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm import Query as SQLAQuery

from cor_pass.database.models import (
    Doctor,
    DoctorStatus,
    Diploma,
    Certificate,
    ClinicAffiliation,
)
from cor_pass.schemas import (
    UserModel,
    PasswordStorageSettings,
    MedicalStorageSettings,
    UserSessionDBModel,
    UserSessionModel,
)
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession


# async def get_doctors(skip: int, limit: int, db: AsyncSession) -> List[Doctor]:
#     """
#     Асинхронно повертає список всіх лікарів з бази даних.

#     :param skip: int: Пропустити перші n записів у базі даних
#     :param limit: int: Обмежити кількість повернутих результатів
#     :param db: AsyncSession: Асинхронна сесія бази даних
#     :return: Список всіх лікарів
#     """
#     stmt = select(Doctor).offset(skip).limit(limit)
#     result = await db.execute(stmt)
#     doctors = result.scalars().all()
#     return list(doctors)



async def get_doctors(
    skip: int,
    limit: int,
    db: AsyncSession,
    status: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "asc",
) -> List[Doctor]:
    """
    Асинхронно возвращает список врачей из базы данных с возможностью фильтрации,
    сортировки и пагинации.

    """
    stmt: SQLAQuery = select(Doctor)

    if status:
            try:
                doctor_status = DoctorStatus[status.upper()]  
                stmt = stmt.where(Doctor.status == doctor_status)
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Недействительный статус врача: {status}")

    # Сортировка
    if sort_by:
        sort_column = getattr(Doctor, sort_by, None)
        if sort_column is not None:
            if sort_order == "desc":
                stmt = stmt.order_by(desc(sort_column))
            else:
                stmt = stmt.order_by(asc(sort_column))
        else:
            raise HTTPException(
                status_code=400, detail=f"Неизвестное поле для сортировки: {sort_by}"
            )

    # Пагинация
    stmt = stmt.offset(skip).limit(limit)

    result = await db.execute(stmt)
    doctors = result.scalars().all()
    return list(doctors)


async def get_doctor(doctor_id: str, db: AsyncSession) -> Doctor | None:
    """
    Асинхронно получает врача по его ID.
    """
    stmt = select(Doctor).where(Doctor.doctor_id == doctor_id)
    result = await db.execute(stmt)
    doctor = result.scalar_one_or_none()
    return doctor


async def get_all_doctor_info(doctor_id: str, db: AsyncSession) -> Doctor | None:
    """
    Асинхронно получает всю информацию о враче, включая дипломы, сертификаты и привязки к клиникам.
    """
    stmt = (
        select(Doctor)
        .where(Doctor.doctor_id == doctor_id)
        .outerjoin(Diploma)
        .outerjoin(Certificate)
        .outerjoin(ClinicAffiliation)
        .options(selectinload(Doctor.diplomas))
        .options(selectinload(Doctor.certificates))
        .options(selectinload(Doctor.clinic_affiliations))
    )
    result = await db.execute(stmt)
    doctor = result.scalar_one_or_none()
    return doctor


async def approve_doctor(doctor: Doctor, db: AsyncSession, status: DoctorStatus):
    """
    Асинхронно обновляет статус врача.
    """
    doctor.status = status
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise e


async def delete_doctor_by_doctor_id(db: AsyncSession, doctor_id: str):
    """
    Асинхронно удаляет врача по его doctor_id.
    """
    try:
        stmt = select(Doctor).where(Doctor.doctor_id == doctor_id)
        result = await db.execute(stmt)
        doctor = result.scalar_one()

        await db.delete(doctor)
        await db.commit()
    except NoResultFound:
        print("Доктор не найден.")
    except Exception as e:
        await db.rollback()
        print(f"Произошла ошибка при удалении врача: {e}")
