"""Runtime configuration for crmbuilder_v2.

Defaults make the system runnable from a fresh checkout without setting
environment variables. Each setting can be overridden via ``CRMBUILDER_V2_*``
environment variables.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    # config.py is at <repo>/crmbuilder-v2/src/crmbuilder_v2/config.py
    return Path(__file__).resolve().parents[3]


def _default_export_dir() -> Path:
    return _repo_root() / "PRDs" / "product" / "crmbuilder-v2" / "db-export"


class Settings(BaseSettings):
    # ``export_dir`` binds from ``CRMBUILDER_V2_EXPORT_DIR`` (sibling of
    # ``CRMBUILDER_V2_DB_PATH``) via the ``env_prefix`` mechanism below.
    # The literal string ``__UNCONFIGURED__`` is a reserved value: the
    # routing helper sets the env var to it when the active engagement
    # has no ``engagement_export_dir`` in the meta DB, so the export-write
    # gate (``runtime.engagement_routing.assert_export_dir_ready``) can
    # fail loud rather than silently fall back to the engine default.
    # An empty/whitespace env var value is treated as unset (falls back
    # to the default); the sentinel is non-empty and passes through.
    model_config = SettingsConfigDict(
        env_prefix="CRMBUILDER_V2_",
        env_file=None,
        case_sensitive=False,
    )

    db_path: Path = Field(
        default_factory=lambda: _repo_root() / "crmbuilder-v2" / "data" / "v2.db"
    )
    export_dir: Path = Field(default_factory=_default_export_dir)

    @field_validator("export_dir", mode="before")
    @classmethod
    def _empty_export_dir_is_default(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return _default_export_dir()
        return value
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    api_base_url: str = "http://127.0.0.1:8765"
    mcp_http_port: int = 8810

    # --- MCP OAuth 2.1 authorization server (streamable-http only) ---
    # We run our own OAuth AS (mcp SDK's OAuthAuthorizationServerProvider)
    # instead of Cloudflare Managed OAuth, which drops the per-request
    # ``resource``/``code_challenge`` params across its login step
    # (empirically confirmed; see the AI-surface notes in CLAUDE.md). The
    # public URL is both the OAuth issuer and the protected-resource URL,
    # and must equal what claude.ai users type as the connector URL. For
    # local end-to-end testing, override via CRMBUILDER_V2_MCP_PUBLIC_URL
    # (e.g. http://localhost:8810). stdio transport is always unauthenticated.
    oauth_enabled: bool = True
    mcp_public_url: str = "https://mcp.crmbuilder.ai"
    google_client_id: str = ""
    google_client_secret: str = ""
    oauth_allowed_email: str = "doug@dougbower.com"
    # Empty => a stable secret is generated and persisted next to oauth_db_path.
    oauth_jwt_secret: str = ""
    oauth_db_path: Path = Field(
        default_factory=lambda: _repo_root() / "crmbuilder-v2" / "data" / "oauth.db"
    )
    access_token_ttl: int = 3600  # 1 hour
    refresh_token_ttl: int = 60 * 60 * 24 * 30  # 30 days
    auth_code_ttl: int = 600  # 10 minutes

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def google_redirect_uri(self) -> str:
        return f"{self.mcp_public_url.rstrip('/')}/oauth/google/callback"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Reset the cached Settings instance (useful for tests)."""
    get_settings.cache_clear()
