
"""
Прокси-роуты для Modbus.
Проксируют запросы к воркеру, который управляет конкретными экземплярами Modbus клиентов.
"""

import httpx
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Tuple
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.database.db import get_db
from cor_pass.repository.energy.cerbo_service import get_energetic_object

router = APIRouter(prefix="/modbus_tcp", tags=["Modbus TCP"]) 

# # URL воркера для прокси (должен быть настроен в окружении)
WORKER_BASE_URL = "http://modbus_worker:45762" 


# ============================================================================
# Старые роуты прямого Modbus over TCP клиента
# ============================================================================

import socket
import struct
from threading import Lock

def modbus_crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if (crc & 1) else crc >> 1
    return crc

def error(message: str, details: str = ""):
    return {"ok": False, "error": message, "details": details}

def success(data):
    return {"ok": True, "data": data}

class ModbusTCP:
    def __init__(self, host: str, port: int = 502, slave_id: int = 1, timeout: int = 3):
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.sock = None
        self.lock = Lock()
    
    def connect(self):
        self.close()
        try:
            s = socket.create_connection((self.host, self.port), timeout=self.timeout)
            s.settimeout(self.timeout)
            self.sock = s
            return True
        except Exception as e:
            self.sock = None
            return error("Ошибка подключения", str(e))
    
    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        self.sock = None
    
    def read(self, start: int, count: int, func: int = 3):
        with self.lock:
            if not self.sock:
                conn = self.connect()
                if conn is not True:
                    return conn
            
            frame = struct.pack(">B B H H", self.slave_id, func, start, count)
            crc = modbus_crc16(frame)
            frame += struct.pack("<H", crc)
            
            try:
                self.sock.sendall(frame)
            except Exception as e:
                self.close()
                return error("Ошибка отправки запроса", str(e))
            
            try:
                response = self.sock.recv(256)
            except socket.timeout:
                return error("Таймаут — устройство не ответило")
            except Exception as e:
                self.close()
                return error("Ошибка при получении ответа", str(e))
            
            if not response:
                return error("Ответ пустой — устройство не ответило")
            
            data = response[:-2]
            recv_crc = (response[-1] << 8) | response[-2]
            calc_crc = modbus_crc16(data)
            
            if calc_crc != recv_crc:
                return error("Ошибка CRC", f"Expected {hex(calc_crc)}, got {hex(recv_crc)}")
            
            try:
                byte_count = response[2]
                values = []
                for i in range(0, byte_count, 2):
                    v = (response[3 + i] << 8) | response[4 + i]
                    values.append(v)
            except Exception as e:
                return error("Некорректный формат ответа", str(e))
            
            return success(values)
    
    def write_single(self, address: int, value: int):
        with self.lock:
            if not self.sock:
                conn = self.connect()
                if conn is not True:
                    return conn
            
            frame = struct.pack(">B B H H", self.slave_id, 6, address, value)
            crc = modbus_crc16(frame)
            frame += struct.pack("<H", crc)
            
            try:
                self.sock.sendall(frame)
                resp = self.sock.recv(256)
                return success(resp.hex())
            except Exception as e:
                return error("Ошибка записи регистра", str(e))
    
    def write_multiple(self, address: int, values: List[int]):
        with self.lock:
            if not self.sock:
                conn = self.connect()
                if conn is not True:
                    return conn
            
            count = len(values)
            byte_count = count * 2
            frame = struct.pack(">B B H H B", self.slave_id, 16, address, count, byte_count)
            
            for v in values:
                frame += struct.pack(">H", v)
            
            crc = modbus_crc16(frame)
            frame += struct.pack("<H", crc)
            
            try:
                self.sock.sendall(frame)
                resp = self.sock.recv(256)
                return success(resp.hex())
            except Exception as e:
                return error("Ошибка множественной записи", str(e))

@router.get("/read")
def modbus_read(host: str, port: int, slave: int, start: int, count: int, func_code: int = 3):
    client = ModbusTCP(host, port, slave)
    return client.read(start=start, count=count, func=func_code)

@router.get("/write_single")
def modbus_write_single(host: str, port: int, slave: int, address: int, value: int):
    client = ModbusTCP(host, port, slave)
    return client.write_single(address, value)

@router.post("/write_multiple")
def modbus_write_multiple(host: str, port: int, slave: int, address: int, values: List[int]):
    client = ModbusTCP(host, port, slave)
    return client.write_multiple(address, values)


