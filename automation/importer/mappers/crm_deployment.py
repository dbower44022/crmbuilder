"""Mapper for crm_deployment payloads.

Target tables: Decision (create), OpenIssue (create).
Per L2 PRD Section 11.3.9.
"""

from __future__ import annotations

import sqlite3

from automation.importer.mappers.base import map_decisions, map_open_issues
from automation.importer.proposed import ProposedBatch, ProposedRecord


def map_payload(
    conn: sqlite3.Connection,
    work_item: dict,
    payload: dict,
    session_type: str,
    ai_session_id: int,
    master_conn: sqlite3.Connection | None = None,
    envelope: dict | None = None,
) -> ProposedBatch:
    """Map a crm_deployment payload to proposed records."""
    records: list[ProposedRecord] = []

    # Infrastructure decisions -> Decision records
    for i, dec in enumerate(payload.get("infrastructure_decisions", [])):
        records.append(ProposedRecord(
            table_name="Decision",
            action="create",
            target_id=None,
            values={
                "identifier": dec.get("identifier", f"DEPLOY-DEC-{i+1:03d}"),
                "title": dec.get("decision", "")[:100],
                "description": (
                    f"{dec.get('decision', '')}\n\n"
                    f"Rationale: {dec.get('rationale', '')}"
                ),
                "status": "locked",
                "locked_by_session_id": ai_session_id,
                "created_by_session_id": ai_session_id,
            },
            source_payload_path=f"payload.infrastructure_decisions[{i}]",
            batch_id=f"batch:decision:DEPLOY-DEC-{i+1:03d}",
        ))

    # Open items -> OpenIssue records
    for i, item in enumerate(payload.get("open_items", [])):
        desc = item if isinstance(item, str) else item.get("description", str(item))
        records.append(ProposedRecord(
            table_name="OpenIssue",
            action="create",
            target_id=None,
            values={
                "identifier": f"DEPLOY-ISS-{i+1:03d}",
                "title": desc[:100],
                "description": desc,
                "status": "open",
                "priority": "medium",
                "created_by_session_id": ai_session_id,
            },
            source_payload_path=f"payload.open_items[{i}]",
            batch_id=f"batch:openissue:DEPLOY-ISS-{i+1:03d}",
        ))

    # Envelope-level decisions and open issues
    if envelope:
        records.extend(map_decisions(
            envelope.get("decisions", []), conn, session_type, ai_session_id,
        ))
        records.extend(map_open_issues(
            envelope.get("open_issues", []), conn, session_type, ai_session_id,
        ))

    return ProposedBatch(
        records=records,
        ai_session_id=ai_session_id,
        work_item_id=work_item["id"],
        session_type=session_type,
    )
