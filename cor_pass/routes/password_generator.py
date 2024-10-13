from fastapi import APIRouter, status
from cor_pass.schemas import PasswordGeneratorSettings, WordPasswordGeneratorSettings

from prometheus_client import start_http_server, Summary
from prometheus_client import Counter, Histogram
from prometheus_client import generate_latest
from starlette.responses import Response

from cor_pass.repository import password_generator as repository_password_generator

# Счетчик запросов на генерацию пароля
password_generator_requests_total = Counter(
    "password_generator_requests_total", "Total number of password generation requests"
)

# Гистограмма времени обработки запросов на генерацию пароля
password_generator_request_duration = Histogram(
    "password_generator_request_duration_seconds",
    "Duration of password generation requests in seconds",
)

# Счетчик запросов на генерацию парольной фразы
word_password_generator_requests_total = Counter(
    "word_password_generator_requests_total",
    "Total number of word password generation requests",
)

# Гистограмма времени обработки запросов на генерацию парольной фразы
word_password_generator_request_duration = Histogram(
    "word_password_generator_request_duration_seconds",
    "Duration of word password generation requests in seconds",
)


router = APIRouter(prefix="/password_generator", tags=["Password Generator"])


@router.post("/generate_password/", status_code=status.HTTP_201_CREATED)
async def generate_password_endpoint(settings: PasswordGeneratorSettings):
    """
    **Генератор пароля** \n
    """
    with password_generator_request_duration.time():
        password_generator_requests_total.inc()
        return {"password": repository_password_generator.generate_password(settings)}


@router.post("/generate_word_password/", status_code=status.HTTP_201_CREATED)
async def generate_word_password_endpoint(settings: WordPasswordGeneratorSettings):
    """
    **Генератор парольной фразы** \n
    """
    with word_password_generator_request_duration.time():
        word_password_generator_requests_total.inc()
        return {
            "password": repository_password_generator.generate_word_password(settings)
        }
