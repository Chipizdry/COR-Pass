"""
User Domain Routes
Authentication, COR-ID, OTP, records, tags, and personal data
"""
from fastapi import APIRouter

from .auth import router as auth_router
from .cor_id import router as cor_id_router
from .otp_auth import router as otp_auth_router
from .records import router as records_router
from .tags import router as tags_router
from .person import router as person_router

router = APIRouter(tags=["User Domain"])

router.include_router(auth_router)
router.include_router(cor_id_router)
router.include_router(otp_auth_router)
router.include_router(records_router)
router.include_router(tags_router)
router.include_router(person_router)
