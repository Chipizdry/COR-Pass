import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from fastapi import FastAPI
from sqlalchemy import UUID, delete, func, select, update
from typing import Any, Dict, List, Optional, Tuple

from cor_pass.database.models import (
    CerboMeasurement,
    EnergeticSchedule
)
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.schemas import EnergeticScheduleBase, EnergeticScheduleCreate, FullDeviceMeasurementCreate, FullDeviceMeasurementResponse
from loguru import logger
from pymodbus.client import AsyncModbusTcpClient
from cor_pass.database.db import async_session_maker

COLLECTION_INTERVAL_SECONDS = 2

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


async def create_modbus_client(app):
    try:
        if hasattr(app.state, "modbus_client") and app.state.modbus_client:
            await app.state.modbus_client.close()
            logger.info("🔌 Старый клиент Modbus закрыт")

        app.state.modbus_client = AsyncModbusTcpClient(host=MODBUS_IP, port=MODBUS_PORT)
        await app.state.modbus_client.connect()

        if not app.state.modbus_client.connected:
            logger.error("❌ Не удалось подключиться к Modbus серверу")
        else:
            logger.info("✅ Подключение к Modbus серверу установлено")

    except Exception as e:
        logger.exception("❗ Ошибка при создании Modbus клиента", exc_info=e)
#

# --- Клиент хранения ---
#async def create_modbus_client(app):
#    app.state.modbus_client = AsyncModbusTcpClient(host=MODBUS_IP, port=MODBUS_PORT)
#    await app.state.modbus_client.connect()

async def close_modbus_client(app):
    client = getattr(app.state, "modbus_client", None)
    if client and client.connected:
        await client.close()
        logger.info("🔌 Клиент Modbus отключён")

# Получение клиента с реконнектом при ошибках
async def get_modbus_client(app):
    global error_count
    client = getattr(app.state, "modbus_client", None)

    # Если клиент не подключен — создаём новый
    if client is None or not client.connected:
        logger.warning(f"🔄 Переподключение Modbus клиента... (errors: {error_count})")

        # Закрытие старого клиента, если есть
        if client:
            try:
                await client.close()
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при закрытии клиента: {e}")

        # Новый клиент
        new_client = AsyncModbusTcpClient(host=MODBUS_IP, port=MODBUS_PORT)
        await new_client.connect()

        if not new_client.connected:
            logger.error("❌ Не удалось переподключиться к Modbus серверу")
        else:
            logger.info("✅ Новое подключение к Modbus успешно")
        error_count = 0  # сброс после успешного подключения
        app.state.modbus_client = new_client
        
        return new_client

    # Если клиент есть и подключён
    return client

def register_modbus_error():
    global error_count
    error_count += 1
    logger.warning(f"❗ Modbus ошибка #{error_count}")


# Функции декодирования
def decode_signed_16(value: int) -> int:
    return value - 0x10000 if value >= 0x8000 else value

def decode_signed_32(high: int, low: int) -> int:
    combined = (high << 16) | low
    return combined - 0x100000000 if combined >= 0x80000000 else combined









async def collect_battery_data(modbus_client: AsyncModbusTcpClient, transaction_id: UUID) -> Dict[str, Any]:
    # logger.debug(f"[{transaction_id}] Collecting battery data directly from Modbus.")
    try:
        addresses = [REGISTERS[key] for key in REGISTERS]
        start = min(addresses)
        count = max(addresses) - start + 1

        result = await modbus_client.read_input_registers(start, count=count, slave=BATTERY_ID)
        if result.isError():
            logger.error(f"[{transaction_id}] Modbus error reading battery registers.", exc_info=True)
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
            "general_battery_power": general_battery_power
        }

    except Exception as e:
        register_modbus_error()
        logger.error(f"[{transaction_id}] Error in collect_battery_data: {e}", exc_info=True)
        raise

