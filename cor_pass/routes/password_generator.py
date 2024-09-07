from fastapi import APIRouter, status
from cor_pass.schemas import PasswordGeneratorSettings, WordPasswordGeneratorSettings


from cor_pass.repository import password_generator as repository_password_generator


router = APIRouter(prefix="/password_generator", tags=["Password Generator"])


@router.post("/generate_password/", status_code=status.HTTP_201_CREATED)
async def generate_password_endpoint(settings: PasswordGeneratorSettings):
    """
    **Генератор пароля** \n

    """
    return {"password": repository_password_generator.generate_password(settings)}


@router.post("/generate_word_password/", status_code=status.HTTP_201_CREATED)
async def generate_word_password_endpoint(settings: WordPasswordGeneratorSettings):
    """
    **Генератор парольной фразы** \n

    """
    return {"password": repository_password_generator.generate_word_password(settings)}
