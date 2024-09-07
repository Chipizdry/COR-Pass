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


class Status(enum.Enum):
    premium: str = "premium"
    basic: str = "basic"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cor_id = Column(String(250), unique=True, nullable=True)
    email = Column(String(250), unique=True, nullable=False)
    backup_email = Column(String(250), unique=True, nullable=True)
    password = Column(String(250), nullable=False)
    access_token = Column(String(250), nullable=True)
    refresh_token = Column(String(250), nullable=True)
    recovery_code = Column(
        String(250), nullable=True
    )  # Уникальный код восстановление пользователя
    is_active = Column(Boolean, default=True)
    account_status: Mapped[Enum] = Column(
        "status", Enum(Status), default=Status.basic
    )  # Статус аккаунта: базовый / премиум
    unique_cipher_key = Column(
        String(250), nullable=False
    )  # уникальный ключ шифрования конкретного пользователя, в базе в зашифрованном виде, шифруется с помошью AES key переменной окружения
    sex = Column(String(10), nullable=True)
    birth = Column(Integer, nullable=True)

    user_records = relationship("Record", back_populates="user")
    user_settings = relationship("UserSettings", back_populates="user")


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


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id = Column(
        String(36), ForeignKey("users.id"), nullable=False, primary_key=True
    )
    local_password_storage = Column(Boolean, default=False)
    cloud_password_storage = Column(Boolean, default=True)
    local_medical_storage = Column(Boolean, default=False)
    cloud_medical_storage = Column(Boolean, default=True)

    user = relationship("User", back_populates="user_settings")


Base.metadata.create_all(bind=engine)
