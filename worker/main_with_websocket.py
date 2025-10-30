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
        port=8003,  # Отдельный порт для WebSocket сервера
        log_level="info",
        loop="asyncio"
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """Запускает оба сервиса параллельно"""
    logger.info("Starting modbus_worker with WebSocket support...")
    
    # Создаем задачи для обоих сервисов
    worker_task = asyncio.create_task(run_worker())
    websocket_task = asyncio.create_task(run_websocket_server())
    
    try:
        # Ждем завершения обеих задач
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
