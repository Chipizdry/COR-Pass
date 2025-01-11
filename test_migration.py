from sqlalchemy import select
from sqlalchemy.orm import sessionmaker


from datetime import datetime
from cor_pass.services.cipher import (
    generate_aes_key,
    encrypt_user_key,
    generate_recovery_code,
    encrypt_data,
)
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from asyncio import WindowsSelectorEventLoopPolicy

import enum
import uuid

from sqlalchemy import Column, Integer, String, Boolean, Enum
from sqlalchemy.orm import declarative_base, Mapped

Base = declarative_base()


# Set the event loop policy
asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
# Настройки подключения к первой и второй базам


FIRST_DB_URL = "cor-identity db"
SECOND_DB_URL = "cor-id db"

first_engine = create_async_engine(FIRST_DB_URL, future=True, echo=True)
second_engine = create_async_engine(SECOND_DB_URL, future=True, echo=True)

FirstSession = sessionmaker(first_engine, class_=AsyncSession, expire_on_commit=False)
SecondSession = sessionmaker(second_engine, class_=AsyncSession, expire_on_commit=False)


# Импорт моделей
# from cor_pass.database.models import User as SecondUser
# from cor_pass.database.old_models import User as FirstUser


# Модели старой базы
class Role(enum.Enum):
    admin: str = "admin"
    moderator: str = "moderator"
    user: str = "user"


class FirstUser(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=str(uuid.uuid4()))
    email = Column(String(250), unique=True, nullable=False)
    password = Column(String(250), nullable=False)
    access_token = Column(String(250), nullable=True)
    refresh_token = Column(String(250), nullable=True)
    role: Mapped[Enum] = Column("role", Enum(Role), default=Role.admin)


# Модели новой базы
import enum
import uuid
from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    func,
    Boolean,
    LargeBinary,
)
from sqlalchemy.orm import declarative_base, relationship, Mapped
from sqlalchemy.sql.sqltypes import DateTime


class Status(enum.Enum):
    premium: str = "premium"
    basic: str = "basic"


class SecondUser(Base):

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cor_id = Column(String(250), unique=True, nullable=True)
    email = Column(String(250), unique=True, nullable=False)
    backup_email = Column(String(250), unique=True, nullable=True)
    password = Column(String(250), nullable=False)
    last_password_change = Column(DateTime, server_default=func.now())
    access_token = Column(String(500), nullable=True)
    refresh_token = Column(String(500), nullable=True)
    recovery_code = Column(LargeBinary, nullable=True)
    is_active = Column(Boolean, default=True)
    account_status: Mapped[Enum] = Column("status", Enum(Status), default=Status.basic)
    unique_cipher_key = Column(String(250), nullable=False)
    user_sex = Column(String(10), nullable=True)
    birth = Column(Integer, nullable=True)
    user_index = Column(Integer, unique=True, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    user_records = relationship(
        "Record", back_populates="user", cascade="all, delete-orphan"
    )
    user_settings = relationship(
        "UserSettings", back_populates="user", cascade="all, delete-orphan"
    )
    user_otp = relationship("OTP", back_populates="user", cascade="all, delete-orphan")


# Миграция данных
async def migrate_users():
    print("Connecting to first database...")
    async with FirstSession() as first_session, SecondSession() as second_session:
        print("Connected to both databases")
        user_index = 1
        try:
            # Выбираем пользователей из первой базы
            result = await first_session.execute(select(FirstUser))
            users = result.scalars().all()

            for user in users:
                # создаем ключ шифрования
                unique_cipher_key = await generate_aes_key()

                # создаем код восстановления
                recovery_code = await generate_recovery_code()
                encrypted_recovery_code = await encrypt_data(
                    data=recovery_code, key=unique_cipher_key
                )

                unique_cipher_key = await encrypt_user_key(unique_cipher_key)

                # max_index = await person.get_max_user_index(second_session)
                # user_index = (max_index + 1) if max_index is not None else 1

                # Создаём запись для второй базы
                new_user = SecondUser(
                    id=user.id,
                    email=user.email,
                    password=user.password,
                    unique_cipher_key=unique_cipher_key,
                    recovery_code=encrypted_recovery_code,
                    user_sex=None,  # Значение по умолчанию
                    birth=None,  # Значение по умолчанию
                    user_index=user_index,
                    is_active=True,
                    created_at=datetime.now(),
                )

                # Добавляем запись во вторую базу
                second_session.add(new_user)
                user_index += 1
            # Фиксируем изменения
            await second_session.commit()
            print(f"{len(users)} пользователей успешно перенесено.")

        except Exception as e:
            print("Ошибка при миграции:", e)
            await second_session.rollback()


if __name__ == "__main__":
    asyncio.run(migrate_users())
