from pathlib import Path

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi_mail.errors import ConnectionErrors
from pydantic import EmailStr

from cor_pass.config.config import settings
from cor_pass.services.logger import logger


conf = ConnectionConfig(
    MAIL_USERNAME=settings.mail_username,
    MAIL_PASSWORD=settings.mail_password,
    MAIL_FROM=settings.mail_from,
    MAIL_PORT=settings.mail_port,
    MAIL_SERVER=settings.mail_server,
    MAIL_FROM_NAME="COR-Pass",
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
    The send_email function sends an email to the user with a link to confirm their email address.
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
    The send_email function sends an email to the user with a link to confirm their email address.
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
