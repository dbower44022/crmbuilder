"""Read-only ground-truth capture of every EspoCRM layout type.

Phase 0 of the full-fidelity layout work. Connects to the default CBM test
instance (per-client SQLite ``Instance`` row, ``is_default = 1``) and issues a
``GET`` for every *candidate* layout type against one native entity and one
custom entity. Each non-empty response is written verbatim to
``tests/fixtures/layouts/<entity>.<type>.json`` so builders/reverse-mappers can
be written and asserted against the real shapes EspoCRM returns.

This script performs **no writes** to the instance — only ``get_layout`` GETs
and a ``get_all_scopes`` metadata read.

Usage::

    uv run python tools/capture_layouts.py

Optionally pass entity names to override auto-selection::

    uv run python tools/capture_layouts.py Contact CEngagement
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.models import InstanceProfile

REPO_ROOT = Path(__file__).resolve().parents[1]
CLIENT_DB = REPO_ROOT / "automation" / "data" / "cbm-client.db"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "layouts"

# Every layout type EspoCRM is documented to expose. Capture probes all of
# them; the run report shows which actually return data on this instance.
CANDIDATE_LAYOUT_TYPES: list[str] = [
    # Class A — panels/rows
    "detail",
    "edit",
    "detailSmall",
    "detailConvert",
    # Class B — columns
    "list",
    "listSmall",
    # Class C — flat field list
    "filters",
    "massUpdate",
    # Class D — ordered relationship/stream panels
    "relationships",
    "sidePanelsDetail",
    "sidePanelsEdit",
    "sidePanelsDetailSmall",
    "sidePanelsEditSmall",
    "bottomPanelsDetail",
    "bottomPanelsEdit",
    "bottomPanelsDetailSmall",
    "bottomPanelsEditSmall",
    # Class E — special
    "kanban",
    # Portal variants (deploy deferred; captured to confirm presence/shape)
    "listPortal",
    "detailPortal",
    "detailSmallPortal",
    "listSmallPortal",
    "relationshipsPortal",
]


def load_default_instance() -> InstanceProfile:
    """Load the default Instance row from the CBM client DB (basic auth).

    :returns: An :class:`InstanceProfile` for the default instance.
    :raises RuntimeError: If the DB or default row is missing.
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


def pick_entities(
    client: EspoAdminClient, overrides: list[str]
) -> tuple[list[str], dict[str, Any]]:
    """Choose a native and a custom entity to probe (unless overridden).

    :param client: Connected admin client.
    :param overrides: Explicit entity names from the CLI; used as-is if given.
    :returns: Tuple of (entity names to probe, raw scopes dict).
    """
    status, scopes = client.get_all_scopes()
    if status != 200 or not isinstance(scopes, dict):
        msg = f"get_all_scopes failed (HTTP {status})"
        raise RuntimeError(msg)

    if overrides:
        return overrides, scopes

    entities = {
        name: sd
        for name, sd in scopes.items()
        if isinstance(sd, dict) and sd.get("entity") is True
    }
    native = next(
        (n for n in ("Contact", "Account", "Lead") if n in entities), None
    )
    custom = next(
        (n for n, sd in sorted(entities.items()) if sd.get("isCustom")), None
    )
    chosen = [e for e in (native, custom) if e]
    if not chosen:
        chosen = sorted(entities)[:2]
    return chosen, scopes


def structure_hint(body: Any) -> str:
    """One-line description of a captured layout's top-level structure."""
    if isinstance(body, list):
        if not body:
            return "list (empty)"
        first = body[0]
        if isinstance(first, str):
            return f"list[str] x{len(body)} (flat field list)"
        if isinstance(first, dict):
            keys = sorted(first.keys())
            return f"list[dict] x{len(body)} keys={keys}"
        return f"list[{type(first).__name__}] x{len(body)}"
    if isinstance(body, dict):
        return f"dict keys={sorted(body.keys())}"
    return type(body).__name__


def main() -> int:
    overrides = sys.argv[1:]
    profile = load_default_instance()
    client = EspoAdminClient(profile, timeout=60)
    print(f"Connected to {profile.name} ({profile.url})\n")

    entities, scopes = pick_entities(client, overrides)
    has_portal = any(
        isinstance(sd, dict) and "Portal" in name
        for name, sd in scopes.items()
    )
    print(f"Probing entities: {entities}")
    print(f"Portal scope present in metadata: {has_portal}\n")

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    summary: list[tuple[str, str, int, str, bool]] = []

    for entity in entities:
        for layout_type in CANDIDATE_LAYOUT_TYPES:
            status, body = client.get_layout(entity, layout_type)
            # Skip the "not separately defined" sentinel: false / null / [] / {}.
            has_data = status == 200 and bool(body)
            saved = False
            if has_data:
                out = FIXTURE_DIR / f"{entity}.{layout_type}.json"
                out.write_text(
                    json.dumps(body, indent=2, sort_keys=True),
                    encoding="utf-8",
                )
                saved = True
            hint = structure_hint(body) if status == 200 else "-"
            summary.append((entity, layout_type, status, hint, saved))

    # Report
    print(f"{'entity':<14}{'type':<24}{'http':<6}{'saved':<7}structure")
    print("-" * 100)
    for entity, layout_type, status, hint, saved in summary:
        mark = "yes" if saved else ""
        print(f"{entity:<14}{layout_type:<24}{status:<6}{mark:<7}{hint}")

    saved_count = sum(1 for *_, s in summary if s)
    print(f"\nSaved {saved_count} fixtures to {FIXTURE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
