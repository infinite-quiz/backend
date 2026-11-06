from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Infinite Quiz API"
    app_env: str = "development"
    debug: bool = True
    api_prefix: str = "/api"

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "sqlite:///./quiz.db"

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    default_lives: int = 3
    max_questions_per_request: int = 20

    generator_mode: str = "stub"  # stub | http
    generator_url: str | None = None
    generator_timeout_sec: int = 30

    # Ranked
    ranked_round_seconds: int = 20
    ranked_default_rounds: int = 5
    public_base_url: str = "http://localhost:8000"
    public_ws_base_url: str = "ws://localhost:8000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