async def collect_inverter_power_data(modbus_client: Any, transaction_id: UUID) -> Dict[str, Any]:
    # logger.debug(f"[{transaction_id}] Collecting inverter power data directly from Modbus.")
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
            res = await modbus_client.read_holding_registers(address=addr, count=2, slave=slave)
            if res.isError():
                logger.error(f"[{transaction_id}] Modbus error reading inverter registers {addr}-{addr+1}.", exc_info=True)
                raise ConnectionError(f"Modbus error: Failed to read inverter registers {addr}-{addr+1}")
            value = decode_signed_32(res.registers[0], res.registers[1])
            result_values[name] = value
        
        total_ac_output = round(result_values["ac_output_l1"] + result_values["ac_output_l2"] + result_values["ac_output_l3"], 2)

        return {
            "inverter_dc_power": result_values["dc_power"],
            "inverter_ac_output_l1": result_values["ac_output_l1"],
            "inverter_ac_output_l2": result_values["ac_output_l2"],
            "inverter_ac_output_l3": result_values["ac_output_l3"],
            "inverter_total_ac_output": total_ac_output
        }

    except Exception as e:
        register_modbus_error()
        logger.error(f"[{transaction_id}] Error in collect_inverter_power_data: {e}", exc_info=True)
        raise


async def collect_ess_ac_data(modbus_client: Any, transaction_id: UUID) -> Dict[str, Any]:
    # logger.debug(f"[{transaction_id}] Collecting ESS AC data directly from Modbus.")
    try:
        slave = ESS_UNIT_ID
        
        registers_map = {
            3: "input_voltage_l1", 4: "input_voltage_l2", 5: "input_voltage_l3",
            6: "input_current_l1", 7: "input_current_l2", 8: "input_current_l3",
            9: "input_frequency_l1", 10: "input_frequency_l2", 11: "input_frequency_l3",
            12: "input_power_l1", 13: "input_power_l2", 14: "input_power_l3",
            
            15: "output_voltage_l1", 16: "output_voltage_l2", 17: "output_voltage_l3",
            18: "output_current_l1", 19: "output_current_l2", 20: "output_current_l3"
        }

        start = min(registers_map.keys())
        count = max(registers_map.keys()) - start + 1

        result = await modbus_client.read_input_registers(start, count=count, slave=slave)
        if result.isError():
            logger.error(f"[{transaction_id}] Modbus error reading ESS AC registers.", exc_info=True)
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
                collected_values[reg_name] = value # Если есть другие типы данных
        
        total_input_power = round(
            collected_values["input_power_l1"] +
            collected_values["input_power_l2"] +
            collected_values["input_power_l3"], 2
        )
        collected_values["ess_total_input_power"] = total_input_power

        return collected_values

    except Exception as e:
        register_modbus_error()
        logger.error(f"[{transaction_id}] Error in collect_ess_ac_data: {e}", exc_info=True)
        raise


SOLAR_CHARGER_SLAVE_IDS = list(range(1, 14)) + [100]

async def collect_solarchargers_data(modbus_client: Any, transaction_id: UUID) -> Dict[str, Any]:
    # logger.debug(f"[{transaction_id}] Collecting solar chargers data directly from Modbus.")
    try:
        slave_ids = SOLAR_CHARGER_SLAVE_IDS
        total_pv_power = 0.0

        for slave in slave_ids:
            try:
                addresses_info = [
                    ("pv_voltage_0", 3700, 100, False),
                    ("pv_voltage_1", 3701, 100, False),
                    ("pv_voltage_2", 3702, 100, False),
                    ("pv_voltage_3", 3703, 100, False),
                    ("pv_power_0", 3724, 1, False),
                    ("pv_power_1", 3725, 1, False),
                    ("pv_power_2", 3726, 1, False),
                    ("pv_power_3", 3727, 1, False),
                ]
                
                needed_regs = [info[1] for info in addresses_info]
                min_reg = min(needed_regs)
                max_reg = max(needed_regs)
                count = max_reg - min_reg + 1

                res = await modbus_client.read_input_registers(address=min_reg, count=count, slave=slave)

                if res.isError() or not hasattr(res, "registers"):
                    logger.warning(f"[{transaction_id}] Modbus error or no registers for slave {slave}. Error: {res}", extra={"slave_id": slave})
                else:
                    regs = res.registers
                    for field_name, reg_address, scale, is_signed in addresses_info:
                        idx = reg_address - min_reg
                        raw = regs[idx]
                        value = decode_signed_16(raw) if is_signed else raw
                        
                        if field_name.startswith("pv_power_"):
                            total_pv_power += round(value / scale, 2)

            except Exception as e:
                logger.warning(f"[{transaction_id}] Exception while reading slave {slave} data: {e}", exc_info=True, extra={"slave_id": slave})

        return {"solar_total_pv_power": round(total_pv_power, 2)}

    except Exception as e:
        register_modbus_error()
        logger.error(f"[{transaction_id}] Overall error during MPPT polling: {e}", exc_info=True)
        raise




