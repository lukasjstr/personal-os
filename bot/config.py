"""Application configuration loaded from environment variables."""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str
    telegram_webhook_url: str
    telegram_webhook_cert: str = "/etc/nginx/ssl/webhook.pem"

    # OpenAI
    openai_api_key: str

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "personal_os"
    db_user: str = "pos_user"
    db_password: str = "personalos2026"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_secret_key: str = "change-me"

    # Web Push (VAPID)
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_mailto: str = "mailto:lukasjstr@gmail.com"

    # V3 P08 — Expansion Guard
    expansion_soft_limit_priority1: int = 3   # max objectives with priority_weight >= 8
    expansion_hard_limit_total: int = 5       # max active objectives total
    expansion_warning_enabled: bool = True

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # allow unknown .env keys without crashing


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Multi-device account mapping: secondary_telegram_id -> primary_telegram_id
# Both devices will share the same account and see the same data.
# Primary account is now 7118468255 (main phone)
LINKED_TELEGRAM_IDS: dict[int, int] = {
    6118629820: 7118468255,
}
