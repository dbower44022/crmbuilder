"""Shared helpers for the view-filters feasibility spike.

Builds an :class:`EspoAdminClient` against the CBM dev instance using the
connection details stored in the per-client SQLite (``Instance`` row,
``is_default = 1``). Provides convenience helpers to dump JSON, save raw
responses, and pretty-print attempt records.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.models import InstanceProfile


SPIKE_DIR = Path(__file__).resolve().parent
CLIENT_DB = (
    Path(__file__).resolve().parents[3] / "automation" / "data" / "cbm-client.db"
)


@dataclass
class Attempt:
    """Record of a single API attempt during the spike."""

    label: str
    method: str
    url: str
    payload: Any
    status: int
    body: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "method": self.method,
            "url": self.url,
            "payload": self.payload,
            "status": self.status,
            "body": self.body,
        }


def load_default_instance() -> InstanceProfile:
    """Load the default Instance row from the CBM client DB.

    :returns: An :class:`InstanceProfile` configured for basic auth.
    :raises RuntimeError: If no default instance is found.
    """
    if not CLIENT_DB.exists():
        msg = f"client DB not found at {CLIENT_DB}"
        raise RuntimeError(msg)
    conn = sqlite3.connect(CLIENT_DB)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name, url, username, password "
            "FROM Instance WHERE is_default = 1 LIMIT 1"
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        msg = "no default Instance row in cbm-client.db"
        raise RuntimeError(msg)
    name, url, username, password = row
    return InstanceProfile(
        name=name,
        url=url,
        api_key=username,
        auth_method="basic",
        secret_key=password,
    )


def make_client() -> EspoAdminClient:
    """Build a connected EspoAdminClient against the default instance."""
    profile = load_default_instance()
    client = EspoAdminClient(profile, timeout=60)
    return client


def save_json(path: Path, data: Any) -> None:
    """Write *data* to *path* as pretty-printed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def load_json(path: Path) -> Any:
    """Read JSON from *path*."""
    return json.loads(path.read_text(encoding="utf-8"))


def append_attempt(log_path: Path, attempt: Attempt) -> None:
    """Append an attempt record to a JSONL log."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(attempt.to_dict()) + "\n")


def print_attempt(attempt: Attempt) -> None:
    """Pretty-print an attempt to stdout."""
    print(f"[{attempt.label}] {attempt.method} -> HTTP {attempt.status}")
    print(f"  URL: {attempt.url}")
    if attempt.payload is not None:
        snippet = json.dumps(attempt.payload)
        if len(snippet) > 240:
            snippet = snippet[:240] + "..."
        print(f"  payload: {snippet}")
    if isinstance(attempt.body, dict):
        snippet = json.dumps(attempt.body)
        if len(snippet) > 240:
            snippet = snippet[:240] + "..."
        print(f"  body: {snippet}")
    elif attempt.body is not None:
        print(f"  body: {attempt.body}")


# Test names used across spike scripts. The slash in "Donor/Sponsor" is
# preserved verbatim as the *value*; the *filter name* is sanitized.
ENUM_VALUES = ["Client", "Partner", "Donor/Sponsor"]
PRIMARY_FILTER_NAMES = [
    "spikeAccountTypeClient",
    "spikeAccountTypePartner",
    "spikeAccountTypeDonorSponsor",
]
BOOL_FILTER_NAMES = [
    "spikeBoolAccountTypeClient",
    "spikeBoolAccountTypePartner",
    "spikeBoolAccountTypeDonorSponsor",
]
