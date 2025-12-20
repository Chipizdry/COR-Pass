"""
Роуты Modbus для воркера.
Обрабатывают запросы к конкретным экземплярам Modbus клиентов по типу протокола.
"""

from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
from loguru import logger

from .modbus_client import (
    get_or_create_modbus_client,
    close_modbus_client,
    ModbusTCP,
)
from .modbus_broker import get_broker, RequestPriority

router = APIRouter(prefix="/modbus", tags=["Modbus"])

@router.get("/read")
async def modbus_read(
    protocol: str,
    host: str,
    port: int = 502,
    slave_id: int = 1,
    object_id: Optional[str] = None,
    start: int = 0,
    count: int = 1,
    func_code: int = 3,
    use_broker: bool = True,
):
    """
    Читает регистры из Modbus устройства.
    
    
    Args:
        protocol: Тип протокола - "modbus_tcp" или "modbus_over_tcp"
        host: IP-адрес устройства
        port: Порт (по умолчанию 502)
        slave_id: Slave ID устройства (для modbus_over_tcp)
        object_id: ID энергообъекта (для modbus_over_tcp)
        start: Начальный адрес регистра
        count: Количество регистров
        func_code: 3 (holding) или 4 (input) для modbus_tcp; для modbus_over_tcp передается как есть
        use_broker: Использовать брокер очередей (рекомендуется)
        
    Returns:
        Dict с данными регистров или ошибкой
    """
    try:
        # Используем брокер 
        if use_broker:
            broker = get_broker()
            result = await broker.submit_request(
                protocol=protocol,
                host=host,
                port=port,
                operation="read",
                params={"start": start, "count": count, "func_code": func_code},
                slave_id=slave_id,
                object_id=object_id,
                priority=RequestPriority.USER_READ,
                timeout=10.0,
                request_id=f"api_read_{host}_{start}",
            )
            return result
        
        # Старый способ 
        client = await get_or_create_modbus_client(
            protocol=protocol,
            ip_address=host,
            port=port,
            object_id=object_id,
            slave_id=slave_id,
        )
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Не удалось создать {protocol} клиент для {host}:{port}"
            )
        
        # Для Modbus OVER TCP
        if protocol == "modbus_over_tcp":
            if not isinstance(client, ModbusTCP):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Неверный тип клиента для modbus_over_tcp"
                )
            
            result = client.read(start=start, count=count, func=func_code)
            
            if not result.get("ok"):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=result.get("error", "Неизвестная ошибка")
                )
            
            return {"ok": True, "data": result.get("data")}
        
        # Для Modbus TCP
        else:
            # AsyncModbusTcpClient
            try:
                if func_code == 3:
                    result = await client.read_holding_registers(address=start, count=count)
                elif func_code == 4:
                    result = await client.read_input_registers(address=start, count=count)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="func_code должен быть 3 (holding) или 4 (input)"
                    )

                if result.isError():
                    # Парсим Modbus exception code для более понятного сообщения
                    error_msg = str(result)
                    exception_code = getattr(result, 'exception_code', None)
                    
                    # Расшифровываем коды ошибок Modbus
                    error_descriptions = {
                        1: "ILLEGAL FUNCTION - функция не поддерживается устройством",
                        2: "ILLEGAL DATA ADDRESS - адрес регистра не существует или недоступен",
                        3: "ILLEGAL DATA VALUE - недопустимое значение данных",
                        4: "SLAVE DEVICE FAILURE - устройство не может выполнить запрос",
                        5: "ACKNOWLEDGE - запрос принят, но обработка займёт много времени",
                        6: "SLAVE DEVICE BUSY - устройство занято",
                        10: "GATEWAY PATH UNAVAILABLE - шлюз не может достучаться до устройства (проверьте IP и порт)",
                        11: "GATEWAY TARGET DEVICE FAILED TO RESPOND - целевое устройство не отвечает",
                    }
                    
                    if exception_code in error_descriptions:
                        error_msg = f"{error_descriptions[exception_code]} (код {exception_code}). Проверьте адрес регистра (start={start}) в документации устройства."
                    
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"Modbus ошибка: {error_msg}"
                    )
                
                return {"ok": True, "data": result.registers}
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Ошибка при чтении регистров: {str(e)}"
                )
        
    except HTTPException:
        raise
    except TimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Таймаут запроса: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"Ошибка в modbus_read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сервера: {str(e)}"
        )


