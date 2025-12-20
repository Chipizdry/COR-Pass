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
from cor_pass.services.shared.totp_service import totp_service
from cor_pass.services.user.cipher import encrypt_data, decrypt_data
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
    
    async def create_partner_company_owner(
        self,
        owner_cor_id: str,
        first_name: str,
        last_name: str,
        email: str,
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """
        Создаёт владельца компании в финансовом бэкенде
        POST /v1/partner_companies/owner/
        
        Args:
            owner_cor_id: COR ID владельца
            first_name: Имя
            last_name: Фамилия
            email: Email
            db: Сессия БД
            
        Returns:
            Dict с данными созданного пользователя или None
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
                "owner_cor_id": owner_cor_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email
            }
            
            # Отправляем запрос на бэкенд финансов
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{api_endpoint}/v1/partner_companies/owner/",
                    json=request_data,
                    headers={
                        "Content-Type": "application/json",
                        # "token": auth_data["totp_code"]  # TOTP в header
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Successfully created partner company owner {owner_cor_id}")
                    
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
            logger.error(f"Failed to create partner company owner: {e}")
            return None
    
    async def create_partner_company(
        self,
        name: str,
        company_format: str,
        phone_number: str,
        tax_id: str,
        address: str,
        owner_id_or_cor_id: str,
        email: Optional[str] = None,
        start_balance: float = 0.0,
        db: AsyncSession = None
    ) -> Optional[Dict[str, Any]]:
        """
        Создаёт компанию в финансовом бэкенде
        POST /v1/partner_companies/
        
        Args:
            name: Название компании
            company_format: Форма підприємства (ТОВ, ФОП, ПП и т.д.)
            phone_number: Контактный телефон
            tax_id: ЄДРПОУ/ИНН
            address: Юридический адрес
            owner_id_or_cor_id: ID или COR ID владельца
            email: Email компании (опционально)
            start_balance: Начальный баланс (по умолчанию 0)
            db: Сессия БД
            
        Returns:
            Dict с данными созданной компании или None
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
                "name": name,
                "company_format": company_format,
                "phone_number": phone_number,
                "tax_id": tax_id,
                "address": address,
                "owner_id_or_cor_id": owner_id_or_cor_id,
                "start_balance": start_balance
            }
            
            if email:
                request_data["email"] = email
            
            # Отправляем запрос на бэкенд финансов
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{api_endpoint}/v1/partner_companies/",
                    json=request_data,
                    headers={
                        "Content-Type": "application/json",
                        # "token": auth_data["totp_code"]  # TOTP в header
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Successfully created partner company {tax_id}")
                    
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
            logger.error(f"Failed to create partner company: {e}")
            return None
    
    async def partner_login(
        self,
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """
        Логин партнёра в финансовый бэкенд с использованием TOTP.
        Возвращает токены доступа от финансового бэкенда.
        
        Args:
            db: Сессия БД
            
        Returns:
            Dict с access_token, refresh_token и token_type или None
        """
        try:
            # Получаем TOTP для авторизации
            auth_data = await self._generate_auth_totp(db)
            
            if not auth_data:
                logger.error("Failed to generate auth data for partner login")
                return None
            
            api_endpoint = auth_data["api_endpoint"]
            totp_code = auth_data["totp_code"]
            
            # Отправляем запрос на логин партнёра
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{api_endpoint}/v1/partner_auth/login",
                    headers={
                        "token": totp_code,
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info("Partner login successful")
                    
                    # Обновляем статус успешной авторизации
                    await self._update_auth_status(db, success=True)
                    
                    return {
                        "access_token": data.get("access_token"),
                        "refresh_token": data.get("refresh_token"),
                        "token_type": data.get("token_type", "bearer")
                    }
                elif response.status_code == 401:
                    logger.error(f"Partner login auth failed: {response.text}")
                    await self._update_auth_status(db, success=False)
                    return {"error": "Authentication failed"}
                elif response.status_code == 422:
                    logger.error(f"Partner login validation error: {response.text}")
                    return {"error": "Validation error"}
                else:
                    logger.error(f"Partner login error: {response.status_code} - {response.text}")
                    return {"error": f"Finance backend error: {response.status_code}"}
                    
        except httpx.TimeoutException:
            logger.error("Partner login request timeout")
            return {"error": "Request timeout"}
        except httpx.RequestError as e:
            logger.error(f"Partner login request error: {e}")
            return {"error": f"Request error: {str(e)}"}
        except Exception as e:
            logger.error(f"Failed to login partner: {e}")
            return {"error": f"Internal error: {str(e)}"}
    
    async def create_account_member(
        self,
        db: AsyncSession,
        first_name: str,
        last_name: str,
        cor_id: str,
        account_id: Optional[int],
        company_id: int,
        limit_amount: Optional[float],
        limit_period: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Создаёт участника компании в финансовом бэкенде.
        
        Args:
            db: Сессия БД
            first_name: Имя пользователя
            last_name: Фамилия пользователя
            cor_id: COR-ID пользователя
            account_id: ID аккаунта в finance backend
            company_id: ID компании в finance backend
            limit_amount: Лимит пользователя
            limit_period: Период лимита (day, week, month)
            
        Returns:
            Dict с данными созданного участника или None
        """
        try:
            # Получаем настройки финансового бэкенда
            auth_config = await self._get_auth_config(db)
            
            if not auth_config:
                logger.error("Finance backend settings not found")
                return None
            
            api_endpoint = auth_config.api_endpoint
            

            # # Получаем TOTP для авторизации
            # auth_data = await self._generate_auth_totp(db)
            # if not auth_data:
            #     logger.error("Failed to generate auth data for account member creation")
            #     return None
            # totp_code = auth_data["totp_code"]
            
            # Формируем payload (с дефолтными значениями для limit_amount и limit_period)
            payload = {
                "first_name": first_name,
                "last_name": last_name,
                "cor_id": cor_id,
                "company_id": company_id,
                "limit_amount": limit_amount if limit_amount is not None else 0,
                "limit_period": limit_period if limit_period is not None else "day",
            }
            
            # Добавляем account_id только если он не None
            if account_id is not None:
                payload["account_id"] = account_id
            
            # Отправляем запрос
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                #Раскомментировать header когда на финансах будет готово
                headers = {
                    "Content-Type": "application/json"
                    # "token": totp_code,
                }
                
                response = await client.post(
                    f"{api_endpoint}/v1/account_members/",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Account member created successfully: {cor_id}")
                    return data
                elif response.status_code == 401:
                    logger.error(f"Account member creation auth failed: {response.text}")
                    return {"error": "Authentication failed"}
                elif response.status_code == 422:
                    logger.error(f"Account member creation validation error: {response.text}")
                    return {"error": "Validation error", "details": response.text}
                else:
                    logger.error(f"Account member creation error: {response.status_code} - {response.text}")
                    return {"error": f"Finance backend error: {response.status_code}"}
                    
        except httpx.TimeoutException:
            logger.error("Account member creation request timeout")
            return {"error": "Request timeout"}
        except httpx.RequestError as e:
            logger.error(f"Account member creation request error: {e}")
            return {"error": f"Request error: {str(e)}"}
        except Exception as e:
            logger.error(f"Failed to create account member: {e}")
            return {"error": f"Internal error: {str(e)}"}
    
    async def get_company_summary_by_cor_id(
        self, 
        db: AsyncSession,
        cor_id: str
    ) -> Optional[Any]:
        """
        Получает сводку по компании или информацию о сотруднике по COR-ID.
        
        Endpoint: GET /v1/partner_companies/{cor_id}/summary
        
        Возвращает:
        - List[PartnerCompanySummary] если пользователь - владелец компаний
        - AccountMemberWithDetails если пользователь - сотрудник  
        - None если пользователь не найден
        
        Args:
            db: Database session
            cor_id: COR-ID пользователя
            
        Returns:
            Данные от finance backend или None
        """
        try:
            # Получаем конфигурацию из БД
            auth_config = await self._get_auth_config(db)
            if not auth_config:
                logger.error("Finance backend auth config not found in database")
                return None
            
            # Формируем URL из конфига БД
            url = f"{auth_config.api_endpoint}/v1/partner_companies/{cor_id}/summary"
            
            # Получаем TOTP токен для авторизации (временно не используем header)
            headers = {}
            # try:
            #     auth_data = await self._generate_auth_totp(db)
            #     if auth_data:
            #         headers["token"] = auth_data["totp_code"]
            # except Exception as totp_error:
            #     logger.warning(f"Failed to generate TOTP token: {totp_error}")
            #     # Продолжаем без токена, если API не требует авторизации
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers)
                
                # Если 404 - пользователь не найден, это нормально
                if response.status_code == 404:
                    logger.info(f"User {cor_id} not found in finance backend")
                    return None
                
                # Проверяем успешность
                response.raise_for_status()
                
                # Возвращаем данные
                data = response.json()
                logger.info(f"Finance backend returned data for {cor_id}: type={type(data)}")
                return data
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Finance backend HTTP error for {cor_id}: {e.response.status_code}")
            return None
        except httpx.TimeoutException:
            logger.error(f"Finance backend timeout for {cor_id}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Finance backend connection error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling finance backend: {e}", exc_info=True)
            return None

    async def update_partner_company_limits(
        self,
        company_id: int,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> Optional[Dict[str, Any]]:
        """
        Обновляет лимиты компании в финансовом бэкенде (PUT запрос).
        
        Обновляет:
        - credit_limit - кредитный лимит (на сколько можно лазить в минус)
        - balance_level_alert_limit - уровень баланса, при котором послать вебхук
        - balance_level_hook_url - URL вебхука для уведомления о превышении лимита
        
        Args:
            company_id: ID компании в финбэке
            payload: Dict с полями для обновления
            db: Сессия БД
            
        Returns:
            Данные от finance backend с обновленной компанией или None
        """
        try:
            # Получаем конфигурацию из БД
            auth_config = await self._get_auth_config(db)
            if not auth_config:
                logger.error("Finance backend auth config not found in database")
                return None
            
            # Формируем URL для PUT запроса
            url = f"{auth_config.api_endpoint}/v1/partner_companies/{company_id}"
            
            # Генерируем TOTP токен для авторизации
            headers = {}
            # try:
            #     auth_data = await self._generate_auth_totp(db)
            #     if auth_data:
            #         headers["token"] = auth_data["totp_code"]
            # except Exception as totp_error:
            #     logger.warning(f"Failed to generate TOTP token: {totp_error}")
            
            logger.info(f"Updating company limits in finance backend: company_id={company_id}, payload={payload}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.put(url, json=payload, headers=headers)
                
                # Проверяем успешность
                if response.status_code >= 400:
                    error_text = response.text
                    logger.error(f"Failed to update company limits: {response.status_code} - {error_text}")
                    return {"error": f"Status {response.status_code}: {error_text}"}
                
                # Возвращаем данные
                data = response.json()
                logger.info(f"Company limits updated successfully in finance backend: {company_id}")
                return data
            
        except httpx.TimeoutException:
            logger.error(f"Finance backend timeout when updating company {company_id}")
            return {"error": "Timeout connecting to finance backend"}
        except httpx.RequestError as e:
            logger.error(f"Finance backend connection error: {e}")
            return {"error": f"Connection error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error updating company limits: {e}", exc_info=True)
            return {"error": f"Error: {str(e)}"}
    
    async def delete_partner_company(
        self,
        company_id: int,
        db: AsyncSession,
    ) -> Optional[Dict[str, Any]]:
        """
        Удаляет партнёрскую компанию в финансовом бэкенде (soft delete).
        
        Args:
            company_id: ID компании в финбэке
            db: Сессия БД
            
        Returns:
            Dict с результатом или None в случае ошибки
        """
        try:
            # Получаем конфигурацию из БД
            auth_config = await self._get_auth_config(db)
            if not auth_config:
                logger.error("Finance backend auth config not found in database")
                return None
            
            # Формируем URL для DELETE запроса
            url = f"{auth_config.api_endpoint}/v1/partner_companies/{company_id}"
            
            # Генерируем TOTP токен для авторизации
            headers = {}
            # try:
            #     auth_data = await self._generate_auth_totp(db)
            #     if auth_data:
            #         headers["token"] = auth_data["totp_code"]
            # except Exception as totp_error:
            #     logger.warning(f"Failed to generate TOTP token: {totp_error}")
            
            logger.info(f"Deleting partner company in finance backend: company_id={company_id}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(url, headers=headers)
                
                # Проверяем успешность
                if response.status_code >= 400:
                    error_text = response.text
                    logger.error(f"Failed to delete partner company: {response.status_code} - {error_text}")
                    return {"error": f"Status {response.status_code}: {error_text}"}
                
                # Возвращаем результат
                if response.status_code == 204:
                    # No Content - успешное удаление
                    logger.info(f"Partner company deleted successfully in finance backend: {company_id}")
                    return {"status": "success", "message": "Partner company deleted"}
                
                data = response.json()
                logger.info(f"Partner company deleted successfully in finance backend: {company_id}")
                return data
                
        except httpx.TimeoutException:
            logger.error(f"Delete partner company request timeout: company_id={company_id}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Delete partner company request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to delete partner company: {e}")
            return None

    async def disable_partner_company(
        self,
        company_id: int,
        db: AsyncSession,
    ) -> Optional[Dict[str, Any]]:
        """
        Блокирует партнёрскую компанию в финансовом бэкенде (sets disabled_at).
        
        Args:
            company_id: ID компании в финбэке
            db: Сессия БД
            
        Returns:
            Dict с результатом или None в случае ошибки
        """
        try:
            # Получаем конфигурацию из БД
            auth_config = await self._get_auth_config(db)
            if not auth_config:
                logger.error("Finance backend auth config not found in database")
                return None
            
            # Формируем URL для PUT запроса
            url = f"{auth_config.api_endpoint}/v1/partner_companies/{company_id}/disable"
            
            # Генерируем TOTP токен для авторизации
            headers = {}
            # try:
            #     auth_data = await self._generate_auth_totp(db)
            #     if auth_data:
            #         headers["token"] = auth_data["totp_code"]
            # except Exception as totp_error:
            #     logger.warning(f"Failed to generate TOTP token: {totp_error}")
            
            logger.info(f"Disabling partner company in finance backend: company_id={company_id}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.put(url, headers=headers)
                
                # Проверяем успешность
                if response.status_code >= 400:
                    error_text = response.text
                    logger.error(f"Failed to disable partner company: {response.status_code} - {error_text}")
                    return {"error": f"Status {response.status_code}: {error_text}"}
                
                # Возвращаем результат
                data = response.json()
                logger.info(f"Partner company disabled successfully in finance backend: {company_id}")
                return data
                
        except httpx.TimeoutException:
            logger.error(f"Disable partner company request timeout: company_id={company_id}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Disable partner company request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to disable partner company: {e}")
            return None

    async def enable_partner_company(
        self,
        company_id: int,
        db: AsyncSession,
    ) -> Optional[Dict[str, Any]]:
        """
        Разблокирует партнёрскую компанию в финансовом бэкенде (sets disabled_at to NULL).
        
        Args:
            company_id: ID компании в финбэке
            db: Сессия БД
            
        Returns:
            Dict с результатом или None в случае ошибки
        """
        try:
            # Получаем конфигурацию из БД
            auth_config = await self._get_auth_config(db)
            if not auth_config:
                logger.error("Finance backend auth config not found in database")
                return None
            
            # Формируем URL для PUT запроса
            url = f"{auth_config.api_endpoint}/v1/partner_companies/{company_id}/enable"
            
            # Генерируем TOTP токен для авторизации
            headers = {}
            # try:
            #     auth_data = await self._generate_auth_totp(db)
            #     if auth_data:
            #         headers["token"] = auth_data["totp_code"]
            # except Exception as totp_error:
            #     logger.warning(f"Failed to generate TOTP token: {totp_error}")
            
            logger.info(f"Enabling partner company in finance backend: company_id={company_id}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.put(url, headers=headers)
                
                # Проверяем успешность
                if response.status_code >= 400:
                    error_text = response.text
                    logger.error(f"Failed to enable partner company: {response.status_code} - {error_text}")
                    return {"error": f"Status {response.status_code}: {error_text}"}
                
                # Возвращаем результат
                data = response.json()
                logger.info(f"Partner company enabled successfully in finance backend: {company_id}")
                return data
                
        except httpx.TimeoutException:
            logger.error(f"Enable partner company request timeout: company_id={company_id}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Enable partner company request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to enable partner company: {e}")
            return None

    async def get_partner_company_summary(
        self,
        company_id: int,
        db: AsyncSession,
    ) -> Optional[Dict[str, Any]]:
        """
        Получает сводку по партнёрской компании из финансового бэкенда.
        
        Возвращает информацию о компании, балансе и последних транзакциях.
        
        Args:
            company_id: ID компании в финбэке
            db: Сессия БД
            
        Returns:
            Dict с данными компании (company_type, company_name, balance, transactions) или None
        """
        try:
            # Получаем конфигурацию из БД
            auth_config = await self._get_auth_config(db)
            if not auth_config:
                logger.error("Finance backend auth config not found in database")
                return None
            
            # Формируем URL для GET запроса
            url = f"{auth_config.api_endpoint}/v1/partner_companies/{company_id}/summary"
            
            # Генерируем TOTP токен для авторизации
            headers = {}
            # try:
            #     auth_data = await self._generate_auth_totp(db)
            #     if auth_data:
            #         headers["token"] = auth_data["totp_code"]
            # except Exception as totp_error:
            #     logger.warning(f"Failed to generate TOTP token: {totp_error}")
            
            logger.info(f"Getting partner company summary from finance backend: company_id={company_id}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers)
                
                # Проверяем успешность
                if response.status_code >= 400:
                    error_text = response.text
                    logger.error(f"Failed to get partner company summary: {response.status_code} - {error_text}")
                    return {"error": f"Status {response.status_code}: {error_text}"}
                
                # Возвращаем результат
                data = response.json()
                logger.info(f"Partner company summary retrieved successfully from finance backend: {company_id}")
                return data
                
        except httpx.TimeoutException:
            logger.error(f"Get partner company summary request timeout: company_id={company_id}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Get partner company summary request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get partner company summary: {e}")
            return None
                




# Singleton instance
finance_backend_service = FinanceBackendService()
