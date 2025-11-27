"""
Laboratory Domain Routes
Cases, samples, cassettes, glasses, laboratories, and image processing
"""
from fastapi import APIRouter

from .cases import router as cases_router
from .samples import router as samples_router
from .cassettes import router as cassettes_router
from .glasses import router as glasses_router
from .laboratories import router as laboratories_router
from .dicom_router import router as dicom_router
from .svs_router import router as svs_router
from .scanner_router import router as scanner_router
from .excel_router import router as excel_router

router = APIRouter(tags=["Laboratory Domain"])

router.include_router(cases_router)
router.include_router(samples_router)
router.include_router(cassettes_router)
router.include_router(glasses_router)
router.include_router(laboratories_router)
router.include_router(dicom_router)
router.include_router(svs_router)
router.include_router(scanner_router)
router.include_router(excel_router)
