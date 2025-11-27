"""
Energy Domain Routes
Cerbo GX devices and energy manager profiles
"""
from fastapi import APIRouter

from .cerbo_routes import router as cerbo_router
from .energy_managers import router as energy_managers_router

router = APIRouter(tags=["Energy Domain"])

router.include_router(cerbo_router)
router.include_router(energy_managers_router)
