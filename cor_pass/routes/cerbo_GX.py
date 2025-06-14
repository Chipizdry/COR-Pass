from fastapi import APIRouter, HTTPException
import logging
import json
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
from pydantic import BaseModel
from typing import Optional


class EssControl(BaseModel):
    switch_position: Optional[int] = None  # 1..4
    disable_charge: Optional[bool] = None  # True/False
    disable_feed: Optional[bool] = None    # True/False

router = APIRouter(prefix="/modbus", tags=["Modbus"])

MODBUS_IP = "91.203.25.12"
MODBUS_PORT = 502
UNIT_ID = 225 
INVERTER_ID =100
ESS_UNIT_ID = 227

REGISTERS = {
    "soc": 266,            # % SoC (0.1%)
    "voltage": 259,        # Battery Voltage (V x100)
    "current": 261,        # Battery Current (A x10)
    "power": 258,          # Power (Watts, signed int16)
    "soh": 304,            # State of Health (0.1%)
    "inverter_power": 870  # /Dc/InverterCharger/Power (signed int32)
}

ESS_REGISTERS = {
    "disable_charge": 38,   # /Hub4/DisableCharge
    "disable_feed": 39,      # /Hub4/DisableFeedIn
     "switch_position": 33     # Switch Position (режим)
}



def decode_signed_16(value: int) -> int:
    if value >= 0x8000:
        return value - 0x10000
    return value

def decode_signed_32(high: int, low: int) -> int:
    combined = (high << 16) | low
    if combined >= 0x80000000:
        combined -= 0x100000000
    return combined

@router.get("/battery_status")
async def get_battery_status():
    try:
        async with AsyncModbusTcpClient(host=MODBUS_IP, port=MODBUS_PORT) as client:
            await client.connect()

            # Читаем только нужные регистры (кроме 870)
            regs_to_read = [REGISTERS[key] for key in REGISTERS if key != "inverter_power"]
            start_address = min(regs_to_read)
            end_address = max(regs_to_read)
            count = end_address - start_address + 1

            result = await client.read_input_registers(start_address, count=count, slave=UNIT_ID)
            if result.isError():
                raise HTTPException(status_code=500, detail="Ошибка чтения регистров батареи")

            raw = result.registers

            def r(name):
                return raw[REGISTERS[name] - start_address]

            status = {
                "soc": r("soc") / 10,
                "voltage": r("voltage") / 100,
                "current": decode_signed_16(r("current")) / 10,
                "power": decode_signed_16(r("power")),
                "soh": r("soh") / 10
            }

            return status

    except Exception as e:
        logging.error("❗ Ошибка получения данных с батареи", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")





@router.get("/inverter_power")
async def get_inverter_power():
    try:
        async with AsyncModbusTcpClient(host=MODBUS_IP, port=MODBUS_PORT) as client:
            await client.connect()

            address = REGISTERS["inverter_power"]
            # Используем чтение holding registers вместо input registers
            result = await client.read_holding_registers(address, count=2, slave=INVERTER_ID)
            
            if result.isError():
                logging.error(f"Ошибка чтения регистра {address}, результат: {result}")
                raise HTTPException(status_code=500, detail="Ошибка чтения регистра мощности инвертора")

            high, low = result.registers
            inverter_power = decode_signed_32(high, low)

            return {"inverter_power": inverter_power}

    except Exception as e:
        logging.error("❗ Ошибка чтения мощности инвертора", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")


@router.get("/ess_status")
async def get_ess_status():
    try:
        async with AsyncModbusTcpClient(host=MODBUS_IP, port=MODBUS_PORT) as client:
            await client.connect()

            # Чтение switch_position (адрес 33)
            res1 = await client.read_holding_registers(ESS_REGISTERS["switch_position"], count=1, slave=ESS_UNIT_ID)
            if res1.isError():
                raise HTTPException(status_code=500, detail="Ошибка чтения switch_position")

            # Чтение disable_charge и disable_feed (адреса 38 и 39)
            res2 = await client.read_holding_registers(ESS_REGISTERS["disable_charge"], count=2, slave=ESS_UNIT_ID)
            if res2.isError():
                raise HTTPException(status_code=500, detail="Ошибка чтения disable_*")

            switch_position = res1.registers[0]
            disable_charge = res2.registers[0]
            disable_feed = res2.registers[1]

            # Вывод в лог
            logging.info(f"ESS Статус: disable_charge={disable_charge}, disable_feed={disable_feed}, switch_position={switch_position}")

            return {
                "disable_charge": disable_charge,
                "disable_feed": disable_feed,
                "switch_position": switch_position
            }

    except Exception as e:
        logging.error("❗ Ошибка чтения ESS регистров", exc_info=e)
        raise HTTPException(status_code=500, detail="Ошибка Modbus")



@router.post("/ess_status")
async def set_ess_flags(flags: EssControl):
    try:
        # Логируем полученные данные
        logging.info("📥 Получен POST /ess_status: %s", json.dumps(flags.dict(), indent=2, ensure_ascii=False))

        async with AsyncModbusTcpClient(host=MODBUS_IP, port=MODBUS_PORT) as client:
            await client.connect()

            # Установка флага disable_charge
            if flags.disable_charge is not None:
                await client.write_register(
                    address=ESS_REGISTERS["disable_charge"],
                    value=1 if flags.disable_charge else 0,
                    slave=ESS_UNIT_ID
                )

            # Установка флага disable_feed
            if flags.disable_feed is not None:
                await client.write_register(
                    address=ESS_REGISTERS["disable_feed"],
                    value=1 if flags.disable_feed else 0,
                    slave=ESS_UNIT_ID
                )

            # Установка switch_position (режима работы: /Mode)
            if flags.switch_position is not None:
                await client.write_register(
                    address=ESS_REGISTERS["switch_position"],
                    value=flags.switch_position,
                    slave=ESS_UNIT_ID
                )

            return {"status": "ok"}

    except Exception as e:
        logging.error("❗ Ошибка установки ESS флагов", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")