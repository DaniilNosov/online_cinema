from email.message import EmailMessage
import aiosmtplib
from src.config.settings import settings


async def send_email(to_email: str, subject: str, body: str) -> None:
    """Send an asynchronous email via the configured SMTP server."""
    message = EmailMessage()
    message["From"] = settings.SMTP_USER
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        use_tls=False,
        start_tls=False,
    )


async def send_activation_email(to_email: str, token: str) -> None:
    """Send an account activation token to the user."""
    subject = "Activate Your Online Cinema Account"
    body = (
        f"Welcome to Online Cinema!\n\n"
        f"Use the following token to activate your account:\n"
        f"{token}\n\n"
        f"This token is valid for 24 hours."
    )
    await send_email(to_email, subject, body)


async def send_password_reset_email(to_email: str, token: str) -> None:
    """Send a password reset token to the user."""
    subject = "Password Reset Request - Online Cinema"
    body = (
        f"You requested a password reset.\n\n"
        f"Use the following token to set a new password:\n"
        f"{token}\n\n"
        f"This token is valid for 1 hour."
    )
    await send_email(to_email, subject, body)
