import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from sqlalchemy import UUID, delete, func, select, update
from typing import Any, Dict, List, Optional, Tuple
from math import ceil

from cor_pass.database.models import CerboMeasurement, EnergeticSchedule
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.schemas import (
    EnergeticScheduleBase,
    EnergeticScheduleCreate,
    FullDeviceMeasurementCreate,
    FullDeviceMeasurementResponse,
    CerboMeasurementResponse
)
from loguru import logger
from pymodbus.client import AsyncModbusTcpClient
from cor_pass.database.db import async_session_maker

error_count = 0

COLLECTION_INTERVAL_SECONDS = 2

# Конфигурация Modbus
MODBUS_IP = "91.203.25.12"
MODBUS_PORT = 502
BATTERY_ID = 225  # Основная батарея
INVERTER_ID = 100  # Инвертор
ESS_UNIT_ID = 227  # Система управления (ESS)

# Определение регистров Modbus
REGISTERS = {
    "soc": 266,  # % SoC (0.1%)
    "voltage": 259,  # Напряжение (x100)
    "current": 261,  # Ток (x10)
    "temperature": 262,
    "power": 258,  # Мощность (signed int16)
    "soh": 304,  # Состояние здоровья (0.1%)
}

INVERTER_REGISTERS = {
    "inverter_power": 870,  # Мощность инвертора/зарядного устройства (DC)
    "output_power_l1": 878,  # Мощность на выходе инвертора (L1)
    "output_power_l2": 880,  # Мощность на выходе инвертора (L2)
    "output_power_l3": 882,  # Мощность на выходе инвертора (L3)
}