async def create_full_device_measurement(db: AsyncSession, data: FullDeviceMeasurementCreate) -> FullDeviceMeasurementResponse:
    # logger.debug(f"Attempting to save full device measurement to DB.")
    try:
        db_measurement = CerboMeasurement(**data.model_dump())
        db.add(db_measurement)
        await db.commit()
        await db.refresh(db_measurement)
        return FullDeviceMeasurementResponse.model_validate(db_measurement)
    except Exception as e:
        logger.error(f"Error saving full device measurement to DB: {e}", exc_info=True)
        raise


async def cerbo_collection_task(app: FastAPI):
    """
    Фоновая задача, которая запускает сбор данных с Modbus и сохраняет их напрямую в базу данных.
    Работает в бесконечном цикле с паузами.
    """

    while True:
        current_transaction_id = uuid4()
        # logger.debug(f"Starting new device data collection cycle. Transaction ID: {current_transaction_id}")

        modbus_client = app.state.modbus_client 

        try:
            if not modbus_client or not modbus_client.connected:
                logger.critical(f"[{current_transaction_id}] Modbus client not connected. Attempting to reconnect...")
                try:
                    if modbus_client is None:
                         modbus_client = AsyncModbusTcpClient(host=MODBUS_IP, port=MODBUS_PORT)
                         app.state.modbus_client = modbus_client 

                    await modbus_client.connect()
                    logger.debug(f"[{current_transaction_id}] Modbus client reconnected.")
                except Exception as e:
                    logger.error(f"[{current_transaction_id}] Failed to reconnect Modbus client: {e}. Skipping this cycle.", exc_info=True)
                    await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)
                    continue

            collected_data = {}

            try:
                battery_data = await collect_battery_data(modbus_client, current_transaction_id)
                collected_data.update(battery_data)
            except Exception as e:
                logger.error(f"[{current_transaction_id}] Failed to collect battery data: {e}. Skipping this data block.", exc_info=True)

            try:
                inverter_data = await collect_inverter_power_data(modbus_client, current_transaction_id)
                collected_data.update(inverter_data)
            except Exception as e:
                logger.error(f"[{current_transaction_id}] Failed to collect inverter data: {e}. Skipping this data block.", exc_info=True)

            try:
                ess_ac_data = await collect_ess_ac_data(modbus_client, current_transaction_id)
                collected_data.update(ess_ac_data)
            except Exception as e:
                logger.error(f"[{current_transaction_id}] Failed to collect ESS AC data: {e}. Skipping this data block.", exc_info=True)

            try:
                solarchargers_data = await collect_solarchargers_data(modbus_client, current_transaction_id)
                collected_data.update(solarchargers_data)
            except Exception as e:
                logger.error(f"[{current_transaction_id}] Failed to collect solar chargers data: {e}. Skipping this data block.", exc_info=True)


            if not collected_data:
                logger.warning(f"[{current_transaction_id}] No data collected from any Modbus device. Skipping database save.")
                await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)
                continue

            final_data_for_pydantic = collected_data
            final_data_for_pydantic["measured_at"] = datetime.now()
            final_data_for_pydantic["object_name"] = "COR-AZK"

            required_fields = [
                "general_battery_power",
                "inverter_total_ac_output",
                "ess_total_input_power",
                "solar_total_pv_power",
                "measured_at",
                "object_name"
            ]

            missing_fields = [field for field in required_fields if field not in final_data_for_pydantic or final_data_for_pydantic[field] is None]
            if missing_fields:
                logger.error(f"[{current_transaction_id}] Incomplete data for FullDeviceMeasurementCreate. Missing: {missing_fields}. Skipping save.",
                             extra={"missing_fields": missing_fields, "collected_data": final_data_for_pydantic})
                await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)
                continue

            full_measurement = FullDeviceMeasurementCreate(**final_data_for_pydantic)

            async with async_session_maker() as db:
                new_record = await create_full_device_measurement(db=db, data=full_measurement)
                # logger.debug(f"[{current_transaction_id}] Successfully saved full measurement to DB. Record ID: {new_record.id}")

        except Exception as e:
            logger.error(f"[{current_transaction_id}] Unhandled error during periodic data collection: {e}", exc_info=True)

        finally:
            # logger.debug(f"[{current_transaction_id}] Waiting {COLLECTION_INTERVAL_SECONDS} seconds before next collection cycle.")
            await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)


