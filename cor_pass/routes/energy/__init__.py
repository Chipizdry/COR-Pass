"""
Energy Domain Routes
Cerbo GX devices and energy manager profiles + Modbus TCP management + Device Polling Tasks
"""
from fastapi import APIRouter

from .cerbo_routes import router as cerbo_router
from .energy_managers import router as energy_managers_router
from .modbus_tcp import router as modbus_tcp_router
from .polling_tasks import router as polling_tasks_router

router = APIRouter(tags=["Energy Domain"])

router.include_router(cerbo_router)
router.include_router(energy_managers_router)
router.include_router(modbus_tcp_router)
router.include_router(polling_tasks_router)
