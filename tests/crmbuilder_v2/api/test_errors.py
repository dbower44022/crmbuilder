"""API tests for the export-dir write-gate exception handlers (slice B).

The multi-tenancy routing fix gates every active export-write path
(``session_scope`` / ``force_export`` / catalog exporter) on the active
engagement's ``engagement_export_dir`` being configured (DEC-109) and
present on disk (DEC-114). When the gate raises, ``api/main.py`` routes
the exception to ``engagement_export_dir_handler`` so the response is the
standard ``{data, meta, errors}`` envelope with a stable code rather than
FastAPI's bare 500.

These tests drive a real write (POST /decisions) with the export dir
unconfigured / missing and assert the envelope shape, the code, and that
the DB write rolled back.
"""

from __future__ import annotations

from crmbuilder_v2.config import reset_settings_cache
from crmbuilder_v2.runtime.engagement_routing import UNCONFIGURED_SENTINEL


def _decision_body(identifier: str = "DEC-001") -> dict:
    return {
        "identifier": identifier,
        "title": f"{identifier} title",
        "decision_date": "05-07-26",
        "status": "Active",
    }


def test_write_with_unconfigured_export_dir_returns_500_envelope(
    client, monkeypatch
):
    monkeypatch.setenv("CRMBUILDER_V2_EXPORT_DIR", UNCONFIGURED_SENTINEL)
    reset_settings_cache()

    r = client.post("/decisions", json=_decision_body())

    assert r.status_code == 500
    body = r.json()
    assert body["data"] is None
    assert body["errors"][0]["code"] == "engagement_export_dir_not_configured"
    assert "engagement_export_dir" in body["errors"][0]["message"]

    # The DB write rolled back inside session_scope.
    assert client.get("/decisions/DEC-001").status_code == 404


def test_write_with_missing_export_dir_returns_500_envelope(
    client, monkeypatch, tmp_path
):
    missing = tmp_path / "not-created-yet"
    monkeypatch.setenv("CRMBUILDER_V2_EXPORT_DIR", str(missing))
    reset_settings_cache()

    r = client.post("/decisions", json=_decision_body())

    assert r.status_code == 500
    body = r.json()
    assert body["data"] is None
    assert body["errors"][0]["code"] == "engagement_export_dir_missing"
    assert str(missing) in body["errors"][0]["message"]

    # The configured path was not auto-created (A7), and the DB rolled back.
    assert not missing.exists()
    assert client.get("/decisions/DEC-001").status_code == 404
