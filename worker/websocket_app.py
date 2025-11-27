"""
FastAPI приложение для WebSocket соединений с энергетическими устройствами в modbus_worker.
Работает только с Cerbo/Modbus устройствами через email/password аутентификацию.
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
from pydantic import BaseModel

from cor_pass.database.db import get_db
from cor_pass.database.models import User
from cor_pass.config.config import settings
from cor_pass.services.shared.websocket_events_manager import websocket_events_manager
from cor_pass.database.redis_db import redis_client
from passlib.context import CryptContext


# Глобальная переменная для хранения фоновых задач
background_tasks = []

# Интервал отправки команд (в секундах)
COMMAND_SEND_INTERVAL = 5  # Отправлять команду каждые 5 секунд


# Pydantic модели для API
class WSMessageBase(BaseModel):
    """Модель для отправки сообщений на энергетические устройства"""
    session_token: str
    data: Dict

from cor_pass.services.shared.pi30_commands import (
    PI30Command, 
    PI30_COMMAND_DESCRIPTIONS,
    format_pi30_command,
    format_pi30_command_with_crc_hex
)

class Pi30CommandRequest(BaseModel):
    """Запрос на отправку PI30 команды"""
    session_token: str
    pi30: PI30Command


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    logger.info("Starting Energetic Devices WebSocket Server...")
    
    # Запускаем подписку на Redis каналы для получения сообщений
    await websocket_events_manager.init_redis_listener()
    logger.info("Redis listener initialized for WebSocket events")
    
    # Запускаем фоновую задачу для отправки Modbus-команд
    modbus_task = asyncio.create_task(send_modbus_command_to_all_devices())
    background_tasks.append(modbus_task)
    logger.info(f"Background task started: Modbus command sender (interval: {COMMAND_SEND_INTERVAL}s)")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Energetic Devices WebSocket Server...")
    
    # Отменяем все фоновые задачи
    for task in background_tasks:
        task.cancel()
    
    # Ждем завершения всех задач
    await asyncio.gather(*background_tasks, return_exceptions=True)
    logger.info("All background tasks stopped")


app = FastAPI(
    title="Energetic Devices WebSocket Server", 
    description="WebSocket сервер для энергетических устройств (Cerbo/Modbus)",
    lifespan=lifespan
)

# Добавляем CORS middleware для поддержки WebSocket соединений из браузера
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Инициализация контекста для проверки паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет соответствие plain-text пароля хешированному.
    Standalone функция для избежания циклических импортов.
    """
    return pwd_context.verify(plain_password, hashed_password)


async def get_user_by_email(email: str, db: AsyncSession):
    """
    Получает пользователя по email из базы данных.
    Standalone функция для избежания циклических импортов.
    """
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def send_modbus_command_to_all_devices():
    """
    Фоновая задача для периодической отправки Modbus-команд всем подключенным энергетическим устройствам.
    Отправляет команды поочередно:
    1. Modbus: 09 03 00 00 00 10 45 4E
    2. Modbus: 09 03 00 00 00 0A C4 85
    3. PI30:   QPIGS (с возвратом каретки, отправляется как ключ "pi30")
    """
    logger.info("🔄 Starting background task: send_modbus_command_to_all_devices")
    
    # Формируем PI30 команду QPIGS с CRC и CR в hex формате
    # Используем новую функцию для автоматического форматирования
    pi30_qpigs_hex = format_pi30_command_with_crc_hex("QPIGS")
    
    # Список команд: смешанный (modbus / pi30).
    mixed_commands = [
        # {"command_type": "modbus_read", "hex_data": "09 03 00 00 00 10 45 4E"},
        # {"command_type": "modbus_read", "hex_data": "09 03 00 00 00 0A C4 85"},
        {"command_type": "pi30", "pi30": pi30_qpigs_hex},  # PI30 команда: QPIGS + CRC + CR
    ]
    command_index = 0  # Индекс текущей команды
    
    while True:
        try:
            await asyncio.sleep(COMMAND_SEND_INTERVAL)
            
            # Получаем все активные подключения
            connections = websocket_events_manager.active_connections
            
            if not connections:
                logger.debug("No active energetic devices connected")
                continue
            
            # Выбираем текущую команду из смешанного списка
            current_command = mixed_commands[command_index]
            
            # Готовим данные для отправки: для pi30 distinta структура
            if current_command["command_type"] == "pi30":
                event_payload = {
                    "command_type": "pi30",
                    "pi30": current_command["pi30"]  
                }
                log_repr = repr(current_command["pi30"]).replace("\r", "\\r")
            else:
                event_payload = {
                    "command_type": "modbus_read",
                    "hex_data": current_command["hex_data"]
                }
                log_repr = current_command["hex_data"]
            
            # Отправляем команду каждому подключенному устройству
            for connection_id, conn_data in connections.items():
                session_id = conn_data.get("session_id")
                if not session_id:
                    continue
                
                try:
                    await websocket_events_manager.send_to_session(
                        session_id=session_id,
                        event_data=event_payload
                    )
                    if current_command["command_type"] == "pi30":
                        logger.debug(f"📤 Sent PI30 command [QPIGS] -> [{log_repr}] to device with session_id: {session_id}")
                    else:
                        logger.debug(f"📤 Sent Modbus command [{log_repr}] to device with session_id: {session_id}")
                except Exception as e:
                    logger.warning(f"Failed to send command to session {session_id}: {e}")
            
            if current_command["command_type"] == "pi30":
                logger.info(f"✅ PI30 command [QPIGS] broadcast complete. Sent to {len(connections)} devices")
            else:
                logger.info(f"✅ Modbus command [{log_repr}] broadcast complete. Sent to {len(connections)} devices")
            
            # Переключаемся на следующую команду
            command_index = (command_index + 1) % len(mixed_commands)
            
        except asyncio.CancelledError:
            logger.info("Background task send_modbus_command_to_all_devices cancelled")
            break
        except Exception as e:
            logger.error(f"Error in send_modbus_command_to_all_devices: {e}", exc_info=True)
            # Продолжаем работу даже при ошибке
            await asyncio.sleep(3)