async def get_device_measurements_paginated(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 10,
    object_name: Optional[str] = None,
    start_date: Optional[datetime] = None, 
    end_date: Optional[datetime] = None
) -> Tuple[List[CerboMeasurement], int]:
    """
    Получает записи CerboMeasurement с пагинацией и необязательными фильтрами.

    Args:
        db: Асинхронная сессия базы данных.
        page: Номер текущей страницы (начиная с 1).
        page_size: Количество записей на странице.
        object_name: Необязательный фильтр по имени объекта.
        start_date: Необязательный фильтр по начальной дате measured_at.
        end_date: Необязательный фильтр по конечной дате measured_at.

    Returns:
        Кортеж, содержащий список объектов CerboMeasurement и общее количество записей.
    """

    query = select(CerboMeasurement)
    count_query = select(func.count()).select_from(CerboMeasurement)


    if object_name:
        query = query.where(CerboMeasurement.object_name == object_name)
        count_query = count_query.where(CerboMeasurement.object_name == object_name)
    
    if start_date:
        query = query.where(CerboMeasurement.measured_at >= start_date)
        count_query = count_query.where(CerboMeasurement.measured_at >= start_date)
        
    if end_date:
        query = query.where(CerboMeasurement.measured_at <= end_date)
        count_query = count_query.where(CerboMeasurement.measured_at <= end_date)



    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(CerboMeasurement.measured_at.desc()) 


    result = await db.execute(query)
    measurements = result.scalars().all()

    total_count_result = await db.execute(count_query)
    total_count = total_count_result.scalar_one()

    return measurements, total_count



async def create_schedule(db: AsyncSession, schedule_data: EnergeticScheduleCreate) -> EnergeticSchedule:
    """
    Создает новое расписание в базе данных.
    """
    duration_delta = timedelta(
        hours=schedule_data.duration_hours,
        minutes=schedule_data.duration_minutes
    )
    
    temp_start_datetime = datetime.combine(datetime.min.date(), schedule_data.start_time)
    calculated_end_time = (temp_start_datetime + duration_delta).time()


    db_schedule = EnergeticSchedule(
        start_time=schedule_data.start_time,
        duration=duration_delta,
        end_time=calculated_end_time,
        grid_feed_w=schedule_data.grid_feed_w,
        battery_level_percent=schedule_data.battery_level_percent,
        charge_battery=schedule_data.charge_battery,
        is_manual_mode=schedule_data.is_manual_mode
    )
    db.add(db_schedule)
    await db.commit()
    await db.refresh(db_schedule)
    return db_schedule



