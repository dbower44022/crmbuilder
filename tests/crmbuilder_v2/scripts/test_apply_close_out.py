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


# ---------------------------------------------------------------------------
# PI-030 slice B: extensions for five new close-out payload sections
# ---------------------------------------------------------------------------


def _create_workstream(client, name="WS for tests"):
    """Helper: create a workstream and return its identifier."""
    r = client.post("/workstreams", json={
        "workstream_name": name,
        "workstream_purpose": "p",
        "workstream_description": "d",
    })
    assert r.status_code == 201, r.text
    return r.json()["data"]["workstream_identifier"]


def _session_block(identifier="SES-200", title="Test session"):
    return {
        "identifier": identifier,
        "title": title,
        "session_date": "2026-05-22",
        "status": "Complete",
        "topics_covered": "x",
        "summary": "x",
    }


def _conversation_block(identifier="CONV-200", ws_id="WS-001", session_id="SES-200"):
    return {
        "conversation_identifier": identifier,
        "conversation_title": f"Conv {identifier}",
        "conversation_purpose": "p",
        "conversation_description": "d",
        "conversation_status": "complete",
        "references": [
            {
                "source_type": "conversation", "source_id": identifier,
                "target_type": "workstream", "target_id": ws_id,
                "relationship": "conversation_belongs_to_workstream",
            },
            {
                "source_type": "conversation", "source_id": identifier,
                "target_type": "session", "target_id": session_id,
                "relationship": "conversation_records_session",
            },
        ],
    }


