import os
import shutil
import logging
import subprocess
from contextlib import suppress

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DICOM_DIR = "/app/dicom_users_data"

def kill_processes_using_path(path: str):
    """Закрывает все процессы, которые используют файлы или папки внутри path"""
    try:
        # Получаем PID процессов через fuser
        result = subprocess.run(
            ["fuser", "-m", "-k", path],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.info(f"Процессы, использующие {path}, завершены: {result.stdout.strip()}")
        else:
            logger.debug(f"fuser вернул: {result.stderr.strip()}")
    except FileNotFoundError:
        logger.warning("fuser не найден, пропускаем завершение процессов")
    except Exception as e:
        logger.warning(f"Не удалось завершить процессы для {path}: {e}")

def safe_delete_dir(path: str):
    """Удаляет директорию и все содержимое безопасно"""
    if not os.path.exists(path):
        logger.info(f"Папка не существует: {path}")
        return

    # Закрываем процессы, которые держат файлы в папке
    kill_processes_using_path(path)

    # Пробуем размонтировать, если это CIFS-шара
    with suppress(Exception):
        subprocess.run(["umount", "-l", path], check=False)

    # Удаляем все файлы и подпапки
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            file_path = os.path.join(root, name)
            with suppress(Exception):
                os.remove(file_path)
        for name in dirs:
            dir_path = os.path.join(root, name)
            with suppress(Exception):
                shutil.rmtree(dir_path, ignore_errors=True)

    # Удаляем саму корневую папку
    with suppress(Exception):
        shutil.rmtree(path, ignore_errors=True)

    # Создаем чистую пустую папку заново
    os.makedirs(path, exist_ok=True)
    logger.info(f"Папка очищена и готова к использованию: {path}")

def main():
    logger.info("Начинаем безопасную очистку dicom_users_data")
    safe_delete_dir(DICOM_DIR)
    logger.info("Очистка завершена")

if __name__ == "__main__":
    main()