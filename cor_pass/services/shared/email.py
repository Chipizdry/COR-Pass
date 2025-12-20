from pathlib import Path

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi_mail.errors import ConnectionErrors
from pydantic import EmailStr

from io import BytesIO
from fastapi import UploadFile

from cor_pass.config.config import settings
from loguru import logger
from cor_pass.schemas import FeedbackProposalsScheema, FeedbackRatingScheema, SupportReportScheema
from cor_pass.services.shared.qr_code import generate_qr_code
from cor_pass.services.user.recovery_file import generate_recovery_file


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
    TEMPLATE_FOLDER=Path(__file__).parent.parent.parent / "templates",
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


async def send_invitation_email(
    email: EmailStr,
    invitation_link: str,
    invited_by_email: str,
    expires_at: str,
):
    """
    Отправляет email с приглашением для регистрации в системе COR-ID.
    
    Args:
        email: Email приглашаемого пользователя
        invitation_link: Полная ссылка для регистрации с токеном
        invited_by_email: Email пользователя, который создал приглашение
        expires_at: Дата истечения приглашения (ISO format)
    """
    logger.debug(f"Sending invitation email to {email}")
    try:
        message = MessageSchema(
            subject="Приглашение в COR-ID",
            recipients=[email],
            template_body={
                "invitation_link": invitation_link,
                "invited_by": invited_by_email,
                "expires_at": expires_at,
                "email": email,
            },
            subtype=MessageType.html,
        )

        fm = FastMail(conf)
        await fm.send_message(message, template_name="invitation_email.html")
        logger.info(f"Invitation email sent to {email}")
    except ConnectionErrors as err:
        logger.error(f"Failed to send invitation email to {email}: {err}")
        raise 


async def send_first_aid_kit_share_email(
    email: EmailStr,
    share_link: str,
    invited_by_email: str,
    expires_at: str,
):
    """
    Отправляет письмо с приглашением на импорт аптечки.

    Args:
        email: Email получателя
        share_link: Deeplink для открытия приложения с токеном
        invited_by_email: Email отправителя
        expires_at: ISO строка времени истечения
    """
    logger.debug(f"Sending first aid kit share email to {email}")
    try:
        message = MessageSchema(
            subject="Приглашение: импорт аптечки в COR-ID",
            recipients=[email],
            template_body={
                "share_link": share_link,
                "invited_by": invited_by_email,
                "expires_at": expires_at,
                "email": email,
            },
            subtype=MessageType.html,
        )

        fm = FastMail(conf)
        await fm.send_message(message, template_name="first_aid_kit_share.html")
        logger.info(f"First aid kit share email sent to {email}")
    except ConnectionErrors as err:
        logger.error(f"Failed to send first aid kit share email to {email}: {err}")
        raise


async def send_employee_invitation_email(
    email: str,
    first_name: str,
    last_name: str,
):
    """
    Отправляет email с приглашением для сотрудника компании на регистрацию.
    
    Args:
        email: Email сотрудника
        first_name: Имя сотрудника
        last_name: Фамилия сотрудника
    """
    logger.debug(f"Sending employee invitation email to {email}")
    try:
        # iOS App Store link
        ios_app_store_link = "https://apps.apple.com/ua/app/cor-energy-app/id6744608535?l=uk"
        # Android Google Play link
        android_play_store_link = "https://play.google.com/store/apps/details?id=com.cormed.corenergy.android&hl=ru"
        
        message = MessageSchema(
            subject="Запрошення до програми корпоративних клієнтів COR-ENERGY",
            recipients=[email],
            template_body={
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "ios_app_store_link": ios_app_store_link,
                "android_play_store_link": android_play_store_link,
            },
            subtype=MessageType.html,
        )

        fm = FastMail(conf)
        await fm.send_message(message, template_name="employee_invitation.html")
        logger.info(f"Employee invitation email sent to {email} ({first_name} {last_name})")
    except ConnectionErrors as err:
        logger.error(f"Failed to send employee invitation email to {email}: {err}")
        # Не пробрасываем исключение, чтобы не сломать основной процесс добавления
        raise 


async def send_employee_added_email(
    email: str,
    first_name: str,
    last_name: str,
):
    """
    Отправляет уведомление, что сотрудник успешно добавлен в корпоративную программу.
    """
    logger.debug(f"Sending employee added email to {email}")
    try:
        ios_app_store_link = "https://apps.apple.com/ua/app/cor-energy-app/id6744608535?l=uk"
        android_play_store_link = "https://play.google.com/store/apps/details?id=com.cormed.corenergy.android&hl=ru"

        message = MessageSchema(
            subject="Вас додали до програми корпоративних клієнтів COR-ENERGY",
            recipients=[email],
            template_body={
                "first_name": first_name,
                "last_name": last_name,
                "ios_app_store_link": ios_app_store_link,
                "android_play_store_link": android_play_store_link,
            },
            subtype=MessageType.html,
        )

        fm = FastMail(conf)
        await fm.send_message(message, template_name="employee_added.html")
        logger.info(f"Employee added email sent to {email} ({first_name} {last_name})")
    except ConnectionErrors as err:
        logger.error(f"Failed to send employee added email to {email}: {err}")
        # Не прерываем основной процесс
        raise


async def send_corporate_request_approved_email(
    email: str,
    company_name: str,
):
    """
    Отправляет уведомление, что заявка на регистрацию корпоративного клиента одобрена.
    """
    logger.debug(f"Sending corporate request approved email to {email}")
    try:
        cabinet_url = "https://dev.web.fuel.cor-medical.ua/"
        
        message = MessageSchema(
            subject="Вашу заявку на програму корпоративних клієнтів схвалено",
            recipients=[email],
            template_body={
                "company_name": company_name,
                "cabinet_url": cabinet_url,
            },
            subtype=MessageType.html,
        )

        fm = FastMail(conf)
        await fm.send_message(message, template_name="corporate_request_approved.html")
        logger.info(f"Corporate request approved email sent to {email} for company {company_name}")
    except ConnectionErrors as err:
        logger.error(f"Failed to send corporate request approved email to {email}: {err}")
        # Не прерываем основной процесс одобрения
        raise