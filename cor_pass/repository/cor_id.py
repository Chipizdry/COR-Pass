from sqlalchemy.orm import Session
import datetime
from datetime import datetime
from cor_pass.database.models import User
from cor_pass.services.logger import logger
from cor_pass.database.redis_db import redis_client
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.config.config import settings
from datetime import datetime

# Исходные данные

n_facility = settings.corid_facility_key
version = settings.corid_version
version_bit = settings.corid_version_bit
days_since_bit = settings.corid_days_since_bit
facility_bit = settings.corid_facility_bit
patient_bit = settings.corid_patient_bit
charset = settings.corid_charset


async def get_cor_id(user: User, db: Session):
    cor_id = user.cor_id
    print(cor_id)
    if cor_id:
        return cor_id
    else:
        return None


"""
Алгоритм Юры

"""


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


# Расшифровка cor_id
def decode_corid(cor_id):
    encoded_corid, birth_year_gender = cor_id.split("-")

    decoded_num = from_custom_base32(encoded_corid, charset)

    # Извлечение данных из числа
    version = (decoded_num >> (patient_bit + facility_bit + days_since_bit)) & 1
    n_days_since = (decoded_num >> (patient_bit + facility_bit)) & (
        (1 << days_since_bit) - 1
    )
    facility_number = (decoded_num >> patient_bit) & ((1 << facility_bit) - 1)
    register_per_day = decoded_num & ((1 << patient_bit) - 1)
    birth_year = birth_year_gender[:-1]
    gender = birth_year_gender[-1]

    return {
        "version": version,
        "n_days_since": n_days_since,
        "facility_number": facility_number,
        "register_per_day": register_per_day,
        "birth_year": birth_year,
        "gender": gender,
    }


# Создание cor_id
async def create_new_corid(user: User, db: AsyncSession):
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
    term4 = await get_register_per_day(n_facility)

    new_corid_decimal = term1 + term2 + term3 + term4
    new_corid_encoded = custom_base32_encode(new_corid_decimal, charset)
    new_corid = new_corid_encoded + "-" + birth_year_gender
    user.cor_id = new_corid
    logger.debug(f"For {user.email} created {user.cor_id}")
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise e


async def get_register_per_day(facility_number):
    """Получить номер регистрации за день для указанного учреждения."""
    # Генерируем уникальный ключ на основе facility_number и текущей даты
    date_str = datetime.now().strftime("%Y-%m-%d")  # Текущая дата в формате ГГГГ-ММ-ДД
    register_key = f"register:{facility_number}:{date_str}"

    if await redis_client.exists(register_key):
        register_number = await redis_client.incr(register_key)
    else:
        await redis_client.set(register_key, 1)
        await redis_client.expire(register_key, 24 * 60 * 60)
        register_number = 1

    return register_number