ESS_REGISTERS = {
    # Базовые регистры
    "switch_position": 33,  # Положение переключателя
    "temperature_alarm": 34,  # Температурная тревога
    "low_battery_alarm": 35,  # Тревога низкого заряда
    "overload_alarm": 36,  # Тревога перегрузки
    "disable_charge": 38,  # Запрет на заряд (0/1)
    "disable_feed": 39,  # Запрет на подачу в сеть (0/1)
    # 32-битные регистры мощности
    "ess_power_setpoint_l1": 96,  # Установка мощности фаза 1 (int32)
    "ess_power_setpoint_l2": 98,  # Установка мощности фаза 2 (int32)
    "ess_power_setpoint_l3": 100,  # Установка мощности фаза 3 (int32)
    # Дополнительные параметры
    "disable_ov_feed": 65,  # Запрет фид-ина при перегрузке
    "ov_feed_limit_l1": 66,  # Лимит мощности для L1
    "ov_feed_limit_l2": 67,  # Лимит мощности для L2
    "ov_feed_limit_l3": 68,  # Лимит мощности для L3
    "setpoints_as_limit": 71,  # Использовать setpoints как лимит
    "ov_offset_mode": 72,  # Режим оффсета (0=1V, 1=100mV)
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
# async def create_modbus_client(app):
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



async def get_device_measurements_paginated(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 10,
    object_name: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
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
    query = (
        query.offset(offset)
        .limit(page_size)
        .order_by(CerboMeasurement.measured_at.desc())
    )

    result = await db.execute(query)
    measurements = result.scalars().all()

    total_count_result = await db.execute(count_query)
    total_count = total_count_result.scalar_one()

    return measurements, total_count


async def create_schedule(
    db: AsyncSession, schedule_data: EnergeticScheduleCreate
) -> EnergeticSchedule:
    """
    Создает новое расписание в базе данных.
    """
    duration_delta = timedelta(
        hours=schedule_data.duration_hours, minutes=schedule_data.duration_minutes
    )

    temp_start_datetime = datetime.combine(
        datetime.min.date(), schedule_data.start_time
    )
    calculated_end_time = (temp_start_datetime + duration_delta).time()

    db_schedule = EnergeticSchedule(
        start_time=schedule_data.start_time,
        duration=duration_delta,
        end_time=calculated_end_time,
        grid_feed_w=schedule_data.grid_feed_w,
        battery_level_percent=schedule_data.battery_level_percent,
        charge_battery_value=schedule_data.charge_battery_value,
        is_manual_mode=schedule_data.is_manual_mode,
    )
    db.add(db_schedule)
    await db.commit()
    await db.refresh(db_schedule)
    return db_schedule


async def get_schedule_by_id(
    db: AsyncSession, schedule_id: str
) -> Optional[EnergeticSchedule]:
    """
    Получает расписание по его ID.
    """
    result = await db.execute(
        select(EnergeticSchedule).where(EnergeticSchedule.id == schedule_id)
    )
    return result.scalars().first()


async def get_all_schedules(db: AsyncSession) -> List[EnergeticSchedule]:
    """
    Получает все расписания (активные и неактивные), отсортированные по времени начала.
    """
    result = await db.execute(
        select(EnergeticSchedule).order_by(EnergeticSchedule.start_time)
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
        hours=schedule_data.duration_hours, minutes=schedule_data.duration_minutes
    )

    temp_start_datetime = datetime.combine(
        datetime.min.date(), schedule_data.start_time
    )
    calculated_end_time = (temp_start_datetime + duration_delta).time()

    db_schedule.start_time = schedule_data.start_time
    db_schedule.duration = duration_delta
    db_schedule.end_time = calculated_end_time
    db_schedule.grid_feed_w = schedule_data.grid_feed_w
    db_schedule.battery_level_percent = schedule_data.battery_level_percent
    db_schedule.charge_battery_value = schedule_data.charge_battery_value
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


async def update_schedule_is_active_status(
    db: AsyncSession, schedule_id: str, is_active_status: bool
):

    stmt = (
        update(EnergeticSchedule)
        .where(EnergeticSchedule.id == schedule_id)
        .values(is_active=is_active_status)
    )
    await db.execute(stmt)
    await db.commit()


async def ensure_modbus_connected(app: FastAPI):
    modbus_client = app.state.modbus_client
    if not modbus_client or not modbus_client.connected:
        logger.critical("Modbus client not connected. Attempting to reconnect...")
        try:
            if modbus_client is None:
                modbus_client = AsyncModbusTcpClient(host=MODBUS_IP, port=MODBUS_PORT)
                app.state.modbus_client = modbus_client
            await modbus_client.connect()
            logger.debug("Modbus client reconnected.")
        except Exception as e:
            logger.error(f"Failed to reconnect Modbus client: {e}. Skipping this cycle.", exc_info=True)
            raise 
    return modbus_client 


async def read_grid_feed_w(app: FastAPI) -> Optional[int]:
    """
    Читает текущее значение AC Power Setpoint Fine (регистр 2703) и возвращает его в Ваттах.
    """
    modbus_client = await ensure_modbus_connected(app)
    if modbus_client is None:
        return None
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
        # logger.debug(f"Прочитано AC Power Setpoint Fine: {actual_value_watts} W (регистр 2703 = {register_value})")
        return actual_value_watts
    except Exception as e:
        logger.error(f"Ошибка при чтении AC Power Setpoint Fine: {e}", exc_info=True)
        return None

async def read_vebus_soc(app: FastAPI) -> Optional[int]:
    """
    Читает текущее значение VE.Bus SoC (регистр 2901) и возвращает его в процентах.
    """
    modbus_client = await ensure_modbus_connected(app)
    if modbus_client is None:
        return None
    try:
        result = await modbus_client.read_holding_registers(address=2901, count=1, slave=INVERTER_ID)
        if result.isError():
            logger.error(f"Ошибка чтения регистра 2901: {result}")
            return None
        
        register_value = result.registers[0]
        actual_value_percent = register_value / 10
        # logger.debug(f"Прочитано VE.Bus SoC: {actual_value_percent}% (регистр 2901 = {register_value})")
        return int(actual_value_percent) 
    except Exception as e:
        logger.error(f"Ошибка при чтении VE.Bus SoC: {e}", exc_info=True)
        return None

async def read_dvcc_max_charge_current(app: FastAPI) -> Optional[int]:
    """
    Читает текущее значение DVCC max charge current (регистр 2705) и возвращает его в Амперах.
    """
    modbus_client = await ensure_modbus_connected(app)
    if modbus_client is None:
        return None
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
            
        # logger.debug(f"Прочитано DVCC max charge current: {actual_value} A (регистр 2705 = {register_value})")
        return actual_value
    except Exception as e:
        logger.error(f"Ошибка при чтении DVCC max charge current: {e}", exc_info=True)
        return None

async def send_grid_feed_w_command(app: FastAPI, grid_feed_w: int):
    modbus_client = await ensure_modbus_connected(app)
    if modbus_client is None: 
        return {"status": "error", "message": "Modbus client not available"}
    try:
        slave = INVERTER_ID
        # Преобразуем значение для записи в регистр
        register_value = int(grid_feed_w / 100)
        
        # Преобразование отрицательных чисел в формат Modbus (дополнительный код)
        if register_value < 0:
            register_value = (1 << 16) + register_value  # Преобразование в 16-битное представление
            
        # Проверяем, что значение вписывается в int16
        if register_value < 0 or register_value > 65535:
            raise HTTPException(status_code=400, detail="Значение выходит за допустимые пределы")
        
        # Записываем значение в регистр 2703
        await modbus_client.write_register(
            address=2703,
            value=register_value,
            slave=slave
        )
        global error_count
        error_count = 0  
        # logger.debug(f"✅ Установлено AC Power Setpoint Fine: {grid_feed_w} W (регистр 2703 = {register_value})")
        return {"status": "ok", "value": grid_feed_w}
    except Exception as e:
        logger.error(
            f" Unhandled error during periodic data collection: {e}",
            exc_info=True,
        )




async def send_vebus_soc_command(app: FastAPI, battery_level_percent: int):
    modbus_client = await ensure_modbus_connected(app)
    if modbus_client is None: 
        return {"status": "error", "message": "Modbus client not available"}
    try:
        scaled_value = int(battery_level_percent * 10)
        await modbus_client.write_register(
            address=2901,  # адрес регистра VE.Bus SoC
            value=scaled_value,
            slave =INVERTER_ID
        )
        global error_count
        error_count = 0
        return {"status": "ok"}
    except Exception as e:
        logger.error(
            f" Unhandled error during periodic data collection: {e}",
            exc_info=True,
        )



async def send_dvcc_max_charge_current_command(app: FastAPI, charge_battery_value: int):
    modbus_client = await ensure_modbus_connected(app)
    if modbus_client is None: 
        return {"status": "error", "message": "Modbus client not available"}
        
    try:
        slave = INVERTER_ID
        value = charge_battery_value
        # Проверка границ значений int16
        if not -32768 <= value <= 32767:
            raise HTTPException(status_code=400, detail="Значение выходит за пределы int16")
        # Преобразуем в формат Modbus (uint16) для передачи
        if value < 0:
            register_value = (1 << 16) + value  # преобразуем -1 в 0xFFFF
        else:
            register_value = value
        # Запись в регистр
        await modbus_client.write_register(address=2705, value=register_value, slave=slave)

        logger.debug(f"✅ Установлен DVCC max charge current: {value} A (регистр 2705 = {register_value})")
        return {"status": "ok", "value": value}
    except Exception as e:
        logger.error(
            f" Unhandled error during periodic data collection: {e}",
            exc_info=True,
        )



async def get_averaged_measurements_service(
    db: AsyncSession,
    object_name: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    intervals: int = 60
) -> List[CerboMeasurementResponse]:
    if not start_date or not end_date:
        raise ValueError("Необходимо указать start_date и end_date")

    # Получаем все данные за период одним запросом
    query = select(CerboMeasurement).where(
        CerboMeasurement.measured_at >= start_date,
        CerboMeasurement.measured_at <= end_date
    )
    
    if object_name:
        query = query.where(CerboMeasurement.object_name == object_name)
    
    result = await db.execute(query)
    all_measurements = result.scalars().all()

    if not all_measurements:
        return []

    # Группируем измерения по интервалам
    interval_size = (end_date - start_date) / intervals
    grouped_measurements = [[] for _ in range(intervals)]
    
    for measurement in all_measurements:
        interval_idx = min(
            int((measurement.measured_at - start_date) / interval_size),
            intervals - 1
        )
        grouped_measurements[interval_idx].append(measurement)

    # Вычисляем средние значения
    averaged_results = []
    for i, measurements in enumerate(grouped_measurements):
        if not measurements:
            continue
            
        interval_start = start_date + i * interval_size
        
        def avg(field):
            values = [getattr(m, field) for m in measurements if getattr(m, field) is not None]
            return sum(values) / len(values) if values else None

        base = measurements[0]
        averaged_results.append(CerboMeasurementResponse(
            id=base.id,
            created_at=base.created_at,
            measured_at=interval_start,
            object_name=base.object_name,
            general_battery_power=avg("general_battery_power"),
            inverter_total_ac_output=avg("inverter_total_ac_output"),
            ess_total_input_power=avg("ess_total_input_power"),
            solar_total_pv_power=avg("solar_total_pv_power"),
            soc=avg("soc")
        ))

    return averaged_results    


async def get_energy_measurements_service(
    db: AsyncSession,
    object_name: Optional[str],
    start_date: datetime,
    end_date: datetime,
    interval_minutes: int = 30
) -> dict:
    if not start_date or not end_date:
        raise ValueError("Необходимо указать start_date и end_date")

    # Округляем начало и конец до ближайшего часа
    rounded_start = start_date.replace(minute=0, second=0, microsecond=0)
    rounded_end = end_date.replace(minute=0, second=0, microsecond=0)
    
    # Создаем интервалы с округлением до ровных временных отметок
    current_interval_start = rounded_start
    intervals = []
    
    while current_interval_start < rounded_end:
        current_interval_end = current_interval_start + timedelta(minutes=interval_minutes)
        intervals.append({
            "start": current_interval_start,
            "end": current_interval_end,
            "measurements": [],
            "measurement_count": 0,
            "has_sufficient_data": False
        })
        current_interval_start = current_interval_end

    # Загружаем все измерения
    query = (
        select(CerboMeasurement)
        .where(CerboMeasurement.measured_at >= rounded_start,
               CerboMeasurement.measured_at <= rounded_end)
        .order_by(CerboMeasurement.measured_at.asc())
    )
    if object_name:
        query = query.where(CerboMeasurement.object_name == object_name)

    result = await db.execute(query)
    all_measurements = result.scalars().all()

    # Распределяем измерения по интервалам и считаем количество
    for measurement in all_measurements:
        for interval in intervals:
            if interval["start"] <= measurement.measured_at < interval["end"]:
                interval["measurements"].append(measurement)
                interval["measurement_count"] += 1
                break

    results = []
    total_solar = 0.0
    total_load = 0.0
    total_grid_import = 0.0
    total_grid_export = 0.0
    total_battery = 0.0

    # Считаем энергию по каждому интервалу
    for interval in intervals:
        measurements = interval["measurements"]
        
        # Помечаем интервалы с достаточным количеством данных (≥3 измерений)
        interval["has_sufficient_data"] = len(measurements) >= 3
        
        if len(measurements) < 2:
            # Возвращаем интервал с нулевыми значениями, но с информацией о недостатке данных
            results.append({
                "interval_start": interval["start"],
                "interval_end": interval["end"],
                "solar_energy_kwh": 0.0,
                "load_energy_kwh": 0.0,
                "grid_energy_kwh": 0.0,
                "battery_energy_kwh": 0.0,
                "measurement_count": interval["measurement_count"],
                "has_sufficient_data": interval["has_sufficient_data"]
            })
            continue

        solar_energy = 0.0
        load_energy = 0.0
        grid_energy = 0.0
        battery_energy = 0.0

        for j in range(1, len(measurements)):
            prev = measurements[j - 1]
            curr = measurements[j]
            delta_h = (curr.measured_at - prev.measured_at).total_seconds() / 3600.0

            if prev.solar_total_pv_power is not None:
                solar_energy += (prev.solar_total_pv_power / 1000.0) * delta_h
            if prev.inverter_total_ac_output is not None:
                load_energy += (prev.inverter_total_ac_output / 1000.0) * delta_h
            if prev.ess_total_input_power is not None:
                grid_power = (prev.ess_total_input_power / 1000.0) * delta_h
                grid_energy += grid_power
                if grid_power >= 0:
                    total_grid_import += grid_power
                else:
                    total_grid_export += abs(grid_power)
            if prev.general_battery_power is not None:
                battery_energy += (prev.general_battery_power / 1000.0) * delta_h

        results.append({
            "interval_start": interval["start"],
            "interval_end": interval["end"],
            "solar_energy_kwh": round(solar_energy, 3),
            "load_energy_kwh": round(load_energy, 3),
            "grid_energy_kwh": round(grid_energy, 3),
            "battery_energy_kwh": round(battery_energy, 3),
            "measurement_count": interval["measurement_count"],
            "has_sufficient_data": interval["has_sufficient_data"]
        })

        if interval["has_sufficient_data"]:
            total_solar += solar_energy
            total_load += load_energy
            total_battery += battery_energy

    return {
        "intervals": results,
        "totals": {
            "solar_energy_total": round(total_solar, 0),
            "load_energy_total": round(total_load, 0),
            "grid_import_total": round(total_grid_import, 0),
            "grid_export_total": round(total_grid_export, 0),
            "battery_energy_total": round(total_battery, 0),
        }
    }