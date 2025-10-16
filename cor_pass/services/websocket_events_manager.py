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



# Рабочий вариант для подписания репортов
# class WebSocketEventsManager:
#     """Менеджер WebSocket с Redis для многоворкеров."""

#     def __init__(self, worker_id: str):
#         self.worker_id = worker_id
#         self.active_connections: Dict[str, WebSocket] = {}  
#         logger.info(f"WebSocketEventsManager initialized for worker {worker_id}")

#     async def init_redis_listener(self):
#         """Запуск подписки на глобальный Redis канал."""
#         asyncio.create_task(self._listen_pubsub())

#     async def _listen_pubsub(self):
#         pubsub = redis_client.pubsub()
#         await pubsub.subscribe("ws:broadcast")

#         async for message in pubsub.listen():
#             if message["type"] != "message":
#                 continue
#             try:
#                 event = json.loads(message["data"])
#                 await self._send_to_local(event)
#             except Exception as e:
#                 logger.error(f"Failed to handle pubsub message: {e}", exc_info=True)

#     async def connect(self, websocket: WebSocket) -> str:
#         """Подключение WebSocket клиента."""
#         await websocket.accept()
#         connection_id = str(uuid.uuid4())
#         connected_at = datetime.now(timezone.utc).isoformat()
#         client_ip = get_websocket_client_ip(websocket)

#         self.active_connections[connection_id] = websocket
#         await redis_client.hset(
#             f"ws:connection:{connection_id}",
#             mapping={
#                 "worker_id": self.worker_id,
#                 "connected_at": connected_at,
#                 "client_ip": client_ip,
#             },
#         )
#         await redis_client.sadd("ws:connections", connection_id)

#         logger.info(f"WS connected {connection_id} from {client_ip}")
#         return connection_id

#     async def disconnect(self, connection_id: str):
#         """Отключение WebSocket клиента."""
#         websocket = self.active_connections.pop(connection_id, None)
#         if websocket and websocket.client_state == WebSocketState.CONNECTED:
#             await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)

#         await redis_client.delete(f"ws:connection:{connection_id}")
#         await redis_client.srem("ws:connections", connection_id)

#         logger.info(f"WS disconnected {connection_id}")

#     async def broadcast_event(self, event_data: Dict):
#         """Глобальная рассылка события всем воркерам через Redis."""
#         message = json.dumps(event_data)
#         await redis_client.publish("ws:broadcast", message)
#         logger.debug("Event published to Redis channel ws:broadcast")

#     async def _send_to_local(self, event: Dict):
#         """Отправка события всем локальным подключенным клиентам этого воркера."""
#         dead_ids = []

#         for connection_id, websocket in self.active_connections.items():
#             if websocket.client_state != WebSocketState.CONNECTED:
#                 dead_ids.append(connection_id)
#                 continue
#             try:
#                 await websocket.send_text(json.dumps(event))
#             except Exception as e:
#                 logger.warning(f"Error sending to {connection_id}: {e}")
#                 dead_ids.append(connection_id)

#         for cid in dead_ids:
#             self.active_connections.pop(cid, None)
#             await redis_client.delete(f"ws:connection:{cid}")
#             await redis_client.srem("ws:connections", cid)

#         logger.info(f"Local broadcast complete. Active connections: {len(self.active_connections)}")






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

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                channel = message["channel"]
                data = json.loads(message["data"])
                if channel == "ws:broadcast":
                    await self._broadcast_to_local(data)
                else:
                    # Targeted message
                    connection_id = data["connection_id"]
                    event = data["event"]
                    await self._send_to_connection(connection_id, event)
            except Exception as e:
                logger.error(f"Failed to handle pubsub message: {e}", exc_info=True)

    async def connect(self, websocket: WebSocket, session_id: Optional[str] = None) -> str:
        """Подключение WebSocket клиента с опциональным session_id."""
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
        logger.debug("Event published to Redis channel ws:broadcast")

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
        logger.info(f"Local broadcast complete. Active connections: {len(self.active_connections)}")

    async def _send_to_connection(self, connection_id: str, event: Dict):
        """Отправка targeted события конкретному локальному соединению."""
        conn = self.active_connections.get(connection_id)
        if not conn:
            return

        websocket = conn["websocket"]
        if websocket.client_state != WebSocketState.CONNECTED:
            await self.disconnect(connection_id)
            return

        try:
            await websocket.send_text(json.dumps(event))
        except Exception as e:
            logger.warning(f"Error sending targeted to {connection_id}: {e}")
            await self.disconnect(connection_id)

    async def _cleanup_dead_connections(self, dead_ids: List[str]):
        """Очистка мёртвых соединений."""
        for cid in dead_ids:
            await self.disconnect(cid)










worker_id = f"{socket.gethostname()}-{os.getpid()}"
websocket_events_manager = WebSocketEventsManager(worker_id=worker_id)



# class WebSocketEventsManager:
#     """Менеджер WebSocket с Redis для многоворкеров."""