# ============================================================================
# Роуты-прокси 
# ============================================================================

async def _proxy_to_worker(method: str, endpoint: str, params: dict = None, json_data: dict = None) -> dict:
    """
    Проксирует запрос к воркеру.
    
    Args:
        method: HTTP метод (GET, POST, DELETE)
        endpoint: Endpoint воркера
        params: Query параметры
        json_data: Тело запроса
        
    Returns:
        Результат от воркера
    """
    # Короткие метки для логов/диагностики
    op = endpoint.strip("/").split("/")[-1] if endpoint else "unknown"
    proto = (params or {}).get("protocol") if params else None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{WORKER_BASE_URL}{endpoint}"
            
            if method == "GET":
                response = await client.get(url, params=params)
            elif method == "POST":
                response = await client.post(url, params=params, json=json_data)
            elif method == "DELETE":
                response = await client.delete(url, params=params)
            else:
                raise ValueError(f"Неизвестный метод: {method}")
            
            if response.status_code != 200:
                # Пытаемся разобрать JSON, но не падаем если это не JSON
                try:
                    payload = response.json()
                except Exception:
                    payload = None

                detail = None
                if isinstance(payload, dict) and "detail" in payload:
                    detail = payload.get("detail")
                else:
                    detail = response.text

                # Пробрасываем таймауты как 504 Gateway Timeout без трейсбека
                if response.status_code in (status.HTTP_504_GATEWAY_TIMEOUT, status.HTTP_408_REQUEST_TIMEOUT) or (
                    isinstance(detail, str) and ("таймаут" in detail.lower() or "timeout" in detail.lower())
                ):
                    logger.warning(f"Modbus timeout (op={op}, protocol={proto}): {detail}")
                    raise HTTPException(
                        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                        detail={
                            "ok": False,
                            "code": "modbus_timeout",
                            "message": "Таймаут — устройство не ответило",
                            "operation": op,
                            "protocol": proto,
                            "params": {**(params or {}), **({"body": json_data} if json_data else {})},
                        },
                    )

                # Иные ошибки воркера пробрасываем как есть (без трейсбека)
                logger.error(f"Worker error {response.status_code} (op={op}, protocol={proto}): {detail}")
                raise HTTPException(status_code=response.status_code, detail=detail)
            
            return response.json()
            
    except httpx.TimeoutException as e:
        # Явный таймаут до воркера — 504, без трейсбека
        logger.warning(f"Timeout contacting worker (op={op}, protocol={proto}): {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "ok": False,
                "code": "worker_timeout",
                "message": "Таймаут при обращении к сервису воркера",
                "operation": op,
                "protocol": proto,
                "params": {**(params or {}), **({"body": json_data} if json_data else {})},
            },
        )
    except httpx.ConnectError as e:
        # Воркер недоступен (DNS/соединение) — 503, без трейсбека
        logger.error(f"Worker unavailable (op={op}, protocol={proto}): {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "ok": False,
                "code": "worker_unavailable",
                "message": "Воркер недоступен",
                "operation": op,
            },
        )
    except httpx.RequestError as e:
        # Прочие сетевые ошибки до воркера — 503, без трейсбека
        logger.error(f"Ошибка при обращении к воркеру (op={op}, protocol={proto}): {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "ok": False,
                "code": "worker_request_error",
                "message": "Ошибка при обращении к воркеру",
                "operation": op,
            },
        )
    except Exception as e:
        # Непредвиденные ошибки — 500, но без трейсбека
        logger.error(f"Ошибка при проксировании запроса (op={op}, protocol={proto}): {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "ok": False,
                "code": "proxy_internal_error",
                "message": f"Ошибка при обращении к воркеру: {str(e)}",
                "operation": op,
            },
        )


async def _resolve_connection_params(
    db: AsyncSession,
    object_id: Optional[str],
    protocol: Optional[str],
    host: Optional[str],
    port: Optional[int],
) -> Tuple[str, str, int]:
    """Дополняет/проверяет параметры подключения. Если передан object_id — берём protocol/host/port из БД.
    Если после подстановки нет необходимых значений — бросаем 400.
    """

    if object_id:
        obj = await get_energetic_object(db, object_id)
        if not obj:
            raise HTTPException(status_code=404, detail=f"Энергообъект {object_id} не найден")
        protocol = protocol or obj.protocol
        host = host or obj.ip_address
        port = port or obj.port

    if not protocol or not host or not port:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нужно указать protocol/host/port явно или object_id с заполненными данными"
        )

    if protocol == "modbus_over_tcp" and not object_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для modbus_over_tcp требуется object_id (уникальный объект/клиент)"
        )

    return protocol, host, int(port)


