import asyncio
from datetime import datetime, time as dt_time
from typing import Optional
from uuid import uuid4

from loguru import logger
from cor_pass.database.db import async_session_maker
from cor_pass.schemas import FullDeviceMeasurementCreate
from worker.modbus_client import (
    get_modbus_client_singleton
)
from worker.data_collector import (
    collect_battery_data,
    collect_inverter_power_data,
    collect_ess_ac_data,
    get_solarchargers_current_sum,
    get_battery_status,
    send_grid_feed_w_command,
)
from worker.db_operations import create_full_device_measurement, get_all_schedules, update_schedule_is_active_status
from worker.schedule_task import send_dvcc_max_charge_current_command, send_vebus_soc_command
from cor_pass.config.config import settings



DEFAULT_grid_feed_kw = 70000
DEFAULT_battery_level_percent = 30
DEFAULT_charge_battery_value = 300

COLLECTION_INTERVAL_SECONDS = 2
SCHEDULE_CHECK_INTERVAL_SECONDS = 3

current_active_schedule_id: Optional[str] = None

async def set_inverter_parameters(
    object_id: str,
    grid_feed_w: int,
    battery_level_percent: int,
    charge_battery_value: int
):
    modbus_client_instance = await get_modbus_client_singleton()
    if not modbus_client_instance:
        logger.error(f"[{object_id}] Не удалось получить Modbus клиент для установки параметров инвертора.")
        return

    if settings.app_env == "development":
        await send_grid_feed_w_command(modbus_client=modbus_client_instance, grid_feed_w=grid_feed_w)
        await send_vebus_soc_command(modbus_client=modbus_client_instance, battery_level_percent=battery_level_percent)
        await send_dvcc_max_charge_current_command(modbus_client=modbus_client_instance, charge_battery_value=charge_battery_value)


async def cerbo_collection_task_worker(object_id: str, object_name: str):
    while True:
        transaction_id = uuid4()
        modbus_client_instance = await get_modbus_client_singleton()

        try:
            if not modbus_client_instance or not modbus_client_instance.connected:
                logger.critical(f"[{object_id}] [{transaction_id}] Modbus client not connected. Skipping cycle.")
                await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)
                continue

            collected_data = {}

            try:
                collected_data.update(await collect_battery_data(modbus_client_instance, transaction_id))
            except Exception:
                pass
            try:
                collected_data.update(await collect_inverter_power_data(modbus_client_instance, transaction_id))
            except Exception:
                pass
            try:
                collected_data.update(await collect_ess_ac_data(modbus_client_instance, transaction_id))
            except Exception:
                pass
            try:
                collected_data.update(await get_solarchargers_current_sum(modbus_client_instance, transaction_id))
            except Exception:
                pass
            try:
                collected_data.update(await get_battery_status(modbus_client_instance, transaction_id))
            except Exception:
                pass

            if not collected_data:
                logger.warning(f"[{object_id}] [{transaction_id}] No data collected. Skipping save.")
                await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)
                continue

            collected_data["measured_at"] = datetime.now()
            collected_data["object_name"] = object_name  # связываем с объектом
            collected_data["energetic_object_id"] = object_id

            required_fields = ["general_battery_power", "inverter_total_ac_output", "ess_total_input_power", "solar_total_pv_power", "measured_at", "object_name", "soc"]
            missing_fields = [f for f in required_fields if f not in collected_data or collected_data[f] is None]
            if missing_fields:
                logger.error(f"[{object_id}] Missing fields: {missing_fields}. Skipping save.", extra={"collected_data": collected_data})
                await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)
                continue

            full_measurement = FullDeviceMeasurementCreate(**collected_data)
            async with async_session_maker() as db:
                await create_full_device_measurement(db=db, data=full_measurement)

        except Exception as e:
            logger.error(f"[{object_id}] Error in collection task: {e}", exc_info=True)

        await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)


async def energetic_schedule_task_worker(object_id: str):
    current_active_schedule_id: str | None = None

    while True:
        try:
            async with async_session_maker() as db:
                all_schedules = await get_all_schedules(db)
                # фильтруем только для этого объекта
                object_schedules = [s for s in all_schedules if s.energetic_object_id == object_id]

                operational_schedules = [s for s in object_schedules if not s.is_manual_mode]
                now_time = datetime.now().time()

                active_schedule = None
                for schedule in operational_schedules:
                    if schedule.start_time <= schedule.end_time:
                        if schedule.start_time <= now_time < schedule.end_time:
                            active_schedule = schedule
                            break
                    else:
                        if now_time >= schedule.start_time or now_time < schedule.end_time:
                            active_schedule = schedule
                            break

                if active_schedule:
                    if active_schedule.id != current_active_schedule_id:
                        # деактивация предыдущей
                        if current_active_schedule_id:
                            await update_schedule_is_active_status(db, current_active_schedule_id, False)
                        current_active_schedule_id = active_schedule.id
                        # установка параметров инвертора для объекта
                        await set_inverter_parameters(
                            object_id,
                            active_schedule.grid_feed_w,
                            active_schedule.battery_level_percent,
                            active_schedule.charge_battery_value,
                        )
                        await update_schedule_is_active_status(db, active_schedule.id, True)
                else:
                    # сброс к дефолтным параметрам
                    if current_active_schedule_id:
                        await update_schedule_is_active_status(db, current_active_schedule_id, False)
                        current_active_schedule_id = None
                    await set_inverter_parameters(object_id, DEFAULT_grid_feed_kw, DEFAULT_battery_level_percent, DEFAULT_charge_battery_value)

        except Exception as e:
            logger.error(f"[{object_id}] Error in schedule task: {e}", exc_info=True)

        await asyncio.sleep(SCHEDULE_CHECK_INTERVAL_SECONDS)