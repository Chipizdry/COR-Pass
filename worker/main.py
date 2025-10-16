import asyncio
from datetime import datetime, time as dt_time
from typing import Optional
from uuid import uuid4

from loguru import logger
from sqlalchemy import select
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
from cor_pass.database.models import EnergeticObject
from worker.schedule_task import send_dvcc_max_charge_current_command, send_vebus_soc_command
from cor_pass.config.config import settings
from worker.worker_manager import WorkerManager


DEFAULT_grid_feed_kw = 70000
DEFAULT_battery_level_percent = 30
DEFAULT_charge_battery_value = 300

COLLECTION_INTERVAL_SECONDS = 2
SCHEDULE_CHECK_INTERVAL_SECONDS = 3

current_active_schedule_id: Optional[str] = None


CHECK_INTERVAL = 5
worker_manager = WorkerManager()

async def main_worker_entrypoint():
    while True:
        try:
            async with async_session_maker() as db:
                result = await db.execute(
                    select(EnergeticObject).where(EnergeticObject.is_active == True)
                )
                active_objects = result.scalars().all()

                # запуск новых воркеров
                for energy_obj in active_objects:
                    object_id = energy_obj.id
                    object_name = energy_obj.name
                    if energy_obj.id not in worker_manager.tasks:
                        await worker_manager.start_worker(object_id=object_id, object_name=object_name)

                # остановка неактивных
                for obj_id in list(worker_manager.tasks.keys()):
                    if obj_id not in [o.id for o in active_objects]:
                        await worker_manager.stop_worker(obj_id)

        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)

        await asyncio.sleep(CHECK_INTERVAL)

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