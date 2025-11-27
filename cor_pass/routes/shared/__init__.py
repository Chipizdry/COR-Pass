"""
Shared/Common Domain Routes
Admin, password generator, WebSocket, support
"""
from fastapi import APIRouter

from .admin import router as admin_router
from .password_generator import router as password_generator_router
from .websocket import router as websocket_router
from .websocket_events import router as websocket_events_router
from .support import router as support_router

router = APIRouter(tags=["Shared Domain"])

router.include_router(admin_router)
router.include_router(password_generator_router)
router.include_router(websocket_router)
router.include_router(websocket_events_router)
router.include_router(support_router)
