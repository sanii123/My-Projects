"""App settings, loaded from environment / .env. See .env.example for the full list.

Kept as one flat Settings object (pydantic-settings) rather than scattering
os.environ.get() calls through the codebase — every other module imports
`settings` from here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    # Agent's own Postgres (docs/architecture.md 4.7) — asyncpg driver.
    database_url: str = "postgresql+asyncpg://ipam_agent:ipam_agent@localhost:5432/ipam_agent"

    # NetBox IPAM backend (4.6) — scoped service-account token, not a personal credential.
    netbox_url: str = "http://localhost:8080"
    netbox_token: str = ""

    # Local LLM (4.4).
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # Auth — standalone JWT for now (open decision in section 11; SSO can replace
    # this behind the same get_current_user dependency later without touching callers).
    jwt_secret_key: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Agent Runtime guardrails (4.3, 6).
    agent_tool_step_limit: int = 8
    agent_turn_timeout_seconds: int = 60


settings = Settings()
