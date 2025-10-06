


import asyncio
from loguru import logger
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
import socket


class ModbusService:
    def __init__(self, host: str = "192.168.154.111", port: int = 502, use_custom_protocol: bool = True):
        self.host = host
        self.port = port
        self.use_custom_protocol = use_custom_protocol
        self.client = None
        self.is_connected = False

    async def check_connection(self) -> bool:
        """Проверка доступности хоста"""
        try:
            loop = asyncio.get_event_loop()
            conn = asyncio.open_connection(self.host, self.port)
            try:
                reader, writer = await asyncio.wait_for(conn, timeout=5.0)
                writer.close()
                await writer.wait_closed()
                return True
            except (asyncio.TimeoutError, ConnectionRefusedError):
                return False
        except Exception as e:
            logger.warning(f"Хост {self.host}:{self.port} недоступен: {e}")
            return False

    async def connect(self) -> bool:
        """Установка соединения с Modbus сервером"""
        try:
            if not await self.check_connection():
                logger.error(f"Modbus сервер {self.host}:{self.port} недоступен")
                return False

            loop = asyncio.get_event_loop()
            self.client = await loop.run_in_executor(
                None, 
                lambda: ModbusTcpClient(
                    host=self.host,
                    port=self.port,
                    timeout=10,
                    retries=1
                )
            )
            
            connection_result = await loop.run_in_executor(None, self.client.connect)
            
            if connection_result:
                logger.info(f"✅ Успешное подключение к Modbus серверу {self.host}:{self.port}")
                self.is_connected = True
                return True
            else:
                logger.error(f"❌ Не удалось подключиться к Modbus серверу")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при подключении к Modbus: {e}")
            return False

    async def _send_custom_request(self, slave_id: int = 8, address: int = 0, count: int = 10):
        """Отправка кастомного Modbus запроса с префиксом AA FE 55"""
        try:
            loop = asyncio.get_event_loop()
            
            # Создаем raw socket для отправки кастомного протокола
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.host, self.port))
            
            # Ваш кастомный запрос из UART
            custom_request = bytes([
                0xAA, 0xFE, 0x55, 0x00, 0x00, 0x01,  # Префикс протокола
                0x00, 0x00, 0x00, 0x06,              # Длина
                slave_id,                            # Unit ID
                0x03,                                # Function Code
                (address >> 8) & 0xFF, address & 0xFF,  # Starting Address
                (count >> 8) & 0xFF, count & 0xFF,   # Quantity
            ])
            
            logger.info(f"Отправляем кастомный Modbus запрос: {custom_request.hex().upper()}")
            sock.send(custom_request)
            
            response = sock.recv(1024)
            sock.close()
            
            if response:
                logger.info(f"Получен ответ: {response.hex().upper()}")
                # Здесь нужно распарсить ответ согласно вашему протоколу
                # Пока вернем сырые данные
                return {"raw_response": response.hex().upper(), "protocol": "custom"}
            else:
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при отправке кастомного запроса: {e}")
            return None

    async def _send_standard_request(self, slave_id: int = 8, address: int = 0, count: int = 10):
        """Отправка стандартного Modbus TCP запроса"""
        try:
            if not self.is_connected or not self.client or not self.client.connected:
                if not await self.connect():
                    return None

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.client.read_holding_registers(
                    address=address,
                    count=count,
                    slave=slave_id
                )
            )

            if result.isError():
                logger.error(f"Modbus ошибка: {result}")
                return None

            logger.info(f"✅ Успешно прочитано {len(result.registers)} регистров")
            return result.registers

        except ModbusException as e:
            logger.error(f"Modbus исключение: {e}")
            return None
        except Exception as e:
            logger.error(f"Общая ошибка: {e}")
            return None

    async def read_holding_registers(self, slave_id: int = 8, address: int = 0, count: int = 10):
        """Чтение регистров - выбирает протокол в зависимости от настройки"""
        if self.use_custom_protocol:
            return await self._send_custom_request(slave_id, address, count)
        else:
            return await self._send_standard_request(slave_id, address, count)

    async def close(self):
        """Закрытие соединения"""
        if self.client:
            await asyncio.get_event_loop().run_in_executor(None, self.client.close)
            self.is_connected = False
            logger.info("Соединение закрыто")


# Глобальный экземпляр с кастомным протоколом
modbus_service = ModbusService(use_custom_protocol=True)