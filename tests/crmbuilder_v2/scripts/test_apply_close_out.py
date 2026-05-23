"""Tests for the v0.7-modified apply_close_out.py script.

The script uses ``urllib.request`` to hit the v2 API; tests monkeypatch
the script's ``_request`` helper to dispatch to a FastAPI ``TestClient``
backed by the per-test SQLite database. That way the full path (script →
API → access layer → DB) is exercised without standing up a real HTTP
server.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from crmbuilder_v2.api.main import create_app
from fastapi.testclient import TestClient

# The apply script lives at crmbuilder-v2/scripts/apply_close_out.py which
# isn't on the package import path; load it by file path.
_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "crmbuilder-v2"
    / "scripts"
    / "apply_close_out.py"
)
_spec = importlib.util.spec_from_file_location("apply_close_out", _SCRIPT_PATH)
apply_close_out = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(apply_close_out)


@pytest.fixture
def api_client(v2_env):
    return TestClient(create_app())


@pytest.fixture
def routed(api_client, monkeypatch):
    """Patch the apply script to use the TestClient instead of urllib."""

    def fake_request(method: str, path: str, body=None) -> tuple[int, dict]:
        resp = api_client.request(method, path, json=body)
        try:
            payload = resp.json()
        except Exception:
            payload = {}
        return resp.status_code, payload

    monkeypatch.setattr(apply_close_out, "_request", fake_request)
    return api_client


def _payload_path(tmp_path: Path, name: str, payload: dict) -> Path:
    """Write a payload JSON at ``<tmp>/PRDs/product/.../close-out-payloads/<name>``."""
    close_out_dir = (
        tmp_path / "PRDs" / "product" / "crmbuilder-v2" / "close-out-payloads"
    )
    close_out_dir.mkdir(parents=True, exist_ok=True)
    path = close_out_dir / name
    path.write_text(json.dumps(payload, indent=2))
    return path


def test_happy_path_lazy_creates_cop_and_records_deposit_event(
    routed, tmp_path, monkeypatch
):
    payload = {
        "label": "Test payload for SES-099",
        "session": {
            "identifier": "SES-099",
            "title": "Test session",
            "session_date": "2026-05-22",
            "status": "Complete",
            "topics_covered": "tests",
            "summary": "ok",
        },
    }
    path = _payload_path(tmp_path, "ses_099.json", payload)
    monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
    rc = apply_close_out.main()
    assert rc == 0

    # Deposit event written.
    deposits = routed.get("/deposit-events").json()["data"]
    assert len(deposits) == 1
    dep = deposits[0]
    assert dep["deposit_event_outcome"] == "success"
    assert dep["deposit_event_records_summary"]["sessions"] == 1
    # Log file present at the expected path.
    log_dir = tmp_path / "PRDs" / "product" / "crmbuilder-v2" / "deposit-event-logs"
    logs = list(log_dir.glob("dep_*.log"))
    assert len(logs) == 1, f"expected 1 log; got {logs}"
    # Close-out payload lazy-created and transitioned to applied.
    cop = routed.get("/close-out-payloads/COP-099").json()["data"]
    assert cop["close_out_payload_status"] == "applied"
    # parent + wrote_record edges exist.
    refs = routed.get(
        f"/references?source_id={dep['deposit_event_identifier']}"
    ).json()["data"]
    kinds = sorted(r["relationship"] for r in refs)
    assert "deposit_event_applies_close_out_payload" in kinds
    assert "deposit_event_wrote_record" in kinds


def test_failure_path_records_error_info_and_leaves_cop_ready(
    routed, tmp_path, monkeypatch
):
    # First record (session) succeeds; second (a malformed decision) fails 422.
    payload = {
        "label": "Test failure",
        "session": {
            "identifier": "SES-100",
            "title": "Test session",
            "session_date": "2026-05-22",
            "status": "Complete",
            "topics_covered": "x",
            "summary": "x",
        },
        "decisions": [
            {
                # Missing required fields → API rejects.
                "identifier": "DEC-INVALID",
            }
        ],
    }
    path = _payload_path(tmp_path, "ses_100.json", payload)
    monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
    rc = apply_close_out.main()
    assert rc == 1  # apply failed

    deposits = routed.get("/deposit-events").json()["data"]
    assert len(deposits) == 1
    dep = deposits[0]
    assert dep["deposit_event_outcome"] == "failure"
    assert dep["deposit_event_error_info"] is not None
    assert dep["deposit_event_error_info"]["step"] == "decisions"
    # The session record landed before the failure → recorded.
    assert dep["deposit_event_records_summary"]["sessions"] == 1
    assert dep["deposit_event_records_summary"]["decisions"] == 0
    # Close-out payload was lazy-created but stayed ready (failure does
    # not drive the ready->applied transition).
    cop = routed.get("/close-out-payloads/COP-100").json()["data"]
    assert cop["close_out_payload_status"] == "ready"


def test_references_in_payload_do_not_break_deposit_event_post(
    routed, tmp_path, monkeypatch
):
    # Regression: the deposit_event POST's references[] block validates
    # target_type against the governance vocab, which does not include
    # 'reference'. If reference rows leak into wrote_records, the
    # deposit_event POST 400s and the apply leaves no audit row.
    payload = {
        "label": "Test payload with references",
        "session": {
            "identifier": "SES-102",
            "title": "Session with refs",
            "session_date": "2026-05-22",
            "status": "Complete",
            "topics_covered": "x",
            "summary": "x",
        },
        "decisions": [
            {
                "identifier": "DEC-300",
                "title": "Test decision",
                "decision_date": "2026-05-22",
                "status": "Active",
            }
        ],
        "references": [
            {
                "source_type": "decision",
                "source_id": "DEC-300",
                "target_type": "session",
                "target_id": "SES-102",
                "relationship": "decided_in",
            }
        ],
    }
    path = _payload_path(tmp_path, "ses_102.json", payload)
    monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
    rc = apply_close_out.main()
    assert rc == 0

    deposits = routed.get("/deposit-events").json()["data"]
    assert len(deposits) == 1
    dep = deposits[0]
    assert dep["deposit_event_outcome"] == "success"
    assert dep["deposit_event_records_summary"]["sessions"] == 1
    assert dep["deposit_event_records_summary"]["decisions"] == 1
    # references are intentionally NOT counted in records_summary: the
    # access layer enforces sum(records_summary) == len(wrote_records),
    # and references can't be in wrote_records (no 'reference' in vocab).
    assert dep["deposit_event_records_summary"]["references"] == 0

    # wrote_record edges exist for session and decision but NOT for the
    # reference row (it's first-class data but its target_type isn't in
    # the governance vocab the deposit_event references block validates
    # against).
    refs = routed.get(
        f"/references?source_id={dep['deposit_event_identifier']}"
        f"&relationship_kind=deposit_event_wrote_record"
    ).json()["data"]
    wrote_targets = sorted((r["target_type"], r["target_id"]) for r in refs)
    assert wrote_targets == [("decision", "DEC-300"), ("session", "SES-102")]


def test_skip_deposit_event_flag_runs_apply_without_log_or_event(
    routed, tmp_path, monkeypatch
):
    payload = {
        "label": "Skip deposit",
        "session": {
            "identifier": "SES-101",
            "title": "x",
            "session_date": "2026-05-22",
            "status": "Complete",
            "topics_covered": "x",
            "summary": "x",
        },
    }
    path = _payload_path(tmp_path, "ses_101.json", payload)
    monkeypatch.setattr(
        "sys.argv",
        ["apply_close_out.py", str(path), "--skip-deposit-event"],
    )
    rc = apply_close_out.main()
    assert rc == 0
    deposits = routed.get("/deposit-events").json()["data"]
    assert deposits == []
    # No log file created.
    log_dir = tmp_path / "PRDs" / "product" / "crmbuilder-v2" / "deposit-event-logs"
    assert not log_dir.exists() or list(log_dir.glob("dep_*.log")) == []
