from sqlalchemy.orm import Session
import datetime
from cor_pass.database.models import User
from cor_pass.schemas import CreateCorIdModel
from cor_pass.services.logger import logger

from cor_pass.config.config import settings
from datetime import datetime


async def get_cor_id(user: User, db: Session):
    cor_id = user.cor_id
    print(cor_id)
    if cor_id:
        return cor_id
    else:
        return None


"""
Алгоритм Андрея

"""

n_facility = settings.facility_key


def transform_integer(n):
    if not (1 <= n <= 99999):
        raise ValueError("Number must be between 1 and 99999 inclusive.")
    return f"{n:05d}"


def to_base36(n_days, n_facility, n_patient):
    num = int(f"{n_days}{n_facility}{n_patient}")
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    result = []
    while num > 0:
        num, remainder = divmod(num, 36)
        result.append(chars[remainder])
    return "".join(reversed(result))


def display_corid_info(corid):
    try:
        base36_str, suffix = corid.split("-")
    except ValueError:
        raise ValueError("Cor-ID format is invalid. Expected a '-'.")

    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    num = 0
    for char in base36_str:
        if char not in chars:
            raise ValueError(f"Invalid character '{char}' in Cor-ID.")
        num = num * 36 + chars.index(char)

    n_str = f"{num:011d}"
    if len(n_str) < 11:
        raise ValueError("Decoded number is too short.")

    n_patient = n_str[-5:]
    n_facility = n_str[-10:-5]
    n_days = n_str[:-10] or "0"

    try:
        birth_year = int(suffix[:-1])
        sex = suffix[-1]
    except ValueError:
        raise ValueError("Invalid birth year or sex in Cor-ID suffix.")

    return {
        "n_days_since_first_jan_2024": int(n_days),
        "n_facility": int(n_facility),
        "n_patient": int(n_patient),
        "birth_year": birth_year,
        "sex": sex,
    }


async def create_corid(user: User, db: Session):
    birth_year_gender = f"{user.birth}{user.user_sex}"
    n_patient = user.user_index
    today = datetime.now().date()
    jan_first_2024 = datetime(2024, 1, 1).date()
    n_days_since_first_jan_2024 = (today - jan_first_2024).days
    n_days_str = transform_integer(n_days_since_first_jan_2024)
    n_facility_str = transform_integer(n_facility)
    n_patient_str = transform_integer(int(n_patient))
    cor_id = (
        to_base36(n_days_str, n_facility_str, n_patient_str) + "-" + birth_year_gender
    )
    user.cor_id = cor_id
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
