import asyncio
from typing import Optional

from loguru import logger
from cor_pass.config.config import settings
from worker.polling_manager import PollingManager


CHECK_INTERVAL = 5
polling_manager = PollingManager()

async def main_worker_entrypoint():
    """
    Главный цикл воркера
    Периодически синхронизирует задачи опроса из БД
    """
    try:
        while True:
            try:
                # Перезагружаем задачи из БД
                await polling_manager.reload_tasks_from_db()
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)

            await asyncio.sleep(CHECK_INTERVAL)
    finally:
        # Закрываем все Modbus клиенты при остановке
        from worker.modbus_client import close_all_modbus_clients
        logger.info("🛑 Shutting down worker, closing all Modbus clients...")
        await close_all_modbus_clients()

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