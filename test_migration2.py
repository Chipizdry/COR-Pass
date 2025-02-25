from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from cor_pass.services.cipher import (
    generate_aes_key,
    encrypt_user_key,
    generate_recovery_code,
    encrypt_data,
)
from cor_pass.services.logger import logger
from cor_pass.services.email import send_email_code_with_qr
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base
from redis import Redis




# from asyncio import WindowsSelectorEventLoopPolicy
# asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())




redis_client = Redis(
    host="localhost", port=6379, db=0
)


# Настройки подключения к первой и второй базам


FIRST_DB_URL = "FIRST_DB_URL"
SECOND_DB_URL = "SECOND_DB_URL"


try:
    logger.debug(f"Connection to {FIRST_DB_URL}")
    first_engine = create_async_engine(FIRST_DB_URL, future=True, echo=True)
    logger.debug(f"Connection to {FIRST_DB_URL} success")
except Exception as e:
    logger.debug(f"Ошибка подключения к {FIRST_DB_URL}- {e}")

try:
    logger.debug(f"Connection to {SECOND_DB_URL}")
    second_engine = create_async_engine(SECOND_DB_URL, future=True, echo=True)
    logger.debug(f"Connection to {SECOND_DB_URL} success")
except Exception as e:
    logger.debug(f"Ошибка подключения к {SECOND_DB_URL}  - {e}")


# FirstSession = sessionmaker(first_engine, class_=AsyncSession, expire_on_commit=False)
# SecondSession = sessionmaker(second_engine, class_=AsyncSession, expire_on_commit=False)


try:
    logger.debug(f"Starting FirstSession")
    FirstSession = sessionmaker(first_engine, class_=AsyncSession, expire_on_commit=False)
    logger.debug(f"Starting {FirstSession} success")
except Exception as e:
    logger.debug(f"Ошибка создания сессии 1 {FirstSession}  - {e}")

try:
    logger.debug(f"Starting SecondSession")
    SecondSession = sessionmaker(second_engine, class_=AsyncSession, expire_on_commit=False)
    logger.debug(f"Starting {SecondSession} success")
except Exception as e:
    logger.debug(f"Ошибка создания сессии 2 {SecondSession}  - {e}")



Base = declarative_base()







# Исходные данные для создания cor-id

n_facility = 1
version = 0
version_bit = 1
days_since_bit = 16
facility_bit = 16
patient_bit = 16
charset = '0123456789ABCDEFGHJKLMNPRSTUVWXYZ'



def custom_base32_encode(value, charset):
    """Кодирует число в строку на основе указанного алфавита (charset)."""
    num = int(value)
    base = len(charset)  # Длина алфавита

    if num == 0:
        return charset[0]  # Если число 0, возвращаем первый символ алфавита

    encoded = []
    while num > 0:
        num, remainder = divmod(num, base)  # Остаток от деления на основание
        encoded.append(
            charset[remainder]
        )  # Добавляем соответствующий символ из алфавита

    return "".join(reversed(encoded))  # Переворачиваем и возвращаем строку


def from_custom_base32(encoded_str, charset):
    """Декодирует строку обратно в число на основе указанного алфавита (charset)."""
    base = len(charset)
    num = 0
    for char in encoded_str:
        num = num * base + charset.index(char)  # Умножаем и добавляем индекс символа
    return num


# Создание cor_id
async def create_new_corid(user, db):
    birth_year_gender = f"{user.birth}{user.user_sex}"
    jan_first_2024 = datetime(2024, 1, 1).date()
    today = datetime.now().date()
    n_days_since_first_jan_2024 = (today - jan_first_2024).days
    term1 = (
        version
        * (2 ** (days_since_bit + facility_bit + patient_bit))
        * (1 if version_bit > 0 else 0)
    )
    term2 = n_days_since_first_jan_2024 * (2 ** (patient_bit + facility_bit))
    term3 = n_facility * (2**patient_bit)
    term4 = get_register_per_day(n_facility)

    new_corid_decimal = term1 + term2 + term3 + term4
    new_corid_encoded = custom_base32_encode(new_corid_decimal, charset)
    new_corid = new_corid_encoded + "-" + birth_year_gender
    user.cor_id = new_corid
    logger.debug(f"For {user.email} created {user.cor_id}")
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise e



def get_register_per_day(facility_number):
    """Получить номер регистрации за день для указанного учреждения."""
    # Генерируем уникальный ключ на основе facility_number и текущей даты
    date_str = datetime.now().strftime("%Y-%m-%d")  # Текущая дата в формате ГГГГ-ММ-ДД
    register_key = f"register:{facility_number}:{date_str}"

    if redis_client.exists(register_key):
        register_number = redis_client.incr(register_key)
    else:
        redis_client.set(register_key, 1)
        redis_client.expire(register_key, 24 * 60 * 60)
        register_number = 1

    return register_number







# Импорт моделей
from cor_pass.database.old_models import User as FirstUser
from cor_pass.database.models import User as SecondUser
from cor_pass.database.models import Base, User, Verification, Record, Tag, RecordTag, UserSettings, OTP  


async def setup_database(engine):
    async with engine.begin() as conn:
        # Создание всех таблиц в базе данных
        await conn.run_sync(Base.metadata.create_all)


# Миграция данных
async def migrate_users():
    logger.debug(f"Start migration")

    # Создание всех таблиц второй базы
    await setup_database(second_engine)

    async with FirstSession() as first_session, SecondSession() as second_session:
        logger.debug(f"Connection to both databases success")
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
                # time.sleep(10)
                # await send_email_code_with_qr(
                #         user.email, host=None, recovery_code=recovery_code)
                # time.sleep(10)
                encrypted_recovery_code = await encrypt_data(
                    data=recovery_code, key=unique_cipher_key
                )

                unique_cipher_key = await encrypt_user_key(unique_cipher_key)

                # Создаём запись для второй базы
                new_user = SecondUser(
                    id=user.id,
                    email=user.email,
                    password=user.password,
                    unique_cipher_key=unique_cipher_key,
                    recovery_code=encrypted_recovery_code,
                    user_sex="M",  # Значение по умолчанию
                    birth=2000,  # Значение по умолчанию
                    user_index=user_index,
                    is_active=True,
                    created_at=datetime.now(),
                )

                # Добавляем запись во вторую базу
                second_session.add(new_user)
                if not new_user.cor_id:
                    await create_new_corid(new_user, second_session)
                user_index += 1
                logger.debug(f"{new_user.email} creation success")


            # Фиксируем изменения
            await second_session.commit()
            logger.debug(f"{len(users)} пользователей успешно перенесено.")

        except Exception as e:
            logger.debug(f"Ошибка при миграции: {e}")
            await second_session.rollback()


if __name__ == "__main__":
    asyncio.run(migrate_users())
