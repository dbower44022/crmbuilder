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


def api_log_path() -> Path:
    """Return the rotating-log file path for the API process.

    Repo-rooted (not engagement-scoped) so a single durable log captures
    every API run regardless of which engagement is active or how the
    process was launched (standalone ``crmbuilder-v2-api`` or the desktop
    UI's spawned subprocess). Both write here; only one API runs at a
    time, so there is no concurrent-writer contention in practice.
    """
    return _repo_root() / "crmbuilder-v2" / "data" / "logs" / "api.log"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CRMBUILDER_V2_",
        env_file=None,
        case_sensitive=False,
    )

    # PI-123 cutover: the canonical DB is the single unified multi-engagement
    # store. Tests override via ``CRMBUILDER_V2_DB_PATH``; the runtime entry
    # points route here through ``route_settings_to_engagement``.
    db_path: Path = Field(
        default_factory=lambda: _repo_root() / "crmbuilder-v2" / "data" / "v2-unified.db"
    )
    # PI-alpha (D1): a full SQLAlchemy URL for the primary engagement store.
    # When set (e.g. ``postgresql+psycopg://user:pw@host:5432/crmbuilder_v2``),
    # it is the engine URL verbatim and the dialect is Postgres; when unset
    # (the default), ``db_url`` falls back to ``sqlite:///{db_path}`` so a fresh
    # checkout, the still-SQLite meta DB, and existing SQLite installs keep
    # working unchanged. This is the single dialect switch the access layer
    # reads (``access/db.py`` builds the engine SQLite- vs PG-conditionally on
    # it). Binds from ``CRMBUILDER_V2_DATABASE_URL``.
    database_url: str = ""
    # PI-alpha (D10): Postgres connection-pool sizing. Ignored on SQLite (which
    # keeps SQLAlchemy's default pool). Conservative defaults; pinned against
    # the prod topology + PI-100 concurrent-writer scale testing at Deployment.
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle: int = 1800  # seconds; recycle connections before PG idle timeout

    @field_validator("database_url", mode="before")
    @classmethod
    def _validate_database_url(cls, value: object) -> object:
        # Empty/whitespace => unset (SQLite fallback in ``db_url``).
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return ""
        if not isinstance(value, str):
            raise ValueError("CRMBUILDER_V2_DATABASE_URL must be a string")
        url = value.strip()
        # Accept any SQLAlchemy URL with a scheme; guard the common typo of a
        # bare host or path with no ``dialect[+driver]://``.
        if "://" not in url:
            raise ValueError(
                "CRMBUILDER_V2_DATABASE_URL must be a full SQLAlchemy URL "
                "(e.g. postgresql+psycopg://user:pw@host:5432/dbname)"
            )
        return url

    api_host: str = "127.0.0.1"
    api_port: int = 8765

    # PI-123 Slice 2c (DEC-375 / D5, D6); PI-β: now the runtime default. The
    # API resolves an active engagement per request from the ``X-Engagement``
    # header and the central read-filter/write-stamp scope every query/insert.
    # (Pre-PI-β this was turned on by the per-engagement routing helper that
    # set ``CRMBUILDER_V2_ENGAGEMENT_SCOPING_ENABLED``; that helper is gone, so
    # the unified-DB runtime defaults it on. Override to False only for the
    # legacy single-file shape, which no longer exists in production.)
    engagement_scoping_enabled: bool = True
    api_base_url: str = "http://127.0.0.1:8765"
    mcp_http_port: int = 8810

    # PI-β follow-on A1: the MCP server names the active engagement on its
    # REST calls via the ``X-Engagement`` header, mirroring the desktop. When
    # set (to an ``ENG-NNN`` identifier or an engagement code such as
    # ``CRMBUILDER``), every MCP tool call is scoped to that engagement;
    # tools may also override it per-session via the ``select_engagement``
    # tool. Empty (the default) sends no header — unscoped, which is correct
    # for the single-engagement dogfood while prod scoping enforcement is off.
    mcp_engagement: str = ""

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
        # PI-alpha (D1): a configured DATABASE_URL is the engine URL verbatim
        # (Postgres in production); otherwise fall back to the SQLite file.
        if self.database_url:
            return self.database_url
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
