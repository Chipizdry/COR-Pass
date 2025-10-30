"""
Менеджер WebSocket соединений для устройств в modbus_worker контейнере.
"""
import asyncio
import json
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger


class DeviceWebSocketManager:
    """Управляет WebSocket соединениями с устройствами"""
    
    def __init__(self):
        # Словарь активных соединений: device_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # Словарь данных от устройств: device_id -> dict
        self.device_data: Dict[str, dict] = {}
        # Очередь команд для отправки: device_id -> list of commands
        self.command_queue: Dict[str, asyncio.Queue] = {}
    
    async def connect(self, device_id: str, websocket: WebSocket):
        """Регистрирует новое WebSocket соединение"""
        await websocket.accept()
        self.active_connections[device_id] = websocket
        self.command_queue[device_id] = asyncio.Queue()
        logger.info(f"Device {device_id} connected via WebSocket")
    
    def disconnect(self, device_id: str):
        """Удаляет WebSocket соединение"""
        if device_id in self.active_connections:
            del self.active_connections[device_id]
        if device_id in self.device_data:
            del self.device_data[device_id]
        if device_id in self.command_queue:
            del self.command_queue[device_id]
        logger.info(f"Device {device_id} disconnected")
    
    async def receive_data(self, device_id: str, data: str):
        """Обрабатывает данные от устройства"""
        try:
            json_data = json.loads(data)
            self.device_data[device_id] = json_data
            logger.debug(f"Received data from device {device_id}: {json_data}")
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from device {device_id}: {data}")
    
    async def send_command(self, device_id: str, command: dict) -> bool:
        """
        Добавляет команду в очередь для отправки устройству.
        Возвращает True если устройство подключено, False иначе.
        """
        if device_id in self.command_queue:
            await self.command_queue[device_id].put(command)
            logger.info(f"Command queued for device {device_id}: {command}")
            return True
        else:
            logger.warning(f"Device {device_id} not connected, command not queued")
            return False
    
    async def process_command_queue(self, device_id: str):
        """
        Фоновая задача для обработки очереди команд для конкретного устройства.
        Постоянно отслеживает очередь и отправляет команды устройству.
        """
        websocket = self.active_connections.get(device_id)
        if not websocket:
            logger.error(f"No websocket found for device {device_id}")
            return
        
        queue = self.command_queue.get(device_id)
        if not queue:
            logger.error(f"No command queue found for device {device_id}")
            return
        
        logger.info(f"Starting command queue processor for device {device_id}")
        
        try:
            while device_id in self.active_connections:
                try:
                    # Ждем команду из очереди с таймаутом
                    command = await asyncio.wait_for(queue.get(), timeout=1.0)
                    
                    # Отправляем команду устройству
                    await websocket.send_json(command)
                    logger.info(f"Command sent to device {device_id}: {command}")
                    
                except asyncio.TimeoutError:
                    # Таймаут - продолжаем ждать
                    continue
                except Exception as e:
                    logger.error(f"Error sending command to device {device_id}: {e}")
                    break
        except Exception as e:
            logger.error(f"Command queue processor error for device {device_id}: {e}")
        finally:
            logger.info(f"Command queue processor stopped for device {device_id}")
    
    def get_connected_devices(self) -> list:
        """Возвращает список ID подключенных устройств"""
        return list(self.active_connections.keys())
    
    def get_device_data(self, device_id: str) -> Optional[dict]:
        """Возвращает последние данные от устройства"""
        return self.device_data.get(device_id)
    
    def is_connected(self, device_id: str) -> bool:
        """Проверяет, подключено ли устройство"""
        return device_id in self.active_connections


# Глобальный экземпляр менеджера
device_ws_manager = DeviceWebSocketManager()
