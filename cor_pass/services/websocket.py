import asyncio
from typing import Optional
from fastapi import WebSocket
import sqlalchemy as sa
from sqlalchemy import delete, select
from cor_pass.database.models import CorIdAuthSession, AuthSessionStatus, DoctorSignatureSession
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import sessionmaker
from cor_pass.database.db import async_session_maker
from loguru import logger

from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.services.websocket_events_manager import websocket_events_manager

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
                
async def expire_sessions_task(db_factory):
    while True:
        async with db_factory() as db:
            now = datetime.now(timezone.utc)
            q = await db.execute(
                sa.select(DoctorSignatureSession).where(
                    DoctorSignatureSession.status == "pending",
                    DoctorSignatureSession.expires_at < now
                )
            )
            expired = q.scalars().all()
            for sess in expired:
                sess.status = "expired"
                await websocket_events_manager.broadcast_event({
                    "event_type": "signature_status",
                    "session_token": sess.session_token,
                    "status": "expired"
                })
            await db.commit()
        await asyncio.sleep(60)


# Доп функции для сессий подписания 
DEEP_LINK_SCHEME = "coreid://sign" 
SESSION_TTL_MINUTES = 15


async def _load_session(db: AsyncSession, session_token: str) -> Optional[DoctorSignatureSession]:
    q = sa.select(DoctorSignatureSession).where(DoctorSignatureSession.session_token == session_token)
    res = await db.execute(q)
    return res.scalar_one_or_none()


def _is_expired(sess: DoctorSignatureSession) -> bool:
    now = datetime.now(timezone.utc)
    # если expires_at без таймзоны, считаем как UTC
    exp = sess.expires_at.replace(tzinfo=timezone.utc) if sess.expires_at.tzinfo is None else sess.expires_at
    return exp < now


async def _broadcast_status(session_token: str, status: str) -> None:
    await websocket_events_manager.broadcast_event(
        {
            "event_type": "signature_status",
            "session_token": session_token,
            "status": status,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    )


def register_signature_expirer(app, db_sessionmaker):
    """
    Запускает фоновую задачу, которая проверяет и удаляет истекшие подписи.
    db_sessionmaker — это sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    """
    @app.on_event("startup")
    async def _start_expirer():
        # Запускаем задачу, передавая sessionmaker напрямую
        app.state._signature_expirer_task = asyncio.create_task(
            _expire_pending_sessions_forever(db_sessionmaker)
        )

    @app.on_event("shutdown")
    async def _stop_expirer():
        task: asyncio.Task = getattr(app.state, "_signature_expirer_task", None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


async def _expire_pending_sessions_forever(db_sessionmaker: sessionmaker):
    """
    Пример фоновой задачи, которая бесконечно проверяет и удаляет истекшие подписи.
    """
    while True:
        try:
            async with db_sessionmaker() as db: 
                await _expire_pending_sessions(db)
        except Exception as e:
            print("Ошибка в expirer:", e)
        await asyncio.sleep(60)  # проверяем каждые 60 секунд

async def _expire_pending_sessions(db: AsyncSession):
    """
    Удаление истекших подписей
    """
    # Пример:
    # await db.execute(delete(Signatures).where(Signatures.expires_at < datetime.utcnow()))
    # await db.commit()
    pass

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
