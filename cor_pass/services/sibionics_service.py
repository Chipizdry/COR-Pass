"""
Сервис для работы с SIBIONICS API
Документация: https://cgm-ce-uat.sisensing.com
"""
import httpx
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from loguru import logger

from cor_pass.config.config import settings


class SibionicsAPIClient:
    """Клиент для взаимодействия с SIBIONICS Open Platform API"""

    def __init__(self):
        self.base_url = settings.SIBIONICS_API_URL
        self.app_key = settings.SIBIONICS_APP_KEY
        self.secret = settings.SIBIONICS_SECRET
        self._access_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

    async def _ensure_token(self) -> str:
        """Получает или обновляет токен доступа"""
        if self._access_token and self._token_expires:
            # Проверяем, не истек ли токен (с запасом 5 минут)
            now = datetime.now(timezone.utc)
            if now < (self._token_expires - 5 * 60):  # 5 минут запаса
                return self._access_token

        # Получаем новый токен
        await self._refresh_token()
        return self._access_token

    async def _refresh_token(self):
        """Получает новый токен доступа от SIBIONICS"""
        url = f"{self.base_url}/open/merchant/token"
        payload = {
            "appKey": self.app_key,
            "secret": self.secret
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("code") != 200:
                    raise Exception(f"SIBIONICS API Error: {data.get('msg')}")
                
                token_data = data.get("data", {})
                self._access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in")  # milliseconds timestamp
                
                # Конвертируем timestamp в datetime
                self._token_expires = datetime.fromtimestamp(expires_in / 1000, tz=timezone.utc)
                
                logger.info(f"✅ SIBIONICS token obtained, expires at {self._token_expires}")
                
        except httpx.HTTPError as e:
            logger.error(f"❌ Failed to get SIBIONICS token: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error getting SIBIONICS token: {e}")
            raise

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Базовый метод для выполнения запросов к SIBIONICS API"""
        token = await self._ensure_token()
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            "Authorization": token,
            "Version": "1.0",
            "Timestamp": str(int(datetime.now(timezone.utc).timestamp() * 1000))
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, params=params)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=json_data)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=headers, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                data = response.json()

                if data.get("code") != 200:
                    error_msg = data.get("msg", "Unknown error")
                    error_data = data.get("errorData")
                    logger.error(f"SIBIONICS API Error: {error_msg}, data: {error_data}")
                    raise Exception(f"SIBIONICS API Error [{data.get('code')}]: {error_msg}")

                return data.get("data", {})

        except httpx.HTTPError as e:
            logger.error(f"HTTP Error calling SIBIONICS API: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling SIBIONICS API: {e}")
            raise

    async def get_device_list(
        self,
        biz_id: str,
        page_num: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """
        Получает список устройств CGM пользователя
        
        Args:
            biz_id: SIBIONICS Authorization resource ID
            page_num: Номер страницы
            page_size: Размер страницы (макс 1000)
        
        Returns:
            Dict с ключами: records, currentPage, pageSize, totalPage, total
        """
        params = {
            "bizId": biz_id,
            "pageNum": page_num,
            "pageSize": min(page_size, 1000)
        }
        
        logger.info(f"📋 Fetching device list for bizId: {biz_id}")
        return await self._make_request("GET", "/open/device/list", params=params)

    async def get_device_glucose_data(
        self,
        biz_id: str,
        device_id: str,
        index: int = 60,
        page_num: int = 1,
        page_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Получает данные глюкозы с устройства
        
        Args:
            biz_id: SIBIONICS Authorization resource ID
            device_id: ID устройства
            index: Стартовый индекс (60-20160)
            page_num: Номер страницы
            page_size: Размер страницы (макс 1000)
        
        Returns:
            Dict с ключами: records, currentPage, pageSize, totalPage, total
        """
        params = {
            "bizId": biz_id,
            "deviceId": device_id,
            "index": max(60, min(index, 20160)),
            "pageNum": page_num,
            "pageSize": min(page_size, 1000)
        }
        
        logger.info(f"📊 Fetching glucose data for device: {device_id}, index: {index}")
        return await self._make_request("GET", "/open/device/glucose", params=params)

    async def revoke_authorization(self, biz_id: str) -> str:
        """
        Отзывает авторизацию пользователя
        
        Args:
            biz_id: SIBIONICS Authorization resource ID
        
        Returns:
            Status message
        """
        params = {"bizId": biz_id}
        
        logger.info(f"🔒 Revoking authorization for bizId: {biz_id}")
        result = await self._make_request("DELETE", "/open/grant", params=params)
        return result


# Singleton instance
sibionics_client = SibionicsAPIClient()
