from typing import List
from sqlalchemy import and_, select


from cor_pass.database.models import User, OTP
from cor_pass.schemas import CreateOTPRecordModel, UpdateOTPRecordModel
from cor_pass.services.cipher import encrypt_data, decrypt_user_key
from cor_pass.services import cor_otp
from cor_pass.services.logger import logger
from sqlalchemy.ext.asyncio import AsyncSession


async def create_otp_record(
    body: CreateOTPRecordModel, db: AsyncSession, user: User
) -> OTP:
    if not user:
        raise Exception("User not found")
    new_record = OTP(
        record_name=body.record_name,
        user_id=user.id,
        username=body.username,
        private_key=await encrypt_data(
            data=body.private_key, key=await decrypt_user_key(user.unique_cipher_key)
        ),
    )
    try:
        otp_password, remaining_time = await cor_otp.generate_and_verify_otp(
            new_record.private_key, user
        )
        db.add(new_record)
        await db.commit()
        await db.refresh(new_record)
        return new_record
    except Exception as e:
        logger.error(f"Failed to create otp record: {e}")
        await db.rollback()
        raise e


async def get_otp_record_by_id(user: User, db: AsyncSession, record_id: int):
    """
    Асинхронно получает запись OTP по его ID, проверяя принадлежность пользователю.
    """
    stmt = (
        select(OTP)
        .join(User, OTP.user_id == User.id)
        .where(and_(OTP.record_id == record_id, User.id == user.id))
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    return record


async def get_all_user_otp_records(
    db: AsyncSession, user_id: str, skip: int, limit: int
) -> List[OTP]:
    """
    Асинхронно получает все записи OTP конкретного пользователя из базы с учетом пагинации.
    """
    stmt = select(OTP).where(OTP.user_id == user_id).offset(skip).limit(limit)
    result = await db.execute(stmt)
    records = result.scalars().all()
    return list(records)


async def update_otp_record(
    record_id: int, body: UpdateOTPRecordModel, user: User, db: AsyncSession
):
    """
    Асинхронно обновляет существующую запись OTP, проверяя ее принадлежность пользователю.
    """
    stmt = (
        select(OTP)
        .join(User, OTP.user_id == User.id)
        .where(and_(OTP.record_id == record_id, User.id == user.id))
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if record:
        record.record_name = body.record_name
        record.username = body.username
        await db.commit()
        await db.refresh(record)
        return record
    return None


async def delete_otp_record(user: User, db: AsyncSession, record_id: int):
    """
    Асинхронно удаляет запись OTP, проверяя его принадлежность пользователю.
    """
    stmt = (
        select(OTP)
        .join(User, OTP.user_id == User.id)
        .where(and_(OTP.record_id == record_id, OTP.user_id == user.id))
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        return None

    await db.delete(record)
    await db.commit()
    print("Record deleted")
    return record
