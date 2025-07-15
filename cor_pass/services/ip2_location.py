import os
import IP2Location
import logging
from loguru import logger

# Путь к файлу базы данных IP2Location
# Убедись, что этот файл (например, IP2LOCATION-LITE-DB3.BIN) находится в указанной директории
# Рекомендуется использовать полный путь, если приложение запускается из разных мест.
# Например, можно положить файл в папку 'data' в корне проекта.
# os.path.dirname(os.path.abspath(__file__)) + "/../data/IP2LOCATION-LITE-DB3.BIN"
IP2LOCATION_DB_PATH = os.path.join("IP2LOCATION-LITE-DB3.BIN")

# Глобальная переменная для базы данных IP2Location
ip2location_database = None

def initialize_ip2location():
    """
    Инициализирует базу данных IP2Location.
    Вызывается при запуске приложения.
    """
    global ip2location_database
    if not os.path.exists(IP2LOCATION_DB_PATH):
        logger.error(f"IP2Location database file not found at: {IP2LOCATION_DB_PATH}")
        # Можно выбросить исключение или просто не инициализировать,
        # если геолокация не является критичной функцией.
        ip2location_database = None # Убедимся, что он None, если файл не найден
        return

    try:
        # Можно использовать "SHARED_MEMORY" для ускорения, если RAM позволяет.
        # database = IP2Location.IP2Location(IP2LOCATION_DB_PATH, "SHARED_MEMORY")
        ip2location_database = IP2Location.IP2Location(IP2LOCATION_DB_PATH)
        logger.info("IP2Location database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize IP2Location database: {e}")
        ip2location_database = None

def get_ip_geolocation(ip_address: str):
    """
    Получает информацию о геолокации по IP-адресу.
    """
    if ip2location_database is None:
        logger.warning("IP2Location database not initialized. Cannot get geolocation.")
        return {
            "country_code": None,
            "country_name": None,
            "region_name": None,
            "city_name": None
        }
    try:
        rec = ip2location_database.get_all(ip_address)
        return {
            "country_code": rec.country_short,
            "country_name": rec.country_long,
            "region_name": rec.region,
            "city_name": rec.city
        }
    except Exception as e:
        logger.error(f"Error getting geolocation for IP {ip_address}: {e}")
        return {
            "country_code": None,
            "country_name": None,
            "region_name": None,
            "city_name": None
        }

