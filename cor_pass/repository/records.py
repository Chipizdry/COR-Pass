from sqlalchemy import and_
from sqlalchemy.orm import Session


from cor_pass.database.models import User, Record, Tag
from cor_pass.schemas import CreateRecordModel
from cor_pass.config.config import settings
from cor_pass.services.cipher import encrypt_data, decrypt_data
import os


async def create_record(body: CreateRecordModel, db: Session, user: User) -> Record:
    if not user:
        raise Exception("User not found")
    record = Record(
        record_name=body.record_name,
        user_id=user.id,
        website=body.website,
        username=body.username,
        password=encrypt_data(data=body.password, key=user.unique_cipher_key),
        notes=body.notes,
    )
    if body.tag_names:
        for tag_name in body.tag_names:
            tag = db.query(Tag).filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
            record.tags.append(tag)

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


async def get_record_by_id(user: User, db: Session, record_id: int):

    record = (
        db.query(Record)
        .join(User, Record.user_id == User.id)
        .filter(and_(Record.record_id == record_id, User.id == user.id))
        .first()
    )
    if record:
        record.password = decrypt_data(
        encrypted_data=record.password, key=user.unique_cipher_key
    )
    return record


async def get_all_user_records(db: Session, user_id: str, skip: int, limit: int):
    records = (
        db.query(Record).filter_by(user_id=user_id).offset(skip).limit(limit).all()
    )
    return records


async def update_record(
    record_id: int, body: CreateRecordModel, user: User, db: Session
):
    record = (
        db.query(Record)
        .join(User, Record.user_id == User.id)
        .filter(and_(Record.record_id == record_id, User.id == user.id))
        .first()
    )
    if record:
        record.record_name = body.record_name
        record.website = body.website
        record.username = body.username
        record.password = encrypt_data(data=body.password, key=user.unique_cipher_key)
        record.notes = body.notes
        tags_copy = list(record.tags)

        for tag in tags_copy:
            record.tags.remove(tag)

        if body.tag_names:
            for tag_name in body.tag_names:
                tag = db.query(Tag).filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                record.tags.append(tag)

        db.commit()
        db.refresh(record)
    return record


async def delete_record(user: User, db: Session, record_id: int):

    record = (
        db.query(Record)
        .join(User, Record.user_id == User.id)
        .filter(and_(Record.record_id == record_id, Record.user_id == user.id))
        .first()
    )
    if not record:
        return False, {"message": "Record not found"}
    if record:
        db.delete(record)
        db.commit()
        print("Record deleted")
    return record
