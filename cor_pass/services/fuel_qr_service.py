"""
Сервис для генерации и верификации QR кодов для системы заправок
"""

import json
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from loguru import logger
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.database.models import User, FuelStationQRSession
from cor_pass.services.totp_service import totp_service
from cor_pass.schemas import (
    FuelQRCodeData,
    FuelQRGenerateResponse,
    FuelQRVerifyRequest,
)


class FuelQRService:
    """Сервис для работы с QR кодами заправки"""
    
    # Настройки
    DEFAULT_QR_VALIDITY_MINUTES = 5
    MAX_QR_VALIDITY_MINUTES = 30
    
    @staticmethod
    async def generate_qr_code(
        user: User,
        db: AsyncSession,
        totp_secret: str,
        validity_minutes: int = DEFAULT_QR_VALIDITY_MINUTES
    ) -> FuelQRGenerateResponse:
        """
        Генерирует QR код для сотрудника
        
        Args:
            user: Объект пользователя
            db: Сессия БД
            totp_secret: TOTP секрет пользователя (из его настроек)
            validity_minutes: Время действия QR кода в минутах
            
        Returns:
            FuelQRGenerateResponse: Данные для QR кода
        """
        try:
            # Валидация времени действия
            if validity_minutes > FuelQRService.MAX_QR_VALIDITY_MINUTES:
                validity_minutes = FuelQRService.MAX_QR_VALIDITY_MINUTES
            
            # Генерируем TOTP код
            totp_code, time_remaining = totp_service.generate_totp_code(totp_secret)
            
            # Генерируем timestamp токен
            timestamp_token = totp_service.generate_timestamp_token()
            
            # Генерируем уникальный токен сессии
            session_token = secrets.token_urlsafe(32)
            
            # Время истечения
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(minutes=validity_minutes)
            
            # Создаём сессию в БД
            qr_session = FuelStationQRSession(
                user_cor_id=user.cor_id,
                session_token=session_token,
                totp_code=totp_code,
                timestamp_token=timestamp_token,
                created_at=now,
                expires_at=expires_at,
                is_used=False
            )
            
            db.add(qr_session)
            await db.commit()
            await db.refresh(qr_session)
            
            logger.info(f"Generated QR code for user {user.cor_id}, session: {session_token}")
            
            # Формируем данные QR кода
            qr_data = FuelQRCodeData(
                cor_id=user.cor_id,
                totp_code=totp_code,
                timestamp_token=timestamp_token,
                session_token=session_token,
                expires_at=expires_at
            )
            
            # Сериализуем в JSON для QR кода
            qr_data_dict = qr_data.model_dump(mode='json')
            qr_data_string = json.dumps(qr_data_dict, ensure_ascii=False)
            
            expires_in_seconds = int((expires_at - now).total_seconds())
            
            return FuelQRGenerateResponse(
                qr_data=qr_data,
                qr_data_string=qr_data_string,
                expires_in_seconds=expires_in_seconds,
                created_at=now
            )
            
        except Exception as e:
            logger.error(f"Failed to generate QR code: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate QR code: {str(e)}"
            )
    
    @staticmethod
    async def verify_qr_code(
        qr_data_string: str,
        db: AsyncSession,
        totp_secret: str
    ) -> Dict[str, Any]:
        """
        Верифицирует отсканированный QR код
        
        Args:
            qr_data_string: JSON строка с данными QR кода
            db: Сессия БД
            totp_secret: TOTP секрет пользователя для проверки
            
        Returns:
            Dict с результатом верификации
        """
        try:
            # Парсим данные QR кода
            try:
                qr_data_dict = json.loads(qr_data_string)
                qr_data = FuelQRCodeData(**qr_data_dict)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid QR code format: {e}")
                return {
                    "is_valid": False,
                    "error_message": "Invalid QR code format"
                }
            except Exception as e:
                logger.warning(f"Failed to parse QR code data: {e}")
                return {
                    "is_valid": False,
                    "error_message": "Failed to parse QR code"
                }
            
            # Проверяем существование сессии в БД
            stmt = select(FuelStationQRSession).where(
                FuelStationQRSession.session_token == qr_data.session_token
            )
            result = await db.execute(stmt)
            qr_session = result.scalar_one_or_none()
            
            if not qr_session:
                logger.warning(f"QR session not found: {qr_data.session_token}")
                return {
                    "is_valid": False,
                    "error_message": "QR code session not found"
                }
            
            # Проверяем, не использован ли уже QR код
            if qr_session.is_used:
                logger.warning(f"QR code already used: {qr_data.session_token}")
                return {
                    "is_valid": False,
                    "error_message": "QR code already used"
                }
            
            # Проверяем срок действия
            now = datetime.now(timezone.utc)
            if now > qr_session.expires_at:
                logger.warning(f"QR code expired: {qr_data.session_token}")
                return {
                    "is_valid": False,
                    "error_message": "QR code expired"
                }
            
            # Проверяем timestamp токен
            if not totp_service.verify_timestamp_token(qr_data.timestamp_token, max_age_seconds=1800):
                logger.warning(f"Invalid timestamp token: {qr_data.session_token}")
                return {
                    "is_valid": False,
                    "error_message": "Invalid or expired timestamp token"
                }
            
            # Проверяем TOTP код (с большим окном, т.к. время могло пройти)
            # window=3 означает ±90 секунд (3 интервала по 30 сек)
            if not totp_service.verify_totp_code(totp_secret, qr_data.totp_code, window=3):
                logger.warning(f"Invalid TOTP code: {qr_data.session_token}")
                return {
                    "is_valid": False,
                    "error_message": "Invalid TOTP code"
                }
            
            # Проверяем COR ID
            if qr_session.user_cor_id != qr_data.cor_id:
                logger.error(f"COR ID mismatch: session={qr_session.user_cor_id}, qr={qr_data.cor_id}")
                return {
                    "is_valid": False,
                    "error_message": "User ID mismatch"
                }
            
            # Получаем информацию о пользователе
            stmt = select(User).where(User.cor_id == qr_data.cor_id)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user or not user.is_active:
                logger.warning(f"User not found or inactive: {qr_data.cor_id}")
                return {
                    "is_valid": False,
                    "error_message": "User not found or inactive"
                }
            
            logger.info(f"QR code verified successfully: {qr_data.session_token} for user {qr_data.cor_id}")
            
            # Всё ОК - возвращаем успешный результат
            return {
                "is_valid": True,
                "user_cor_id": user.cor_id,
                "user_email": user.email,
                "session_token": qr_data.session_token,
                "qr_session_id": qr_session.id,
                "error_message": None
            }
            
        except Exception as e:
            logger.error(f"Failed to verify QR code: {e}")
            return {
                "is_valid": False,
                "error_message": f"Verification error: {str(e)}"
            }
    
    @staticmethod
    async def mark_qr_as_used(
        session_token: str,
        db: AsyncSession
    ) -> bool:
        """
        Помечает QR код как использованный
        
        Args:
            session_token: Токен сессии QR кода
            db: Сессия БД
            
        Returns:
            bool: True если успешно
        """
        try:
            stmt = select(FuelStationQRSession).where(
                FuelStationQRSession.session_token == session_token
            )
            result = await db.execute(stmt)
            qr_session = result.scalar_one_or_none()
            
            if not qr_session:
                return False
            
            qr_session.is_used = True
            qr_session.used_at = datetime.now(timezone.utc)
            
            await db.commit()
            logger.info(f"Marked QR session as used: {session_token}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark QR as used: {e}")
            await db.rollback()
            return False


# Singleton instance
fuel_qr_service = FuelQRService()
