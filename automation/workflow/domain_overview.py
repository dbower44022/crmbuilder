"""Domain Overview output handling for CRM Builder Automation.

Implements L2 PRD Section 9.10: when a domain_overview session is imported,
the engine writes the generated overview text to the Domain record's
domain_overview_text column.
"""

import sqlite3

from automation.db.connection import transaction


def save_domain_overview_text(
    conn: sqlite3.Connection,
    domain_id: int,
    text: str,
) -> None:
    """Write the Domain Overview text to the Domain record.

    :param conn: An open sqlite3.Connection.
    :param domain_id: The Domain.id to update.
    :param text: The generated overview text to store.
    :raises ValueError: If the domain is not found.
    """
    row = conn.execute(
        "SELECT id FROM Domain WHERE id = ?", (domain_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Domain {domain_id} not found")

    with transaction(conn):
        conn.execute(
            "UPDATE Domain SET domain_overview_text = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (text, domain_id),
        )
