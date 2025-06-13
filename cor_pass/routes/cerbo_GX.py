from fastapi import APIRouter, HTTPException
import logging
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian


router = APIRouter(prefix="/modbus", tags=["Modbus"])

MODBUS_IP = "91.203.25.12"
MODBUS_PORT = 502
UNIT_ID = 225  # Pylontech battery

# Адреса регистров
REGISTERS = {
    "soc": 266,        # % SoC (0.1%)
    "voltage": 259,    # Battery Voltage (V x100)
    "current": 261,    # Battery Current (A x10)
    "power": 258,      # Power (Watts)
    "soh": 267         # State of Health (0.1%)
}

def decode_signed_16(value: int) -> int:
    if value >= 0x8000:
        return value - 0x10000
    return value

@router.get("/battery_status")
async def get_battery_status():
    try:
        async with AsyncModbusTcpClient(host=MODBUS_IP, port=MODBUS_PORT) as client:
            await client.connect()

            start_address = min(REGISTERS.values())
            count = max(REGISTERS.values()) - start_address + 1

            result = await client.read_input_registers(start_address, count=count, slave=UNIT_ID)
            if result.isError():
                logging.error(f"❌ Ошибка чтения Modbus: {result}")
                raise HTTPException(status_code=500, detail="Ошибка чтения регистров батареи")

            raw = result.registers

            raw_current = raw[REGISTERS["current"] - start_address]
            current = decode_signed_16(raw_current) / 10

            status = {
                "soc": raw[REGISTERS["soc"] - start_address] / 10,
                "voltage": raw[REGISTERS["voltage"] - start_address] / 100,
                "current": current,
                "power": raw[REGISTERS["power"] - start_address],
                "soh": raw[REGISTERS["soh"] - start_address] / 10,
            }

            return status

    except Exception as e:
        logging.error("❗ Ошибка получения данных с батареи", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")