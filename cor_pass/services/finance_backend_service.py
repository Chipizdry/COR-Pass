"""
Сервис для интеграции с бэкендом финансов
Использует TOTP для server-to-server аутентификации
"""

import time
import httpx
from typing import Optional, Dict, Any
from loguru import logger
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.database.models import FinanceBackendAuth
from cor_pass.services.totp_service import totp_service
from cor_pass.services.cipher import encrypt_data, decrypt_data
from cor_pass.config.config import settings


def _normalize_aes_key(key: bytes) -> bytes:
    """
    Нормализует AES ключ до корректной длины (16, 24 или 32 байта)
    
    Args:
        key: Исходный ключ
        
    Returns:
        Нормализованный ключ
    """
    if len(key) < 16:
        return key.ljust(16, b'\0')
    elif len(key) > 32:
        return key[:32]
    elif 16 < len(key) < 24:
        return key.ljust(24, b'\0')
    elif 24 < len(key) < 32:
        return key.ljust(32, b'\0')
    return key


class FinanceBackendService:
    """
    Сервис для взаимодействия с бэкендом финансов
    """
    
    def __init__(self):
        self.service_name = "finance_backend"
        self.timeout = 30.0  # Таймаут запросов в секундах
    
    async def _get_auth_config(self, db: AsyncSession) -> Optional[FinanceBackendAuth]:
        """
        Получает конфигурацию авторизации для бэкенда финансов
        
        Args:
            db: Сессия БД
            
        Returns:
            FinanceBackendAuth или None
        """
        try:
            stmt = select(FinanceBackendAuth).where(
                FinanceBackendAuth.service_name == self.service_name,
                FinanceBackendAuth.is_active == True
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get finance backend auth config: {e}")
            return None
    
    async def _generate_auth_totp(self, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """
        Генерирует TOTP код для авторизации на бэкенде финансов
        
        Args:
            db: Сессия БД
            
        Returns:
            Dict с TOTP кодом и timestamp или None
        """
        try:
            auth_config = await self._get_auth_config(db)
            
            if not auth_config:
                logger.error("Finance backend auth configuration not found")
                return None
            
            # Расшифровываем TOTP секрет используя системный AES ключ
            try:
                if isinstance(auth_config.totp_secret, bytes):
                    # Секрет зашифрован - расшифровываем
                    aes_key = _normalize_aes_key(settings.aes_key.encode())
                    totp_secret = await decrypt_data(auth_config.totp_secret, aes_key)
                else:
                    totp_secret = auth_config.totp_secret
            except Exception as e:
                logger.error(f"Failed to decrypt TOTP secret: {e}")
                return None
            
            # Генерируем TOTP код
            totp_code, _ = totp_service.generate_totp_code(totp_secret)
            
            # Обновляем время последней успешной авторизации
            auth_config.last_successful_auth = None  # Обновим после успешного запроса
            
            return {
                "totp_code": totp_code,
                "timestamp": int(time.time()),
                "api_endpoint": auth_config.api_endpoint
            }
        except Exception as e:
            logger.error(f"Failed to generate auth TOTP: {e}")
            return None
    
    async def check_user_limit(
        self,
        cor_id: str,
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """
        Проверяет лимиты пользователя на бэкенде финансов
        
        Args:
            cor_id: COR ID сотрудника
            db: Сессия БД
            
        Returns:
            Dict с информацией о лимитах или None
        """
        try:
            # Получаем TOTP для авторизации
            auth_data = await self._generate_auth_totp(db)
            
            if not auth_data:
                logger.error("Failed to generate auth data for finance backend")
                return None
            
            api_endpoint = auth_data["api_endpoint"]
            
            # Формируем запрос
            request_data = {
                "cor_id": cor_id,
                "auth": {
                    "totp_code": auth_data["totp_code"],
                    "timestamp": auth_data["timestamp"]
                }
            }
            
            # Отправляем запрос на бэкенд финансов
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{api_endpoint}/api/fuel/check-limit",
                    json=request_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Successfully checked limit for user {cor_id}")
                    
                    # Обновляем статус успешной авторизации
                    await self._update_auth_status(db, success=True)
                    
                    return data
                elif response.status_code == 401:
                    logger.error(f"Finance backend auth failed: {response.text}")
                    await self._update_auth_status(db, success=False)
                    return None
                elif response.status_code == 404:
                    logger.warning(f"User not found in finance backend: {cor_id}")
                    return None
                else:
                    logger.error(f"Finance backend error: {response.status_code} - {response.text}")
                    return None
                    
        except httpx.TimeoutException:
            logger.error("Finance backend request timeout")
            return None
        except httpx.RequestError as e:
            logger.error(f"Finance backend request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to check user limit: {e}")
            return None
    
    async def update_user_limit(
        self,
        cor_id: str,
        amount: float,
        transaction_id: str,
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """
        Обновляет лимиты пользователя на бэкенде финансов (списывает средства)
        
        Args:
            cor_id: COR ID сотрудника
            amount: Сумма для списания
            transaction_id: ID транзакции в нашей системе
            db: Сессия БД
            
        Returns:
            Dict с обновлёнными лимитами или None
        """
        try:
            # Получаем TOTP для авторизации
            auth_data = await self._generate_auth_totp(db)
            
            if not auth_data:
                logger.error("Failed to generate auth data for finance backend")
                return None
            
            api_endpoint = auth_data["api_endpoint"]
            
            # Формируем запрос
            request_data = {
                "cor_id": cor_id,
                "amount": amount,
                "transaction_id": transaction_id,
                "auth": {
                    "totp_code": auth_data["totp_code"],
                    "timestamp": auth_data["timestamp"]
                }
            }
            
            # Отправляем запрос на бэкенд финансов
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{api_endpoint}/api/fuel/update-limit",
                    json=request_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Successfully updated limit for user {cor_id}, amount: {amount}")
                    
                    # Обновляем статус успешной авторизации
                    await self._update_auth_status(db, success=True)
                    
                    return data
                elif response.status_code == 401:
                    logger.error(f"Finance backend auth failed: {response.text}")
                    await self._update_auth_status(db, success=False)
                    return None
                elif response.status_code == 400:
                    logger.warning(f"Finance backend validation error: {response.text}")
                    return {"error": response.json().get("detail", "Validation error")}
                elif response.status_code == 402:
                    logger.warning(f"Insufficient funds for user {cor_id}")
                    return {"error": "Insufficient funds"}
                else:
                    logger.error(f"Finance backend error: {response.status_code} - {response.text}")
                    return None
                    
        except httpx.TimeoutException:
            logger.error("Finance backend request timeout")
            return None
        except httpx.RequestError as e:
            logger.error(f"Finance backend request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to update user limit: {e}")
            return None
    
    async def _update_auth_status(self, db: AsyncSession, success: bool):
        """
        Обновляет статус авторизации
        
        Args:
            db: Сессия БД
            success: Успешна ли была авторизация
        """
        try:
            auth_config = await self._get_auth_config(db)
            
            if not auth_config:
                return
            
            from datetime import datetime, timezone
            
            if success:
                auth_config.last_successful_auth = datetime.now(timezone.utc)
                auth_config.failed_attempts = 0
            else:
                auth_config.last_failed_auth = datetime.now(timezone.utc)
                auth_config.failed_attempts += 1
            
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to update auth status: {e}")
            await db.rollback()


# Singleton instance
finance_backend_service = FinanceBackendService()
