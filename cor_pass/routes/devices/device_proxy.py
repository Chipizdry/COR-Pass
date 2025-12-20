"""
API для взаимодействия с энергетическими устройствами через modbus_worker контейнер.
Проксирует запросы к WebSocket серверу в modbus_worker.
Только для энергетических устройств (Cerbo/Modbus).
"""
import httpx
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from loguru import logger

from cor_pass.database.db import get_db
from cor_pass.database.models import User
from cor_pass.repository.energy import (
    get_device_access,
    get_device_by_id,
    list_device_accesses,
    list_devices_for_user,
    list_all_devices,
    upsert_device_access,
    update_device,
)
from cor_pass.schemas import (
    EnergeticDeviceAccessCreate,
    EnergeticDeviceAccessResponse,
    EnergeticDeviceResponse,
    EnergeticDeviceUpdate,
)
from cor_pass.services.shared.access import user_access, admin_access
from cor_pass.services.shared.pi30_commands import PI30Command
from cor_pass.services.user.auth import auth_service


class Pi30ProxyRequest(BaseModel):
    """Запрос на отправку PI30 команды через proxy"""
    session_token: str
    pi30: PI30Command


router = APIRouter(prefix="/energetic_device_proxy", tags=["Energetic Device Proxy"])


ENERGETIC_WS_SERVER_URL = "http://modbus_worker:45762"
logger.info(f"Energetic device proxy base URL set to {ENERGETIC_WS_SERVER_URL}")


# ============== Energetic device registry (DB) ==============


@router.get(
    "/devices",
    response_model=List[EnergeticDeviceResponse],
    dependencies=[Depends(user_access)],
)
async def list_energetic_devices(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(auth_service.get_current_user)
):
    """Возвращает устройства, которыми владеет пользователь или к которым есть доступ."""
    return await list_devices_for_user(db, current_user.cor_id)


@router.get(
    "/devices/{device_id}",
    response_model=EnergeticDeviceResponse,
    dependencies=[Depends(user_access)],
)
async def get_energetic_device(
    device_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(auth_service.get_current_user)
):
    device = await get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Энергетическое устройство не найдено")
    if device.owner_cor_id != current_user.cor_id:
        access = await get_device_access(
            db, device_id=device_id, accessing_user_cor_id=current_user.cor_id
        )
        if not access:
            raise HTTPException(status_code=403, detail="Нет доступа к устройству")
    return device


