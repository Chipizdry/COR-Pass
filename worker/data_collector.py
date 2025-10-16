from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import HTTPException
from loguru import logger
from pymodbus.client import AsyncModbusTcpClient
from worker.modbus_client import (
    BATTERY_ID,
    INVERTER_ID,
    ESS_UNIT_ID,
    SOLAR_CHARGER_SLAVE_IDS,
    REGISTERS,
    decode_signed_16,
    decode_signed_32,
    register_modbus_error, 
   
)

async def collect_battery_data(
    modbus_client: AsyncModbusTcpClient, transaction_id: UUID
) -> Dict[str, Any]:
    """Собирает данные с батареи по Modbus."""
    try:
        addresses = [REGISTERS[key] for key in REGISTERS]
        start = min(addresses)
        count = max(addresses) - start + 1

        result = await modbus_client.read_input_registers(
            start, count=count, slave=BATTERY_ID
        )
        if result.isError():
            logger.error(
                f"[{transaction_id}] Modbus error reading battery registers.",
                exc_info=True,
            )
            raise ConnectionError("Modbus error: Failed to read battery registers")

        raw = result.registers

        def get_value(name: str) -> int:
            return raw[REGISTERS[name] - start]

        voltage = get_value("voltage") / 100
        current = decode_signed_16(get_value("current")) / 10
        general_battery_power = round(voltage * current, 2)

        return {
            "battery_voltage": voltage,
            "battery_current": current,
            "battery_soc": get_value("soc") / 10,
            "battery_temperature": get_value("temperature") / 10,
            "battery_power_reg": decode_signed_16(get_value("power")),
            "battery_soh": get_value("soh") / 10,
            "general_battery_power": general_battery_power,
        }

    except Exception as e:
        register_modbus_error() 
        logger.error(
            f"[{transaction_id}] Error in collect_battery_data: {e}", exc_info=True
        )
        raise

async def collect_inverter_power_data(
    modbus_client: AsyncModbusTcpClient, transaction_id: UUID 
) -> Dict[str, Any]:
    """Собирает данные о мощности инвертора."""
    try:
        slave = INVERTER_ID
        reg_map = {
            "dc_power": 870,
            "ac_output_l1": 878,
            "ac_output_l2": 880,
            "ac_output_l3": 882,
        }
        result_values = {}

        for name, addr in reg_map.items():
            res = await modbus_client.read_holding_registers(
                address=addr, count=2, slave=slave
            )
            if res.isError():
                logger.error(
                    f"[{transaction_id}] Modbus error reading inverter registers {addr}-{addr+1}.",
                    exc_info=True,
                )
                raise ConnectionError(
                    f"Modbus error: Failed to read inverter registers {addr}-{addr+1}"
                )
            value = decode_signed_32(res.registers[0], res.registers[1])
            result_values[name] = value

        total_ac_output = round(
            result_values["ac_output_l1"]
            + result_values["ac_output_l2"]
            + result_values["ac_output_l3"],
            2,
        )

        return {
            "inverter_dc_power": result_values["dc_power"],
            "inverter_ac_output_l1": result_values["ac_output_l1"],
            "inverter_ac_output_l2": result_values["ac_output_l2"],
            "inverter_ac_output_l3": result_values["ac_output_l3"],
            "inverter_total_ac_output": total_ac_output,
        }

    except Exception as e:
        register_modbus_error()
        logger.error(
            f"[{transaction_id}] Error in collect_inverter_power_data: {e}",
            exc_info=True,
        )
        raise


async def collect_ess_ac_data(
    modbus_client: AsyncModbusTcpClient, transaction_id: UUID 
) -> Dict[str, Any]:
    """Собирает AC-данные с ESS."""
    try:
        slave = ESS_UNIT_ID
        registers_map = {
            3: "input_voltage_l1", 4: "input_voltage_l2", 5: "input_voltage_l3",
            6: "input_current_l1", 7: "input_current_l2", 8: "input_current_l3",
            9: "input_frequency_l1", 10: "input_frequency_l2", 11: "input_frequency_l3",
            12: "input_power_l1", 13: "input_power_l2", 14: "input_power_l3",
            15: "output_voltage_l1", 16: "output_voltage_l2", 17: "output_voltage_l3",
            18: "output_current_l1", 19: "output_current_l2", 20: "output_current_l3",
        }
        start = min(registers_map.keys())
        count = max(registers_map.keys()) - start + 1

        result = await modbus_client.read_input_registers(
            start, count=count, slave=slave
        )
        if result.isError():
            logger.error(
                f"[{transaction_id}] Modbus error reading ESS AC registers.",
                exc_info=True,
            )
            raise ConnectionError("Modbus error: Failed to read ESS AC registers")

        raw = result.registers
        collected_values = {}
        for reg_address, reg_name in registers_map.items():
            value = raw[reg_address - start]
            if "voltage" in reg_name:
                collected_values[reg_name] = round(value / 10.0, 2)
            elif "current" in reg_name:
                collected_values[reg_name] = round(decode_signed_16(value) / 10.0, 2)
            elif "frequency" in reg_name:
                collected_values[reg_name] = round(decode_signed_16(value) / 100.0, 2)
            elif "power" in reg_name:
                collected_values[reg_name] = round(decode_signed_16(value) * 10, 2)
            else:
                collected_values[reg_name] = value

        total_input_power = round(
            collected_values["input_power_l1"]
            + collected_values["input_power_l2"]
            + collected_values["input_power_l3"],
            2,
        )
        collected_values["ess_total_input_power"] = total_input_power

        return collected_values

    except Exception as e:
        register_modbus_error()
        logger.error(
            f"[{transaction_id}] Error in collect_ess_ac_data: {e}", exc_info=True
        )
        raise