async def get_schedule_by_id(db: AsyncSession, schedule_id: str) -> Optional[EnergeticSchedule]:
    """
    Получает расписание по его ID.
    """
    result = await db.execute(
        select(EnergeticSchedule).where(EnergeticSchedule.id == schedule_id)
    )
    return result.scalars().first()

# async def get_all_schedules(db: AsyncSession) -> List[EnergeticSchedule]:
#     """
#     Получает все активные расписания, отсортированные по времени начала.
#     """
#     result = await db.execute(
#         select(EnergeticSchedule)
#         .order_by(EnergeticSchedule.start_time)
#     )
#     return result.scalars().all()

async def get_all_schedules(db: AsyncSession) -> List[EnergeticSchedule]:
    """
    Получает все расписания (активные и неактивные), отсортированные по времени начала.
    """
    result = await db.execute(
        select(EnergeticSchedule)
        .order_by(EnergeticSchedule.start_time)
    )
    return result.scalars().all()

async def update_schedule(
    db: AsyncSession, schedule_id: str, schedule_data: EnergeticScheduleBase
) -> Optional[EnergeticSchedule]:
    """
    Обновляет существующее расписание по ID.
    """
    db_schedule = await get_schedule_by_id(db, schedule_id)
    if not db_schedule:
        return None

    duration_delta = timedelta(
        hours=schedule_data.duration_hours,
        minutes=schedule_data.duration_minutes
    )
    

    temp_start_datetime = datetime.combine(datetime.min.date(), schedule_data.start_time)
    calculated_end_time = (temp_start_datetime + duration_delta).time()


    db_schedule.start_time = schedule_data.start_time
    db_schedule.duration = duration_delta
    db_schedule.end_time = calculated_end_time 
    db_schedule.grid_feed_w = schedule_data.grid_feed_w
    db_schedule.battery_level_percent = schedule_data.battery_level_percent
    db_schedule.charge_battery = schedule_data.charge_battery
    db_schedule.is_manual_mode = schedule_data.is_manual_mode

    await db.commit()
    await db.refresh(db_schedule)
    return db_schedule

async def delete_schedule(db: AsyncSession, schedule_id: str) -> bool:
    """
    Удаляет расписание по ID.
    """
    result = await db.execute(
        delete(EnergeticSchedule).where(EnergeticSchedule.id == schedule_id)
    )
    await db.commit()
    return result.rowcount > 0


async def update_schedule_is_active_status(db: AsyncSession, schedule_id: str, is_active_status: bool):

    stmt = update(EnergeticSchedule).where(EnergeticSchedule.id == schedule_id).values(is_active=is_active_status)
    await db.execute(stmt)
    await db.commit()





async def set_inverter_parameters(
    grid_feed_w: int,
    battery_level_percent: int,
    charge_battery: bool
):
    logger.debug(f"\n--- Тестовая отправка параметров на инвертор ---")
    logger.debug(f"Отдача в сеть: {grid_feed_w} Вт")
    logger.debug(f"Целевой уровень батареи: {battery_level_percent}%")
    logger.debug(f"Зарядка батареи: {charge_battery}")
    logger.debug("--------------------------------------")


current_active_schedule_id: Optional[str] = None


SCHEDULE_CHECK_INTERVAL_SECONDS = 3
DEFAULT_grid_feed_kw = 70000
DEFAULT_battery_level_percent = 30
DEFAULT_charge_battery = True

