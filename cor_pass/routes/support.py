from fastapi import APIRouter, Depends, status, BackgroundTasks

from cor_pass.services.auth import auth_service

from cor_pass.services.email import send_report_email
from cor_pass.database.models import User

from loguru import logger
from cor_pass.schemas import (
    SupportReportScheema

)

from fastapi_limiter.depends import RateLimiter

router = APIRouter(prefix="/support", tags=["Support"])



@router.post("/report/send", 
             dependencies=[Depends(RateLimiter(times=5, seconds=60))],
             status_code=status.HTTP_200_OK)
async def send_report(
    report: SupportReportScheema,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(auth_service.get_current_user)
):
    """
    Принимает сообщение об ошибке от пользователя и отправляет её на почту отдела поддержки.
    """
    background_tasks.add_task(
        send_report_email,
        report=report,
        user_cor_id=current_user.cor_id,
        user_email=current_user.email
    )
    
    return {"message": "Спасибо за ваше сообщение! Мы рассмотрим его и свяжемся с Вами при необходимости"}