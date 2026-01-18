from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Exam Record"

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

settings = Settings()
