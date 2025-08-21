



# progress_ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter(prefix="/ws", tags=["WebSocket"])

connections: dict[str, WebSocket] = {}


@router.websocket("/progress/{user_id}")
async def progress_ws(websocket: WebSocket, user_id: str):
    """Подключение клиента для получения прогресса"""
    await websocket.accept()
    connections[user_id] = websocket
    logger.info(f"WS connected for {user_id}")
    try:
        while True:
            await websocket.receive_text()  # держим соединение
    except WebSocketDisconnect:
        logger.info(f"WS disconnected for {user_id}")
        connections.pop(user_id, None)


async def send_progress(user_id: str, step: str, percent: int):
    """Отправка прогресса клиенту"""
    ws = connections.get(user_id)
    if ws:
        try:
            await ws.send_json({"step": step, "percent": percent})
        except Exception as e:
            logger.error(f"Ошибка при отправке WS: {e}")