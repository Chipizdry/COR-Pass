"""
Fuel Domain Routes
Fuel station management
"""
from fastapi import APIRouter

from .fuel_station import router as fuel_station_router

router = APIRouter(tags=["Fuel Domain"])

router.include_router(fuel_station_router)
