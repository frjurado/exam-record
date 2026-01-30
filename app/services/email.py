import resend
import logging
from app.core.config import settings

logger = logging.getLogger("uvicorn")

class EmailService:
    def __init__(self):
        if settings.RESEND_API_KEY:
            resend.api_key = settings.RESEND_API_KEY
        else:
            logger.warning("RESEND_API_KEY not found. Email sending will be disabled (logged only).")

    async def send_magic_link(self, email: str, link: str):
        """
        Send a magic link email to the user.
        """
        if not settings.RESEND_API_KEY:
            logger.info(f"EMAIL SIMULATION for {email}: {link}")
            return

        html_content = f"""
        <h1>Log in to Exam Record</h1>
        <p>Click the link below to verify your email and complete your action:</p>
        <p>
            <a href="{link}" style="background-color: #2563EB; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                Verify Email
            </a>
        </p>
        <p><small>Or copy this link: {link}</small></p>
        """

        try:
            r = resend.Emails.send({
                "from": settings.FROM_EMAIL,
                "to": email,
                "subject": "Verify your email for Exam Record",
                "html": html_content
            })
            logger.info(f"Email sent to {email}. ID: {r.get('id')}")
        except Exception as e:
            logger.error(f"Failed to send email to {email}: {str(e)}")
            # In production, we might want to re-raise this, but for now log it.
            # If email fails, the user can't log in.
            raise e

email_service = EmailService()
