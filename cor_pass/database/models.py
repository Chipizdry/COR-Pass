import enum
import uuid
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Enum,
    Text,
    Date,
    Float,
    func,
    Boolean,
    LargeBinary,
)
from sqlalchemy.orm import declarative_base, relationship, Mapped
from sqlalchemy.sql.sqltypes import DateTime
from cor_pass.database.db import engine

Base = declarative_base()


class Role(enum.Enum):
    admin: str = "admin"
    user: str = "user"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(250), unique=True, nullable=False)
    password = Column(String(250), nullable=False)
    access_token = Column(String(250), nullable=True)
    refresh_token = Column(String(250), nullable=True)
    restore_code = Column(String(250), nullable=True)
    is_active = Column(Boolean, default=True)
    role: Mapped[Enum] = Column("role", Enum(Role), default=Role.admin)
    unique_cipher_key = Column(LargeBinary, nullable=False)

    user_records = relationship("Record", back_populates="user")


class Verification(Base):
    __tablename__ = "verification"
    id = Column(Integer, primary_key=True)
    email = Column(String(250), unique=True, nullable=False)
    verification_code = Column(Integer, default=None)
    email_confirmation = Column(Boolean, default=False)


class Record(Base):
    __tablename__ = "records"

    record_id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    record_name = Column(String(250), nullable=False)
    website = Column(String(250), nullable=True)
    username = Column(String(250), nullable=True)
    password = Column(String(250), nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    edited_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
    notes = Column(Text, nullable=True)

    user = relationship("User", back_populates="user_records")
    tags = relationship("Tag", secondary="records_tags")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)


class RecordTag(Base):
    __tablename__ = "records_tags"

    record_id = Column(Integer, ForeignKey("records.record_id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)


# class Record(Base):
#     __tablename__ = "record"
#     id = Column(Integer, primary_key=True)
#     user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
#     record_name = Column(String(250), nullable=False)
#     website = Column(String(250), nullable=True)
#     username = Column(String(250), nullable=True)
#     password = Column(String(250), nullable=True)

#     created_at = Column(DateTime, nullable=False, default=func.now())
#     edited_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

#     attachments = Column(String(250), nullable=True)
#     notes = Column(Text, nullable=True)

#     user = relationship("User", back_populates="records")
#     fields = relationship("RecordFieldValue", back_populates="record")
#     tags = relationship("Tag", secondary="record_tags", back_populates="records")

# class FieldType(enum.Enum):
#     TEXT = "text"
#     URL = "url"
#     ALPHA_NUMERIC = "alpha_numeric"
#     PHONE_NUMBER = "phone_number"
#     EMAIL = "email"
#     NUMBER = "number"
#     USERNAME = "username"
#     PASSWORD = "password"
#     SENSITIVE_NUMBER = "sensitive_number"
#     DATE = "date"
#     MONTH_YEAR = "month_year"
#     CREDIT_CARD = "credit_card"
#     ONE_TIME_PASSWORD = "otp"

# class RecordField(Base):
#     __tablename__ = "record_field"
#     id = Column(Integer, primary_key=True)
#     name = Column(String(250), nullable=False)
#     type = Column(Enum(FieldType), nullable=False)

#     values = relationship("RecordFieldValue", back_populates="field")

# class RecordFieldValue(Base):
#     __tablename__ = "record_field_value"
#     id = Column(Integer, primary_key=True)
#     record_id = Column(Integer, ForeignKey("record.id"), nullable=False)
#     field_id = Column(Integer, ForeignKey("record_field.id"), nullable=False)

#     # Используем разные колонки для разных типов данных
#     string_value = Column(Text, nullable=True)
#     date_value = Column(Date, nullable=True)
#     number_value = Column(Float, nullable=True)

#     record = relationship("Record", back_populates="fields")
#     field = relationship("RecordField", back_populates="values")


Base.metadata.create_all(bind=engine)