@app.get("/health")
async def health_check():
    """Health check endpoint для энергетических устройств"""
    energetic_count = len(websocket_events_manager.active_connections)
    
    return {
        "status": "healthy",
        "service": "energetic_devices_websocket_server",
        "connected_devices": energetic_count
    }


@app.get("/devices/connected")
async def get_connected_energetic_devices():
    """Возвращает список подключенных энергетических устройств"""
    # active_connections это Dict[connection_id, {"websocket": ws, "session_id": str}]
    connections = websocket_events_manager.active_connections
    
    # Собираем уникальные session_id
    session_ids = []
    for conn_id, conn_data in connections.items():
        session_id = conn_data.get("session_id")
        if session_id:
            session_ids.append(session_id)
    
    return {
        "connected_devices": session_ids,
        "count": len(session_ids)
    }


@app.get("/devices/{session_id}/status")
async def get_energetic_device_status(session_id: str):
    """Проверяет статус подключения энергетического устройства"""
    connections = websocket_events_manager.active_connections
    
    # Ищем соединение по session_id
    is_connected = False
    connection_info = None
    
    for conn_id, conn_data in connections.items():
        if conn_data.get("session_id") == session_id:
            is_connected = True
            connection_info = {
                "connection_id": conn_id,
                "session_id": session_id,
                "connected": True
            }
            break
    
    if not is_connected:
        raise HTTPException(
            status_code=404,
            detail=f"Energetic device with session_id {session_id} is not connected"
        )
    
    return connection_info


