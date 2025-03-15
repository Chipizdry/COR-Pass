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
    Index,
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
    last_password_change = Column(DateTime, server_default=func.now())
    access_token = Column(String(500), nullable=True)
    refresh_token = Column(String(500), nullable=True)
    recovery_code = Column(
        LargeBinary, nullable=True
    )  # Уникальный код восстановление пользователя
    is_active = Column(Boolean, default=True)
    account_status: Mapped[Enum] = Column(
        "status", Enum(Status), default=Status.basic
    )  # Статус аккаунта: базовый / премиум
    unique_cipher_key = Column(
        String(250), nullable=False
    )  # уникальный ключ шифрования конкретного пользователя, в базе в зашифрованном виде, шифруется с помошью AES key переменной окружения
    user_sex = Column(String(10), nullable=True)
    birth = Column(Integer, nullable=True)
    user_index = Column(
        Integer, unique=True, nullable=True
    )  # индекс пользователя, используется в создании cor_id
    created_at = Column(DateTime, nullable=False, default=func.now())

    # Связи
    user_records = relationship(
        "Record", back_populates="user", cascade="all, delete-orphan"
    )
    user_settings = relationship(
        "UserSettings", back_populates="user", cascade="all, delete-orphan"
    )
    user_otp = relationship("OTP", back_populates="user", cascade="all, delete-orphan")

    user_sessions = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )

    # Индексы
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_cor_id", "cor_id"),
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.cor_id"), nullable=False)
    device_type = Column(String(250), nullable=True)
    device_info = Column(String(250), nullable=True)
    ip_address = Column(String(250), nullable=True)
    device_os = Column(String(250), nullable=True)
    refresh_token = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Связи
    user = relationship("User", back_populates="user_sessions")

    # Индексы
    __table_args__ = (Index("idx_user_sessions_user_id", "user_id"),)


class Verification(Base):
    __tablename__ = "verification"
    id = Column(Integer, primary_key=True)
    email = Column(String(250), unique=True, nullable=False)
    verification_code = Column(Integer, default=None)
    email_confirmation = Column(Boolean, default=False)

    # Индексы
    __table_args__ = (Index("idx_verification_email", "email"),)


class Record(Base):
    __tablename__ = "records"

    record_id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    record_name = Column(String(250), nullable=False)
    website = Column(String(250), nullable=True)
    username = Column(LargeBinary, nullable=True)
    password = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    edited_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
    notes = Column(Text, nullable=True)
    is_favorite = Column(Boolean, default=False, nullable=True)

    # Связи
    user = relationship("User", back_populates="user_records")
    tags = relationship("Tag", secondary="records_tags")

    # Индексы
    __table_args__ = (Index("idx_records_user_id", "user_id"),)


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)

    # Индексы
    __table_args__ = (Index("idx_tags_name", "name"),)


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

    # Связи
    user = relationship("User", back_populates="user_settings")


class OTP(Base):
    __tablename__ = "otp_records"

    record_id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    record_name = Column(String(250), nullable=False)
    username = Column(String(250), nullable=True)
    private_key = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    edited_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Связи
    user = relationship("User", back_populates="user_otp")

    # Индексы
    __table_args__ = (Index("idx_otp_records_user_id", "user_id"),)


# Base.metadata.create_all(bind=engine)