@router.patch(
    "/devices/{device_id}",
    response_model=EnergeticDeviceResponse,
    dependencies=[Depends(user_access)],
)
async def update_energetic_device(
    device_id: str,
    payload: EnergeticDeviceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    """Обновить данные устройства (имя, описание, протокол, активность). Только владелец."""
    device = await update_device(
        db,
        device_id=device_id,
        owner_cor_id=current_user.cor_id,
        name=payload.name,
        protocol=payload.protocol,
        description=payload.description,
        is_active=payload.is_active,
    )
    return device


@router.post(
    "/devices/{device_id}/share",
    response_model=EnergeticDeviceAccessResponse,
    dependencies=[Depends(user_access)],
)
async def share_energetic_device(
    device_id: str,
    payload: EnergeticDeviceAccessCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    device = await get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Энергетическое устройство не найдено")
    if device.owner_cor_id != current_user.cor_id:
        raise HTTPException(status_code=403, detail="Доступ для шаринга есть только у владельца")
    if payload.device_id != device_id:
        raise HTTPException(status_code=400, detail="device_id в теле должен совпадать с путем")

    access = await upsert_device_access(
        db,
        device_id=device_id,
        accessing_user_cor_id=payload.accessing_user_cor_id,
        access_level=payload.access_level,
        granting_user_cor_id=current_user.cor_id,
    )
    return access


@router.get(
    "/devices/{device_id}/access",
    response_model=List[EnergeticDeviceAccessResponse],
    dependencies=[Depends(user_access)],
)
async def list_energetic_device_accesses(
    device_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(auth_service.get_current_user)
):
    device = await get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Энергетическое устройство не найдено")
    if device.owner_cor_id != current_user.cor_id:
        raise HTTPException(status_code=403, detail="Доступ к списку доступов есть только у владельца")

    return await list_device_accesses(db, device_id)


@router.get(
    "/admin/devices",
    response_model=List[EnergeticDeviceResponse],
    dependencies=[Depends(admin_access)],
)
async def admin_list_all_energetic_devices(db: AsyncSession = Depends(get_db)):
    """Админский эндпоинт: возвращает все энергетические устройства со всей информацией о владельцах."""
    return await list_all_devices(db)


@router.get("/devices/connected", dependencies=[Depends(user_access)])
async def get_connected_energetic_devices_via_proxy():
    """
    Получает список подключенных энергетических устройств из modbus_worker контейнера.
    """
    url = f"{ENERGETIC_WS_SERVER_URL}/devices/connected"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.json()
            detail_msg = f"Upstream error {response.status_code} from modbus_worker: {response.text}"
            logger.warning(detail_msg)
            raise HTTPException(status_code=response.status_code, detail=detail_msg)
    except httpx.TimeoutException as e:
        logger.error(f"Timeout connecting to modbus_worker at {url}: {e}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Timeout connecting to energetic device WebSocket server")
    except httpx.RequestError as e:
        logger.error(f"Connection failure to modbus_worker at {url}: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Energetic device WebSocket server is unavailable")


@router.get("/devices/{session_id}/status", dependencies=[Depends(user_access)])
async def get_energetic_device_status_via_proxy(session_id: str):
    """
    Проверяет статус подключения энергетического устройства по session_id через modbus_worker контейнер.
    """
    url = f"{ENERGETIC_WS_SERVER_URL}/devices/{session_id}/status"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Energetic device with session_id {session_id} is not connected")
            detail_msg = f"Upstream error {response.status_code} at {url}: {response.text}"
            logger.warning(detail_msg)
            raise HTTPException(status_code=response.status_code, detail=detail_msg)
    except httpx.TimeoutException as e:
        logger.error(f"Timeout connecting to {url}: {e}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Timeout connecting to energetic device WebSocket server")
    except httpx.RequestError as e:
        logger.error(f"Connection failure to {url}: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Energetic device WebSocket server is unavailable")


@router.get("/health")
async def check_websocket_server_health():
    """
    Проверяет здоровье WebSocket сервера энергетических устройств в modbus_worker.
    """
    url = f"{ENERGETIC_WS_SERVER_URL}/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Energetic devices WebSocket server is unhealthy")
    except (httpx.TimeoutException, httpx.RequestError) as e:
        logger.error(f"Health check failed for {url}: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Cannot reach energetic devices WebSocket server")


@router.post("/send_message", dependencies=[Depends(user_access)])
async def send_message_to_energetic_device_via_proxy(session_token: str, data: Dict):
    """
    Отправляет сообщение на энергетическое устройство (Cerbo/Modbus) через modbus_worker контейнер.
    Устройство должно быть подключено через /ws/devices эндпоинт.
    
    Args:
        session_token: ID сессии устройства (тот же, что использовался при подключении WebSocket)
        data: Данные для отправки устройству (JSON объект)
    """
    url = f"{ENERGETIC_WS_SERVER_URL}/send_message"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, json={"session_token": session_token, "data": data})
            if response.status_code == 200:
                return response.json()
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Энергетическое устройство с session_token {session_token} не подключено")
            detail_msg = f"Upstream error {response.status_code} at {url}: {response.text}"
            logger.warning(detail_msg)
            raise HTTPException(status_code=response.status_code, detail=detail_msg)
    except httpx.TimeoutException as e:
        logger.error(f"Timeout sending to {url}: {e}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Timeout connecting to energetic device WebSocket server")
    except httpx.RequestError as e:
        logger.error(f"Connection failure to {url}: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Energetic device WebSocket server is unavailable")


