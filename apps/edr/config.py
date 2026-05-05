from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    public_base_url: str = "http://localhost:8000"
    n8n_base_url: str = "http://n8n:5678"
    n8n_webhook_token: str | None = None
    daily_cost_cap_usd: float = 12
    monthly_cost_target_usd: float = 300


settings = Settings()
