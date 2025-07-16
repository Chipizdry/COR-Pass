from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
import logging
import json
from typing import List, Optional
from pydantic import BaseModel 
from cor_pass.repository.cerbo_service import BATTERY_ID, ESS_UNIT_ID, INVERTER_ID, REGISTERS, create_schedule, decode_signed_16, decode_signed_32, delete_schedule, get_all_schedules, get_device_measurements_paginated, get_modbus_client, get_schedule_by_id, register_modbus_error, update_schedule
from cor_pass.schemas import CerboMeasurementResponse, EnergeticScheduleBase, EnergeticScheduleCreate, EnergeticScheduleResponse, EssAdvancedControl, GridLimitUpdate, PaginatedResponse, VebusSOCControl
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.db import get_db
from math import ceil
from loguru import logger

ERROR_THRESHOLD = 9
error_count = 0


# Создание роутера FastAPI
router = APIRouter(prefix="/modbus", tags=["Modbus"])
schedules_storage = {
    "schedule_enabled": True,
    "periods": []
}


class SchedulePeriod(BaseModel):
    id: int
    startHour: int
    startMinute: int
    durationHour: int
    durationMinute: int
    feedIn: float
    batteryLevel: int
    chargeEnabled: bool
    active: bool

class ScheduleData(BaseModel):
    scheduleEnabled: bool
    periods: list[SchedulePeriod]


class RegisterWriteRequest(BaseModel):
    slave_id: int
    register: int
    value: int


class InverterPowerPayload(BaseModel):
    inverter_power: float



@router.get("/error_count")
async def get_error_count():
    """Возвращает текущее количество ошибок Modbus"""
    return {"error_count": error_count}

# Получение статуса батареи
@router.get("/battery_status")

