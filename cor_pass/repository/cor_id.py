from sqlalchemy.orm import Session
import datetime
from cor_pass.database.models import User
from cor_pass.schemas import CreateCorIdModel
from cor_pass.services.logger import logger


async def create_cor_id(body: CreateCorIdModel, db: Session, user: User):

    creation_time = datetime.datetime.now()
    print(creation_time)
    cor_id = f"{creation_time.strftime('%d%m%Y')}{body.medical_institution_code}{body.patient_number}-{body.patient_birth}{body.patient_sex}"
    print(cor_id)
    user.cor_id = cor_id
    try:
        db.commit()
        logger.debug("Cor_id is created")
    except Exception as e:
        db.rollback()
        raise e
    return cor_id


async def get_cor_id(user: User, db: Session):
    cor_id = user.cor_id
    print(cor_id)
    if cor_id:
        return cor_id
    else:
        return None