@app.websocket("/wssdevices")
async def websocket_energetic_device_endpoint(
    websocket: WebSocket, 
    session_id: str, 
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint для подключения энергетических устройств (Cerbo/Modbus).
    Аутентификация по email/password через первое сообщение.
    Использует websocket_events_manager для broadcast событий.
    """
    # Сначала принимаем WebSocket соединение
    await websocket.accept()
    logger.info(f"Energetic device WebSocket accepted, session_id: {session_id}")
    
    connection_id = await websocket_events_manager.connect(websocket, session_id=session_id, accept_connection=False)
    logger.info(f"Energetic device connection registered, session_id: {session_id}")
    
    try:
        # Первое сообщение с credentials
        auth_data = await websocket.receive_json()
        user_email = auth_data.get("email")
        password = auth_data.get("password")
        
        if not user_email or not password:
            await websocket.send_json({"cloud_status": "Auth error: Missing credentials"})
            await websocket_events_manager.disconnect(connection_id)
            logger.warning(f"Missing credentials for session {session_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing credentials"
            )
        
        # Проверяем пользователя без использования auth_service
        user = await get_user_by_email(email=user_email, db=db)
        if user is None or not verify_password(plain_password=password, hashed_password=user.password):
            await websocket.send_json({"cloud_status": "Auth error: Invalid credentials"})
            await websocket_events_manager.disconnect(connection_id)
            logger.warning(f"Invalid credentials for session {session_id}, email: {user_email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        logger.info(f"Energetic device authenticated: session_id={session_id}, user={user_email}")
        await websocket.send_json({"cloud_status": "authenticated"})
        
        # Основной цикл приема данных
        while True:
            data = await websocket.receive_json()
            logger.debug(f"Received data from energetic device {session_id}: {data}")
            
            # Broadcast события всем подключенным клиентам
            await websocket_events_manager.broadcast_event({
                "device_id": session_id, 
                "data": data
            })
    
    except WebSocketDisconnect:
        logger.info(f"Energetic device {session_id} disconnected normally")
    except HTTPException as e:
        logger.error(f"Authentication failed for session {session_id}: {e.detail}")
    except Exception as e:
        logger.error(f"Error in energetic device connection {session_id}: {e}", exc_info=True)
    finally:
        await websocket_events_manager.disconnect(connection_id)
        logger.info(f"Energetic device {session_id} disconnected")


@app.post(
    "/send_message",
    status_code=status.HTTP_200_OK,
    summary="Отправить сообщение на энергетическое устройство по WebSocket"
)
async def send_message_to_energetic_device(message: WSMessageBase, db: AsyncSession = Depends(get_db)):
    """
    Отправляет JSON-сообщение на энергетическое устройство через WebSocket.
    Устройство идентифицируется по session_token.
    """
    # Проверяем, есть ли активное соединение для этой сессии в Redis
    connection_id = await redis_client.get(f"ws:session:{message.session_token}")
    if not connection_id:
        logger.warning(f"No connection found for session_token {message.session_token}")
        raise HTTPException(
            status_code=404, 
            detail=f"Сессия не найдена или устройство не подключено: {message.session_token}"
        )
    
    try:
        # Отправляем сообщение через websocket_events_manager
        await websocket_events_manager.send_to_session(
            session_id=message.session_token,
            event_data=message.data
        )
        logger.info(f"Message sent to energetic device session {message.session_token} via connection {connection_id}")
        return {
            "detail": "Сообщение успешно отправлено",
            "session_token": message.session_token,
            "connection_id": connection_id.decode() if isinstance(connection_id, bytes) else connection_id
        }
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения на устройство {message.session_token}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Ошибка при отправке сообщения: {str(e)}"
        )


@app.post(
    "/send_pi30_command",
    status_code=status.HTTP_200_OK,
    summary="Отправить PI30 команду на энергетическое устройство"
)
async def send_pi30_command(request: Pi30CommandRequest, db: AsyncSession = Depends(get_db)):
    """
    Отправляет PI30 команду на энергетическое устройство через WebSocket.
    Команда выбирается из предопределенного списка PI30Command.
    
    Команда отправляется в hex формате с CRC и CR: COMMAND (hex) + CRC + 0D
    """
    connection_id = await redis_client.get(f"ws:session:{request.session_token}")
    if not connection_id:
        logger.warning(f"No connection found for session_token {request.session_token}")
        raise HTTPException(
            status_code=404, 
            detail=f"Сессия не найдена или устройство не подключено: {request.session_token}"
        )
    
    command_str = request.pi30.value
    description = PI30_COMMAND_DESCRIPTIONS.get(request.pi30, "PI30 command")
    
    # Форматируем команду в hex с CRC и CR
    formatted_command_hex = format_pi30_command_with_crc_hex(command_str)
    
    try:
        await websocket_events_manager.send_to_session(
            session_id=request.session_token,
            event_data={
                "command_type": "pi30",
                "pi30": formatted_command_hex,  # Hex строка с CRC и CR
                "description": description
            }
        )
        logger.info(f"PI30 command {command_str} (hex: {formatted_command_hex}) sent to device session {request.session_token}")
        return {
            "detail": "PI30 команда успешно отправлена",
            "session_token": request.session_token,
            "command": command_str,
            "formatted_command_hex": formatted_command_hex,
            "description": description
        }
    except Exception as e:
        logger.error(f"Ошибка при отправке PI30 команды {command_str}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Ошибка при отправке PI30 команды: {str(e)}"
        )


@app.get(
    "/pi30/commands",
    status_code=status.HTTP_200_OK,
    summary="Получить список доступных PI30 команд"
)
async def list_pi30_commands():
    """
    Возвращает список всех доступных PI30 команд с описаниями.
    """
    commands = [
        {
            "command": cmd.value,
            "description": PI30_COMMAND_DESCRIPTIONS.get(cmd, "")
        }
        for cmd in PI30Command
    ]
    return {"commands": commands}


@app.post(
    "/broadcast_modbus_command",
    status_code=status.HTTP_200_OK,
    summary="Вручную отправить Modbus-команду всем устройствам"
)
async def broadcast_modbus_command_manual(hex_data: str = "09 03 00 00 00 08 05 48"):
    """
    Вручную отправляет Modbus-команду (hex) всем подключенным энергетическим устройствам.
    По умолчанию отправляет: 09 03 00 00 00 08 05 48
    """
    connections = websocket_events_manager.active_connections
    
    if not connections:
        raise HTTPException(status_code=404, detail="No active energetic devices connected")
    
    command_data = {
        "command_type": "modbus_read",
        "data": hex_data
    }
    
    sent_count = 0
    failed_count = 0
    
    for connection_id, conn_data in connections.items():
        session_id = conn_data.get("session_id")
        if not session_id:
            continue
        
        try:
            await websocket_events_manager.send_to_session(
                session_id=session_id,
                event_data=command_data
            )
            sent_count += 1
            logger.info(f"📤 Manual Modbus command sent to session_id: {session_id}")
        except Exception as e:
            failed_count += 1
            logger.warning(f"Failed to send manual command to session {session_id}: {e}")
    
    return {
        "detail": "Modbus command broadcast complete",
        "total_devices": len(connections),
        "sent_successfully": sent_count,
        "failed": failed_count,
        "hex_command": hex_data
    }
