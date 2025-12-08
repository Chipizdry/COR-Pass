#тест удалённого файла: worker/device_background_tasks.py 
# 
# 
# """
# Фоновые задачи для работы с устройствами через WebSocket.
# """
# import asyncio
# from datetime import datetime
# from loguru import logger
# from sqlalchemy import select

# from cor_pass.database.db import async_session_maker
# from cor_pass.database.models import Device
# from worker.device_websocket_manager import device_ws_manager


# async def periodic_device_ping_task(interval_seconds: int = 30):
#     """
#     Фоновая задача для периодической отправки ping сообщений всем подключенным устройствам.
#     Помогает поддерживать соединение активным и проверять состояние устройств.
    
#     Args:
#         interval_seconds: Интервал между отправкой ping сообщений (по умолчанию 30 секунд)
#     """
#     logger.info(f"Starting periodic device ping task (interval: {interval_seconds}s)")
    
#     while True:
#         try:
#             await asyncio.sleep(interval_seconds)
            
#             connected_devices = device_ws_manager.get_connected_devices()
            
#             if connected_devices:
#                 logger.debug(f"Sending ping to {len(connected_devices)} devices")
                
#                 for device_id in connected_devices:
#                     ping_command = {
#                         "type": "ping",
#                         "timestamp": datetime.now().isoformat()
#                     }
#                     await device_ws_manager.send_command(device_id, ping_command)
            
#         except Exception as e:
#             logger.error(f"Error in periodic ping task: {e}", exc_info=True)
#             await asyncio.sleep(5)  # Короткая пауза перед повтором при ошибке


# async def device_status_sync_task(interval_seconds: int = 60):
#     """
#     Фоновая задача для синхронизации статуса устройств с базой данных.
#     Периодически запрашивает статус у подключенных устройств.
    
#     Args:
#         interval_seconds: Интервал между синхронизациями (по умолчанию 60 секунд)
#     """
#     logger.info(f"Starting device status sync task (interval: {interval_seconds}s)")
    
#     while True:
#         try:
#             await asyncio.sleep(interval_seconds)
            
#             connected_devices = device_ws_manager.get_connected_devices()
            
#             if connected_devices:
#                 logger.info(f"Syncing status for {len(connected_devices)} devices")
                
#                 for device_id in connected_devices:
#                     status_command = {
#                         "type": "get_status",
#                         "timestamp": datetime.now().isoformat()
#                     }
#                     await device_ws_manager.send_command(device_id, status_command)
            
#         except Exception as e:
#             logger.error(f"Error in status sync task: {e}", exc_info=True)
#             await asyncio.sleep(5)


# async def scheduled_command_processor_task(interval_seconds: int = 10):
#     """
#     Фоновая задача для обработки запланированных команд из базы данных.
#     Проверяет наличие команд, которые нужно отправить устройствам.
    
#     Это пример - вы можете создать таблицу в БД для хранения запланированных команд.
    
#     Args:
#         interval_seconds: Интервал проверки команд (по умолчанию 10 секунд)
#     """
#     logger.info(f"Starting scheduled command processor task (interval: {interval_seconds}s)")
    
#     while True:
#         try:
#             await asyncio.sleep(interval_seconds)
            
#             # async with async_session_maker() as db:
#             #     pending_commands = await get_pending_commands(db)
#             #     for cmd in pending_commands:
#             #         if device_ws_manager.is_connected(cmd.device_id):
#             #             await device_ws_manager.send_command(cmd.device_id, cmd.command)
#             #             await mark_command_as_sent(db, cmd.id)
            
#             pass
            
#         except Exception as e:
#             logger.error(f"Error in scheduled command processor: {e}", exc_info=True)
#             await asyncio.sleep(5)


# async def device_data_logger_task(interval_seconds: int = 300):
#     """
#     Фоновая задача для логирования данных от устройств.
#     Периодически сохраняет последние данные от устройств в лог.
    
#     Args:
#         interval_seconds: Интервал логирования (по умолчанию 300 секунд / 5 минут)
#     """
#     logger.info(f"Starting device data logger task (interval: {interval_seconds}s)")
    
#     while True:
#         try:
#             await asyncio.sleep(interval_seconds)
            
#             connected_devices = device_ws_manager.get_connected_devices()
            
#             for device_id in connected_devices:
#                 device_data = device_ws_manager.get_device_data(device_id)
#                 if device_data:
#                     logger.info(f"Device {device_id} data: {device_data}")
            
#         except Exception as e:
#             logger.error(f"Error in data logger task: {e}", exc_info=True)
#             await asyncio.sleep(5)



# async def start_background_tasks():
#     """
#     Запускает все фоновые задачи для работы с устройствами.
#     Вызывается при старте приложения.
#     """
#     logger.info("Starting device background tasks...")
    
#     tasks = [
#         asyncio.create_task(periodic_device_ping_task(interval_seconds=30)),
#         asyncio.create_task(device_status_sync_task(interval_seconds=60)),
#         asyncio.create_task(scheduled_command_processor_task(interval_seconds=10)),
#         asyncio.create_task(device_data_logger_task(interval_seconds=300)),
#     ]
    
#     logger.info(f"Started {len(tasks)} background tasks for device management")
    
#     return tasks
