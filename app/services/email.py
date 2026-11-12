import logging

import resend

from app.core.config import settings

logger = logging.getLogger("uvicorn")


class EmailService:
    def __init__(self) -> None:
        if settings.RESEND_API_KEY:
            resend.api_key = settings.RESEND_API_KEY
        else:
            logger.warning(
                "RESEND_API_KEY not found. Email sending will be disabled (logged only)."
            )

    async def send_magic_link(self, email: str, link: str) -> None:
        """
        Send a magic link email to the user.
        """
        if not settings.RESEND_API_KEY:
            logger.info(f"EMAIL SIMULATION for {email}: {link}")
            return

        minutes = settings.LINK_TOKEN_EXPIRE_MINUTES
        html_content = f"""
        <h1 style="font-family: Georgia, serif; font-weight: 500;">WikiAnálisis</h1>
        <p>Pulsa el botón para verificar tu email y terminar lo que estabas haciendo:</p>
        <p>
            <a href="{link}" style="background-color: #1F5A5E; color: #ffffff; padding: 10px 20px; text-decoration: none; border-radius: 3px;">
                Verificar mi email
            </a>
        </p>
        <p><small>Ábrelo en el mismo navegador donde lo pediste. El enlace caduca en {minutes} minutos.</small></p>
        <p><small>Si el botón no funciona, copia esta dirección: {link}</small></p>
        <p><small>Si no has pedido este enlace, puedes ignorar este mensaje.</small></p>
        """

        try:
            r = resend.Emails.send(
                {
                    "from": settings.FROM_EMAIL,
                    "to": email,
                    "subject": "Tu enlace para WikiAnálisis",
                    "html": html_content,
                }
            )
            logger.info(f"Email sent to {email}. ID: {r.get('id')}")
        except Exception as e:
            logger.error(f"Failed to send email to {email}: {str(e)}")
            # In production, we might want to re-raise this, but for now log it.
            # If email fails, the user can't log in.
            raise e


email_service = EmailService()
