from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Dynamicore Wallet Credit API"
    app_env: str = Field(default="local", alias="APP_ENV")
    app_secret_key: str = Field(
        default="local-development-secret-key-change-before-production",
        alias="APP_SECRET_KEY",
    )
    database_url: str = Field(
        default="postgresql://dynamicore:dynamicore@localhost:5432/dynamicore",
        alias="DATABASE_URL",
    )
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    rate_limit_requests: int = Field(default=120, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window_seconds: int = Field(default=60, alias="RATE_LIMIT_WINDOW_SECONDS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
