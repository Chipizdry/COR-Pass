from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy import asc, desc, select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Query as SQLAQuery

from cor_pass.database.models import (
    Doctor,
    Doctor_Status,
    Diploma,
    Certificate,
    ClinicAffiliation,
    Lawyer,
    User,
)
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.schemas import LawyerCreate


async def create_lawyer(
    lawyer_data: LawyerCreate,
    db: AsyncSession,
    user: User,
) -> Lawyer:
    """
    Асинхронная сервисная функция по созданию lawyer.
    """
    lawyer = Lawyer(
        lawyer_cor_id=user.cor_id,
        first_name=lawyer_data.first_name,
        surname=lawyer_data.last_name,
        middle_name=lawyer_data.middle_name,
    )

    db.add(lawyer)

    await db.commit()
    await db.refresh(lawyer)

    return lawyer


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
            doctor_status = Doctor_Status[status.upper()]
            stmt = stmt.where(Doctor.status == doctor_status)
        except KeyError:
            raise HTTPException(
                status_code=400, detail=f"Недействительный статус врача: {status}"
            )

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


async def approve_doctor(doctor: Doctor, db: AsyncSession, status: Doctor_Status):
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


async def get_diploma_by_id(diploma_id: str, db: AsyncSession):
    """Получает информацию о документе по его ID."""
    result = await db.execute(select(Diploma).where(Diploma.id == diploma_id))
    return result.scalar_one_or_none()


async def get_certificate_by_id(certificate_id: str, db: AsyncSession):
    """Получает информацию о документе по его ID."""
    result = await db.execute(
        select(Certificate).where(Certificate.id == certificate_id)
    )
    return result.scalar_one_or_none()
