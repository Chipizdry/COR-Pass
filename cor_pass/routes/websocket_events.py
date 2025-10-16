
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from cor_pass.services.websocket_events_manager import websocket_events_manager

from loguru import logger

router = APIRouter()


@router.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket-эндпоинт для подписки на события токенов.
    """
    connection_id = await websocket_events_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_events_manager.disconnect(connection_id)
    except Exception as e:
        logger.error(
            f"Unhandled error in WebSocket endpoint for ID {connection_id}: {e}",
            exc_info=True,
        )
        websocket_events_manager.disconnect(connection_id)
