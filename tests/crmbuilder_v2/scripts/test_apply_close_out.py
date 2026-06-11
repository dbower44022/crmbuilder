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
    # PI-β: the engagement is named per request by the X-Engagement header (the
    # marker fallback is gone); v2_env seeds ENG-001 as the default engagement,
    # so the apply script's scoped writes stamp/resolve against it.
    tc = TestClient(create_app())
    tc.headers.update({"X-Engagement": "ENG-001"})
    return tc


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
    # Pin the Model A branch guard: these tests exercise apply logic against a
    # TestClient, not the guard, and the ADO verification gate (PI-147) runs
    # the suite inside agent worktrees that are never on 'main'.
    monkeypatch.setattr(apply_close_out, "_current_git_branch", lambda: "main")
    return api_client


# A valid 200-800 char executive_summary, reused across fixtures for the
# PI-074/PI-075 (now-required) executive_summary columns on sessions,
# planning_items, and decisions.
_EXEC_SUMMARY = (
    "This planning item reconciles stale test fixtures with the current "
    "governance schema so the suite validates real behavior; it carries no "
    "production code change and exists purely to keep the regression net "
    "aligned with the PI-073 and PI-102 data-model decisions now in effect."
)


def _payload_path(tmp_path: Path, name: str, payload: dict) -> Path:
    """Write a payload JSON at ``<tmp>/PRDs/product/.../close-out-payloads/<name>``."""
    close_out_dir = (
        tmp_path / "PRDs" / "product" / "crmbuilder-v2" / "close-out-payloads"
    )
    close_out_dir.mkdir(parents=True, exist_ok=True)
    path = close_out_dir / name
    path.write_text(json.dumps(payload, indent=2))
    return path


def _create_project(client, name="WS for tests"):
    """Helper: create a workstream and return its identifier."""
    r = client.post("/projects", json={
        "project_name": name,
        "project_purpose": "p",
        "project_description": "d",
    })
    assert r.status_code == 201, r.text
    return r.json()["data"]["project_identifier"]


def _session_block(identifier="SES-200", title="Test session", ws_id="PRJ-001",
                   status=None):
    """Build a PI-073-shape session block with its mandatory inline
    ``session_belongs_to_project`` membership edge."""
    block = {
        "session_identifier": identifier,
        "session_title": title,
        "session_description": "Test session description.",
        "session_medium": "chat",
        "session_executive_summary": _EXEC_SUMMARY,
        "references": [
            {
                "source_type": "session", "source_id": identifier,
                "target_type": "project", "target_id": ws_id,
                "relationship": "session_belongs_to_project",
            },
        ],
    }
    if status is not None:
        block["session_status"] = status
    return block


