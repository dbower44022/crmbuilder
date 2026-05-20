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

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Reset the cached Settings instance (useful for tests)."""
    get_settings.cache_clear()
