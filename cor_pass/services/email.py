from pathlib import Path

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi_mail.errors import ConnectionErrors
from pydantic import EmailStr

from io import BytesIO
from fastapi import UploadFile

from cor_pass.config.config import settings
from loguru import logger
from cor_pass.schemas import FeedbackProposalsScheema, FeedbackRatingScheema, SupportReportScheema
from cor_pass.services.qr_code import generate_qr_code
from cor_pass.services.recovery_file import generate_recovery_file


conf = ConnectionConfig(
    MAIL_USERNAME=settings.mail_username,
    MAIL_PASSWORD=settings.mail_password,
    MAIL_FROM=settings.mail_from,
    MAIL_PORT=settings.mail_port,
    MAIL_SERVER=settings.mail_server,
    MAIL_FROM_NAME="COR-ID",
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=True,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=Path(__file__).parent.parent / "templates",
)


async def send_email_code(
    email: EmailStr, host: str, verification_code
):  # registration
    """
    The send_email function sends an email to the user with a link to confirm their email address.\n
        Args:
            email (str): The user's email address.
            host (str): The hostname that will be used in constructing a URL for confirming their account registration.

    :param email: EmailStr: Validate the email address
    :param host: str: Pass the hostname of the server to the template
    :return: A coroutine object
    """
    logger.debug(f"Sending email to {email}")
    try:
        message = MessageSchema(
            subject="Confirm your email ",
            recipients=[email],
            template_body={
                "host": host,
                "code": verification_code,
            },
            subtype=MessageType.html,
        )

        fm = FastMail(conf)
        await fm.send_message(message, template_name="email_templates.html")
        logger.debug(f"Sending email to {email} done!")
    except ConnectionErrors as err:
        print(err)


async def send_email_code_forgot_password(
    email: EmailStr, host: str, verification_code
):  # forgot password
    """
    The send_email function sends an email to the user with a link to confirm their email address.\n
        Args:
            email (str): The user's email address.
            host (str): The hostname that will be used in constructing a URL for confirming their account registration.

    :param email: EmailStr: Validate the email address
    :param host: str: Pass the hostname of the server to the template
    :return: A coroutine object
    """
    logger.debug(f"Sending email to {email}")
    try:
        message = MessageSchema(
            subject="Forgot Password",
            recipients=[email],
            template_body={
                "host": host,
                "code": verification_code,
            },
            subtype=MessageType.html,
        )

        fm = FastMail(conf)
        await fm.send_message(
            message, template_name="forgot_password_email_template.html"
        )
        logger.debug(f"Sending email to {email} done!")
    except ConnectionErrors as err:
        print(err)


async def send_email_code_with_qr(email: EmailStr, host: str, recovery_code):
    logger.debug(f"Sending email to {email}")
    try:
        qr_code_bytes = generate_qr_code(recovery_code)
        recovery_file = await generate_recovery_file(recovery_code)

        message = MessageSchema(
            subject="Recovery code",
            recipients=[email],
            template_body={
                "host": host,
                "recovery_code": recovery_code,
            },
            subtype=MessageType.html,
            attachments=[
                UploadFile(filename="qrcode.png", file=BytesIO(qr_code_bytes)),
                UploadFile(filename="recovery_key.bin", file=recovery_file),
            ],
        )

        fm = FastMail(conf)
        await fm.send_message(message, template_name="recovery_code.html")
        logger.debug(f"Sending email to {email} with QR code done!")
    except ConnectionErrors as err:
        print(err)


async def send_email_code_with_temp_pass(
    email: EmailStr,
    temp_pass,
):
    logger.debug(f"Sending email to {email}")
    try:

        message = MessageSchema(
            subject="Temp Pass",
            recipients=[email],
            template_body={
                "temp_pass": temp_pass,
            },
            subtype=MessageType.html,
        )

        fm = FastMail(conf)
        await fm.send_message(message, template_name="temp_pass.html")
        logger.debug(f"Sending email to {email} with temp_pass done!")
    except ConnectionErrors as err:
        print(err)


async def send_feedback_email(
    feedback: FeedbackRatingScheema,
    user_cor_id: str,
    user_email: EmailStr,
):
    """
    Отправляет email с обратной связью, используя FastMail library.
    """
    
    template_body = {
        "rating": feedback.rating,
        "comment": feedback.comment,
        "user_cor_id": user_cor_id,
        "user_email": user_email,
    }
    
    message = MessageSchema(
        subject="Новый отзыв от пользователя",
        recipients=[settings.marketing_email], 
        template_body=template_body,
        subtype=MessageType.html, 
    )
    
    fm = FastMail(conf)
    

    await fm.send_message(message, template_name="feedback.html") 

async def send_proposal_email(
    feedback: FeedbackProposalsScheema,
    user_cor_id: str,
    user_email: EmailStr,
):
    """
    Отправляет email с обратной связью, используя FastMail library.
    """
    
    template_body = {
        "proposal": feedback.proposal,
        "user_cor_id": user_cor_id,
        "user_email": user_email,
    }
    
    message = MessageSchema(
        subject="Новое предложение от пользователя",
        recipients=[settings.marketing_email], 
        template_body=template_body,
        subtype=MessageType.html, 
    )
    
    fm = FastMail(conf)
    

    await fm.send_message(message, template_name="proposal.html") 



async def send_report_email(
    report: SupportReportScheema,
    user_cor_id: str,
    user_email: EmailStr,
):
    """
    Отправляет email с сообщением о проблеме, используя FastMail library.
    """
    
    template_body = {
        "product_name": report.product_name,
        "report_text": report.report_text,
        "user_cor_id": user_cor_id,
        "user_email": user_email,
    }
    
    message = MessageSchema(
        subject="Обнаружена проблема",
        recipients=["support@cor-int.com"], 
        template_body=template_body,
        subtype=MessageType.html, 
    )
    
    fm = FastMail(conf)
    

    await fm.send_message(message, template_name="report.html") 