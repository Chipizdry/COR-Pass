"""
API для взаимодействия с энергетическими устройствами через modbus_worker контейнер.
Проксирует запросы к WebSocket серверу в modbus_worker.
Только для энергетических устройств (Cerbo/Modbus).
"""
import httpx
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from cor_pass.services.access import user_access


router = APIRouter(prefix="/energetic_device_proxy", tags=["Energetic Device Proxy"])


# URL для подключения к WebSocket серверу в modbus_worker
# В docker-compose это будет имя сервиса
ENERGETIC_WS_SERVER_URL = "http://modbus_worker:8003"


@router.get("/devices/connected", dependencies=[Depends(user_access)])
async def get_connected_energetic_devices_via_proxy():
    """
    Получает список подключенных энергетических устройств из modbus_worker контейнера.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ENERGETIC_WS_SERVER_URL}/devices/connected")
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error from WebSocket server: {response.text}"
                )
                
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout connecting to energetic device WebSocket server"
        )
    except httpx.RequestError as e:
        logger.error(f"Error connecting to energetic device WebSocket server: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Energetic device WebSocket server is unavailable"
        )


@router.get("/devices/{session_id}/status", dependencies=[Depends(user_access)])
async def get_energetic_device_status_via_proxy(session_id: str):
    """
    Проверяет статус подключения энергетического устройства по session_id через modbus_worker контейнер.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ENERGETIC_WS_SERVER_URL}/devices/{session_id}/status")
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Energetic device with session_id {session_id} is not connected"
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error from WebSocket server: {response.text}"
                )
                
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout connecting to energetic device WebSocket server"
        )
    except httpx.RequestError as e:
        logger.error(f"Error connecting to energetic device WebSocket server: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Energetic device WebSocket server is unavailable"
        )


@router.get("/health")
async def check_websocket_server_health():
    """
    Проверяет здоровье WebSocket сервера энергетических устройств в modbus_worker.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ENERGETIC_WS_SERVER_URL}/health")
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Energetic devices WebSocket server is unhealthy"
                )
                
    except (httpx.TimeoutException, httpx.RequestError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot reach energetic devices WebSocket server"
        )


@router.post("/send_message", dependencies=[Depends(user_access)])
async def send_message_to_energetic_device_via_proxy(session_token: str, data: Dict):
    """
    Отправляет сообщение на энергетическое устройство (Cerbo/Modbus) через modbus_worker контейнер.
    Устройство должно быть подключено через /ws/devices эндпоинт.
    
    Args:
        session_token: ID сессии устройства (тот же, что использовался при подключении WebSocket)
        data: Данные для отправки устройству (JSON объект)
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{ENERGETIC_WS_SERVER_URL}/send_message",
                json={
                    "session_token": session_token,
                    "data": data
                }
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Энергетическое устройство с session_token {session_token} не подключено"
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Ошибка от WebSocket сервера: {response.text}"
                )
                
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout connecting to energetic device WebSocket server"
        )
    except httpx.RequestError as e:
        logger.error(f"Error connecting to energetic device WebSocket server: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Energetic device WebSocket server is unavailable"
        )
