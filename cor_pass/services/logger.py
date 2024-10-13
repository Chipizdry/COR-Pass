from loguru import logger
import sys
from cor_pass.config.config import settings

logger_level = "DEBUG" if settings.debug else "INFO"

logger.remove()

logger.add(
    "logs/application.log",  # Путь к файлу логов
    rotation="500 MB",  # Размер файла перед ротацией
    retention="10 days",  # Хранение логов в течение 10 дней
    compression="zip",  # Сжатие старых логов
    level=logger_level,  # Уровень логирования
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)


logger.add(
    sys.stdout,  # Вывод в консоль
    level=logger_level,  # Уровень логирования
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)
