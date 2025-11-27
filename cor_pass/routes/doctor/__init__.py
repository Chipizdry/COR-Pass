"""
Doctor Domain Routes
Doctor profiles and lawyer management
"""
from fastapi import APIRouter

from .doctor import router as doctor_router
from .lawyer import router as lawyer_router

router = APIRouter(tags=["Doctor Domain"])

router.include_router(doctor_router)
router.include_router(lawyer_router)
