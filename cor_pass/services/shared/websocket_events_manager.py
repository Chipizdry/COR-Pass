import asyncio
from datetime import datetime, timezone
import os
import socket
from typing import List, Dict, Optional
import uuid
from fastapi import WebSocket, WebSocketDisconnect, status
import json
from cor_pass.database.redis_db import redis_client
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
    """Менеджер WebSocket с Redis для многоворкеров."""

    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.active_connections: Dict[str, Dict[str, any]] = {}  # {"websocket": WebSocket, "session_id": str | None}
        logger.info(f"WebSocketEventsManager initialized for worker {worker_id}")

    async def init_redis_listener(self):
        """Запуск подписки на глобальный и персональный Redis каналы."""
        asyncio.create_task(self._listen_pubsub())

    async def _listen_pubsub(self):
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("ws:broadcast", f"ws:worker:{self.worker_id}")
        logger.info(f"Subscribed to Redis channels: ws:broadcast, ws:worker:{self.worker_id}")

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                channel = message["channel"]
                data = json.loads(message["data"])
                # logger.debug(f"Received message from Redis channel {channel}: {data}")
                
                if channel == "ws:broadcast":
                    await self._broadcast_to_local(data)
                else:
                    # Targeted message
                    connection_id = data["connection_id"]
                    event = data["event"]
                    logger.debug(f"Processing targeted message for connection {connection_id}")
                    await self._send_to_connection(connection_id, event)
            except Exception as e:
                logger.error(f"Failed to handle pubsub message: {e}", exc_info=True)

    async def connect(self, websocket: WebSocket, session_id: Optional[str] = None, accept_connection: bool = True) -> str:
        """
        Подключение WebSocket клиента с опциональным session_id.
        
        Args:
            websocket: WebSocket соединение
            session_id: Опциональный идентификатор сессии
            accept_connection: Если True, вызовет websocket.accept(). Если False, предполагается что соединение уже принято.
        """
        if accept_connection:
            await websocket.accept()
        
        connection_id = str(uuid.uuid4())
        connected_at = datetime.now(timezone.utc).isoformat()
        client_ip = get_websocket_client_ip(websocket)

        self.active_connections[connection_id] = {"websocket": websocket, "session_id": session_id}
        
        mapping = {
            "worker_id": self.worker_id,
            "connected_at": connected_at,
            "client_ip": client_ip,
        }
        if session_id:
            mapping["session_id"] = session_id
            await redis_client.set(f"ws:session:{session_id}", connection_id)
        
        await redis_client.hset(f"ws:connection:{connection_id}", mapping=mapping)
        await redis_client.sadd("ws:connections", connection_id)

        logger.info(f"WS connected {connection_id} from {client_ip} with session_id={session_id}")
        return connection_id

    async def disconnect(self, connection_id: str):
        """Отключение WebSocket клиента."""
        conn = self.active_connections.pop(connection_id, None)
        if conn and conn["websocket"].client_state == WebSocketState.CONNECTED:
            await conn["websocket"].close(code=status.WS_1000_NORMAL_CLOSURE)

        session_id_bytes = await redis_client.hget(f"ws:connection:{connection_id}", "session_id")
        if session_id_bytes:
            session_id = session_id_bytes
            await redis_client.delete(f"ws:session:{session_id}")

        await redis_client.delete(f"ws:connection:{connection_id}")
        await redis_client.srem("ws:connections", connection_id)

        logger.info(f"WS disconnected {connection_id}")

    async def broadcast_event(self, event_data: Dict):
        """Глобальная рассылка события всем воркерам через Redis (только для клиентов без session_id)."""
        message = json.dumps(event_data)
        await redis_client.publish("ws:broadcast", message)
        # logger.debug("Event published to Redis channel ws:broadcast")

    async def send_to_session(self, session_id: str, event_data: Dict):
        """Точечная рассылка события по session_id."""
        connection_id_bytes = await redis_client.get(f"ws:session:{session_id}")
        if not connection_id_bytes:
            logger.warning(f"No connection found for session_id {session_id}")
            return

        connection_id = connection_id_bytes
        worker_id_bytes = await redis_client.hget(f"ws:connection:{connection_id}", "worker_id")
        if not worker_id_bytes:
            logger.warning(f"No worker found for connection_id {connection_id}")
            return

        worker_id = worker_id_bytes
        message = json.dumps({
            "connection_id": connection_id,
            "event": event_data
        })
        await redis_client.publish(f"ws:worker:{worker_id}", message)
        logger.debug(f"Targeted event published to worker {worker_id} for session_id {session_id}")

    async def _broadcast_to_local(self, event: Dict):
        """Отправка broadcast события только локальным клиентам без session_id."""
        dead_ids = []

        for connection_id, conn in self.active_connections.items():
            if conn["session_id"] is not None:
                continue  # Пропускаем клиентов с session_id
            websocket = conn["websocket"]
            if websocket.client_state != WebSocketState.CONNECTED:
                dead_ids.append(connection_id)
                continue
            try:
                await websocket.send_text(json.dumps(event))
            except Exception as e:
                logger.warning(f"Error sending to {connection_id}: {e}")
                dead_ids.append(connection_id)

        await self._cleanup_dead_connections(dead_ids)
        # logger.info(f"Local broadcast complete. Active connections: {len(self.active_connections)}")

    async def _send_to_connection(self, connection_id: str, event: Dict):
        """Отправка targeted события конкретному локальному соединению."""
        logger.debug(f"Attempting to send targeted event to connection {connection_id}")
        
        conn = self.active_connections.get(connection_id)
        if not conn:
            logger.warning(f"Connection {connection_id} not found in active_connections")
            return

        websocket = conn["websocket"]
        if websocket.client_state != WebSocketState.CONNECTED:
            logger.warning(f"Connection {connection_id} is not in CONNECTED state")
            await self.disconnect(connection_id)
            return

        try:
            await websocket.send_text(json.dumps(event))
            logger.info(f"✅ Targeted event successfully sent to connection {connection_id}")
        except Exception as e:
            logger.warning(f"Error sending targeted to {connection_id}: {e}")
            await self.disconnect(connection_id)

    async def _cleanup_dead_connections(self, dead_ids: List[str]):
        """Очистка мёртвых соединений."""
        for cid in dead_ids:
            await self.disconnect(cid)



worker_id = f"{socket.gethostname()}-{os.getpid()}"
websocket_events_manager = WebSocketEventsManager(worker_id=worker_id)