def test_happy_path_lazy_creates_cop_and_records_deposit_event(
    routed, tmp_path, monkeypatch
):
    ws_id = _create_project(routed)
    payload = {
        "label": "Test payload for SES-099",
        "session": _session_block("SES-099", "Test session", ws_id),
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
    ws_id = _create_project(routed)
    payload = {
        "label": "Test failure",
        "session": _session_block("SES-100", "Test session", ws_id),
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
    ws_id = _create_project(routed)
    payload = {
        "label": "Test payload with references",
        "session": _session_block("SES-102", "Session with refs", ws_id),
        "decisions": [
            {
                "identifier": "DEC-300",
                "title": "Test decision",
                "decision_date": "2026-05-22",
                "status": "Active",
                "executive_summary": _EXEC_SUMMARY,
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
    ws_id = _create_project(routed)
    payload = {
        "label": "Skip deposit",
        "session": _session_block("SES-101", "x", ws_id),
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


def _conversation_block(identifier="CNV-200", ws_id="PRJ-001", session_id="SES-200"):
    """Build a PI-073-shape conversation block.

    Under DEC-314 the conversation is a topical sub-unit nested within a
    session (1:N), so its mandatory parent edge is the outbound
    ``conversation_belongs_to_session`` edge to the owning session. The
    legacy ``conversation_belongs_to_project`` + ``conversation_records_
    session`` pair is retired; ``ws_id`` is retained as an accepted (unused)
    parameter so existing call sites still work.
    """
    return {
        "conversation_identifier": identifier,
        "conversation_title": f"Conv {identifier}",
        "conversation_purpose": "p",
        "conversation_description": "d",
        "conversation_status": "complete",
        "references": [
            {
                "source_type": "conversation", "source_id": identifier,
                "target_type": "session", "target_id": session_id,
                "relationship": "conversation_belongs_to_session",
            },
        ],
    }


class TestPI030NewSections:
    """PI-030 slice B: apply_close_out.py extensions for the five new
    close-out payload sections (conversation, work_tickets, commits,
    resolves_planning_items, addresses_planning_items)."""

    def test_conversation_block_creates_record_with_belongs_to_session_edge(
        self, routed, tmp_path, monkeypatch
    ):
        ws_id = _create_project(routed)
        payload = {
            "label": "Conversation test",
            "session": _session_block("SES-201"),
            "conversation": _conversation_block("CNV-201", ws_id, "SES-201"),
        }
        path = _payload_path(tmp_path, "ses_201.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
        rc = apply_close_out.main()
        assert rc == 0

        # Conversation created
        conv = routed.get("/conversations/CNV-201").json()["data"]
        assert conv["conversation_identifier"] == "CNV-201"
        # conversation_belongs_to_session edge exists (PI-073 replaces the
        # legacy conversation_records_session edge)
        refs = routed.get(
            "/references?source_id=CNV-201&target_id=SES-201"
        ).json()["data"]
        kinds = [r["relationship"] for r in refs]
        assert "conversation_belongs_to_session" in kinds

    def test_commits_section_propagates_session_id(
        self, routed, tmp_path, monkeypatch
    ):
        ws_id = _create_project(routed)
        payload = {
            "label": "Commits test",
            "session": _session_block("SES-202"),
            "conversation": _conversation_block("CNV-202", ws_id, "SES-202"),
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
                # NOTE: no commit_session_id — apply should inject it from
                # the payload's session block (PI-073 renamed the FK from
                # commit_conversation_id to commit_session_id).
            }],
        }
        path = _payload_path(tmp_path, "ses_202.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
        rc = apply_close_out.main()
        assert rc == 0

        commits = routed.get("/commits").json()["data"]
        assert len(commits) == 1
        assert commits[0]["commit_session_id"] == "SES-202"

    def test_commits_without_session_block_raises_clear_error(
        self, routed, tmp_path, monkeypatch
    ):
        # PI-073: commits derive their FK (commit_session_id) from the
        # payload's session block. With no session block, the commit shape
        # function raises a clear ValueError at the "commits" step.
        payload = {
            "label": "Commits no session",
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
        assert "session block" in err["message"]
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
                "status": "Draft",
                "executive_summary": _EXEC_SUMMARY,
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
        ws_id = _create_project(routed)
        payload = {
            "label": "Resolves test",
            "session": _session_block("SES-205"),
            "conversation": _conversation_block("CNV-205", ws_id, "SES-205"),
            "planning_items": [{
                "identifier": "PI-205",
                "title": "Test PI",
                "item_type": "pending_work",
                "status": "Draft",
                "executive_summary": _EXEC_SUMMARY,
            }],
            "resolves_planning_items": [{"planning_item_identifier": "PI-205"}],
        }
        path = _payload_path(tmp_path, "ses_205.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
        rc = apply_close_out.main()
        assert rc == 0

        # Reference row created
        refs = routed.get(
            "/references?source_id=CNV-205&target_id=PI-205"
        ).json()["data"]
        kinds = [r["relationship"] for r in refs]
        assert "resolves" in kinds
        # Slice A flip behavior fires server-side
        pi = routed.get("/planning-items/PI-205").json()["data"]
        assert pi["status"] == "Resolved"

    def test_addresses_planning_items_translates_to_references_post(
        self, routed, tmp_path, monkeypatch
    ):
        ws_id = _create_project(routed)
        payload = {
            "label": "Addresses test",
            "session": _session_block("SES-206"),
            "conversation": _conversation_block("CNV-206", ws_id, "SES-206"),
            "planning_items": [{
                "identifier": "PI-206",
                "title": "Test PI",
                "item_type": "pending_work",
                "status": "Draft",
                "executive_summary": _EXEC_SUMMARY,
            }],
            "addresses_planning_items": [{"planning_item_identifier": "PI-206"}],
        }
        path = _payload_path(tmp_path, "ses_206.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
        rc = apply_close_out.main()
        assert rc == 0

        refs = routed.get(
            "/references?source_id=CNV-206&target_id=PI-206"
        ).json()["data"]
        kinds = [r["relationship"] for r in refs]
        assert "addresses" in kinds
        # No status flip on addresses
        pi = routed.get("/planning-items/PI-206").json()["data"]
        assert pi["status"] == "Draft"

    def test_apply_ordering_section_headers_in_methodology_order(
        self, routed, tmp_path, monkeypatch, capsys
    ):
        """Full payload with all sections applies in PI-099 apply order:
        conversation → session → work_tickets → planning_items → ... → decisions."""
        ws_id = _create_project(routed)
        payload = {
            "label": "Ordering test",
            "session": _session_block("SES-207"),
            "conversation": _conversation_block("CNV-207", ws_id, "SES-207"),
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
                "status": "Draft",
                "executive_summary": _EXEC_SUMMARY,
            }],
            "decisions": [{
                "identifier": "DEC-207",
                "title": "Test decision",
                "decision_date": "2026-05-22",
                "status": "Active",
                "executive_summary": _EXEC_SUMMARY,
            }],
        }
        path = _payload_path(tmp_path, "ses_207.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])
        rc = apply_close_out.main()
        assert rc == 0

        captured = capsys.readouterr()
        out = captured.out
        # PI-099 order: conversation → session → work_tickets →
        # planning_items → ... → decisions → ...
        idx_conv = out.find("=== conversation ")
        idx_session = out.find("=== session ")
        idx_wt = out.find("=== work_tickets ")
        idx_pi = out.find("=== planning_items ")
        idx_dec = out.find("=== decisions ")
        assert idx_conv != -1
        assert idx_conv < idx_session < idx_wt < idx_pi < idx_dec

    def test_409_skip_idempotent_on_re_run_all_sections(
        self, routed, tmp_path, monkeypatch
    ):
        ws_id = _create_project(routed)
        payload = {
            "label": "Idempotent test",
            "session": _session_block("SES-208"),
            "conversation": _conversation_block("CNV-208", ws_id, "SES-208"),
            "planning_items": [{
                "identifier": "PI-208",
                "title": "Test PI 208",
                "item_type": "pending_work",
                "status": "Draft",
                "executive_summary": _EXEC_SUMMARY,
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
        _create_project(routed)
        payload = {
            "label": "v0.7 backward compat",
            "session": _session_block("SES-209"),
            "decisions": [{
                "identifier": "DEC-209",
                "title": "Test decision",
                "decision_date": "2026-05-22",
                "status": "Active",
                "executive_summary": _EXEC_SUMMARY,
            }],
            "planning_items": [{
                "identifier": "PI-209",
                "title": "Test PI",
                "item_type": "pending_work",
                "status": "Draft",
                "executive_summary": _EXEC_SUMMARY,
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
        ws_id = _create_project(routed)
        payload = {
            "label": "Audit chain test",
            "session": _session_block("SES-210"),
            "conversation": _conversation_block("CNV-210", ws_id, "SES-210"),
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
        ws_id = _create_project(routed)
        bad_conv = _conversation_block("CNV-211", ws_id, "SES-211")
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
        r = routed.get("/conversations/CNV-211")
        assert r.status_code == 404
        # No refs row landed for the conversation
        refs = routed.get("/references?source_id=CNV-211").json()["data"]
        assert refs == []

    def test_resolves_for_already_resolved_pi_is_idempotent(
        self, routed, tmp_path, monkeypatch
    ):
        """Re-applying a payload whose resolves edge already exists
        returns 409 SKIP; the PI status remains Resolved."""
        ws_id = _create_project(routed)
        payload = {
            "label": "Resolves idempotent",
            "session": _session_block("SES-212"),
            "conversation": _conversation_block("CNV-212", ws_id, "SES-212"),
            "planning_items": [{
                "identifier": "PI-212",
                "title": "Test PI",
                "item_type": "pending_work",
                "status": "Draft",
                "executive_summary": _EXEC_SUMMARY,
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


# ---------------------------------------------------------------------------
# PI-099: section ordering — conversation before session
# ---------------------------------------------------------------------------


class TestPI099SectionOrdering:
    """PI-099: every close-out's first apply was failing because the
    apply script POSTed the session before the conversation, but the
    post-PI-073 ``complete_session_requires_conversation`` validation
    rule needs the inbound ``conversation_belongs_to_session`` edge to
    exist at session-create time. The fix swaps the section order so
    the conversation (and its inline membership edge) lands first.
    """

    def test_section_order_has_conversation_before_session(self):
        """Regression guard: the swap can't quietly drift back."""
        sections = apply_close_out._SECTIONS
        assert sections[0].name == "conversation"
        assert sections[1].name == "session"

    def test_single_pass_apply_succeeds_for_complete_session_with_conversation(
        self, routed, tmp_path, monkeypatch
    ):
        """Authoritative proof: a minimal close-out with a session
        whose status is ``complete`` and a conversation supplying the
        mandatory inbound ``conversation_belongs_to_session`` edge
        applies cleanly in a single pass — no retry needed.

        Pre-PI-099, this payload's first apply failed on the session
        POST with ``complete_session_requires_conversation`` because
        the conversation (and therefore its inbound edge) hadn't been
        created yet. Post-PI-099, the conversation creates first, its
        inline membership edge to the not-yet-existent session lands,
        and then the session create finds the edge and validates.
        """
        # Create the workstream the session will belong to.
        ws_id = _create_project(routed)

        payload = {
            "label": "PI-099 single-pass apply test",
            "session": {
                "session_identifier": "SES-300",
                "session_title": "PI-099 single-pass test session",
                "session_description": "Verifies that a complete session "
                "with an inbound conversation_belongs_to_session edge "
                "applies in one pass.",
                "session_medium": "chat",
                "session_executive_summary": _EXEC_SUMMARY,
                "session_status": "complete",
                "references": [
                    {
                        "source_type": "session",
                        "source_id": "SES-300",
                        "target_type": "project",
                        "target_id": ws_id,
                        "relationship": "session_belongs_to_project",
                    }
                ],
            },
            "conversation": {
                "conversation_identifier": "CNV-300",
                "conversation_title": "PI-099 single-pass test conversation",
                "conversation_purpose": "Provide the inbound edge the "
                "session create-validation requires.",
                "conversation_description": "Empty body — exists only to "
                "supply the conversation_belongs_to_session edge.",
                "conversation_status": "complete",
                "references": [
                    {
                        "source_type": "conversation",
                        "source_id": "CNV-300",
                        "target_type": "session",
                        "target_id": "SES-300",
                        "relationship": "conversation_belongs_to_session",
                    }
                ],
            },
        }
        path = _payload_path(tmp_path, "ses_300.json", payload)
        monkeypatch.setattr("sys.argv", ["apply_close_out.py", str(path)])

        rc = apply_close_out.main()
        assert rc == 0, "single-pass apply should succeed without retry"

        # Session landed in 'complete' status.
        sess = routed.get("/sessions/SES-300").json()["data"]
        assert sess["session_identifier"] == "SES-300"
        assert sess["session_status"] == "complete"

        # Conversation landed.
        conv = routed.get("/conversations/CNV-300").json()["data"]
        assert conv["conversation_identifier"] == "CNV-300"

        # The membership edge exists.
        refs = routed.get(
            "/references?source_id=CNV-300&target_id=SES-300"
        ).json()["data"]
        kinds = [r["relationship"] for r in refs]
        assert "conversation_belongs_to_session" in kinds

        # Deposit event recorded the apply as a success in one pass.
        deposits = routed.get("/deposit-events").json()["data"]
        assert len(deposits) == 1
        assert deposits[0]["deposit_event_outcome"] == "success"
