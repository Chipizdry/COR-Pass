import asyncio
from datetime import datetime, time as dt_time
from typing import Optional
from uuid import uuid4

from loguru import logger
from cor_pass.database.db import async_session_maker
from cor_pass.schemas import FullDeviceMeasurementCreate
from worker.modbus_client import (
    create_modbus_client_singleton,
    get_modbus_client_singleton, 
    MODBUS_IP, 
    MODBUS_PORT
)
from worker.data_collector import (
    collect_battery_data,
    collect_inverter_power_data,
    collect_ess_ac_data,
    collect_solarchargers_data,
    get_battery_status,
    read_dvcc_max_charge_current,
    read_grid_feed_w,
    read_vebus_soc,
    send_grid_feed_w_command,
)
from worker.db_operations import create_full_device_measurement, get_all_schedules, update_schedule_is_active_status
from cor_pass.database.models import EnergeticSchedule
from worker.schedule_task import send_dvcc_max_charge_current_command, send_vebus_soc_command
from cor_pass.config.config import settings
DEFAULT_grid_feed_kw = 70000
DEFAULT_battery_level_percent = 30
DEFAULT_charge_battery_value = 300

COLLECTION_INTERVAL_SECONDS = 2
SCHEDULE_CHECK_INTERVAL_SECONDS = 3

current_active_schedule_id: Optional[str] = None

async def set_inverter_parameters(
    grid_feed_w: int, battery_level_percent: int, charge_battery_value: int
):
    modbus_client_instance = await get_modbus_client_singleton()
    if not modbus_client_instance:
        logger.error("Не удалось получить Modbus клиент для установки параметров инвертора.")
        return

    # logger.debug(f"\n--- Sending parameters to inverter ---")
    if settings.app_env == "development":
        await send_grid_feed_w_command(modbus_client=modbus_client_instance, grid_feed_w=grid_feed_w)
        await send_vebus_soc_command(modbus_client=modbus_client_instance, battery_level_percent=battery_level_percent)
        await send_dvcc_max_charge_current_command(modbus_client=modbus_client_instance, charge_battery_value=charge_battery_value)
    # logger.debug("--------------------------------------")


async def cerbo_collection_task_worker():
    """
    Фоновая задача, которая запускает сбор данных с Modbus и сохраняет их напрямую в базу данных.
    Работает в бесконечном цикле с паузами.
    """
    while True:
        current_transaction_id = uuid4()
        modbus_client_instance = await get_modbus_client_singleton()

        try:
            if not modbus_client_instance or not modbus_client_instance.connected:
                logger.critical(f"[{current_transaction_id}] Modbus client not connected. Skipping this cycle.")
                await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)
                continue

            collected_data = {}

            try:
                collected_data.update(await collect_battery_data(modbus_client_instance, current_transaction_id))
            except Exception:
                pass

            try:
                collected_data.update(await collect_inverter_power_data(modbus_client_instance, current_transaction_id))
            except Exception:
                pass

            try:
                collected_data.update(await collect_ess_ac_data(modbus_client_instance, current_transaction_id))
            except Exception:
                pass

            try:
                collected_data.update(await collect_solarchargers_data(modbus_client_instance, current_transaction_id))
            except Exception:
                pass

            try:
                collected_data.update(await get_battery_status(modbus_client_instance, current_transaction_id))
            except Exception:
                pass

            if not collected_data:
                logger.warning(
                    f"[{current_transaction_id}] No data collected from any Modbus device. Skipping database save."
                )
                await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)
                continue

            final_data_for_pydantic = collected_data
            final_data_for_pydantic["measured_at"] = datetime.now()
            final_data_for_pydantic["object_name"] = "COR-AZK"

            required_fields = ["general_battery_power", "inverter_total_ac_output", "ess_total_input_power", "solar_total_pv_power", "measured_at", "object_name", "soc"]
            missing_fields = [
                field for field in required_fields if field not in final_data_for_pydantic or final_data_for_pydantic[field] is None
            ]
            
            if missing_fields:
                logger.error(
                    f"[{current_transaction_id}] Incomplete data for FullDeviceMeasurementCreate. Missing: {missing_fields}. Skipping save.",
                    extra={"missing_fields": missing_fields, "collected_data": final_data_for_pydantic},
                )
                await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)
                continue

            full_measurement = FullDeviceMeasurementCreate(**final_data_for_pydantic)
            
            async with async_session_maker() as db:
                await create_full_device_measurement(db=db, data=full_measurement)
            
        except Exception as e:
            logger.error(
                f"[{current_transaction_id}] Unhandled error during periodic data collection: {e}",
                exc_info=True,
            )
        finally:
            await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)


