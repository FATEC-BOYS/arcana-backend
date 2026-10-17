from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)
    environment: Literal["development", "test", "production"] = Field(
        default="development", validation_alias="ARCANA_ENV"
    )
    daily_chart_limit: int = Field(default=30, ge=1, le=1000)
    daily_message_limit: int = Field(default=60, ge=1, le=1000)
    max_job_attempts: int = Field(default=3, ge=1, le=5)
    max_context_chars: int = Field(default=96000, ge=8000, le=200000)
    app_name: str = "Arcana API"
    database_url: str = "postgresql+psycopg://arcana:arcana@localhost:5432/arcana"
    cors_origins: list[str] = ["http://localhost:4200"]
    openai_api_key: SecretStr | None = None
    llm_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    daily_reading_limit: int = Field(default=20, ge=1, le=1000)
    max_messages_per_reading: int = Field(default=30, ge=1, le=100)
    auth_window_seconds: int = 900
    auth_attempt_limit: int = 20
    # Generate a random value for production. Used only to pseudonymize rate-limit keys.
    rate_limit_secret: SecretStr = SecretStr("local-development-only")
    public_frontend_url: str = "http://localhost:4200"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str | None = None

    @model_validator(mode="after")
    def production_settings(self):
        if self.environment == "production" and len(self.rate_limit_secret.get_secret_value()) < 32:
            raise ValueError("Production requires RATE_LIMIT_SECRET with at least 32 characters")
        if "*" in self.cors_origins:
            raise ValueError("Use explicit frontend origins, not wildcard CORS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