async def get_battery_status(request: Request):
    try:
        #client = request.app.state.modbus_client
        client = await get_modbus_client(request.app)  
        addresses = [REGISTERS[key] for key in REGISTERS]
        start = min(addresses)
        count = max(addresses) - start + 1

        result = await client.read_input_registers(start, count=count, slave=BATTERY_ID)
        if result.isError():
            raise HTTPException(status_code=500, detail="Ошибка чтения регистров батареи")

        raw = result.registers

        def get_value(name: str) -> int:
            return raw[REGISTERS[name] - start]
        error_count = 0

        return {
            "soc": get_value("soc") / 10,
            "voltage": get_value("voltage") / 100,
            "current": decode_signed_16(get_value("current")) / 10,
            "temperature":get_value("temperature") / 10,
            "power": decode_signed_16(get_value("power")),
            "soh": get_value("soh") / 10
        }

    except Exception as e:
        register_modbus_error()
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
       #client = request.app.state.modbus_client
        client = await get_modbus_client(request.app)
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
        error_count = 0
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
        register_modbus_error()
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
        #client = request.app.state.modbus_client
        client = await get_modbus_client(request.app) 
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
        error_count = 0  
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

        # Логи отладки
      #  logging.info("ESS AC Status:")
      #  logging.info(f"Input Voltages: L1={response['input']['voltages']['l1']}V, L2={response['input']['voltages']['l2']}V, L3={response['input']['voltages']['l3']}V")
      #  logging.info(f"Input Currents: L1={response['input']['currents']['l1']}A, L2={response['input']['currents']['l2']}A, L3={response['input']['currents']['l3']}A")
      #  logging.info(f"Input Frequencies: L1={response['input']['frequencies']['l1']}Hz, L2={response['input']['frequencies']['l2']}Hz, L3={response['input']['frequencies']['l3']}Hz")
      #  logging.info(f"Input Power Total: {response['input']['powers']['total']}W")
      #  logging.info(f"Output Voltages: L1={response['output']['voltages']['l1']}V, L2={response['output']['voltages']['l2']}V, L3={response['output']['voltages']['l3']}V")
      #  logging.info(f"Output Currents: L1={response['output']['currents']['l1']}A, L2={response['output']['currents']['l2']}A, L3={response['output']['currents']['l3']}A")

        return response

    except Exception as e:
        register_modbus_error()
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
        error_count = 0
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
        register_modbus_error()
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
            address=2901,  # адрес регистра VE.Bus SoC
            value=scaled_value,
            slave=100
        )
        error_count = 0
        return {"status": "ok"}
    except Exception as e:
        register_modbus_error()
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
        error_count = 0  
        logging.info(f"✅ Установлено AC Power Setpoint Fine: {control.ac_power_setpoint_fine} W (регистр 2703 = {register_value})")
        return {"status": "ok", "value": control.ac_power_setpoint_fine}
        
    except Exception as e:
        register_modbus_error() 
        logging.error("❗ Ошибка записи AC Power Setpoint Fine", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")



@router.post("/ess_advanced_settings/inverter_power")
async def set_inverter_power_setpoint(payload: InverterPowerPayload, request: Request):
    try:
        client = request.app.state.modbus_client
        slave = INVERTER_ID

        raw_value = payload.inverter_power
        if raw_value is None:
            raise HTTPException(status_code=400, detail="Не передано значение inverter_power")

        # Масштабируем и проверяем на допустимые границы int16
        scaled_value = int(float(raw_value/10))
        if not -32768 <= scaled_value <= 32767:
            raise HTTPException(status_code=400, detail="Значение выходит за пределы int16")

        # Преобразуем в формат Modbus (uint16, если отрицательное — в дополнительный код)
        if scaled_value < 0:
            register_value = (1 << 16) + scaled_value
        else:
            register_value = scaled_value

        await client.write_register(address=2704, value=register_value, slave=slave)

        logging.info(f"✅ Установлено значение инвертора: {raw_value} W (регистр 2704 = {register_value})")
        return {"status": "ok", "value": raw_value}

    except Exception as e:
        logging.error("❗ Ошибка записи регистра 2704", exc_info=e)
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
        error_count = 0
        return {"success": True, "grid_limiting_status": value}

    except Exception as e:
        register_modbus_error()
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
        error_count = 0
        return {
            "battery_life_state": regs[0],               # 2900
            "minimum_soc_limit": regs[1] / 10.0,         # 2901, scale x10
            "ess_mode": regs[2],                         # 2902
            "battery_life_soc_limit": regs[3] / 10.0     # 2903, scale x10
        }

    except Exception as e:
        register_modbus_error()
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
        error_count = 0
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

        # logging.info("✅ ESS Advanced Settings:\n%s", json.dumps(result_data, indent=2, ensure_ascii=False))
        return result_data

    except Exception as e:
        register_modbus_error() 
        logging.error("❗ Ошибка при чтении ESS настроек", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")

@router.get("/solarchargers_status")
async def get_solarchargers_status(request: Request):
    """
    Быстрое чтение PV-напряжения и тока с MPPT по Modbus + суммарная мощность
    """
    try:
        client = request.app.state.modbus_client
        slave_ids = list(range(1, 14)) + [100]

        results = {}
        total_pv_power = 0  # Инициализация переменной для суммарной мощности

        for slave in slave_ids:
            charger_data = {}

            try:
                # Читаем диапазон: 3700–3703 и 3724–3727 = 8 регистров
                addresses = [
                    ("pv_voltage_0", 3700, 100, False),
                    ("pv_voltage_1", 3701, 100, False),
                    ("pv_voltage_2", 3702, 100, False),
                    ("pv_voltage_3", 3703, 100, False),
                    ("pv_power_0", 3724, 1, False),
                    ("pv_power_1", 3725, 1, False),
                    ("pv_power_2", 3726, 1, False),
                    ("pv_power_3", 3727, 1, False),
                ]

                # Все нужные адреса
                needed_regs = [3700, 3701, 3702, 3703, 3724, 3725, 3726, 3727]
                min_reg = min(needed_regs)
                max_reg = max(needed_regs)
                count = max_reg - min_reg + 1

                # Один запрос
                res = await client.read_input_registers(address=min_reg, count=count, slave=slave)

                if res.isError() or not hasattr(res, "registers"):
                    for name, reg, scale, _ in addresses:
                        charger_data[name] = None
                    logging.warning(f"⚠️ Ошибка чтения диапазона у slave {slave}")
                else:
                    regs = res.registers  # список считанных значений
                    for name, reg, scale, is_signed in addresses:
                        idx = reg - min_reg
                        raw = regs[idx]
                        value = decode_signed_16(raw) if is_signed else raw
                        charger_data[name] = round(value / scale, 2)
                        
                        # Суммируем только мощности (pv_power_*)
                        if name.startswith("pv_power_"):
                            total_pv_power += charger_data[name]

            except Exception as e:
                charger_data["error"] = str(e)
                logging.warning(f"⚠️ Исключение при чтении slave {slave}: {e}")

            results[f"charger_{slave}"] = charger_data

        # Добавляем суммарную мощность в результаты
        results["total_pv_power"] = round(total_pv_power, 2)
        
        return results

    except Exception as e:
        register_modbus_error()
        logging.error("❗️ Общая ошибка при опросе MPPT", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")


@router.get("/dynamic_ess_settings")
async def get_dynamic_ess_settings(request: Request):
    client = request.app.state.modbus_client
    try:
        unit_id = 100
        start_address = 5420
        count = 10  # 5430 не читается
        result = await client.read_holding_registers(start_address, count=count, slave=unit_id)

        if result.isError():
            raise HTTPException(status_code=500, detail=f"Modbus error: {result}")

        regs = result.registers

        if len(regs) != count:
            raise HTTPException(
                status_code=500,
                detail=f"Ожидалось {count} регистров, получено {len(regs)}: {regs}"
            )

        data = {
            "BatteryCapacity_kWh": regs[0] / 10.0,                    # 5420
            "FullChargeDuration_hr": regs[1],                         # 5421
            "FullChargeInterval_day": regs[2],                        # 5422
            "DynamicEssMode": regs[3],                                # 5423
            "Schedule_AllowGridFeedIn": regs[4],                      # 5424
            "Schedule_Duration_sec": regs[5],                         # 5425
            "Schedule_Restrictions": regs[6],                         # 5426
            "Schedule_TargetSoc_pct": regs[7],                        # 5427
            "Schedule_Start_unix": (regs[8] << 16) + regs[9],         # 5428 + 5429
            # Schedule_Strategy отсутствует — 5430 недоступен
        }

        return data

    except Exception as e:
        logger.error("🛑 Unexpected error", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка чтения Dynamic ESS: {e}")


@router.get("/test_dynamic_ess_registers")
async def test_dynamic_ess_registers(
    request: Request,
    start: int = Query(..., description="Начальный регистр"),
    end: int = Query(..., description="Конечный регистр"),
    unit_id: int = Query(100, description="Slave UID устройства")
):
    client = request.app.state.modbus_client
    results = {}

    for reg in range(start, end + 1):
        try:
            res = await client.read_holding_registers(address=reg, count=1, slave=unit_id)
            if res.isError():
                results[str(reg)] = f"❌ Error: {res}"
            elif hasattr(res, "registers"):
                results[str(reg)] = f"✅ Value: {res.registers[0]}"
            else:
                results[str(reg)] = "❓ No 'registers' attribute"
        except Exception as e:
            results[str(reg)] = f"💥 Exception: {str(e)}"

    return results


@router.post("/write_register")
async def write_register(request_data: RegisterWriteRequest, request: Request):
    """
    Записывает значение в указанный регистр Modbus.
    """
    try:
        client = request.app.state.modbus_client
        
        # Записываем значение в регистр
        result = await client.write_register(
            address=request_data.register,
            value=request_data.value,
            slave=request_data.slave_id
        )
        
        if result.isError():
            raise HTTPException(status_code=500, detail="Ошибка записи регистра")
            
        return {"status": "success", "register": request_data.register, "value": request_data.value}
        
    except Exception as e:
        register_modbus_error()
        logging.error(f"❗ Ошибка записи регистра {request_data.register}", exc_info=e)
        raise HTTPException(status_code=500, detail="Modbus ошибка")



@router.get(
    "/measurements/",
    response_model=PaginatedResponse[CerboMeasurementResponse], 
    summary="Получить все измерения CerboMeasurement с пагинацией и фильтрацией",
    description="Получает список всех измерений с поддержкой пагинации, фильтрации по имени объекта и диапазону дат.",
    tags=["Measurements"]
)
async def read_measurements(
    page: int = Query(1, ge=1, description="Номер страницы (начиная с 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Количество элементов на странице (от 1 до 100)"),
    object_name: Optional[str] = Query(None, description="Фильтр по имени объекта"),
    start_date: Optional[datetime] = Query(None, description="Начальная дата измерения (ISO 8601, например '2023-01-01T00:00:00')"),
    end_date: Optional[datetime] = Query(None, description="Конечная дата измерения (ISO 8601, например '2023-12-31T23:59:59')"),
    db: AsyncSession = Depends(get_db)
):
    measurements, total_count = await get_device_measurements_paginated(
        db=db,
        page=page,
        page_size=page_size,
        object_name=object_name,
        start_date=start_date,
        end_date=end_date
    )

    total_pages = ceil(total_count / page_size) if total_count > 0 else 0

    return PaginatedResponse(
        items=[CerboMeasurementResponse.model_validate(m) for m in measurements],
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )




@router.post("/schedules/create", 
             response_model=EnergeticScheduleResponse, 
             status_code=status.HTTP_201_CREATED,
             tags=["Energetic Shedule CRUD"])
async def create_energetic_schedule(
    schedule_data: EnergeticScheduleCreate,
    db: AsyncSession = Depends(get_db)
):
    new_schedule = await create_schedule(db, schedule_data)
    return new_schedule



@router.get("/schedules/{schedule_id}", 
            response_model=EnergeticScheduleResponse,
            tags=["Energetic Shedule CRUD"])
async def get_energetic_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db)
):
    schedule = await get_schedule_by_id(db, schedule_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return schedule

@router.get("/schedules/", 
            response_model=List[EnergeticScheduleResponse],
            tags=["Energetic Shedule CRUD"])
async def get_all_energetic_schedules_api(
    db: AsyncSession = Depends(get_db)
):
    schedules = await get_all_schedules(db)
    response = []
    for schedule in schedules:
        schedule = EnergeticScheduleResponse(
            id=schedule.id,
            start_time=schedule.start_time,
            duration=schedule.duration,
            grid_feed_w=schedule.grid_feed_w,
            battery_level_percent=schedule.battery_level_percent,
            charge_battery=schedule.charge_battery,
            is_active=schedule.is_active,
            is_manual_mode=schedule.is_manual_mode,
            end_time=schedule.end_time
        )
        response.append(schedule)
    return response

@router.put("/schedules/{schedule_id}", 
            response_model=EnergeticScheduleResponse,
            tags=["Energetic Shedule CRUD"])
async def update_energetic_schedule_api(
    schedule_id: str,
    schedule_data: EnergeticScheduleBase,
    db: AsyncSession = Depends(get_db)
):
    updated_schedule = await update_schedule(db, schedule_id, schedule_data)
    if not updated_schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return updated_schedule

@router.delete("/schedules/{schedule_id}", 
               status_code=status.HTTP_204_NO_CONTENT,
               tags=["Energetic Shedule CRUD"])
async def delete_energetic_schedule_api(
    schedule_id: str,
    db: AsyncSession = Depends(get_db)
):
    deleted = await delete_schedule(db, schedule_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return

