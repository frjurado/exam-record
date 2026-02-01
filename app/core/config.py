from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Exam Record"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    
    # Email
    RESEND_API_KEY: str | None = None
    FROM_EMAIL: str = "onboarding@resend.dev"

    # Turnstile
    TURNSTILE_SITE_KEY: str | None = None
    TURNSTILE_SECRET_KEY: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

settings = Settings()
