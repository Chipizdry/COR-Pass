from fastapi import APIRouter, HTTPException
import logging
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian



router = APIRouter(prefix="/modbus", tags=["Modbus"])

MODBUS_IP = "91.203.25.12"
MODBUS_PORT = 502
UNIT_ID = 225 
INVERTER_ID =100

REGISTERS = {
    "soc": 266,            # % SoC (0.1%)
    "voltage": 259,        # Battery Voltage (V x100)
    "current": 261,        # Battery Current (A x10)
    "power": 258,          # Power (Watts, signed int16)
    "soh": 304,            # State of Health (0.1%)
    "inverter_power": 870  # /Dc/InverterCharger/Power (signed int32)
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