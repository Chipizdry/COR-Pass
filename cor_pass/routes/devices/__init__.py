"""
Devices Domain Routes
Device proxy, WebSocket, printing devices
"""
from fastapi import APIRouter

from .device_proxy import router as device_proxy_router
from .device_ws import router as device_ws_router
from .printing_device import router as printing_device_router
from .printer import router as printer_router

router = APIRouter(tags=["Devices Domain"])

router.include_router(device_proxy_router)
router.include_router(device_ws_router)
router.include_router(printing_device_router)
router.include_router(printer_router)
