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
        
    Returns:
        Dict с данными регистров или ошибкой
    """
    try:
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
                    result = await client.read_holding_registers(start, count)
                elif func_code == 4:
                    result = await client.read_input_registers(start, count)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="func_code должен быть 3 (holding) или 4 (input)"
                    )

                if result.isError():
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"Modbus ошибка при чтении: {result}"
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
        
    Returns:
        Dict с результатом
    """
    try:
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
        
    Returns:
        Dict с результатом
    """
    try:
        if not values:
            values = []
        
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
