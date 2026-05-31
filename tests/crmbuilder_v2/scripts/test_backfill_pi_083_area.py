"""Tests for the PI-083 area-inference heuristic.

``backfill_pi_083_area.py`` lives at ``crmbuilder-v2/scripts/`` which
isn't on the package import path, so it's loaded by file path the same
way the other script tests load their targets. Only the pure
``infer_areas`` heuristic is exercised here — propose/apply hit the live
API and are not unit-tested.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from crmbuilder_v2.access.vocab import SYSTEM_AREAS as AREAS

_SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "crmbuilder-v2"
    / "scripts"
    / "backfill_pi_083_area.py"
)
_spec = importlib.util.spec_from_file_location("backfill_pi_083_area", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
infer_areas = _mod.infer_areas


def test_ui_signal():
    assert "ui" in infer_areas(
        "Surface executive_summary in the planning_items desktop UI",
        "Edit the create dialog and master panel widget.",
    )


def test_api_signal():
    assert "api" in infer_areas(
        "Implement orchestration ready-batches API endpoint",
        "Add a FastAPI router returning batches.",
    )


def test_storage_signal():
    areas = infer_areas(
        "Add area column to planning_items",
        "Alembic migration adds a JSON column with a CHECK constraint.",
    )
    assert "storage" in areas


def test_mcp_signal():
    assert "mcp" in infer_areas(
        "Expose executive_summary on MCP create/update tools",
        "Update the stdio MCP server tool definitions.",
    )


def test_multi_area():
    areas = infer_areas(
        "Wire the access-layer validator and the REST API endpoint",
        "Repository validator plus a new router and Pydantic model.",
    )
    assert "access" in areas
    assert "api" in areas


def test_no_signal_returns_empty():
    assert infer_areas("Reconcile the duplicate session artifact", "Tidy up.") == []


def test_only_returns_registered_areas():
    areas = infer_areas(
        "Migration, API, UI, MCP, methodology template, EspoCRM, CBM",
        "kitchen sink of signals",
    )
    assert set(areas) <= AREAS
    # Output order is the canonical AREAS order (deterministic).
    assert areas == sorted(areas, key=_mod._area_order().index)
