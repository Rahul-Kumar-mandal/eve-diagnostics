"""
Centralized application settings, loaded from environment variables (.env supported).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Default to SQLite so the project runs with zero external setup.
    # Set DATABASE_URL to a Postgres DSN in production, e.g.:
    # postgresql+psycopg2://user:password@localhost:5432/eve_healthcare
    database_url: str = "sqlite:///./eve_healthcare.db"

    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION_super_secret_key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Shared secret the (simulated) payment provider must send back on webhook
    # calls, so we can reject webhooks that didn't originate from our mock
    # payment service. In a real integration this would be a signature check.
    webhook_shared_secret: str = "mock_provider_shared_secret"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
