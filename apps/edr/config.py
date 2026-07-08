from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65535)
    public_base_url: str = "http://localhost:8000"
    public_hostname: str = "localhost"

    # Identity
    entra_client_id: str | None = None
    entra_tenant_id: str | None = None
    entra_client_secret: str | None = None

    # LLM providers
    # Generation-provider runtime switch: "anthropic" | "deepseek".  The
    # inactive provider stays installed and configured-but-dormant; only the
    # active one is used by apps.edr.llm.call_llm and required for go-live.
    llm_provider: str = "anthropic"
    anthropic_api_key: str | None = None
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    voyage_api_key: str | None = None
    cohere_api_key: str | None = None

    # Data stores
    postgres_db: str = "decision_center"
    postgres_user: str = "decision_center"
    postgres_password: str = "change-me"
    postgres_host: str = "postgres"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    redis_url: str = "redis://redis:6379/0"
    qdrant_url: str = "http://qdrant:6333"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "decisioncenter"
    minio_secret_key: str = "change-me"
    minio_bucket: str = "decision-center"

    # Connector layer
    n8n_base_url: str = "http://n8n:5678"
    n8n_webhook_token: str | None = None
    n8n_timeout: int = Field(default=60, ge=1, le=300)
    sharepoint_search_webhook: str = "/webhook/sharepoint-search"
    owncloud_list_webhook: str = "/webhook/owncloud-list"
    email_search_webhook: str = "/webhook/email-search"
    odoo_read_webhook: str = "/webhook/odoo-read"

    # ownCloud service-account credentials (read by n8n only)
    owncloud_username: str | None = None
    owncloud_password: str | None = None

    # Odoo read-only API (read by n8n only)
    odoo_url: str | None = None
    odoo_database: str | None = None
    odoo_username: str | None = None
    odoo_api_key: str | None = None
    # Extended multi-source Odoo retrieval (node_08). Off by default so the
    # narrow project+cost flow is unchanged until an operator opts in AND the
    # n8n odoo_read workflow returns structured fields. Read-only either way.
    odoo_extended_sources_enabled: bool = False
    odoo_extended_include_medium: bool = True
    # Per-source read cap for extended Odoo sources. The live Odoo backend
    # needs >5s for purchase_order_lines / material_requests — a tight cap
    # silently drops committed-cost evidence from financial reports.
    odoo_extended_source_timeout_s: float = Field(default=15.0, gt=0, le=60)

    # Odoo Source Map batched scan (admin-only, read-only). These bound the
    # automatic per-source/per-batch scanning so a scan can never hit the
    # reverse-proxy timeout: the scan runs in a background session and each
    # webcall is strictly time-boxed. Tuned conservatively; safe to raise.
    odoo_scan_page_size: int = Field(default=100, ge=1, le=100)
    odoo_scan_sample_target: int = Field(default=300, ge=1, le=5000)
    odoo_scan_max_pages_per_source: int = Field(default=50, ge=1, le=1000)
    odoo_scan_batch_timeout_s: float = Field(default=20.0, gt=0, le=120)
    odoo_scan_source_timeout_s: float = Field(default=45.0, gt=0, le=300)
    odoo_scan_poll_hint_ms: int = Field(default=1500, ge=250, le=30000)

    # Observability and budget
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"
    daily_cost_cap_usd: float = Field(default=12, gt=0)
    monthly_cost_target_usd: float = Field(default=300, gt=0)


def _reject_placeholder_secrets_in_production(s: Settings) -> None:
    """Fail fast when production runs on the local-convenience defaults.

    Deliberately a plain check (not a pydantic validator): a ValidationError
    would echo the full settings input — secrets included — into startup logs.
    """
    if s.app_env != "production":
        return
    weak = [
        name
        for name, value in (
            ("POSTGRES_PASSWORD", s.postgres_password),
            ("MINIO_SECRET_KEY", s.minio_secret_key),
        )
        if value == "change-me"
    ]
    if weak:
        raise RuntimeError(
            "Placeholder secrets are not allowed when APP_ENV=production: "
            + ", ".join(weak)
            + ". Rotate them in .env (or set APP_ENV=local for development)."
        )


settings = Settings()
_reject_placeholder_secrets_in_production(settings)