async def energetic_schedule_task_worker(async_session_maker):
    """
    Фоновая задача для проверки и применения энергетического расписания.
    """
    global current_active_schedule_id

    while True:
        try:
            current_check_time = datetime.now()
            # logger.debug(f"[{current_check_time.strftime('%H:%M:%S')}] Checking schedule and current parameters...")

            async with async_session_maker() as db_session:
                all_schedules = await get_all_schedules(db_session)

                operational_schedules = [
                    s for s in all_schedules if not s.is_manual_mode
                ]

                current_time = current_check_time.time()

                desired_grid_feed_w: int
                desired_battery_level_percent: int
                desired_charge_battery_value: int
                
                active_auto_schedule_for_now: Optional[EnergeticSchedule] = None

                for schedule in operational_schedules:
                    if schedule.start_time <= schedule.end_time:
                        if schedule.start_time <= current_time < schedule.end_time:
                            active_auto_schedule_for_now = schedule
                            break
                    else: 
                        if (current_time >= schedule.start_time or current_time < schedule.end_time):
                            active_auto_schedule_for_now = schedule
                            break

                if active_auto_schedule_for_now:
                    desired_grid_feed_w = active_auto_schedule_for_now.grid_feed_w
                    desired_battery_level_percent = active_auto_schedule_for_now.battery_level_percent
                    desired_charge_battery_value = active_auto_schedule_for_now.charge_battery_value
                    
                    if active_auto_schedule_for_now.id != current_active_schedule_id:
                        logger.debug(f"New active schedule found: ID {active_auto_schedule_for_now.id}. Activating.")
                        if current_active_schedule_id is not None:
                            await update_schedule_is_active_status(
                                db=db_session,
                                schedule_id=current_active_schedule_id,
                                is_active_status=False,
                            )
                        current_active_schedule_id = active_auto_schedule_for_now.id
                        await set_inverter_parameters(
                            grid_feed_w=desired_grid_feed_w,
                            battery_level_percent=desired_battery_level_percent,
                            charge_battery_value=desired_charge_battery_value,
                        )
                        await update_schedule_is_active_status(
                            db=db_session,
                            schedule_id=active_auto_schedule_for_now.id,
                            is_active_status=True,
                        )
                    else:
                        # logger.debug(f"Automatic schedule {active_auto_schedule_for_now.id} is active. Checking parameter actuality.")
                        pass

                else: 
                    desired_grid_feed_w = DEFAULT_grid_feed_kw
                    desired_battery_level_percent = DEFAULT_battery_level_percent
                    desired_charge_battery_value = DEFAULT_charge_battery_value

                    if current_active_schedule_id is not None:
                        # logger.info("Current time is outside any schedule. Reverting to default parameters.")
                        await update_schedule_is_active_status(
                            db=db_session,
                            schedule_id=current_active_schedule_id,
                            is_active_status=False,
                        )
                        current_active_schedule_id = None
                    else:
                        # logger.debug("Current time is outside any schedule. Inverter is already at default parameters (or should be).")
                        pass


            # logger.debug("Reading current Modbus register values...")
            actual_grid_feed_w = await read_grid_feed_w(await get_modbus_client_singleton())
            actual_battery_level_percent = await read_vebus_soc(await get_modbus_client_singleton())
            actual_charge_battery_value = await read_dvcc_max_charge_current(await get_modbus_client_singleton())


            if (actual_grid_feed_w is None or 
                actual_battery_level_percent is None or 
                actual_charge_battery_value is None):
                # logger.warning("Failed to read all actual values from Modbus. Skipping check and retrying.")
                pass
            else:
                needs_update = False
                if actual_grid_feed_w != desired_grid_feed_w:
                    # logger.debug(f"Mismatch AC Power Setpoint Fine: desired={desired_grid_feed_w}, actual={actual_grid_feed_w}")
                    needs_update = True
                if actual_battery_level_percent != desired_battery_level_percent:
                    # logger.debug(f"Mismatch VE.Bus SoC: desired={desired_battery_level_percent}, actual={actual_battery_level_percent}")
                    needs_update = True
                if actual_charge_battery_value != desired_charge_battery_value:
                    # logger.debug(f"Mismatch DVCC max charge current: desired={desired_charge_battery_value}, actual={actual_charge_battery_value}")
                    needs_update = True

                if needs_update:
                    # logger.warning("Inverter parameter mismatch detected. Sending actual values.")
                    await set_inverter_parameters(
                        grid_feed_w=desired_grid_feed_w,
                        battery_level_percent=desired_battery_level_percent,
                        charge_battery_value=desired_charge_battery_value,
                    )
                else:
                    # logger.debug("Inverter parameters match schedule/default values.")
                    pass


            for schedule in all_schedules:
                if (
                    not schedule.is_manual_mode
                    and schedule.id != current_active_schedule_id
                    and schedule.is_active
                ):
                    # logger.warning(f"Schedule {schedule.id} is active, but not current. Deactivating.")
                    await update_schedule_is_active_status(
                        db=db_session,
                        schedule_id=schedule.id,
                        is_active_status=False,
                    )

        except Exception as e:
            logger.error(
                f"Ошибка в фоновой задаче energetic_schedule_task: {e}", exc_info=True
            )

        await asyncio.sleep(SCHEDULE_CHECK_INTERVAL_SECONDS)


async def main_worker_entrypoint():
    logger.info("Modbus Worker starting up...")
    modbus_client_instance = await create_modbus_client_singleton()
    
    if not modbus_client_instance:
        logger.error("Failed to establish initial Modbus connection. Worker will not start tasks.")
        return

    await asyncio.gather(
        cerbo_collection_task_worker(), 
        energetic_schedule_task_worker(async_session_maker=async_session_maker)
    )

if __name__ == "__main__":
    DEFAULT_grid_feed_kw = 70000
    DEFAULT_battery_level_percent = 30
    DEFAULT_charge_battery_value = 300
    current_active_schedule_id: Optional[str] = None
    if settings.app_env == "development":
        try:
            asyncio.run(main_worker_entrypoint())
        except KeyboardInterrupt:
            logger.info("Modbus Worker stopped by user.")
        except Exception as e:
            logger.error(f"Modbus Worker crashed: {e}", exc_info=True)