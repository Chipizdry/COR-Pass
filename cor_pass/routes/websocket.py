from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from cor_pass.database.models import CorIdAuthSession, AuthSessionStatus
from cor_pass.repository.user_session import get_auth_session_by_token
from cor_pass.services import websocket as ws
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.db import get_db


router = APIRouter(prefix="/websockets", tags=["Websockets"])


@router.websocket("/auth/{session_token}")
async def websocket_endpoint(
    websocket: WebSocket, session_token: str, db: AsyncSession = Depends(get_db)
):
    """
    WebSocket-эндпоинт для ожидания статуса подтверждения от Cor-ID.
    Принимает подключение только для сессий со статусом PENDING.
    """
    db_session = await get_auth_session_by_token(session_token, db)

    if not db_session:
        print(f"Сессия с токеном {session_token} не найдена.")
        await websocket.close(code=1008, reason="Сессия не найдена")
        return

    if db_session.status != AuthSessionStatus.PENDING:
        print(
            f"Подключение к сессии с токеном {session_token} отклонено. Статус: {db_session.status}"
        )
        await websocket.close(
            code=1008, reason=f"Неверный статус сессии: {db_session.status}"
        )
        return

    await websocket.accept()
    ws.active_connections[session_token] = websocket
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Получено сообщение от клиента {session_token}: {data}")
            # You might want to process the received data here
    except WebSocketDisconnect:
        print(f"Клиент {session_token} отключился")
        if session_token in ws.active_connections:
            del ws.active_connections[session_token]
    except Exception as e:
        print(f"Ошибка в WebSocket-соединении с {session_token}: {e}")
        if session_token in ws.active_connections:
            del ws.active_connections[session_token]
