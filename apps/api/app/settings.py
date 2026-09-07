from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Website Growth Agent"
    app_env: str = "development"
    database_url: str = "sqlite:///./website_growth.db"
    api_base_url: str = "http://localhost:8000"
    web_base_url: str = "http://localhost:3000"
    allow_private_urls: bool = False
    max_pages_per_audit: int = 25
    max_crawl_bytes: int = 25 * 1024 * 1024
    crawl_timeout_seconds: float = 12.0
    max_agent_steps: int = 12

    nvidia_api_key: str | None = Field(default=None, validation_alias="NVIDIA_API_KEY")
    nvidia_nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_nim_primary_model: str = "meta/llama-3.3-70b-instruct"
    nvidia_nim_fast_model: str = "meta/llama-3.1-8b-instruct"
    nvidia_nim_embed_model: str = "nvidia/nemotron-3-embed-1b"
    nim_timeout_seconds: float = 45.0

    connector_encryption_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/connectors/google/callback"
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/api/v1/connectors/github/callback"
    github_api_base_url: str = "https://api.github.com"
    autonomy_enabled: bool = False
    autonomy_max_open_prs: int = 3
    autonomy_max_files_per_pr: int = 10
    autonomy_max_diff_bytes: int = 100_000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