async def energetic_schedule_task(async_session_maker):
    """
    Фоновая задача для проверки и применения энергетического расписания.
    """
    global current_active_schedule_id
    
    while True:
        try:
            current_check_time = datetime.now() 
            # logger.debug(f"[{current_check_time.strftime('%H:%M:%S')}] Проверка расписания...")
            
            async with async_session_maker() as db_session:
                all_schedules = await get_all_schedules(db_session)
                
                operational_schedules = [s for s in all_schedules if not s.is_manual_mode]

                current_time = current_check_time.time()

                if not operational_schedules:
                    # logger.debug("Нет расписаний для применения.")
                    if current_active_schedule_id is not None:
                        await set_inverter_parameters(grid_feed_w=DEFAULT_grid_feed_kw, battery_level_percent=DEFAULT_battery_level_percent, charge_battery=DEFAULT_charge_battery)
                        await update_schedule_is_active_status(db=db_session, schedule_id=current_active_schedule_id, is_active_status=False)
                        current_active_schedule_id = None
                    else:
                        pass
                        # logger.debug("Инвертор уже в дефолтных параметрах (расписание отсутствует).")
                    
                    for schedule in operational_schedules:
                        if schedule.is_active:
                            await update_schedule_is_active_status(db=db_session, schedule_id=schedule.id, is_active_status=False)
                    
                    await asyncio.sleep(SCHEDULE_CHECK_INTERVAL_SECONDS)
                    continue 
                

                active_auto_schedule_for_now: Optional[EnergeticSchedule] = None


                for schedule in operational_schedules:
                    if schedule.start_time <= schedule.end_time:
                        if schedule.start_time <= current_time < schedule.end_time:
                            active_auto_schedule_for_now = schedule
                            break
                    else: 
                        if current_time >= schedule.start_time or current_time < schedule.end_time:
                            active_auto_schedule_for_now = schedule
                            break
                

                if active_auto_schedule_for_now:
                    if active_auto_schedule_for_now.id != current_active_schedule_id:
                        # logger.debug(f"Найдено активное расписание: ID {active_auto_schedule_for_now.id} (Время: {active_auto_schedule_for_now.start_time}-{active_auto_schedule_for_now.end_time}). Активация.")
                        

                        if current_active_schedule_id is not None:
                            await update_schedule_is_active_status(db=db_session, schedule_id=current_active_schedule_id, is_active_status=False)
                            
                        await set_inverter_parameters(
                            grid_feed_w=active_auto_schedule_for_now.grid_feed_w, 
                            battery_level_percent=active_auto_schedule_for_now.battery_level_percent,
                            charge_battery=active_auto_schedule_for_now.charge_battery
                        )
                        await update_schedule_is_active_status(db=db_session, schedule_id=active_auto_schedule_for_now.id, is_active_status=True)
                        current_active_schedule_id = active_auto_schedule_for_now.id
                    else:
                        # logger.debug(f"Автоматическое расписание {active_auto_schedule_for_now.id} уже активно. Параметры не меняются.")

                        if not active_auto_schedule_for_now.is_active: 
                             await update_schedule_is_active_status(db=db_session, schedule_id=active_auto_schedule_for_now.id, is_active_status=True)
                else:
                   
                    if current_active_schedule_id is not None:
                        # logger.debug("Текущее время вне любого расписания. Возврат к дефолтным параметрам.")
                        await set_inverter_parameters(grid_feed_w=DEFAULT_grid_feed_kw, battery_level_percent=DEFAULT_battery_level_percent, charge_battery=DEFAULT_charge_battery)
                        await update_schedule_is_active_status(db=db_session, schedule_id=current_active_schedule_id, is_active_status=False)
                        current_active_schedule_id = None
                    else:
                        pass
                        # logger.debug("Текущее время вне любого расписания. Инвертор уже в дефолтных параметрах.")
                    
                for schedule in all_schedules:
                    if (not schedule.is_manual_mode and 
                        schedule.id != current_active_schedule_id and 
                        schedule.is_active):
                        await update_schedule_is_active_status(db=db_session, schedule_id=schedule.id, is_active_status=False)

        except Exception as e:
            logger.error(f"Ошибка в фоновой задаче energetic_schedule_task: {e}", exc_info=True) 
        
        await asyncio.sleep(SCHEDULE_CHECK_INTERVAL_SECONDS)