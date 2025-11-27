"""
Medical Domain Routes
Medical cards and medical data management
"""
from fastapi import APIRouter

from .medical_cards import router as medical_cards_router
from .medical_card_data import router as medical_card_data_router

router = APIRouter(tags=["Medical Domain"])

router.include_router(medical_cards_router)
router.include_router(medical_card_data_router)