@router.post("/pi30/send_command", dependencies=[Depends(user_access)])
async def send_pi30_command_via_proxy(request: Pi30ProxyRequest):
    """
    Отправляет PI30 команду на энергетическое устройство через modbus_worker.
    
    Args:
        request: Запрос с session_token и pi30 командой
    """
    url = f"{ENERGETIC_WS_SERVER_URL}/send_pi30_command"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                url, 
                json={"session_token": request.session_token, "pi30": request.pi30.value}
            )
            if response.status_code == 200:
                return response.json()
            if response.status_code == 404:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Энергетическое устройство с session_token {request.session_token} не подключено"
                )
            detail_msg = f"Upstream error {response.status_code} at {url}: {response.text}"
            logger.warning(detail_msg)
            raise HTTPException(status_code=response.status_code, detail=detail_msg)
    except httpx.TimeoutException as e:
        logger.error(f"Timeout sending PI30 command to {url}: {e}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Timeout connecting to energetic device WebSocket server")
    except httpx.RequestError as e:
        logger.error(f"Connection failure to {url}: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Energetic device WebSocket server is unavailable")


@router.get("/pi30/commands", dependencies=[Depends(user_access)])
async def list_pi30_commands_via_proxy():
    """
    Получает список доступных PI30 команд из modbus_worker
    """
    url = f"{ENERGETIC_WS_SERVER_URL}/pi30/commands"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Upstream returned {response.status_code}, using local PI30 command list")
    except (httpx.TimeoutException, httpx.RequestError) as e:
        logger.warning(f"Failed to fetch PI30 commands from modbus_worker, using local list: {e}")
    
    # Fallback: возвращаем список локально
    from cor_pass.services.shared.pi30_commands import PI30_COMMAND_DESCRIPTIONS
    commands = [
        {
            "command": cmd.value,
            "description": PI30_COMMAND_DESCRIPTIONS.get(cmd, "")
        }
        for cmd in PI30Command
    ]
    return {"commands": commands}


# ===================== Broadcast Task Proxy =====================

from typing import Optional


class BroadcastTaskCreateProxy(BaseModel):
    """Запрос на создание фоновой рассылки команд"""
    task_name: str = Field(..., description="Название задачи")
    session_id: str = Field(..., description="ID устройства для отправки команд")
    command_type: str = Field(..., description="Тип команды: 'pi30' или 'modbus_read'")
    pi30_command: Optional[str] = Field(None, description="PI30 команда (например 'QPIGS') - только для command_type='pi30'")
    hex_data: Optional[str] = Field(None, description="Hex данные (например '09 03 00 00 00 10 45 4E') - только для command_type='modbus_read'")
    interval_seconds: float = Field(..., le=3600, description="Интервал отправки команд в секундах (поддерживает значения < 1)")
    is_active: bool = Field(True, description="Запускать задачу сразу после создания")
    created_by: Optional[str] = Field(None, description="ID пользователя, создавшего задачу")


@router.get("/broadcast/tasks", dependencies=[Depends(user_access)])
async def list_broadcast_tasks_proxy():
    """
    Получить список всех фоновых рассылок команд.
    Возвращает задачи со статусом is_running и информацией о session_id.
    """
    url = f"{ENERGETIC_WS_SERVER_URL}/broadcast/tasks"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.json()
            detail_msg = f"Upstream error {response.status_code} from modbus_worker: {response.text}"
            logger.warning(detail_msg)
            raise HTTPException(status_code=response.status_code, detail=detail_msg)
    except httpx.TimeoutException as e:
        logger.error(f"Timeout connecting to modbus_worker at {url}: {e}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Timeout connecting to energetic device WebSocket server")
    except httpx.RequestError as e:
        logger.error(f"Connection failure to modbus_worker at {url}: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Energetic device WebSocket server is unavailable")


