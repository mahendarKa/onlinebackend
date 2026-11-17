from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    # 8 hours — long enough for an exam session, short enough that a
    # leaked token expires quickly. Override per-environment in .env.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # "production" disables interactive API docs (/docs, /redoc).
    ENVIRONMENT: str = "production"


settings = Settings()