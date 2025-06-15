from fastapi import APIRouter, HTTPException,Request
import logging
import json
from pymodbus.client import AsyncModbusTcpClient
from pydantic import BaseModel, Field
from typing import Optional


# Конфигурация Modbus
MODBUS_IP = "91.203.25.12"
MODBUS_PORT = 502
BATTERY_ID = 225         # Основная батарея
INVERTER_ID = 100     # Инвертор
ESS_UNIT_ID = 227     # Система управления (ESS)

# Определение регистров Modbus
REGISTERS = {
    "soc": 266,            # % SoC (0.1%)
    "voltage": 259,        # Напряжение (x100)
    "current": 261,        # Ток (x10)
    "power": 258,          # Мощность (signed int16)
    "soh": 304,            # Состояние здоровья (0.1%)
    "inverter_power": 870  # Мощность инвертора (signed int32)
}

ESS_REGISTERS = {
    "switch_position": 33,   # Положение переключателя (режим работы)
    "temperature_alarm": 34,  # Температурная тревога
    "low_battery_alarm": 35,  # Тревога низкого заряда
    "overload_alarm": 36,     # Тревога перегрузки
    "ess_power_setpoint_l1": 37,  # Установка мощности ESS фаза 1
    "disable_charge": 38,    # Запрет на заряд
    "disable_feed": 39,      # Запрет на подачу в сеть
    "ess_power_setpoint_l2": 40,  # Установка мощности ESS фаза 2
    "ess_power_setpoint_l3": 41   # Установка мощности ESS фаза 3
}

# Модель данных для управления ESS
class EssModeControl(BaseModel):
    switch_position: int = Field(..., ge=1, le=4)

class EssFlagsControl(BaseModel):
    disable_charge: bool
    disable_feed: bool

class EssPowerControl(BaseModel):
    ess_power_setpoint_l1: Optional[int] = Field(None, ge=-32768, le=32767)
    ess_power_setpoint_l2: Optional[int] = Field(None, ge=-32768, le=32767)
    ess_power_setpoint_l3: Optional[int] = Field(None, ge=-32768, le=32767)
# Создание роутера FastAPI
router = APIRouter(prefix="/modbus", tags=["Modbus"])


# --- Клиент хранения ---
async def create_modbus_client(app):
    app.state.modbus_client = AsyncModbusTcpClient(host=MODBUS_IP, port=MODBUS_PORT)
    await app.state.modbus_client.connect()

async def close_modbus_client(app):
    await app.state.modbus_client.close()

# Функции декодирования
def decode_signed_16(value: int) -> int:
    return value - 0x10000 if value >= 0x8000 else value

def decode_signed_32(high: int, low: int) -> int:
    combined = (high << 16) | low
    return combined - 0x100000000 if combined >= 0x80000000 else combined

