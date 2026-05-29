"""Cross-entity integration tests for the governance entities.

Exercises a full workstream → session → conversation → work_ticket →
close_out_payload → deposit_event chain end-to-end, and the two transition
rules the implementation plan §2.1 calls out explicitly.

Updated for the PI-073 / DEC-314 session-conversation redesign: a session
is the medium-agnostic communication container (belongs to a workstream)
and a conversation is a topical sub-unit nested within a session (1:N).
Conversations use the ``CNV-NNN`` identifier prefix and carry a mandatory
outbound ``conversation_belongs_to_session`` membership edge.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import close_out_payloads as cop
from crmbuilder_v2.access.repositories import conversations as cr
from crmbuilder_v2.access.repositories import deposit_events as dep
from crmbuilder_v2.access.repositories import sessions as se
from crmbuilder_v2.access.repositories import work_tickets as wt
from crmbuilder_v2.access.repositories import workstreams as ws

# A valid 200-800 char executive summary reused across the session creates.
_EXEC_SUMMARY = (
    "This planning item reconciles stale test fixtures with the current "
    "governance schema so the suite validates real behavior; it carries no "
    "production code change and exists purely to keep the regression net "
    "aligned with the PI-073 and PI-102 data-model decisions now in effect."
)


def test_full_governance_chain(v2_env):
    with session_scope() as s:
        wid = ws.create_workstream(
            s, name="Gov", purpose="p", description="d", status="in_flight",
            timestamps={"workstream_started_at": "2026-05-20T00:00:00"},
        )["workstream_identifier"]

        # Session belonging to the workstream (the communication container).
        sid = se.create_session(
            s, title="Build planning session", description="d",
            medium="chat", executive_summary=_EXEC_SUMMARY,
            identifier="SES-901", status="in_flight",
            references=[{
                "source_type": "session", "source_id": "SES-901",
                "target_type": "workstream", "target_id": wid,
                "relationship": "session_belongs_to_workstream",
            }],
        )["session_identifier"]

        # Conversation nested within the session (topical sub-unit).
        conv = cr.create_conversation(
            s, title="Build planning", purpose="p", description="d",
            identifier="CNV-001",
            references=[{
                "source_type": "conversation", "source_id": "CNV-001",
                "target_type": "session", "target_id": sid,
                "relationship": "conversation_belongs_to_session",
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
                {"target_type": "session", "target_id": sid,
                 "relationship": "deposit_event_wrote_record"},
            ],
        )
        assert cop.get_close_out_payload(s, "COP-001")[
            "close_out_payload_status"
        ] == "applied"

        # Conversation runs and completes (planned -> in_flight -> complete).
        cr.patch_conversation(s, conv, status="in_flight")
        cr.patch_conversation(s, conv, status="complete")
        assert cr.get_conversation(s, conv)[
            "conversation_status"
        ] == "complete"

        # Workstream completes.
        ws.patch_workstream(s, wid, status="complete")
        assert ws.get_workstream(s, wid)["workstream_status"] == "complete"


def test_first_success_transition_then_failure_reconfirm(v2_env):
    """ready->applied fires on first success; later failure does not retract."""
    with session_scope() as s:
        wid = ws.create_workstream(s, name="W", purpose="p", description="d")[
            "workstream_identifier"
        ]
        sid = se.create_session(
            s, title="Apply session", description="d", medium="chat",
            executive_summary=_EXEC_SUMMARY, identifier="SES-901",
            references=[{
                "source_type": "session", "source_id": "SES-901",
                "target_type": "workstream", "target_id": wid,
                "relationship": "session_belongs_to_workstream",
            }],
        )["session_identifier"]
        conv = cr.create_conversation(
            s, title="C", purpose="p", description="d", identifier="CNV-001",
            references=[{
                "source_type": "conversation", "source_id": "CNV-001",
                "target_type": "session", "target_id": sid,
                "relationship": "conversation_belongs_to_session",
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