@router.get("/v1/read")
async def modbus_read(
    protocol: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = 502,
    slave_id: int = 1,
    object_id: Optional[str] = None,
    start: int = 0,
    count: int = 1,
    func_code: int = 3,
    db: AsyncSession = Depends(get_db),
):
    """
    Читает регистры из Modbus устройства.
    Проксирует запрос к воркеру.
    
    Args:
        protocol: Тип протокола - "modbus_tcp" (Victron) или "modbus_over_tcp" (Deye)
        host: IP-адрес устройства
        port: Порт (по умолчанию 502)
        slave_id: Slave ID устройства (для modbus_over_tcp)
        object_id: ID энергообъекта (для modbus_over_tcp)
        start: Начальный адрес регистра
        count: Количество регистров
        func_code: 3 (holding) или 4 (input) для TCP; для modbus_over_tcp проксируется как есть
        
    Returns:
        Dict с данными регистров или ошибкой
    """
    protocol, host, port = await _resolve_connection_params(db, object_id, protocol, host, port)

    params = {
        "protocol": protocol,
        "host": host,
        "port": port,
        "slave_id": slave_id,
        "start": start,
        "count": count,
        "func_code": func_code,
    }
    if object_id:
        params["object_id"] = object_id
    
    return await _proxy_to_worker("GET", "/modbus/read", params=params)


@router.post("/v1/write_single")
async def modbus_write_single(
    protocol: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = 502,
    slave_id: int = 1,
    object_id: Optional[str] = None,
    address: int = 0,
    value: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """
    Записывает одиночный регистр.
    Проксирует запрос к воркеру.
    
    Args:
        protocol: Тип протокола - "modbus_tcp" или "modbus_over_tcp"
        host: IP-адрес устройства
        port: Порт (по умолчанию 502)
        slave_id: Slave ID устройства
        object_id: ID энергообъекта (для modbus_over_tcp)
        address: Адрес регистра
        value: Значение для записи
        
    Returns:
        Dict с результатом
    """
    protocol, host, port = await _resolve_connection_params(db, object_id, protocol, host, port)

    params = {
        "protocol": protocol,
        "host": host,
        "port": port,
        "slave_id": slave_id,
        "address": address,
        "value": value,
    }
    if object_id:
        params["object_id"] = object_id
    
    return await _proxy_to_worker("POST", "/modbus/write_single", params=params)


@router.post("/v1/write_multiple")
async def modbus_write_multiple(
    protocol: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = 502,
    slave_id: int = 1,
    object_id: Optional[str] = None,
    address: int = 0,
    values: List[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Записывает несколько регистров.
    Проксирует запрос к воркеру.
    
    Args:
        protocol: Тип протокола - "modbus_tcp" или "modbus_over_tcp"
        host: IP-адрес устройства
        port: Порт (по умолчанию 502)
        slave_id: Slave ID устройства
        object_id: ID энергообъекта (для modbus_over_tcp)
        address: Начальный адрес
        values: Список значений для записи
        
    Returns:
        Dict с результатом
    """
    if not values:
        values = []

    protocol, host, port = await _resolve_connection_params(db, object_id, protocol, host, port)

    params = {
        "protocol": protocol,
        "host": host,
        "port": port,
        "slave_id": slave_id,
        "address": address,
    }
    if object_id:
        params["object_id"] = object_id
    
    return await _proxy_to_worker("POST", "/modbus/write_multiple", params=params, json_data={"values": values})


@router.delete("/v1/close")
async def modbus_close(
    protocol: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = 502,
    object_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Закрывает соединение с Modbus устройством.
    Проксирует запрос к воркеру.
    
    Args:
        protocol: Тип протокола - "modbus_tcp" или "modbus_over_tcp"
        host: IP-адрес устройства
        port: Порт (по умолчанию 502)
        object_id: ID энергообъекта (для modbus_over_tcp)
        
    Returns:
        Dict с результатом
    """
    protocol, host, port = await _resolve_connection_params(db, object_id, protocol, host, port)

    params = {
        "protocol": protocol,
        "host": host,
        "port": port,
    }
    if object_id:
        params["object_id"] = object_id
    
    return await _proxy_to_worker("DELETE", "/modbus/close", params=params)


