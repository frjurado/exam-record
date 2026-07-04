import sentry_sdk

from app.core.config import settings


def init_sentry() -> None:
    """Enable Sentry error tracking in production, if a DSN is configured.

    No-ops in development or when SENTRY_DSN is unset, same pattern as the
    optional RESEND_API_KEY/Turnstile integrations.
    """
    if settings.ENVIRONMENT != "production" or not settings.SENTRY_DSN:
        return

    sentry_sdk.init(dsn=settings.SENTRY_DSN, send_default_pii=False)