class TestPI030NewSections:
    """PI-030 slice B: apply_close_out.py extensions for the five new
    close-out payload sections (conversation, work_tickets, commits,
    resolves_planning_items, addresses_planning_items)."""

    def test_conversation_block_creates_record_with_records_session_edge(
        self, routed, tmp_path, monkeypatch
    ):
        ws_id = _create_workstream(routed)
        payload = {
            "label": "Conversation test",
            "session": _session_block("SES-201"),
            "conversation": _conversation_block("CONV-201", ws_id, "SES-201"),
        }
        path = _payload_path(tmp_path, "ses_201.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
        rc = apply_close_out.main()
        assert rc == 0

        # Conversation created
        conv = routed.get("/conversations/CONV-201").json()["data"]
        assert conv["conversation_identifier"] == "CONV-201"
        # conversation_records_session edge exists
        refs = routed.get(
            "/references?source_id=CONV-201&target_id=SES-201"
        ).json()["data"]
        kinds = [r["relationship"] for r in refs]
        assert "conversation_records_session" in kinds

    def test_commits_section_propagates_conversation_id(
        self, routed, tmp_path, monkeypatch
    ):
        ws_id = _create_workstream(routed)
        payload = {
            "label": "Commits test",
            "session": _session_block("SES-202"),
            "conversation": _conversation_block("CONV-202", ws_id, "SES-202"),
            "commits": [{
                "commit_sha": "a" * 40,
                "commit_message_first_line": "first line",
                "commit_message_full": "first line\n\nbody",
                "commit_author_name": "Doug Bower",
                "commit_author_email": "doug@dougbower.com",
                "commit_committed_at": "2026-05-23T20:45:12-04:00",
                "commit_repository": "crmbuilder",
                "commit_branch": "main",
                "commit_parent_shas": ["1" * 40],
                "commit_files_changed_count": 3,
                # NOTE: no commit_conversation_id — apply should inject it
            }],
        }
        path = _payload_path(tmp_path, "ses_202.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
        rc = apply_close_out.main()
        assert rc == 0

        commits = routed.get("/commits").json()["data"]
        assert len(commits) == 1
        assert commits[0]["commit_conversation_id"] == "CONV-202"

    def test_commits_without_conversation_block_raises_clear_error(
        self, routed, tmp_path, monkeypatch
    ):
        payload = {
            "label": "Commits no conversation",
            "session": _session_block("SES-203"),
            "commits": [{
                "commit_sha": "b" * 40,
                "commit_message_first_line": "x",
                "commit_message_full": "x",
                "commit_author_name": "x",
                "commit_author_email": "x@x",
                "commit_committed_at": "2026-05-23T20:45:12-04:00",
                "commit_repository": "crmbuilder",
                "commit_parent_shas": [],
                "commit_files_changed_count": 1,
            }],
        }
        path = _payload_path(tmp_path, "ses_203.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
        rc = apply_close_out.main()
        # Apply fails because shape function raises ValueError
        assert rc == 1
        deposits = routed.get("/deposit-events").json()["data"]
        assert len(deposits) == 1
        assert deposits[0]["deposit_event_outcome"] == "failure"
        err = deposits[0]["deposit_event_error_info"]
        assert err["kind"] == "shape_error"
        assert "conversation block" in err["message"]
        assert err["step"] == "commits"

    def test_work_ticket_addresses_pi_becomes_embedded_reference(
        self, routed, tmp_path, monkeypatch
    ):
        payload = {
            "label": "WT addresses PI",
            "session": _session_block("SES-204"),
            "planning_items": [{
                "identifier": "PI-204",
                "title": "Test PI",
                "item_type": "pending_work",
                "status": "Open",
            }],
            "work_tickets": [{
                "work_ticket_identifier": "WT-001",
                "work_ticket_title": "Test WT",
                "work_ticket_description": "d",
                "work_ticket_file_path": "PRDs/test/foo.md",
                "work_ticket_kind": "kickoff_prompt",
                "work_ticket_status": "drafted",
                "addresses_planning_item": "PI-204",
            }],
        }
        path = _payload_path(tmp_path, "ses_204.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
        rc = apply_close_out.main()
        assert rc == 0

        # Work ticket created
        wt = routed.get("/work-tickets/WT-001").json()["data"]
        assert wt["work_ticket_identifier"] == "WT-001"
        # addresses edge exists
        refs = routed.get(
            "/references?source_id=WT-001&target_id=PI-204"
        ).json()["data"]
        kinds = [r["relationship"] for r in refs]
        assert "addresses" in kinds

    def test_resolves_planning_items_translates_to_references_post(
        self, routed, tmp_path, monkeypatch
    ):
        ws_id = _create_workstream(routed)
        payload = {
            "label": "Resolves test",
            "session": _session_block("SES-205"),
            "conversation": _conversation_block("CONV-205", ws_id, "SES-205"),
            "planning_items": [{
                "identifier": "PI-205",
                "title": "Test PI",
                "item_type": "pending_work",
                "status": "Open",
            }],
            "resolves_planning_items": [{"planning_item_identifier": "PI-205"}],
        }
        path = _payload_path(tmp_path, "ses_205.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
        rc = apply_close_out.main()
        assert rc == 0

        # Reference row created
        refs = routed.get(
            "/references?source_id=CONV-205&target_id=PI-205"
        ).json()["data"]
        kinds = [r["relationship"] for r in refs]
        assert "resolves" in kinds
        # Slice A flip behavior fires server-side
        pi = routed.get("/planning-items/PI-205").json()["data"]
        assert pi["status"] == "Resolved"

    def test_addresses_planning_items_translates_to_references_post(
        self, routed, tmp_path, monkeypatch
    ):
        ws_id = _create_workstream(routed)
        payload = {
            "label": "Addresses test",
            "session": _session_block("SES-206"),
            "conversation": _conversation_block("CONV-206", ws_id, "SES-206"),
            "planning_items": [{
                "identifier": "PI-206",
                "title": "Test PI",
                "item_type": "pending_work",
                "status": "Open",
            }],
            "addresses_planning_items": [{"planning_item_identifier": "PI-206"}],
        }
        path = _payload_path(tmp_path, "ses_206.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
        rc = apply_close_out.main()
        assert rc == 0

        refs = routed.get(
            "/references?source_id=CONV-206&target_id=PI-206"
        ).json()["data"]
        kinds = [r["relationship"] for r in refs]
        assert "addresses" in kinds
        # No status flip on addresses
        pi = routed.get("/planning-items/PI-206").json()["data"]
        assert pi["status"] == "Open"

    def test_apply_ordering_section_headers_in_methodology_order(
        self, routed, tmp_path, monkeypatch, capsys
    ):
        """Full payload with all sections applies in methodology §4 order."""
        ws_id = _create_workstream(routed)
        payload = {
            "label": "Ordering test",
            "session": _session_block("SES-207"),
            "conversation": _conversation_block("CONV-207", ws_id, "SES-207"),
            "work_tickets": [{
                "work_ticket_identifier": "WT-207",
                "work_ticket_title": "Test WT 207",
                "work_ticket_description": "d",
                "work_ticket_file_path": "PRDs/test/foo207.md",
                "work_ticket_kind": "kickoff_prompt",
                "work_ticket_status": "drafted",
            }],
            "planning_items": [{
                "identifier": "PI-207",
                "title": "Test PI 207",
                "item_type": "pending_work",
                "status": "Open",
            }],
            "decisions": [{
                "identifier": "DEC-207",
                "title": "Test decision",
                "decision_date": "2026-05-22",
                "status": "Active",
            }],
        }
        path = _payload_path(tmp_path, "ses_207.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
        rc = apply_close_out.main()
        assert rc == 0

        captured = capsys.readouterr()
        out = captured.out
        # Methodology §4 order: session → conversation → work_tickets →
        # planning_items → ... → decisions → ...
        idx_session = out.find("=== session ")
        idx_conv = out.find("=== conversation ")
        idx_wt = out.find("=== work_tickets ")
        idx_pi = out.find("=== planning_items ")
        idx_dec = out.find("=== decisions ")
        assert idx_session != -1
        assert idx_session < idx_conv < idx_wt < idx_pi < idx_dec

    def test_409_skip_idempotent_on_re_run_all_sections(
        self, routed, tmp_path, monkeypatch
    ):
        ws_id = _create_workstream(routed)
        payload = {
            "label": "Idempotent test",
            "session": _session_block("SES-208"),
            "conversation": _conversation_block("CONV-208", ws_id, "SES-208"),
            "planning_items": [{
                "identifier": "PI-208",
                "title": "Test PI 208",
                "item_type": "pending_work",
                "status": "Open",
            }],
            "resolves_planning_items": [{"planning_item_identifier": "PI-208"}],
        }
        path = _payload_path(tmp_path, "ses_208.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])

        rc1 = apply_close_out.main()
        assert rc1 == 0
        rc2 = apply_close_out.main()
        assert rc2 == 0  # 409 SKIPs are not failures

    def test_v0_7_payload_still_applies_without_new_sections(
        self, routed, tmp_path, monkeypatch
    ):
        """Backward compatibility: v0.7 payload (no conversation, no
        work_tickets/commits/resolves/addresses) applies cleanly."""
        payload = {
            "label": "v0.7 backward compat",
            "session": _session_block("SES-209"),
            "decisions": [{
                "identifier": "DEC-209",
                "title": "Test decision",
                "decision_date": "2026-05-22",
                "status": "Active",
            }],
            "planning_items": [{
                "identifier": "PI-209",
                "title": "Test PI",
                "item_type": "pending_work",
                "status": "Open",
            }],
            "references": [{
                "source_type": "decision",
                "source_id": "DEC-209",
                "target_type": "session",
                "target_id": "SES-209",
                "relationship": "decided_in",
            }],
        }
        path = _payload_path(tmp_path, "ses_209.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
        rc = apply_close_out.main()
        assert rc == 0
        deposits = routed.get("/deposit-events").json()["data"]
        assert len(deposits) == 1
        assert deposits[0]["deposit_event_outcome"] == "success"

    def test_resolves_status_flip_audit_chain(
        self, routed, tmp_path, monkeypatch
    ):
        """The deposit_event at apply close includes wrote_record edges to
        conversation, work_ticket, and commit records (new v0.8 types)."""
        ws_id = _create_workstream(routed)
        payload = {
            "label": "Audit chain test",
            "session": _session_block("SES-210"),
            "conversation": _conversation_block("CONV-210", ws_id, "SES-210"),
            "work_tickets": [{
                "work_ticket_identifier": "WT-210",
                "work_ticket_title": "Test WT 210",
                "work_ticket_description": "d",
                "work_ticket_file_path": "PRDs/test/foo210.md",
                "work_ticket_kind": "kickoff_prompt",
                "work_ticket_status": "drafted",
            }],
            "commits": [{
                "commit_sha": "c" * 40,
                "commit_message_first_line": "x",
                "commit_message_full": "x",
                "commit_author_name": "x",
                "commit_author_email": "x@x",
                "commit_committed_at": "2026-05-23T20:45:12-04:00",
                "commit_repository": "crmbuilder",
                "commit_parent_shas": [],
                "commit_files_changed_count": 1,
            }],
        }
        path = _payload_path(tmp_path, "ses_210.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
        rc = apply_close_out.main()
        assert rc == 0

        deposits = routed.get("/deposit-events").json()["data"]
        dep = deposits[0]
        summary = dep["deposit_event_records_summary"]
        # New entity types counted in summary
        assert summary.get("conversations", 0) == 1
        assert summary.get("work_tickets", 0) == 1
        assert summary.get("commits", 0) == 1
        # Audit invariant: wrote_record edges cover all new types
        refs = routed.get(
            f"/references?source_id={dep['deposit_event_identifier']}"
            f"&relationship_kind=deposit_event_wrote_record"
        ).json()["data"]
        wrote_types = sorted({r["target_type"] for r in refs})
        assert "conversation" in wrote_types
        assert "work_ticket" in wrote_types
        assert "commit" in wrote_types

    def test_conversation_records_session_edge_atomic_with_conversation(
        self, routed, tmp_path, monkeypatch
    ):
        """If the conversation POST fails (missing required nonempty field),
        no orphan refs row is left."""
        ws_id = _create_workstream(routed)
        bad_conv = _conversation_block("CONV-211", ws_id, "SES-211")
        bad_conv["conversation_purpose"] = ""  # required nonempty → 422
        payload = {
            "label": "Atomic conv test",
            "session": _session_block("SES-211"),
            "conversation": bad_conv,
        }
        path = _payload_path(tmp_path, "ses_211.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
        rc = apply_close_out.main()
        assert rc == 1

        # Conversation didn't land
        r = routed.get("/conversations/CONV-211")
        assert r.status_code == 404
        # No refs row landed for the conversation
        refs = routed.get("/references?source_id=CONV-211").json()["data"]
        assert refs == []

    def test_resolves_for_already_resolved_pi_is_idempotent(
        self, routed, tmp_path, monkeypatch
    ):
        """Re-applying a payload whose resolves edge already exists
        returns 409 SKIP; the PI status remains Resolved."""
        ws_id = _create_workstream(routed)
        payload = {
            "label": "Resolves idempotent",
            "session": _session_block("SES-212"),
            "conversation": _conversation_block("CONV-212", ws_id, "SES-212"),
            "planning_items": [{
                "identifier": "PI-212",
                "title": "Test PI",
                "item_type": "pending_work",
                "status": "Open",
            }],
            "resolves_planning_items": [{"planning_item_identifier": "PI-212"}],
        }
        path = _payload_path(tmp_path, "ses_212.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])

        rc1 = apply_close_out.main()
        assert rc1 == 0
        # Confirm flip
        pi = routed.get("/planning-items/PI-212").json()["data"]
        assert pi["status"] == "Resolved"

        # Re-apply — the resolves edge already exists; 409 SKIP path
        rc2 = apply_close_out.main()
        assert rc2 == 0
        # Status still Resolved
        pi = routed.get("/planning-items/PI-212").json()["data"]
        assert pi["status"] == "Resolved"
