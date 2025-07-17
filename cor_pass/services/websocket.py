import asyncio
from fastapi import WebSocket
from sqlalchemy import delete, select
from cor_pass.database.models import CorIdAuthSession, AuthSessionStatus
from datetime import datetime, timedelta

from cor_pass.database.db import async_session_maker
from loguru import logger

active_connections: dict[str, WebSocket] = {}


async def send_websocket_message(session_token: str, message: dict):
    """Отправляет сообщение через WebSocket конкретному клиенту."""
    if session_token in active_connections:
        await active_connections[session_token].send_json(message)


async def close_websocket_connection(session_token: str):
    """Закрывает WebSocket-соединение и удаляет его из активных."""
    if session_token in active_connections:
        await active_connections[session_token].close()
        del active_connections[session_token]
        logger.debug(
            f"WebSocket соединение для {session_token} закрыто из-за таймаута."
        )


async def check_session_timeouts():
    """Асинхронная фоновая задача для проверки и обработки таймаутов сессий."""
    while True:
        async with async_session_maker() as db:
            try:
                now = datetime.utcnow()
                stmt = select(CorIdAuthSession).where(
                    CorIdAuthSession.status == AuthSessionStatus.PENDING,
                    CorIdAuthSession.expires_at < now,
                )
                result = await db.execute(stmt)
                expired_sessions = result.scalars().all()

                for session in expired_sessions:
                    session.status = AuthSessionStatus.TIMEOUT
                    await db.commit()

                    await send_websocket_message(
                        session.session_token, {"status": "timeout"}
                    )
                    await close_websocket_connection(session.session_token)
            except Exception as e:
                logger.error(
                    f"Ошибка в асинхронной фоновой задаче проверки таймаутов: {e}"
                )
                await db.rollback()
            finally:
                await asyncio.sleep(60)


async def cleanup_auth_sessions():
    """Асинхронная фоновая задача для удаления старых сессий авторизации."""
    while True:
        async with async_session_maker() as db:
            try:
                now = datetime.utcnow()

                expired_stmt = delete(CorIdAuthSession).where(
                    CorIdAuthSession.expires_at < now
                )
                expired_result = await db.execute(expired_stmt)
                expired_count = expired_result.rowcount

                cutoff_time = now - timedelta(minutes=30)  # Завершенные 30 минут назад
                completed_stmt = delete(CorIdAuthSession).where(
                    CorIdAuthSession.status.in_(
                        [
                            AuthSessionStatus.APPROVED,
                            AuthSessionStatus.REJECTED,
                            AuthSessionStatus.TIMEOUT,
                        ]
                    ),
                    CorIdAuthSession.created_at < cutoff_time,
                )
                completed_result = await db.execute(completed_stmt)
                completed_count = completed_result.rowcount

                await db.commit()
            except Exception as e:
                logger.error(f"Ошибка при асинхронной очистке сессий авторизации: {e}")
                await db.rollback()
            finally:
                await asyncio.sleep(900)  # запуск каждые 15 минут
