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
    "temperature": 262, 
    "power": 258,          # Мощность (signed int16)
    "soh": 304,            # Состояние здоровья (0.1%)
}

INVERTER_REGISTERS = {
    "inverter_power": 870,      # Мощность инвертора/зарядного устройства (DC)
    "output_power_l1": 878,     # Мощность на выходе инвертора (L1)
    "output_power_l2": 880,     # Мощность на выходе инвертора (L2)
    "output_power_l3": 882      # Мощность на выходе инвертора (L3)
}

ESS_REGISTERS = {
    # Базовые регистры
    "switch_position": 33,        # Положение переключателя
    "temperature_alarm": 34,      # Температурная тревога
    "low_battery_alarm": 35,      # Тревога низкого заряда
    "overload_alarm": 36,         # Тревога перегрузки
    "disable_charge": 38,         # Запрет на заряд (0/1)
    "disable_feed": 39,           # Запрет на подачу в сеть (0/1)
    
    # 32-битные регистры мощности
    "ess_power_setpoint_l1": 96,  # Установка мощности фаза 1 (int32)
    "ess_power_setpoint_l2": 98,  # Установка мощности фаза 2 (int32)
    "ess_power_setpoint_l3": 100, # Установка мощности фаза 3 (int32)
    
    # Дополнительные параметры
    "disable_ov_feed": 65,        # Запрет фид-ина при перегрузке
    "ov_feed_limit_l1": 66,       # Лимит мощности для L1
    "ov_feed_limit_l2": 67,       # Лимит мощности для L2
    "ov_feed_limit_l3": 68,       # Лимит мощности для L3
    "setpoints_as_limit": 71,     # Использовать setpoints как лимит
    "ov_offset_mode": 72          # Режим оффсета (0=1V, 1=100mV)
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
    "ess_power_setpoint_l1": 96,  # 32-bit
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
# Модель данных для управления ESS

class VebusSOCControl(BaseModel):
    soc_threshold: int 

class EssAdvancedControl(BaseModel):
    ac_power_setpoint_fine: int = Field(..., ge=-100000, le=100000)

class GridLimitUpdate(BaseModel):
    enabled: bool  # True → 1, False → 0

class EssModeControl(BaseModel):
    switch_position: int = Field(..., ge=1, le=4)



class EssPowerControl(BaseModel):
    ess_power_setpoint_l1: Optional[int] = Field(None, ge=-32768, le=32767)
    ess_power_setpoint_l2: Optional[int] = Field(None, ge=-32768, le=32767)
    ess_power_setpoint_l3: Optional[int] = Field(None, ge=-32768, le=32767)

class EssFeedInControl(BaseModel):
    max_feed_in_l1: Optional[int] = None
    max_feed_in_l2: Optional[int] = None
    max_feed_in_l3: Optional[int] = None

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

        addresses = [REGISTERS[key] for key in REGISTERS]
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
            "temperature":get_value("temperature") / 10,
            "power": decode_signed_16(get_value("power")),
            "soh": get_value("soh") / 10
        }

    except Exception as e:
        logging.error("❗ Ошибка получения данных с батареи", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")

@router.get("/inverter_power_status")
async def get_inverter_power_status(request: Request):
    """
    Получает данные по мощности инвертора/зарядного устройства:
    - Общая мощность DC
    - Мощность на выходе по фазам (AC)
    Исключает чтение input_power_l1/l2/l3 (регистры 872, 874, 876)
    """
    try:
        client = request.app.state.modbus_client
        slave = INVERTER_ID
        reg_map = {
            "dc_power": 870,
            "ac_output_l1": 878,
            "ac_output_l2": 880,
            "ac_output_l3": 882,
        }

        result = {}

        # Чтение всех нужных регистров по отдельности
        for name, addr in reg_map.items():
            res = await client.read_holding_registers(address=addr, count=2, slave=slave)
            if res.isError():
                raise HTTPException(status_code=500, detail=f"Ошибка чтения регистров {addr}-{addr+1}")
            value = decode_signed_32(res.registers[0], res.registers[1])
            result[name] = value
           # logging.info(f"✅ {name}: {value} Вт")

        return {
            "dc_power": result["dc_power"],
            "ac_output": {
                "l1": result["ac_output_l1"],
                "l2": result["ac_output_l2"],
                "l3": result["ac_output_l3"],
                "total": result["ac_output_l1"] + result["ac_output_l2"] + result["ac_output_l3"]
            }
        }

    except Exception as e:
        logging.error("❗ Ошибка получения данных мощности инвертора", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")

@router.get("/ess_ac_status")
async def get_ess_ac_status(request: Request):
    """
    Reads AC input and output parameters from the ESS unit:
    - Voltages (L1-L3)
    - Currents (L1-L3)
    - Frequencies (L1-L3)
    - Power (L1-L3)
    """
    try:
        client = request.app.state.modbus_client
        slave = ESS_UNIT_ID
        
        # Define all registers to read (address: description)
        registers = {
            # Input parameters
            3: "input_voltage_l1",
            4: "input_voltage_l2",
            5: "input_voltage_l3",
            6: "input_current_l1",
            7: "input_current_l2",
            8: "input_current_l3",
            9: "input_frequency_l1",
            10: "input_frequency_l2",
            11: "input_frequency_l3",
            12: "input_power_l1",
            13: "input_power_l2",
            14: "input_power_l3",
            
            # Output parameters
            15: "output_voltage_l1",
            16: "output_voltage_l2",
            17: "output_voltage_l3",
            18: "output_current_l1",
            19: "output_current_l2",
            20: "output_current_l3"
        }

        # Calculate read range
        start = min(registers.keys())
        count = max(registers.keys()) - start + 1

        # Read all registers in one operation
        result = await client.read_input_registers(start, count=count, slave=slave)
        if result.isError():
            raise HTTPException(status_code=500, detail="Ошибка чтения AC регистров ESS")

        raw = result.registers

        def get_value(reg_name: str):
            reg_address = next(k for k, v in registers.items() if v == reg_name)
            value = raw[reg_address - start]
            
            # Apply appropriate scaling and decoding
            if "voltage" in reg_name:
                return value / 10.0  # uint16 scaled by 10
            elif "current" in reg_name:
                return decode_signed_16(value) / 10.0  # int16 scaled by 10
            elif "frequency" in reg_name:
                return decode_signed_16(value) / 100.0  # int16 scaled by 100
            elif "power" in reg_name:
                return decode_signed_16(value) * 10  # int16 scaled by 0.1
            return value

        # Build response structure
        response = {
            "input": {
                "voltages": {
                    "l1": get_value("input_voltage_l1"),
                    "l2": get_value("input_voltage_l2"),
                    "l3": get_value("input_voltage_l3")
                },
                "currents": {
                    "l1": get_value("input_current_l1"),
                    "l2": get_value("input_current_l2"),
                    "l3": get_value("input_current_l3")
                },
                "frequencies": {
                    "l1": get_value("input_frequency_l1"),
                    "l2": get_value("input_frequency_l2"),
                    "l3": get_value("input_frequency_l3")
                },
                "powers": {
                    "l1": get_value("input_power_l1"),
                    "l2": get_value("input_power_l2"),
                    "l3": get_value("input_power_l3"),
                    "total": get_value("input_power_l1") + get_value("input_power_l2") + get_value("input_power_l3")
                }
            },
            "output": {
                "voltages": {
                    "l1": get_value("output_voltage_l1"),
                    "l2": get_value("output_voltage_l2"),
                    "l3": get_value("output_voltage_l3")
                },
                "currents": {
                    "l1": get_value("output_current_l1"),
                    "l2": get_value("output_current_l2"),
                    "l3": get_value("output_current_l3")
                }
            }
        }

        # Add logging for debugging
      #  logging.info("ESS AC Status:")
      #  logging.info(f"Input Voltages: L1={response['input']['voltages']['l1']}V, L2={response['input']['voltages']['l2']}V, L3={response['input']['voltages']['l3']}V")
      #  logging.info(f"Input Currents: L1={response['input']['currents']['l1']}A, L2={response['input']['currents']['l2']}A, L3={response['input']['currents']['l3']}A")
      #  logging.info(f"Input Frequencies: L1={response['input']['frequencies']['l1']}Hz, L2={response['input']['frequencies']['l2']}Hz, L3={response['input']['frequencies']['l3']}Hz")
      #  logging.info(f"Input Power Total: {response['input']['powers']['total']}W")
      #  logging.info(f"Output Voltages: L1={response['output']['voltages']['l1']}V, L2={response['output']['voltages']['l2']}V, L3={response['output']['voltages']['l3']}V")
      #  logging.info(f"Output Currents: L1={response['output']['currents']['l1']}A, L2={response['output']['currents']['l2']}A, L3={response['output']['currents']['l3']}A")

        return response

    except Exception as e:
        logging.error("❗ Ошибка чтения AC параметров ESS", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")

@router.get("/vebus_status")
async def get_vebus_status(request: Request):
    """
    Чтение VE.Bus регистров с 21 по 41 (устройство 227):
    - Частота, ограничения, мощность, напряжение/ток АКБ, тревоги, состояния, ESS настройки
    """
    try:
        client = request.app.state.modbus_client
        slave = ESS_UNIT_ID
        start = 21
        count = 21  # от 21 до 41 включительно

        result = await client.read_input_registers(start, count=count, slave=slave)
        if result.isError():
            raise HTTPException(status_code=500, detail="Ошибка чтения регистров VE.Bus")

        r = result.registers

        def val(idx): return r[idx - start]

        def s16(v): return decode_signed_16(v)

        return {
            "output_frequency_hz": s16(val(21)) / 100,
            "input_current_limit_a": s16(val(22)) / 10,
            "output_power": {
                "l1": s16(val(23)) * 10,
                "l2": s16(val(24)) * 10,
                "l3": s16(val(25)) * 10,
            },
            "battery_voltage_v": val(26) / 100,
            "battery_current_a": s16(val(27)) / 10,
            "phase_count": val(28),
            "active_input": val(29),
            "soc_percent": val(30) / 10,
            "vebus_state": val(31),
            "vebus_error": val(32),
            "switch_position": val(33),
            "alarms": {
                "temperature": val(34),
                "low_battery": val(35),
                "overload": val(36),
            },
            "ess": {
                "power_setpoint_l1": s16(val(37)),
                "disable_charge": val(38),
                "disable_feed": val(39),
                "power_setpoint_l2": s16(val(40)),
                "power_setpoint_l3": s16(val(41))
            }
        }

    except Exception as e:
        logging.error("❗ Ошибка чтения VE.Bus регистров", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")


@router.post("/vebus/soc")
async def set_vebus_soc(control: VebusSOCControl, request: Request):
    """
    Устанавливает VE.Bus SoC (state of charge threshold)
    """
    try:
        logging.info(f"📤 Установка VE.Bus SoC: {control.soc_threshold}%")
        client = request.app.state.modbus_client

        # Значение с масштабированием x10 (как в описании)
        scaled_value = int(control.soc_threshold * 10)

        await client.write_register(
           # address=30,  # адрес регистра VE.Bus SoC
           # value=scaled_value,
           # slave=ESS_UNIT_ID
            address=2901,  # адрес регистра VE.Bus SoC
            value=scaled_value,
            slave=100
        )

        return {"status": "ok"}
    except Exception as e:
        logging.error("❗ Ошибка установки VE.Bus SoC", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")


@router.post("/ess_advanced_settings/setpoint_fine")
async def set_ess_advanced_setpoint_fine(control: EssAdvancedControl, request: Request):
    """
    Устанавливает точное значение AC Power Setpoint (регистр 2703)
    Диапазон: от -100000 до 100000
    """
    try:
        client = request.app.state.modbus_client
        slave = INVERTER_ID
        
        # Преобразуем значение для записи в регистр
        register_value = int(control.ac_power_setpoint_fine / 100)
        
        # Преобразование отрицательных чисел в формат Modbus (дополнительный код)
        if register_value < 0:
            register_value = (1 << 16) + register_value  # Преобразование в 16-битное представление
            
        # Проверяем, что значение вписывается в int16
        if register_value < 0 or register_value > 65535:
            raise HTTPException(status_code=400, detail="Значение выходит за допустимые пределы")
        
        # Записываем значение в регистр 2703
        await client.write_register(
            address=2703,
            value=register_value,
            slave=slave
        )
        
        logging.info(f"✅ Установлено AC Power Setpoint Fine: {control.ac_power_setpoint_fine} W (регистр 2703 = {register_value})")
        return {"status": "ok", "value": control.ac_power_setpoint_fine}
        
    except Exception as e:
        logging.error("❗ Ошибка записи AC Power Setpoint Fine", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")


@router.post("/ess/grid_limiting_status")
async def set_grid_limiting_status(data: GridLimitUpdate, request: Request):
    """
    Переключение grid_limiting_status (регистр 2709): включение / отключение.
    """
    try:
        client = request.app.state.modbus_client
        slave = INVERTER_ID
        register = 2707
        value = 1 if data.enabled else 0

        # Запись значения
        result = await client.write_register(register, value, slave=slave)

        if result.isError():
            raise HTTPException(status_code=500, detail="Ошибка записи регистра 2709")

        return {"success": True, "grid_limiting_status": value}

    except Exception as e:
        import logging
        logging.error("❗ Ошибка при записи grid_limiting_status", exc_info=e)
        raise HTTPException(status_code=500, detail="Ошибка записи Modbus")



@router.get("/ess_settings")
async def get_ess_settings(request: Request):
    """
    Чтение настроек ESS:
    - BatteryLife State
    - Minimum SoC
    - ESS Mode
    - BatteryLife SoC limit (read-only)
    """
    try:
        client = request.app.state.modbus_client
        slave = 100

        start_address = 2900
        count = 4

        result = await client.read_holding_registers(start_address, count=count, slave=slave)
        if result.isError():
            raise HTTPException(status_code=500, detail="Ошибка чтения регистров ESS Settings")

        regs = result.registers
        return {
            "battery_life_state": regs[0],               # 2900
            "minimum_soc_limit": regs[1] / 10.0,         # 2901, scale x10
            "ess_mode": regs[2],                         # 2902
            "battery_life_soc_limit": regs[3] / 10.0     # 2903, scale x10
        }

    except Exception as e:
        logging.error("❗ Ошибка чтения ESS настроек", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")



@router.get("/ess_advanced_settings")
async def get_ess_advanced_settings(request: Request):
    """
    Чтение базовых ESS и системных настроек с адресов 2700–2712 + 2715 + 2716 (устройство 100).
    Также определяет активный режим ESS: 1, 2 или 3.
    """
    try:
        client = request.app.state.modbus_client
        slave = INVERTER_ID  # Обычно 100

        # 2700–2712 (13 регистров)
        start_main = 2700
        count_main = 13
        result_main = await client.read_input_registers(start_main, count=count_main, slave=slave)
        if result_main.isError() or not hasattr(result_main, "registers"):
            raise HTTPException(status_code=500, detail="Ошибка чтения регистров 2700–2712")

        r_main = result_main.registers
        def safe_main(idx): return r_main[idx - start_main] if (idx - start_main) < len(r_main) else None
        def s16(v): return decode_signed_16(v) if v is not None else None

        # Формируем результат
        result_data = {
            "ac_power_setpoint": safe_main(2700),  # Просто читаем значение регистра 2700
            "max_charge_percent": safe_main(2701),
            "max_discharge_percent": safe_main(2702),
            "ac_power_setpoint_fine": s16(safe_main(2703)) * 100 if safe_main(2703) is not None else None,
            "max_discharge_power": s16(safe_main(2704)) * 10 if safe_main(2704) is not None else None,
            "dvcc_max_charge_current": s16(safe_main(2705)),
            "max_feed_in_power": s16(safe_main(2706)) * 10 if safe_main(2706) is not None else None,
            "overvoltage_feed_in": safe_main(2707),
            "prevent_feedback": safe_main(2708),
            "grid_limiting_status": safe_main(2709),
            "max_charge_voltage": safe_main(2710) / 10.0 if safe_main(2710) is not None else None,
            "ac_input_1_source": safe_main(2711),
            "ac_input_2_source": safe_main(2712),
        }

        logging.info("✅ ESS Advanced Settings:\n%s", json.dumps(result_data, indent=2, ensure_ascii=False))
        return result_data

    except Exception as e:
        logging.error("❗ Ошибка при чтении ESS настроек", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")