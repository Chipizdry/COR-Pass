"""
Health Domain Routes
Blood pressure, ECG measurements, and continuous glucose monitoring (Sibionics)
"""
from fastapi import APIRouter

from .blood_pressures import router as blood_pressures_router
from .ecg_measurements import router as ecg_measurements_router
from .sibionics_routes import router as sibionics_router

router = APIRouter(tags=["Health Domain"])

router.include_router(blood_pressures_router)
router.include_router(ecg_measurements_router)
router.include_router(sibionics_router)
