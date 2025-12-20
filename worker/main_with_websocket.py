"""
Главная точка входа для modbus_worker с поддержкой WebSocket сервера для устройств.
Запускает два процесса параллельно:
1. Worker для сбора данных с Modbus устройств
2. WebSocket сервер для подключения устройств
"""
import asyncio
import uvicorn
from loguru import logger
from cor_pass.config.config import settings


async def run_worker():
    """Запускает основной worker для Modbus"""
    from worker.main import main_worker_entrypoint
    logger.info("Starting Modbus worker...")
    await main_worker_entrypoint()


async def run_websocket_server():
    """Запускает WebSocket сервер для устройств"""
    from worker.websocket_app import app
    logger.info("Starting WebSocket server for devices...")
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=45762,  # Отдельный порт для WebSocket сервера
        log_level="info",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def _supervise(coro_fn, name: str, restart_delay: float = 5.0):
    """Надзор за задачей: при падении перезапускает, чтобы контейнер не умирал."""
    while True:
        try:
            await coro_fn()
        except asyncio.CancelledError:
            logger.info(f"{name} cancelled, stopping supervisor loop")
            raise
        except Exception as e:
            logger.error(f"{name} crashed: {e}. Restarting in {restart_delay}s", exc_info=True)
            await asyncio.sleep(restart_delay)


async def main():
    """Запускает оба сервиса параллельно"""
    logger.info("Starting modbus_worker with WebSocket support...")
    
    # Инициализируем Telegram бот для мониторинга батарей (только для development)
    if settings.app_env == "development":
        try:
            from worker.telegram_bot import init_telegram_monitor, start_commands_handler_task
            logger.info("🤖 Initializing Telegram battery monitor (development mode)...")
            telegram_initialized = await init_telegram_monitor()
            if telegram_initialized:
                logger.info("✅ Telegram battery monitor initialized successfully")
                # Запускаем обработчик команд
                logger.info("🤖 Starting Telegram commands handler...")
                commands_task = start_commands_handler_task()
                logger.info("✅ Telegram commands handler started")
            else:
                logger.warning("⚠️ Telegram battery monitor not configured or initialization failed")
        except Exception as e:
            logger.error(f"Failed to initialize Telegram monitor: {e}", exc_info=True)
    else:
        logger.info("ℹ️ Telegram battery monitor disabled (production mode)")
    
    # Создаем задачи с надзором для обоих сервисов
    worker_task = asyncio.create_task(_supervise(run_worker, "Modbus worker"))
    websocket_task = asyncio.create_task(_supervise(run_websocket_server, "WebSocket server"))

    try:
        await asyncio.gather(worker_task, websocket_task)
    except KeyboardInterrupt:
        logger.info("Shutting down services...")
        worker_task.cancel()
        websocket_task.cancel()
        try:
            await asyncio.gather(worker_task, websocket_task, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        logger.info("Services stopped")


if __name__ == "__main__":
    if settings.app_env == "development":
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("Application stopped by user")
        except Exception as e:
            logger.error(f"Application crashed: {e}", exc_info=True)