#     def __init__(self, worker_id: str):
#         self.worker_id = worker_id
#         self.active_connections: Dict[str, WebSocket] = {}  
#         logger.info(f"WebSocketEventsManager initialized for worker {worker_id}")

#     async def init_redis_listener(self):
#         """Запуск подписки на глобальный Redis канал с повторными попытками."""
#         asyncio.create_task(self._listen_pubsub())

#     async def _listen_pubsub(self):
#         while True:
#             try:
#                 pubsub = redis_client.pubsub()
#                 await pubsub.subscribe("ws:broadcast", f"ws:direct:{self.worker_id}")
#                 logger.info(f"Subscribed to Redis channels for worker {self.worker_id}")
#                 async for message in pubsub.listen():
#                     if message["type"] != "message":
#                         continue
#                     try:
#                         event = json.loads(message["data"])
#                         if message["channel"] == b"ws:broadcast":
#                             await self._send_to_local(event)
#                         elif message["channel"] == f"ws:direct:{self.worker_id}".encode():
#                             await self._send_direct_local(event)
#                     except Exception as e:
#                         logger.error(f"Failed to handle pubsub message: {e}", exc_info=True)
#             except Exception as e:
#                 logger.error(f"Redis pubsub error: {e}. Reconnecting in 5 seconds...", exc_info=True)
#                 await asyncio.sleep(5)

#     async def connect(self, websocket: WebSocket, session_token: str | None = None) -> str:
#         """Подключение клиента. Привязка connection_id к session_token в Redis.
#         Если session_token уже существует, обновляем connection_id и worker_id."""
#         await websocket.accept()
        
#         # Генерируем уникальный connection_id
#         for _ in range(3):
#             connection_id = str(uuid.uuid4())
#             if not await redis_client.exists(f"ws:connection:{connection_id}"):
#                 break
#         else:
#             raise RuntimeError("Failed to generate unique connection_id")

#         connected_at = datetime.now(timezone.utc).isoformat()
#         client_ip = get_websocket_client_ip(websocket)

#         if not session_token:
#             session_token = str(uuid.uuid4())

#         # Проверяем существующую сессию и очищаем старое соединение, если нужно
#         existing_meta = await redis_client.hgetall(f"ws:session:{session_token}")
#         if existing_meta:
#             old_connection_id = existing_meta.get("connection_id")
#             old_worker_id = existing_meta.get("worker_id")
#             if old_connection_id:
#                 await redis_client.delete(f"ws:connection:{old_connection_id}")
#                 await redis_client.srem("ws:connections", old_connection_id)
#                 if old_worker_id == self.worker_id:
#                     self.active_connections.pop(old_connection_id, None)
#             logger.info(f"Updating existing session {session_token} with new connection {connection_id}")

#         self.active_connections[connection_id] = websocket

#         await redis_client.hset(
#             f"ws:connection:{connection_id}",
#             mapping={
#                 "worker_id": self.worker_id,
#                 "session_token": session_token,
#                 "connected_at": connected_at,
#                 "client_ip": client_ip,
#             },
#         )
#         await redis_client.sadd("ws:connections", connection_id)

#         # Связь session_token -> connection_id
#         await redis_client.hset(
#             f"ws:session:{session_token}",
#             mapping={
#                 "worker_id": self.worker_id,
#                 "connection_id": connection_id,
#                 "connected_at": connected_at,
#                 "client_ip": client_ip,
#             },
#         )

#         logger.info(f"WS connected {connection_id} (session={session_token}) from {client_ip}")
#         return connection_id

#     async def disconnect(self, connection_id: str):
#         """Отключение WebSocket клиента с полной очисткой."""
#         websocket = self.active_connections.pop(connection_id, None)
#         if websocket and websocket.client_state == WebSocketState.CONNECTED:
#             try:
#                 await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
#             except Exception as e:
#                 logger.error(f"Error closing websocket {connection_id}: {e}")

#         # Получаем session_token и очищаем сессию
#         connection_data = await redis_client.hgetall(f"ws:connection:{connection_id}")
#         session_token = connection_data.get("session_token")

#         await redis_client.delete(f"ws:connection:{connection_id}")
#         await redis_client.srem("ws:connections", connection_id)

#         if session_token:
#             await redis_client.delete(f"ws:session:{session_token}")
#             logger.debug(f"Session {session_token} removed for connection {connection_id}")

#         logger.info(f"WS disconnected {connection_id}")

#     async def broadcast_event(self, event_data: dict) -> None:
#         """
#         Шлём всем: сразу локально + публикуем в Redis.
#         """
#         await self._send_to_local(event_data)
#         payload = json.dumps(event_data)
#         try:
#             receivers = await redis_client.publish("ws:broadcast", payload)
#             logger.debug(f"Published to ws:broadcast; receivers={receivers}")
#             if receivers == 0:
#                 logger.warning("No Redis subscribers on ws:broadcast")
#         except Exception as e:
#             logger.error(f"publish failed: {e}", exc_info=True)

