"""Mapper for crm_selection payloads.

Target tables: Client (update), Decision (create), OpenIssue (create).
Per L2 PRD Section 11.3.8.
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
    """Map a crm_selection payload to proposed records."""
    records: list[ProposedRecord] = []

    # Recommended platform -> Client.crm_platform update
    platforms = payload.get("recommended_platforms", [])
    if platforms and master_conn is not None:
        # Use the first recommended platform
        platform_name = platforms[0].get("name", "") if platforms else ""
        if platform_name:
            client_row = master_conn.execute(
                "SELECT id FROM Client LIMIT 1"
            ).fetchone()
            if client_row:
                records.append(ProposedRecord(
                    table_name="Client",
                    action="update",
                    target_id=client_row[0],
                    values={"crm_platform": platform_name},
                    source_payload_path="payload.recommended_platforms[0]",
                ))

    # Platform evaluation decisions
    for i, platform in enumerate(platforms):
        # Each platform evaluation conclusion as a Decision
        if platform.get("summary"):
            records.append(ProposedRecord(
                table_name="Decision",
                action="create",
                target_id=None,
                values={
                    "identifier": f"CRM-DEC-{i+1:03d}",
                    "title": f"CRM Platform: {platform.get('name', '')}",
                    "description": platform.get("summary", ""),
                    "status": "locked" if i == 0 else "proposed",
                    "locked_by_session_id": ai_session_id if i == 0 else None,
                    "created_by_session_id": ai_session_id,
                },
                source_payload_path=f"payload.recommended_platforms[{i}]",
                batch_id=f"batch:decision:CRM-DEC-{i+1:03d}",
            ))

    # Platform risks -> OpenIssue
    for i, risk in enumerate(payload.get("platform_risks", [])):
        records.append(ProposedRecord(
            table_name="OpenIssue",
            action="create",
            target_id=None,
            values={
                "identifier": f"CRM-ISS-{i+1:03d}",
                "title": risk.get("risk_description", "")[:100],
                "description": risk.get("risk_description", ""),
                "status": "open",
                "priority": _map_severity(risk.get("severity", "medium")),
                "created_by_session_id": ai_session_id,
            },
            source_payload_path=f"payload.platform_risks[{i}]",
            batch_id=f"batch:openissue:CRM-ISS-{i+1:03d}",
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


def _map_severity(severity: str) -> str:
    """Map risk severity to OpenIssue priority."""
    mapping = {"high": "high", "medium": "medium", "low": "low"}
    return mapping.get(severity.lower(), "medium")
