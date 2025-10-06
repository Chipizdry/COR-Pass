


from fastapi import APIRouter, HTTPException, Depends
from loguru import logger
from cor_pass.services.modbus_service import modbus_service

router = APIRouter(prefix="/RAW_modbus", tags=["modbus"])


@router.get("/status")
async def get_modbus_status():
    """Получение статуса подключения к Modbus серверу"""
    try:
        is_available = await modbus_service.check_connection()
        return {
            "status": "connected" if modbus_service.is_connected else "disconnected",
            "host_available": is_available,
            "host": modbus_service.host,
            "port": modbus_service.port,
            "details": "Modbus сервер доступен" if is_available else "Modbus сервер недоступен"
        }
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса Modbus: {e}")
        return {
            "status": "error",
            "host": modbus_service.host,
            "port": modbus_service.port,
            "error": str(e)
        }


@router.get("/test-connection")
async def test_modbus_connection():
    """Тест подключения к Modbus серверу"""
    try:
        success = await modbus_service.connect()
        return {
            "success": success,
            "message": "Подключение установлено" if success else "Не удалось подключиться",
            "host": modbus_service.host,
            "port": modbus_service.port
        }
    except Exception as e:
        logger.error(f"Ошибка при тестировании подключения: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка подключения: {e}")


@router.get("/registers")
async def read_modbus_registers():
    """Чтение регистров с Modbus устройства"""
    try:
        # Сначала проверяем доступность
        if not await modbus_service.check_connection():
            raise HTTPException(
                status_code=503,
                detail=f"Modbus сервер {modbus_service.host}:{modbus_service.port} недоступен"
            )

        # Чтение 10 регистров с устройства 8, начиная с адреса 0
        registers = await modbus_service.read_holding_registers(
            slave_id=8,
            address=0,
            count=10
        )
        
        if registers is None:
            raise HTTPException(
                status_code=500, 
                detail="Не удалось прочитать регистры с Modbus устройства. Проверьте настройки slave_id и адреса."
            )
        
        return {
            "slave_id": 8,
            "registers_count": len(registers),
            "registers": registers,
            "registers_hex": [hex(reg) for reg in registers],
            "registers_binary": [bin(reg) for reg in registers]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при чтении регистров: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка чтения: {e}")


@router.get("/registers/{start_address}/{count}")
async def read_custom_registers(start_address: int, count: int):
    """Чтение произвольного количества регистров с указанного адреса"""
    try:
        if count > 100:  # Ограничение для безопасности
            raise HTTPException(
                status_code=400, 
                detail="Слишком большое количество регистров для чтения (максимум 100)"
            )
            
        if count <= 0:
            raise HTTPException(
                status_code=400, 
                detail="Количество регистров должно быть положительным числом"
            )

        # Сначала проверяем доступность
        if not await modbus_service.check_connection():
            raise HTTPException(
                status_code=503,
                detail=f"Modbus сервер {modbus_service.host}:{modbus_service.port} недоступен"
            )
            
        registers = await modbus_service.read_holding_registers(
            slave_id=8,
            address=start_address,
            count=count
        )
        
        if registers is None:
            raise HTTPException(
                status_code=500, 
                detail="Не удалось прочитать регистры с Modbus устройства"
            )
        
        return {
            "slave_id": 8,
            "start_address": start_address,
            "registers_count": len(registers),
            "registers": registers,
            "registers_hex": [hex(reg) for reg in registers],
            "registers_binary": [bin(reg) for reg in registers]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при чтении регистров: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка чтения: {e}")