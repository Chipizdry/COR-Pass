from datetime import datetime, timezone
from typing import List, Dict
import uuid
from fastapi import WebSocket, WebSocketDisconnect, status
import logging
import json

from fastapi.websockets import WebSocketState

from loguru import logger

def get_websocket_client_ip(websocket: WebSocket) -> str:
    """
    Получение реального IP-адреса клиента WebSocket из scope.
    Аналогично get_client_ip для HTTP-запросов, но адаптировано под WebSocket.
    """
    scope = websocket.scope
    headers = {k.decode("utf-8"): v.decode("utf-8") for k, v in scope["headers"]}

    if "x-forwarded-for" in headers:
        client_ip = headers["x-forwarded-for"].split(",")[0].strip()
    elif "x-real-ip" in headers:
        client_ip = headers["x-real-ip"].strip()
    elif "http_client_ip" in headers:
        client_ip = headers["http_client_ip"].strip()
    else:
        client = scope.get("client")
        if client:
            client_ip = client[0]
        else:
            client_ip = "unknown" 

    return client_ip



class WebSocketEventsManager:
    """
    Управляет активными WebSocket-подключениями и рассылкой событий.
    """
    def __init__(self):

        self.active_connections: Dict[str, Dict] = {} 
        logger.info("WebSocketEventsManager initialized.")

    async def connect(self, websocket: WebSocket) -> str:
        """
        Устанавливает новое WebSocket-соединение и присваивает ему уникальный ID,
        а также сохраняет реальный IP клиента.
        Возвращает ID соединения.
        """
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        client_ip = get_websocket_client_ip(websocket) 

        self.active_connections[connection_id] = {
            "websocket": websocket,
            "ip": client_ip,
            "connected_at": datetime.now(timezone.utc).isoformat() 
        }
        logger.info(f"WebSocket connected from {client_ip} with ID: {connection_id}. Total active: {len(self.active_connections)}")
        return connection_id

    async def disconnect(self, connection_id: str): # <--- Сделаем её async
        """
        Закрывает WebSocket-соединение по его ID.
        """
        conn_data = self.active_connections.pop(connection_id, None)
        if conn_data:
            websocket = conn_data["websocket"]
            client_ip = conn_data["ip"] # Получаем IP из conn_data
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    # Отправляем сообщение клиенту перед закрытием (необязательно, но полезно)
                    await websocket.send_json({"event_type": "server_disconnect", "reason": "Administrative action"})
                    await websocket.close(code=1000)
                    logger.info(f"WebSocket with ID {connection_id} actively closed by manager: {client_ip}. Total active: {len(self.active_connections)}")
                except RuntimeError as e:
                    logger.warning(f"Error when actively closing WebSocket with ID {connection_id} ({client_ip}), might be already closed: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error during active close of WebSocket with ID {connection_id} ({client_ip}): {e}", exc_info=True)
            else:
                logger.info(f"WebSocket with ID {connection_id} ({client_ip}) already closed or in closing state. Total active: {len(self.active_connections)}")
        else:
            logger.warning(f"Attempted to disconnect non-existent WebSocket with ID: {connection_id}")

    async def disconnect_all(self):
        """
        Отключает все активные WebSocket-соединения.
        """
        connection_ids_to_disconnect = list(self.active_connections.keys())
        logger.info(f"Initiating disconnection of {len(connection_ids_to_disconnect)} active WebSocket connections.")

        for connection_id in connection_ids_to_disconnect:
            conn_data = self.active_connections.get(connection_id)
            if conn_data:
                websocket = conn_data["websocket"]
                client_ip = conn_data["ip"]
                try:
                    await websocket.send_json({"event_type": "server_disconnect", "reason": "All connections reset by administrative action"})
                    await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
                    logger.info(f"Force-disconnected WebSocket with ID {connection_id} from {client_ip}.")
                except RuntimeError as e:
                    logger.warning(f"Error closing WebSocket {connection_id} from {client_ip} during disconnect_all: {e} (might be already closed)")
                except Exception as e:
                    logger.error(f"Unexpected error when closing WebSocket {connection_id} from {client_ip} during disconnect_all: {e}", exc_info=True)
                finally:
                    self.active_connections.pop(connection_id, None)
            else:
                logger.warning(f"WebSocket with ID {connection_id} already removed from active_connections during disconnect_all.")

        logger.info(f"All WebSocket connections disconnection attempt complete. Total active: {len(self.active_connections)}")



    async def disconnect_by_id_internal(self, connection_id: str):
        """
        Внутренний метод для отключения по ID, безопасно удаляет из словаря.
        """
        websocket = self.active_connections.get(connection_id)
        if websocket:
            try:
                await websocket.send_json({"event_type": "disconnect_server_initiated", "reason": "Administrative action"})
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
                logger.info(f"Force-disconnected WebSocket with ID {connection_id}: {websocket.client.host}:{websocket.client.port}")
            except RuntimeError as e:
                logger.warning(f"Error closing WebSocket {connection_id}: {e} (might be already closed)")
            except Exception as e:
                logger.error(f"Unexpected error when closing WebSocket {connection_id}: {e}")
            finally:
                self.active_connections.pop(connection_id, None)
        else:
            logger.warning(f"Attempted to disconnect non-existent WebSocket (internal) with ID: {connection_id}")


    def get_active_connection_info(self) -> List[Dict]:
        """
        Возвращает информацию обо всех активных соединениях.
        """
        info = []
        for conn_id, conn_data in self.active_connections.items():
            info.append({
                "connection_id": conn_id,
                "client_host": conn_data["ip"], # Теперь используем реальный IP
                "client_port": conn_data["websocket"].client.port, # Порт все еще из websocket.client
                "connected_at": conn_data["connected_at"]
            })
        return info   
            
    async def broadcast_event(self, event_data: Dict):
        """
        Рассылает событие всем активным WebSocket-подключениям.
        """
        message = json.dumps(event_data)
        connections_to_check = list(self.active_connections.keys())
        for connection_id in connections_to_check:
            conn_data = self.active_connections.get(connection_id)
            if not conn_data:
                continue

            connection = conn_data["websocket"]
            client_ip = conn_data["ip"]

            if connection.client_state != WebSocketState.CONNECTED:
                logger.warning(f"Skipping disconnected/closing WebSocket ID {connection_id} from {client_ip}. State: {connection.client_state}")
                self.active_connections.pop(connection_id, None)
                continue

            try:
                await connection.send_text(message)
                logger.debug(f"Event sent to {client_ip}: {message}")
            except WebSocketDisconnect:
                logger.warning(f"WebSocket disconnected during broadcast: {client_ip}. Removing from list.")
                self.active_connections.pop(connection_id, None)
            except RuntimeError as e:
                logger.warning(f"RuntimeError sending to WebSocket {client_ip}: {e}. Removing.")
                self.active_connections.pop(connection_id, None)
            except Exception as e:
                logger.error(f"Error sending event to {client_ip}: {e}", exc_info=True)
                self.active_connections.pop(connection_id, None)

        logger.info(f"Broadcast complete. Total active connections after cleanup: {len(self.active_connections)}")


websocket_events_manager = WebSocketEventsManager()