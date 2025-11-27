"""
Общие константы и Enum для PI30 команд инвертора.
Используется в worker/websocket_app.py и device_proxy.py для унификации.

ВАЖНО: Согласно протоколу PI30/HS/MS/MSX:
- Команды ОТ КОМПЬЮТЕРА идут БЕЗ CRC, только COMMAND<cr>
- Ответы ОТ УСТРОЙСТВА содержат CRC: (DATA<CRC><cr>
- Функция calculate_crc() нужна для проверки ответов устройства, не для отправки команд

Источник: HS_MS_MSX-RS232-Protocol.txt, Inverter-protocol.txt
"""
from enum import Enum
from typing import Dict


class PI30Command(str, Enum):
    """Допустимые PI30 команды протокола инвертора"""
    QPIRI = "QPIRI"   # Inverter rated parameters
    QPIGS = "QPIGS"   # General status values
    QPIWS = "QPIWS"   # Warning status bits
    QPIGS2 = "QPIGS2" # Additional PV2 data
    QMOD = "QMOD"     # Device mode
    QID = "QID"       # Serial number
    QMN = "QMN"       # Model name
    QDI = "QDI"       # Device settings
    QFLAG = "QFLAG"   # Flag/status register


PI30_COMMAND_DESCRIPTIONS: Dict[PI30Command, str] = {
    PI30Command.QPIRI: "Inverter rated parameters",
    PI30Command.QPIGS: "General status values",
    PI30Command.QPIWS: "Warning status bits",
    PI30Command.QPIGS2: "Additional PV2 data",
    PI30Command.QMOD: "Device mode",
    PI30Command.QID: "Serial number",
    PI30Command.QMN: "Model name",
    PI30Command.QDI: "Device settings",
    PI30Command.QFLAG: "Flag/status register",
}


def calculate_crc(command: str) -> bytes:
    """
    Вычисляет CRC для проверки ответов PI30/HS инвертора.
    
    ПРИМЕЧАНИЕ: Эта функция нужна для ПРОВЕРКИ ответов устройства,
    НЕ для формирования команд! Команды от ПК идут без CRC.
    
    Алгоритм из документации (Appendix 4.1):
    - CRC-16 XMODEM (также известен как CRC-16 CCITT)
    - Polynomial: 0x1021
    - Initial value: 0x0000
    
    Args:
        command: Строка для которой вычисляется CRC (например, ответ устройства)
        
    Returns:
        2 байта CRC в формате big-endian
        
    Example:
        >>> crc = calculate_crc("QPIGS")
        >>> crc.hex()
        'b7a9'
    """
    crc = 0
    for byte in command.encode('ascii'):
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
    
    # Возвращаем CRC в big-endian формате (старший байт первым)
    return crc.to_bytes(2, byteorder='big')


def format_pi30_command(command: str) -> str:
    """
    Форматирует PI30 команду для отправки от ПК к инвертору.
    
    ВАЖНО: Согласно протоколу, команды ОТ КОМПЬЮТЕРА идут БЕЗ CRC!
    Цитата из документации:
    "All commands return values have a CRC check before '0x0d', 
     but the command coming from PC without CRC."
    
    Формат команды от ПК: COMMAND<cr>
    Формат ответа устройства: (DATA<CRC><cr>
    
    Args:
        command: Команда (например, "QPIGS")
        
    Returns:
        Команда с carriage return готовая к отправке
        
    Example:
        >>> format_pi30_command("QPIGS")
        "QPIGS\\r"
    """
    # Только команда + CR (0x0D), БЕЗ CRC согласно протоколу
    return command + '\r'


def format_pi30_command_with_crc_hex(command: str) -> str:
    """
    Форматирует PI30 команду в hex формат с CRC и возвратом каретки.
    Используется для устройств, которые ожидают команды с CRC.
    
    Формат: COMMAND (ASCII hex) + CRC (2 байта) + CR (0x0D)
    
    Args:
        command: Команда (например, "QPIGS")
        
    Returns:
        Hex строка вида "51 50 49 47 53 B7 A9 0D" (для QPIGS)
        
    Example:
        >>> format_pi30_command_with_crc_hex("QPIGS")
        "51 50 49 47 53 B7 A9 0D"
    """
    # Конвертируем команду в hex байты
    command_hex = ' '.join(f'{ord(c):02X}' for c in command)
    
    # Вычисляем CRC
    crc_bytes = calculate_crc(command)
    crc_hex = ' '.join(f'{b:02X}' for b in crc_bytes)
    
    # Добавляем CR (0x0D)
    cr_hex = "0D"
    
    # Собираем полную команду
    return f"{command_hex} {crc_hex} {cr_hex}"


__all__ = [
    "PI30Command", 
    "PI30_COMMAND_DESCRIPTIONS", 
    "calculate_crc", 
    "format_pi30_command",
    "format_pi30_command_with_crc_hex"
]
