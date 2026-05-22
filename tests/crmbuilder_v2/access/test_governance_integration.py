"""Cross-entity integration tests for the v0.7 governance entities.

Exercises a full workstream → conversation → work_ticket → close_out_payload
→ deposit_event chain end-to-end, and the two transition rules the
implementation plan §2.1 calls out explicitly.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import close_out_payloads as cop
from crmbuilder_v2.access.repositories import conversations as cr
from crmbuilder_v2.access.repositories import deposit_events as dep
from crmbuilder_v2.access.repositories import work_tickets as wt
from crmbuilder_v2.access.repositories import workstreams as ws


def test_full_governance_chain(v2_env):
    with session_scope() as s:
        wid = ws.create_workstream(
            s, name="Gov", purpose="p", description="d", status="in_flight",
            timestamps={"workstream_started_at": "2026-05-20T00:00:00"},
        )["workstream_identifier"]

        # Conversation belonging to the workstream.
        conv = cr.create_conversation(
            s, title="Build planning", purpose="p", description="d",
            identifier="CONV-001",
            references=[{
                "source_type": "conversation", "source_id": "CONV-001",
                "target_type": "workstream", "target_id": wid,
                "relationship": "conversation_belongs_to_workstream",
            }],
        )["conversation_identifier"]

        # Work ticket consumed by the conversation.
        wt.create_work_ticket(
            s, title="Kickoff", description="d", kind="kickoff_prompt",
            file_path="PRDs/k.md", identifier="WT-001", status="ready",
        )
        wt.patch_work_ticket(
            s, "WT-001", status="consumed",
            references=[{
                "source_type": "conversation", "source_id": conv,
                "target_type": "work_ticket", "target_id": "WT-001",
                "relationship": "conversation_opens_against_work_ticket",
            }],
        )
        assert wt.get_work_ticket(s, "WT-001")["work_ticket_status"] == "consumed"

        # Close-out payload produced by the conversation, queued ready.
        cop.create_close_out_payload(
            s, title="Payload", description="d",
            file_path="close-out-payloads/ses_055.json",
            identifier="COP-001", status="ready",
            references=[{
                "source_type": "close_out_payload", "source_id": "COP-001",
                "target_type": "conversation", "target_id": conv,
                "relationship": "close_out_payload_produced_by_conversation",
            }],
        )

        # Deposit event applies the payload (success) — drives ready->applied.
        dep.create_deposit_event(
            s, title="Apply COP-001", description="ok", outcome="success",
            records_summary={"sessions": 1, "decisions": 0},
            apply_context={"runner": "claude_code"},
            log_file_path="deposit-event-logs/dep_001.log",
            references=[
                {"target_type": "close_out_payload", "target_id": "COP-001",
                 "relationship": "deposit_event_applies_close_out_payload"},
                {"target_type": "session", "target_id": "SES-055",
                 "relationship": "deposit_event_wrote_record"},
            ],
        )
        assert cop.get_close_out_payload(s, "COP-001")[
            "close_out_payload_status"
        ] == "applied"

        # Workstream completes.
        cr.patch_conversation(
            s, conv, status="kickoff_drafted",
        )
        for st in ("ready", "in_flight"):
            cr.patch_conversation(s, conv, status=st)
        cr.patch_conversation(
            s, conv, status="complete",
            references=[{
                "source_type": "conversation", "source_id": conv,
                "target_type": "session", "target_id": "SES-055",
                "relationship": "conversation_records_session",
            }],
        )
        ws.patch_workstream(s, wid, status="complete")
        assert ws.get_workstream(s, wid)["workstream_status"] == "complete"


def test_first_success_transition_then_failure_reconfirm(v2_env):
    """ready->applied fires on first success; later failure does not retract."""
    with session_scope() as s:
        wid = ws.create_workstream(s, name="W", purpose="p", description="d")[
            "workstream_identifier"
        ]
        conv = cr.create_conversation(
            s, title="C", purpose="p", description="d", identifier="CONV-001",
            references=[{
                "source_type": "conversation", "source_id": "CONV-001",
                "target_type": "workstream", "target_id": wid,
                "relationship": "conversation_belongs_to_workstream",
            }],
        )["conversation_identifier"]
        cop.create_close_out_payload(
            s, title="P", description="d", file_path="close-out-payloads/x.json",
            identifier="COP-001", status="ready",
            references=[{
                "source_type": "close_out_payload", "source_id": "COP-001",
                "target_type": "conversation", "target_id": conv,
                "relationship": "close_out_payload_produced_by_conversation",
            }],
        )
        parent = {"target_type": "close_out_payload", "target_id": "COP-001",
                  "relationship": "deposit_event_applies_close_out_payload"}
        dep.create_deposit_event(
            s, title="first", description="ok", outcome="success",
            records_summary={"sessions": 0}, apply_context={},
            log_file_path="deposit-event-logs/dep_001.log", references=[parent],
        )
        assert cop.get_close_out_payload(s, "COP-001")[
            "close_out_payload_status"
        ] == "applied"
        applied_at = cop.get_close_out_payload(s, "COP-001")[
            "close_out_payload_applied_at"
        ]
        # A later failure re-apply records the fact but does not retract.
        dep.create_deposit_event(
            s, title="reapply-fail", description="boom", outcome="failure",
            records_summary={"sessions": 0}, apply_context={},
            error_info={"kind": "x", "message": "y", "step": "z"},
            log_file_path="deposit-event-logs/dep_002.log", references=[parent],
        )
        after = cop.get_close_out_payload(s, "COP-001")
        assert after["close_out_payload_status"] == "applied"
        assert after["close_out_payload_applied_at"] == applied_at
        assert len(dep.list_deposit_events(s)) == 2
