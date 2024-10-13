from sqlalchemy import and_
from sqlalchemy.orm import Session


from cor_pass.database.models import User, OTP
from cor_pass.schemas import CreateOTPRecordModel, UpdateOTPRecordModel
from cor_pass.repository.person import get_user_by_uuid
from cor_pass.config.config import settings
from cor_pass.services.cipher import encrypt_data, decrypt_data, decrypt_user_key
import os


async def create_otp_record(body: CreateOTPRecordModel, db: Session, user: User) -> OTP:
    if not user:
        raise Exception("User not found")
    new_record = OTP(
        record_name=body.record_name,
        user_id=user.id,
        username=body.username,
        # private_key=await encrypt_data(
        #     data=body.private_key, key=await decrypt_user_key(user.unique_cipher_key)
        # ),
        private_key=body.private_key,
    )

    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    return new_record


async def get_otp_record_by_id(user: User, db: Session, record_id: int):

    record = (
        db.query(OTP)
        .join(User, OTP.user_id == User.id)
        .filter(and_(OTP.record_id == record_id, User.id == user.id))
        .first()
    )
    return record


async def get_all_user_otp_records(db: Session, user_id: str, skip: int, limit: int):
    records = db.query(OTP).filter_by(user_id=user_id).offset(skip).limit(limit).all()
    return records


async def update_otp_record(
    record_id: int, body: UpdateOTPRecordModel, user: User, db: Session
):
    record = (
        db.query(OTP)
        .join(User, OTP.user_id == User.id)
        .filter(and_(OTP.record_id == record_id, User.id == user.id))
        .first()
    )
    if record:
        record.record_name = body.record_name
        record.username = body.username
        db.commit()
        db.refresh(record)
    return record


async def delete_otp_record(user: User, db: Session, record_id: int):

    record = (
        db.query(OTP)
        .join(User, OTP.user_id == User.id)
        .filter(and_(OTP.record_id == record_id, OTP.user_id == user.id))
        .first()
    )
    if not record:
        return None
    if record:
        db.delete(record)
        db.commit()
        print("Record deleted")
    return record
