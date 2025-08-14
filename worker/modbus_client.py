from typing import Optional
from loguru import logger
from pymodbus.client import AsyncModbusTcpClient

error_count = 0

_modbus_client_instance: Optional[AsyncModbusTcpClient] = None

# Конфигурация Modbus
MODBUS_IP = "91.203.25.12"
MODBUS_PORT = 502
BATTERY_ID = 225
INVERTER_ID = 100
ESS_UNIT_ID = 227
SOLAR_CHARGER_SLAVE_IDS = list(range(1, 14)) + [100]

# Определение регистров Modbus 
REGISTERS = {
    "soc": 266,
    "voltage": 259,
    "current": 261,
    "temperature": 262,
    "power": 258,
    "soh": 304,
}

INVERTER_REGISTERS = {
    "inverter_power": 870,
    "output_power_l1": 878,
    "output_power_l2": 880,
    "output_power_l3": 882,
}

ESS_REGISTERS_MODE = {
    "switch_position": 33,
}

ESS_REGISTERS_FLAGS = {
    "disable_charge": 38,
    "disable_feed": 39,
    "disable_pv_inverter": 56,
    "do_not_feed_in_ov": 65,
    "setpoints_as_limit": 71,
    "ov_offset_mode": 72,
    "prefer_renewable": 102,
}

ESS_REGISTERS_POWER = {
    "ess_power_setpoint_l1": 96,
    "ess_power_setpoint_l2": 98,
    "ess_power_setpoint_l3": 100,
    "max_feed_in_l1": 66,
    "max_feed_in_l2": 67,
    "max_feed_in_l3": 68,
}

ESS_REGISTERS_ALARMS = {
    "temperature_alarm": 34,
    "low_battery_alarm": 35,
    "overload_alarm": 36,
    "temp_sensor_alarm": 42,
    "voltage_sensor_alarm": 43,
    "grid_lost": 64,
}


async def create_modbus_client_singleton() -> Optional[AsyncModbusTcpClient]:
    """
    Создаёт и подключает Modbus-клиент.
    Использует глобальную переменную для хранения клиента.
    """
    global _modbus_client_instance
    try:
        if _modbus_client_instance and _modbus_client_instance.connected:
            logger.info("🔌 Modbus клиент уже подключен. Переиспользование.")
            return _modbus_client_instance
        if _modbus_client_instance:
            try:
                await _modbus_client_instance.close()
                logger.info("🔌 Старый Modbus клиент закрыт перед переподключением.")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при закрытии старого Modbus клиента: {e}")

        logger.info("🔄 Попытка подключения к Modbus серверу...")
        new_client = AsyncModbusTcpClient(host=MODBUS_IP, port=MODBUS_PORT, timeout=5)
        await new_client.connect()

        if not new_client.connected:
            logger.error("❌ Не удалось подключиться к Modbus серверу.")
            _modbus_client_instance = None  
        else:
            logger.info("✅ Подключение к Modbus серверу установлено.")
            _modbus_client_instance = new_client
        
        return _modbus_client_instance
    except Exception as e:
        logger.exception("❗ Ошибка при создании/подключении Modbus клиента", exc_info=e)
        _modbus_client_instance = None  
        return None 


async def get_modbus_client_singleton() -> Optional[AsyncModbusTcpClient]:
    """
    Возвращает текущий Modbus клиент. Если клиент не создан или не подключен,
    попытается его создать/переподключить.
    """
    global _modbus_client_instance
    if _modbus_client_instance and _modbus_client_instance.connected:
        return _modbus_client_instance
    
    logger.warning("🔄 Modbus клиент не подключен. Попытка пересоздания/переподключения.")
    return await create_modbus_client_singleton()


def register_modbus_error():
    """Регистрирует ошибку Modbus и инкрементирует счётчик."""
    global error_count
    error_count += 1
    logger.warning(f"❗ Modbus ошибка #{error_count}")


def decode_signed_16(value: int) -> int:
    """Декодирует 16-битное знаковое целое число."""
    return value - 0x10000 if value >= 0x8000 else value


def decode_signed_32(high: int, low: int) -> int:
    """Декодирует 32-битное знаковое целое число из двух 16-битных регистров."""
    combined = (high << 16) | low
    return combined - 0x100000000 if combined >= 0x80000000 else combined