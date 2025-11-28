"""
Улучшенный сервис для работы с TOTP (Time-based One-Time Password)
Используется для:
1. Генерации QR кодов для сотрудников (заправка)
2. Авторизации между бэкендами (COR-ID <-> Finance Backend)
"""

import pyotp
import time
import secrets
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from loguru import logger
from fastapi import HTTPException, status


class TOTPService:
    """Сервис для работы с TOTP"""
    
    # Настройки TOTP
    TOTP_INTERVAL = 30  # Интервал в секундах (стандарт)
    TOTP_DIGITS = 6     # Количество цифр в коде
    TOTP_WINDOW = 1     # Окно для проверки (±1 интервал = ±30 сек)
    
    @staticmethod
    def generate_secret() -> str:
        """
        Генерирует новый секретный ключ для TOTP
        
        Returns:
            str: Base32-encoded секрет
        """
        return pyotp.random_base32()
    
    @staticmethod
    def generate_totp_code(secret: str, interval: Optional[int] = None) -> Tuple[str, int]:
        """
        Генерирует текущий TOTP код
        
        Args:
            secret: Base32-encoded секрет
            interval: Интервал TOTP в секундах. Если None - используется стандартный
            
        Returns:
            Tuple[str, int]: (TOTP код, время до истечения в секундах)
        """
        try:
            if interval is None:
                interval = TOTPService.TOTP_INTERVAL
                
            totp = pyotp.TOTP(
                secret,
                interval=interval,
                digits=TOTPService.TOTP_DIGITS
            )
            code = totp.now()
            time_remaining = interval - (int(time.time()) % interval)
            
            return code, time_remaining
        except Exception as e:
            logger.error(f"Failed to generate TOTP code: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate TOTP code"
            )
    
    @staticmethod
    def verify_totp_code(secret: str, code: str, window: Optional[int] = None, interval: Optional[int] = None) -> bool:
        """
        Проверяет TOTP код
        
        Args:
            secret: Base32-encoded секрет
            code: TOTP код для проверки
            window: Окно проверки (±N интервалов). По умолчанию TOTP_WINDOW
            interval: Интервал TOTP в секундах. Если None - используется стандартный
            
        Returns:
            bool: True если код валиден, False иначе
        """
        try:
            if window is None:
                window = TOTPService.TOTP_WINDOW
            if interval is None:
                interval = TOTPService.TOTP_INTERVAL
                
            totp = pyotp.TOTP(
                secret,
                interval=interval,
                digits=TOTPService.TOTP_DIGITS
            )
            
            # verify() проверяет текущий код и ±window интервалов
            is_valid = totp.verify(code, valid_window=window)
            
            if is_valid:
                logger.info(f"TOTP code verified successfully")
            else:
                logger.warning(f"TOTP code verification failed")
                
            return is_valid
        except Exception as e:
            logger.error(f"Failed to verify TOTP code: {e}")
            return False
    
    @staticmethod
    def get_provisioning_uri(secret: str, name: str, issuer: str = "COR-ID") -> str:
        """
        Создаёт provisioning URI для QR кода (для настройки в Google Authenticator и т.п.)
        
        Args:
            secret: Base32-encoded секрет
            name: Имя аккаунта (например, email или cor_id)
            issuer: Название сервиса
            
        Returns:
            str: URI для генерации QR кода
        """
        totp = pyotp.TOTP(
            secret,
            interval=TOTPService.TOTP_INTERVAL,
            digits=TOTPService.TOTP_DIGITS
        )
        return totp.provisioning_uri(name=name, issuer_name=issuer)
    
    @staticmethod
    def generate_timestamp_token() -> str:
        """
        Генерирует токен на основе timestamp для дополнительной защиты
        
        Returns:
            str: Base64-encoded токен с timestamp
        """
        timestamp = int(time.time())
        random_bytes = secrets.token_bytes(8)
        token_data = f"{timestamp}:{random_bytes.hex()}"
        return base64.urlsafe_b64encode(token_data.encode()).decode()
    
    @staticmethod
    def verify_timestamp_token(token: str, max_age_seconds: int = 300) -> bool:
        """
        Проверяет timestamp токен
        
        Args:
            token: Base64-encoded токен
            max_age_seconds: Максимальный возраст токена в секундах (по умолчанию 5 минут)
            
        Returns:
            bool: True если токен валиден и не истёк
        """
        try:
            decoded = base64.urlsafe_b64decode(token.encode()).decode()
            timestamp_str = decoded.split(':')[0]
            timestamp = int(timestamp_str)
            
            current_time = int(time.time())
            age = current_time - timestamp
            
            if age < 0 or age > max_age_seconds:
                logger.warning(f"Timestamp token expired or invalid. Age: {age}s")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Failed to verify timestamp token: {e}")
            return False


# Singleton instance
totp_service = TOTPService()
