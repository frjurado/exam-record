from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "WikiAnálisis"
    ALGORITHM: str = "HS256"
    # The emailed link is short-lived; the session it opens is long-lived.
    LINK_TOKEN_EXPIRE_MINUTES: int = 15
    SESSION_EXPIRE_DAYS: int = 30

    # Email
    RESEND_API_KEY: str | None = None
    FROM_EMAIL: str = "onboarding@resend.dev"

    # Turnstile
    TURNSTILE_SITE_KEY: str | None = None
    TURNSTILE_SECRET_KEY: str | None = None

    # The one public address of the site (e.g. "wikianalisis.org"). When set, requests to
    # its www form or to the *.fly.dev address are redirected to it.
    CANONICAL_HOST: str | None = None

    # Monitoring
    SENTRY_DSN: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)


settings = Settings()  # type: ignore[call-arg]