@router.post("/write_single")
async def modbus_write_single(
    protocol: str,
    host: str,
    port: int = 502,
    slave_id: int = 1,
    object_id: Optional[str] = None,
    address: int = 0,
    value: int = 0,
    use_broker: bool = True,
):
    """
    Записывает одиночный регистр.
    
    Args:
        protocol: Тип протокола - "modbus_tcp" или "modbus_over_tcp"
        host: IP-адрес устройства
        port: Порт (по умолчанию 502)
        slave_id: Slave ID устройства
        object_id: ID энергообъекта (для modbus_over_tcp)
        address: Адрес регистра
        value: Значение для записи
        use_broker: Использовать брокер очередей (рекомендуется)
        
    Returns:
        Dict с результатом
    """
    try:
        # Используем брокер
        if use_broker:
            broker = get_broker()
            result = await broker.submit_request(
                protocol=protocol,
                host=host,
                port=port,
                operation="write_single",
                params={"address": address, "value": value},
                slave_id=slave_id,
                object_id=object_id,
                priority=RequestPriority.USER_WRITE,
                timeout=10.0,
                request_id=f"api_write_{host}_{address}",
            )
            return result
        
        # Старый способ
        client = await get_or_create_modbus_client(
            protocol=protocol,
            ip_address=host,
            port=port,
            object_id=object_id,
            slave_id=slave_id,
        )
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Не удалось создать {protocol} клиент для {host}:{port}"
            )
        
        # Для Modbus OVER TCP
        if protocol == "modbus_over_tcp":
            if not isinstance(client, ModbusTCP):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Неверный тип клиента для modbus_over_tcp"
                )
            
            result = client.write_single(address=address, value=value)
            
            if not result.get("ok"):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=result.get("error", "Неизвестная ошибка")
                )
            
            return {"ok": True, "data": result.get("data")}
        
        # Для Modbus TCP
        else:
            try:
                result = await client.write_register(address, value)
                if result.isError():
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"Modbus ошибка при записи: {result}"
                    )
                
                return {"ok": True, "message": "Регистр успешно записан"}
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Ошибка при записи регистра: {str(e)}"
                )
        
    except HTTPException:
        raise
    except TimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Таймаут запроса: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"Ошибка в modbus_write_single: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сервера: {str(e)}"
        )


@router.post("/write_multiple")
async def modbus_write_multiple(
    protocol: str,
    host: str,
    port: int = 502,
    slave_id: int = 1,
    object_id: Optional[str] = None,
    address: int = 0,
    values: List[int] = None,
    use_broker: bool = True,
):
    """
    Записывает несколько регистров.
    
    Args:
        protocol: Тип протокола - "modbus_tcp" или "modbus_over_tcp"
        host: IP-адрес устройства
        port: Порт (по умолчанию 502)
        slave_id: Slave ID устройства
        object_id: ID энергообъекта (для modbus_over_tcp)
        address: Начальный адрес
        values: Список значений для записи
        use_broker: Использовать брокер очередей (рекомендуется)
        
    Returns:
        Dict с результатом
    """
    try:
        if not values:
            values = []
        
        # Используем брокер
        if use_broker:
            broker = get_broker()
            result = await broker.submit_request(
                protocol=protocol,
                host=host,
                port=port,
                operation="write_multiple",
                params={"address": address, "values": values},
                slave_id=slave_id,
                object_id=object_id,
                priority=RequestPriority.USER_WRITE,
                timeout=15.0,  # Больше таймаут для множественной записи
                request_id=f"api_write_multi_{host}_{address}",
            )
            return result
        
        # Старый способ
        client = await get_or_create_modbus_client(
            protocol=protocol,
            ip_address=host,
            port=port,
            object_id=object_id,
            slave_id=slave_id,
        )
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Не удалось создать {protocol} клиент для {host}:{port}"
            )
        
        # Для Modbus OVER TCP
        if protocol == "modbus_over_tcp":
            if not isinstance(client, ModbusTCP):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Неверный тип клиента для modbus_over_tcp"
                )
            
            result = client.write_multiple(address=address, values=values)
            
            if not result.get("ok"):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=result.get("error", "Неизвестная ошибка")
                )
            
            return {"ok": True, "data": result.get("data")}
        
        # Для Modbus TCP
        else:
            try:
                result = await client.write_registers(address, values)
                if result.isError():
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"Modbus ошибка при записи: {result}"
                    )
                
                return {"ok": True, "message": f"{len(values)} регистров успешно записано"}
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Ошибка при записи регистров: {str(e)}"
                )
        
    except HTTPException:
        raise
    except TimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Таймаут запроса: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"Ошибка в modbus_write_multiple: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сервера: {str(e)}"
        )


@router.delete("/close")
async def modbus_close(
    protocol: str,
    host: str,
    port: int = 502,
    object_id: Optional[str] = None,
):
    """
    Закрывает соединение с Modbus устройством.
    
    Args:
        protocol: Тип протокола - "modbus_tcp" или "modbus_over_tcp"
        host: IP-адрес устройства
        port: Порт (по умолчанию 502)
        object_id: ID энергообъекта (для modbus_over_tcp)
        
    Returns:
        Dict с результатом
    """
    try:
        await close_modbus_client(
            protocol=protocol,
            ip_address=host,
            port=port,
            object_id=object_id,
        )
        
        return {"ok": True, "message": f"Соединение с {host}:{port} закрыто"}
        
    except Exception as e:
        logger.exception(f"Ошибка в modbus_close: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при закрытии соединения: {str(e)}"
        )


@router.get("/broker/stats")
async def get_broker_stats(
    protocol: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    object_id: Optional[str] = None,
):
    """
    Получает статистику работы брокера запросов.
    
    Args:
        protocol: Фильтр по протоколу (опционально)
        host: Фильтр по хосту (опционально)
        port: Фильтр по порту (опционально)
        object_id: Фильтр по ID объекта (опционально)
        
    Returns:
        Статистика очереди запросов
    """
    try:
        broker = get_broker()
        
        if protocol and host and port is not None:
            # Статистика для конкретного устройства
            stats = broker.get_stats(protocol, host, port, object_id)
            return {
                "device": f"{protocol}://{host}:{port}" + (f"/{object_id}" if object_id else ""),
                "stats": stats
            }
        else:
            # Статистика для всех устройств
            all_stats = broker.get_all_stats()
            return {
                "devices": all_stats,
                "total_devices": len(all_stats)
            }
        
    except Exception as e:
        logger.exception(f"Ошибка в get_broker_stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сервера: {str(e)}"
        )
