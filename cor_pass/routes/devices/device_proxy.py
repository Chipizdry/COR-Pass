"""
API для взаимодействия с энергетическими устройствами через modbus_worker контейнер.
Проксирует запросы к WebSocket серверу в modbus_worker.
Только для энергетических устройств (Cerbo/Modbus).
"""
import httpx
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from loguru import logger

from cor_pass.services.shared.access import user_access
from cor_pass.services.shared.pi30_commands import PI30Command


class Pi30ProxyRequest(BaseModel):
    """Запрос на отправку PI30 команды через proxy"""
    session_token: str
    pi30: PI30Command


router = APIRouter(prefix="/energetic_device_proxy", tags=["Energetic Device Proxy"])


ENERGETIC_WS_SERVER_URL = "http://modbus_worker:45762"
logger.info(f"Energetic device proxy base URL set to {ENERGETIC_WS_SERVER_URL}")


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