@router.get("/broadcast/tasks/session/{session_id}", dependencies=[Depends(user_access)])
async def get_session_broadcast_tasks_proxy(session_id: str):
    """
    Получить все фоновые рассылки для конкретного устройства.
    Возвращает задачи, привязанные к session_id, с количеством активных задач.
    """
    url = f"{ENERGETIC_WS_SERVER_URL}/broadcast/tasks/session/{session_id}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Device {session_id} has no broadcast tasks")
            detail_msg = f"Upstream error {response.status_code} from modbus_worker: {response.text}"
            logger.warning(detail_msg)
            raise HTTPException(status_code=response.status_code, detail=detail_msg)
    except httpx.TimeoutException as e:
        logger.error(f"Timeout connecting to modbus_worker at {url}: {e}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Timeout connecting to energetic device WebSocket server")
    except httpx.RequestError as e:
        logger.error(f"Connection failure to modbus_worker at {url}: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Energetic device WebSocket server is unavailable")


@router.post("/broadcast/tasks", dependencies=[Depends(user_access)], status_code=status.HTTP_201_CREATED)
async def create_broadcast_task_proxy(req: BroadcastTaskCreateProxy):
    """
    Создать новую фоновую рассылку команд на устройство.
    
    **Для PI30 команд:**
    - command_type="pi30", pi30_command="QPIGS" (команда автоматически форматируется с CRC)
    
    **Для Modbus команд:**
    - command_type="modbus_read", hex_data="09 03 00 00 00 10 45 4E"
    
    Задача сохраняется в БД и автоматически запускается если is_active=True.
    """
    url = f"{ENERGETIC_WS_SERVER_URL}/broadcast/tasks"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, json=req.model_dump())
            if response.status_code in (200, 201):
                return response.json()
            detail_msg = f"Upstream error {response.status_code} from modbus_worker: {response.text}"
            logger.warning(detail_msg)
            raise HTTPException(status_code=response.status_code, detail=detail_msg)
    except httpx.TimeoutException as e:
        logger.error(f"Timeout connecting to modbus_worker at {url}: {e}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Timeout connecting to energetic device WebSocket server")
    except httpx.RequestError as e:
        logger.error(f"Connection failure to modbus_worker at {url}: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Energetic device WebSocket server is unavailable")


@router.patch("/broadcast/tasks/{task_id}/toggle", dependencies=[Depends(user_access)])
async def toggle_broadcast_task_proxy(task_id: str):
    """
    Включить/выключить фоновую рассылку команд.
    Переключает is_active и запускает/останавливает задачу без удаления из БД.
    """
    url = f"{ENERGETIC_WS_SERVER_URL}/broadcast/tasks/{task_id}/toggle"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.patch(url)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Broadcast task '{task_id}' not found")
            detail_msg = f"Upstream error {response.status_code} from modbus_worker: {response.text}"
            logger.warning(detail_msg)
            raise HTTPException(status_code=response.status_code, detail=detail_msg)
    except httpx.TimeoutException as e:
        logger.error(f"Timeout connecting to modbus_worker at {url}: {e}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Timeout connecting to energetic device WebSocket server")
    except httpx.RequestError as e:
        logger.error(f"Connection failure to modbus_worker at {url}: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Energetic device WebSocket server is unavailable")


@router.delete("/broadcast/tasks/{task_id}", dependencies=[Depends(user_access)])
async def delete_broadcast_task_proxy(task_id: str):
    """
    Удалить фоновую рассылку команд.
    Останавливает задачу и удаляет из БД.
    """
    url = f"{ENERGETIC_WS_SERVER_URL}/broadcast/tasks/{task_id}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.delete(url)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Broadcast task '{task_id}' not found")
            detail_msg = f"Upstream error {response.status_code} from modbus_worker: {response.text}"
            logger.warning(detail_msg)
            raise HTTPException(status_code=response.status_code, detail=detail_msg)
    except httpx.TimeoutException as e:
        logger.error(f"Timeout connecting to modbus_worker at {url}: {e}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Timeout connecting to energetic device WebSocket server")
    except httpx.RequestError as e:
        logger.error(f"Connection failure to modbus_worker at {url}: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Energetic device WebSocket server is unavailable")
