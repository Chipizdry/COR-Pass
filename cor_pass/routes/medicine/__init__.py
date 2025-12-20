"""
Medicine Domain Routes
Medicines, first aid kits, intakes, prescriptions
"""
from fastapi import APIRouter

from .medicines import router as medicines_router
from .first_aid_kits import router as first_aid_kits_router
from .medicine_intakes import router as medicine_intakes_router
from .prescriptions import router as prescriptions_router
from .ophthalmological_prescriptions import router as ophthalmological_prescriptions_router
from .first_aid_kit_shares import router as first_aid_kit_shares_router

router = APIRouter(tags=["Medicine Domain"])

router.include_router(medicines_router)
router.include_router(first_aid_kits_router)
router.include_router(medicine_intakes_router)
router.include_router(prescriptions_router)
router.include_router(ophthalmological_prescriptions_router)
router.include_router(first_aid_kit_shares_router)
