"""
Roles Domain Routes
Lab assistants and financier management
"""
from fastapi import APIRouter

from .lab_assistants import router as lab_assistants_router
from .financier import router as financier_router

router = APIRouter(tags=["Roles Domain"])

router.include_router(lab_assistants_router)
router.include_router(financier_router)
