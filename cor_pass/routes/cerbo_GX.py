from fastapi import APIRouter, HTTPException
import logging
from pymodbus.client import AsyncModbusTcpClient

router = APIRouter(prefix="/modbus", tags=["Modbus"])

MODBUS_IP = "91.203.25.12"
MODBUS_PORT = 502
UNIT_ID_BATTERY = 225  # Pylontech
REGISTER_SOC = 266     # SoC 0.1%

@router.get("/battery_soc")
async def get_battery_soc():
    try:
        async with AsyncModbusTcpClient(host=MODBUS_IP, port=MODBUS_PORT) as client:
            await client.connect()
            result = await client.read_input_registers(REGISTER_SOC, count=1, slave=UNIT_ID_BATTERY)
            if result.isError():
                logging.error(f"❌ Ошибка чтения регистра: {result}")
                raise HTTPException(status_code=500, detail="Ошибка чтения регистра")
            soc = result.registers[0] / 10
            return {"soc": soc}
    except Exception as e:
        logging.error("❗ Произошла ошибка при получении SoC через Modbus", exc_info=e)
        raise HTTPException(status_code=500, detail="Ошибка связи с батареей")
