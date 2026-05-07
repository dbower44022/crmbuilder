"""Runtime configuration for crmbuilder_v2.

Defaults make the system runnable from a fresh checkout without setting
environment variables. Each setting can be overridden via ``CRMBUILDER_V2_*``
environment variables.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    # config.py is at <repo>/crmbuilder-v2/src/crmbuilder_v2/config.py
    return Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CRMBUILDER_V2_",
        env_file=None,
        case_sensitive=False,
    )

    db_path: Path = Field(
        default_factory=lambda: _repo_root() / "crmbuilder-v2" / "data" / "v2.db"
    )
    export_dir: Path = Field(
        default_factory=lambda: _repo_root()
        / "PRDs"
        / "product"
        / "crmbuilder-v2"
        / "db-export"
    )
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
