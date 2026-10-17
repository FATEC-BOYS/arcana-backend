from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "Arcana API"
    database_url: str = "postgresql+psycopg://arcana:arcana@localhost:5432/arcana"
    cors_origins: list[str] = ["http://localhost:4200"]
    llm_api_key: str | None = None
    max_question_length: int = 2000


@lru_cache
def get_settings() -> Settings:
    return Settings()