#     async def _send_to_local(self, event: Dict):
#         dead_ids = []
#         tasks = []
#         for connection_id, websocket in self.active_connections.items():
#             if websocket.client_state != WebSocketState.CONNECTED:
#                 dead_ids.append(connection_id)
#                 continue
#             # Проверяем, существует ли connection_id в Redis
#             if not await redis_client.exists(f"ws:connection:{connection_id}"):
#                 dead_ids.append(connection_id)
#                 continue
#             logger.debug(f"Sending broadcast to {connection_id}")
#             tasks.append(
#                 asyncio.create_task(
#                     self._safe_send(websocket, json.dumps(event), connection_id)
#                 )
#             )
#         if tasks:
#             results = await asyncio.gather(*tasks, return_exceptions=True)
#             for i, result in enumerate(results):
#                 if isinstance(result, Exception):
#                     logger.warning(f"Failed to send to {list(self.active_connections.keys())[i]}: {result}")
#                     dead_ids.append(list(self.active_connections.keys())[i])
#         for cid in dead_ids:
#             await self.disconnect(cid)
#         logger.info(f"Local broadcast complete. Active: {len(self.active_connections)}")

#     async def _safe_send(self, websocket: WebSocket, message: str, connection_id: str) -> None:
#         """Безопасная отправка с обработкой исключений."""
#         try:
#             await asyncio.wait_for(websocket.send_text(message), timeout=5.0)
#         except asyncio.TimeoutError:
#             logger.warning(f"Timeout sending to {connection_id}")
#             raise
#         except WebSocketDisconnect:
#             logger.warning(f"WebSocketDisconnect for {connection_id}")
#             raise
#         except Exception as e:
#             logger.warning(f"Error sending to {connection_id}: {e}")
#             raise

#     async def send_to_client(self, session_token: str, event: Dict, wrap_message: bool = True) -> None:
#         """Отправка targeted сообщения по session_token. Унифицированный метод.
#         wrap_message: True для обертки (по умолчанию, для совместимости с _send_direct_local)."""
#         meta = await redis_client.hgetall(f"ws:session:{session_token}")
#         if not meta:
#             logger.warning(f"Session {session_token} not found in Redis", extra={"session_token": session_token})
#             return

#         target_worker = meta.get("worker_id")
#         connection_id = meta.get("connection_id")

#         if not target_worker or not connection_id:
#             logger.warning(f"Invalid meta for session {session_token}: {meta}")
#             return

#         # Проверяем живость соединения в Redis
#         if not await redis_client.exists(f"ws:connection:{connection_id}"):
#             logger.warning(f"Connection {connection_id} not found in Redis for session {session_token}. Cleaning up.")
#             await redis_client.delete(f"ws:session:{session_token}")
#             return

#         message = json.dumps({
#             "type": "direct",
#             "connection_id": connection_id,
#             "event": event,
#         }) if wrap_message else json.dumps(event)

#         if target_worker == self.worker_id:
#             ws = self.active_connections.get(connection_id)
#             if ws and ws.client_state == WebSocketState.CONNECTED:
#                 try:
#                     await self._safe_send(ws, message, connection_id)
#                     logger.debug(f"Sent direct to local client {connection_id} (session={session_token})")
#                 except Exception:
#                     await self.disconnect(connection_id)
#             else:
#                 logger.warning(f"Local client {connection_id} not connected (state={ws.client_state if ws else 'None'})")
#                 await self.disconnect(connection_id)
#         else:
#             try:
#                 await redis_client.publish(f"ws:direct:{target_worker}", message)
#                 logger.debug(f"Published direct to worker {target_worker} for {connection_id} (session={session_token})")
#             except Exception as e:
#                 logger.error(f"Failed to publish to ws:direct:{target_worker}: {e}")

#     async def _send_direct_local(self, event: Dict):
#         """Отправка targeted события локальному клиенту."""
#         # Если нет обертки, логируем и пропускаем (для обратной совместимости, но лучше всегда использовать обертку)
#         if "connection_id" not in event or "event" not in event:
#             logger.error(f"Invalid direct event format: missing 'connection_id' or 'event'. Event: {event}")
#             return

#         connection_id = event["connection_id"]
#         ws = self.active_connections.get(connection_id)

#         if not ws or ws.client_state != WebSocketState.CONNECTED:
#             logger.warning(f"Direct send failed, no local client {connection_id}")
#             await self.disconnect(connection_id)
#             return

#         try:
#             await self._safe_send(ws, json.dumps(event["event"]), connection_id)
#         except Exception as e:
#             logger.error(f"Error sending direct to {connection_id}: {e}")
#             await self.disconnect(connection_id)


# worker_id = f"{socket.gethostname()}-{os.getpid()}"
# websocket_events_manager = WebSocketEventsManager(worker_id=worker_id)