# Получение статуса батареи
@router.get("/battery_status")
async def get_battery_status(request: Request):
    try:
        client = request.app.state.modbus_client

        addresses = [REGISTERS[key] for key in REGISTERS if key != "inverter_power"]
        start = min(addresses)
        count = max(addresses) - start + 1

        result = await client.read_input_registers(start, count=count, slave=BATTERY_ID)
        if result.isError():
            raise HTTPException(status_code=500, detail="Ошибка чтения регистров батареи")

        raw = result.registers

        def get_value(name: str) -> int:
            return raw[REGISTERS[name] - start]

        return {
            "soc": get_value("soc") / 10,
            "voltage": get_value("voltage") / 100,
            "current": decode_signed_16(get_value("current")) / 10,
            "power": decode_signed_16(get_value("power")),
            "soh": get_value("soh") / 10
        }

    except Exception as e:
        logging.error("❗ Ошибка получения данных с батареи", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")

# Получение мощности инвертора
@router.get("/inverter_power")
async def get_inverter_power(request: Request):
    try:
        client = request.app.state.modbus_client

        address = REGISTERS["inverter_power"]
        result = await client.read_holding_registers(address, count=2, slave=INVERTER_ID)

        if result.isError():
            raise HTTPException(status_code=500, detail="Ошибка чтения регистра мощности инвертора")

        high, low = result.registers
        return {"inverter_power": decode_signed_32(high, low)}

    except Exception as e:
        logging.error("❗ Ошибка чтения мощности инвертора", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")

# Получение состояния ESS
@router.get("/ess_status")
async def get_ess_status(request: Request):
    try:
        client = request.app.state.modbus_client

        # Читаем все регистры с 33 по 41 за один запрос
        start_address = min(ESS_REGISTERS.values())
        count = max(ESS_REGISTERS.values()) - start_address + 1
        
        result = await client.read_holding_registers(start_address, count=count, slave=ESS_UNIT_ID)
        if result.isError():
            raise HTTPException(status_code=500, detail="Ошибка чтения регистров ESS")

        registers = result.registers
        
        # Функция для получения значения регистра по имени
        def get_ess_value(name: str) -> int:
            return registers[ESS_REGISTERS[name] - start_address]

        response = {
            "switch_position": get_ess_value("switch_position"),
            "disable_charge": get_ess_value("disable_charge"),
            "disable_feed": get_ess_value("disable_feed"),
            "temperature_alarm": get_ess_value("temperature_alarm"),
            "low_battery_alarm": get_ess_value("low_battery_alarm"),
            "overload_alarm": get_ess_value("overload_alarm"),
            "ess_power_setpoint_l1": decode_signed_16(get_ess_value("ess_power_setpoint_l1")),
            "ess_power_setpoint_l2": decode_signed_16(get_ess_value("ess_power_setpoint_l2")),
            "ess_power_setpoint_l3": decode_signed_16(get_ess_value("ess_power_setpoint_l3"))
        }

        logging.info(f"ESS Статус: {response}")

        return response

    except Exception as e:
        logging.error("❗ Ошибка чтения ESS регистров", exc_info=e)
        raise HTTPException(status_code=500, detail="Ошибка Modbus")

# Установка параметров ESS
@router.post("/ess_status/mode")
async def set_ess_mode(control: EssModeControl, request: Request):
    try:
        logging.info(f"📥 Установка режима ESS: {control.switch_position}")
        client = request.app.state.modbus_client
        
        await client.write_register(
            address=ESS_REGISTERS["switch_position"],
            value=control.switch_position,
            slave=ESS_UNIT_ID
        )
        return {"status": "ok"}
    except Exception as e:
        logging.error("❗ Ошибка установки режима ESS", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")

@router.post("/ess_status/flags")
async def set_ess_flags(control: EssFlagsControl, request: Request):
    try:
        logging.info(f"📥 Установка флагов ESS: charge={control.disable_charge}, feed={control.disable_feed}")
        client = request.app.state.modbus_client
        
        await client.write_register(
            address=ESS_REGISTERS["disable_charge"],
            value=1 if control.disable_charge else 0,
            slave=ESS_UNIT_ID
        )
        await client.write_register(
            address=ESS_REGISTERS["disable_feed"],
            value=1 if control.disable_feed else 0,
            slave=ESS_UNIT_ID
        )
        return {"status": "ok"}
    except Exception as e:
        logging.error("❗ Ошибка установки флагов ESS", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")

@router.post("/ess_status/power")
async def set_ess_power(control: EssPowerControl, request: Request):
    try:
        logging.info(f"📥 Установка мощности ESS: L1={control.ess_power_setpoint_l1}, L2={control.ess_power_setpoint_l2}, L3={control.ess_power_setpoint_l3}")
        client = request.app.state.modbus_client
        
        # Функция для безопасной записи значения
        async def write_power_register(address, value):
            if value is not None:
                reg_value = value if value >= 0 else 65536 + value
                await client.write_register(
                    address=address,
                    value=reg_value,
                    slave=ESS_UNIT_ID
                )
        
        await write_power_register(ESS_REGISTERS["ess_power_setpoint_l1"], control.ess_power_setpoint_l1)
        await write_power_register(ESS_REGISTERS["ess_power_setpoint_l2"], control.ess_power_setpoint_l2)
        await write_power_register(ESS_REGISTERS["ess_power_setpoint_l3"], control.ess_power_setpoint_l3)
        
        return {"status": "ok"}
    except Exception as e:
        logging.error("❗ Ошибка установки мощности ESS", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")