# new
async def get_solarchargers_current_sum(modbus_client: AsyncModbusTcpClient, transaction_id: UUID
) -> Dict[str, Any]:
    """
    Чтение регистров 3730 с MPPT для всех UID и суммирование их значений
    """
    try:
        slave_ids = list(range(1, 14)) + [100]
        results = {}
        total_power = 0  

        for slave in slave_ids:
            try:
                res = await modbus_client.read_input_registers(address=3730, count=1, slave=slave)
                if res.isError() or not hasattr(res, "registers"):
                    results[f"charger_{slave}"] = None
                    logger.warning(f"⚠️ Ошибка чтения регистра 3730 у slave {slave}")
                else:
                    value = res.registers[0]
                    results[f"charger_{slave}"] = value
                    total_power += value

            except Exception as e:
                logger.warning(
                    f"[{transaction_id}] Exception while reading slave {slave} data: {e}",
                    exc_info=True,
                    extra={"slave_id": slave},
                )

        return {"solar_total_pv_power": total_power}

    except Exception as e:
        register_modbus_error()
        logger.error(
            f"[{transaction_id}] Overall error during MPPT polling, Общая ошибка при опросе регистров 3730: {e}", exc_info=True
        )
        raise


async def get_battery_status(modbus_client: AsyncModbusTcpClient, transaction_id: UUID) -> Dict[str, Any]: 
    """Получает статус батареи (SOC) по Modbus."""
    try:
        addresses = [REGISTERS[key] for key in REGISTERS]
        start = min(addresses)
        count = max(addresses) - start + 1
        result = await modbus_client.read_input_registers(start, count=count, slave=BATTERY_ID)
        if result.isError():
            raise HTTPException(status_code=500, detail="Ошибка чтения регистров батареи")
        raw = result.registers
        def get_value(name: str) -> int:
            return raw[REGISTERS[name] - start]
        return {"soc": get_value("soc") / 10}
    except Exception as e:
        register_modbus_error()
        logger.error("❗️ Ошибка получения данных с батареи", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")


async def read_grid_feed_w(modbus_client: AsyncModbusTcpClient) -> Optional[int]: 
    """Чтение текущего значения AC Power Setpoint Fine."""
    try:
        result = await modbus_client.read_holding_registers(address=2703, count=1, slave=INVERTER_ID)
        if result.isError():
            logger.error(f"Ошибка чтения регистра 2703: {result}")
            return None
        register_value = result.registers[0]
        if register_value > 32767:
            actual_value = register_value - (1 << 16)
        else:
            actual_value = register_value
        actual_value_watts = actual_value * 100
        return actual_value_watts
    except Exception as e:
        logger.error(f"Ошибка при чтении AC Power Setpoint Fine: {e}", exc_info=True)
        return None

async def read_vebus_soc(modbus_client: AsyncModbusTcpClient) -> Optional[int]: 
    """Чтение текущего значения VE.Bus SoC."""
    try:
        result = await modbus_client.read_holding_registers(address=2901, count=1, slave=INVERTER_ID)
        if result.isError():
            logger.error(f"Ошибка чтения регистра 2901: {result}")
            return None
        register_value = result.registers[0]
        actual_value_percent = register_value / 10
        return int(actual_value_percent)
    except Exception as e:
        logger.error(f"Ошибка при чтении VE.Bus SoC: {e}", exc_info=True)
        return None

async def read_dvcc_max_charge_current(modbus_client: AsyncModbusTcpClient) -> Optional[int]: 
    """Чтение текущего значения DVCC max charge current."""
    try:
        result = await modbus_client.read_holding_registers(address=2705, count=1, slave=INVERTER_ID)
        if result.isError():
            logger.error(f"Ошибка чтения регистра 2705: {result}")
            return None
        register_value = result.registers[0]
        if register_value > 32767:
            actual_value = register_value - (1 << 16)
        else:
            actual_value = register_value
        return actual_value
    except Exception as e:
        logger.error(f"Ошибка при чтении DVCC max charge current: {e}", exc_info=True)
        return None

async def send_grid_feed_w_command(modbus_client: AsyncModbusTcpClient, grid_feed_w: int): 
    """Отправка команды для установки AC Power Setpoint Fine."""
    if modbus_client is None:
        return {"status": "error", "message": "Modbus client not available"}
    try:
        slave = INVERTER_ID
        register_value = int(grid_feed_w / 100)
        if register_value < 0:
            register_value = (1 << 16) + register_value
        if not (0 <= register_value <= 65535):
            raise HTTPException(status_code=400, detail="Значение выходит за допустимые пределы")
        await modbus_client.write_register(
            address=2703,
            value=register_value,
            slave=slave
        )
        logger.debug(f"✅ grid_feed_w: {register_value} W (регистр 2703 = {register_value})")
        return {"status": "ok", "value": grid_feed_w}
    except Exception as e:
        logger.error(
            f" Unhandled error during periodic data collection: {e}",
            exc_info=True,
        )
        raise