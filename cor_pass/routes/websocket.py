from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from cor_pass.database.models import AuthSessionStatus
from cor_pass.repository.user_session import get_auth_session_by_token
from cor_pass.services import websocket as ws
from cor_pass.services.websocket_events_manager import websocket_events_manager
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.db import get_db


router = APIRouter(prefix="/websockets", tags=["Websockets"])


@router.websocket("/auth/{session_token}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket-эндпоинт для ожидания статуса подтверждения от Cor-ID.
    Если session_token передан → проверяем в БД.
    """

    db_session = await get_auth_session_by_token(session_token, db)
    if not db_session:
        print(f"Сессия с токеном {session_token} не найдена.")
        await websocket.close(code=1008, reason="Сессия не найдена")
        return

    if db_session.status != AuthSessionStatus.PENDING:
        print(
            f"Подключение к сессии {session_token} отклонено. Статус: {db_session.status}"
        )
        await websocket.close(
            code=1008, reason=f"Неверный статус сессии: {db_session.status}"
        )
        return

    connection_id = await websocket_events_manager.connect(websocket=websocket, session_id=session_token)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        await websocket_events_manager.disconnect(connection_id)
    except Exception as e:
        await websocket_events_manager.disconnect(connection_id)
