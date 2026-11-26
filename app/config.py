"""Environment configuration."""

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    bot_token: SecretStr = SecretStr("")
    bot_username: str = ""
    admin_ids: str = ""
    main_channel_id: int | None = None
    database_url: str = "postgresql+asyncpg://bot:bot@localhost:5432/bot"
    redis_url: str = "redis://localhost:6379/0"
    webhook_url: str = ""
    webhook_secret: SecretStr = SecretStr("")
    tz: str = "Asia/Tashkent"

    @field_validator("main_channel_id", mode="before")
    @classmethod
    def optional_channel(cls, value: object) -> object:
        """Treat a blank optional channel as unset."""
        return None if value == "" else value

    @property
    def admins(self) -> list[int]:
        """Return configured Telegram administrators."""
        return [int(value.strip()) for value in self.admin_ids.split(",") if value.strip()]

    @field_validator("webhook_url")
    @classmethod
    def https_only(cls, value: str) -> str:
        """Require TLS for public webhooks."""
        if value and not value.startswith("https://"):
            raise ValueError("WEBHOOK_URL HTTPS bo'lishi kerak")
        return value.rstrip("/")


settings = Settings()
