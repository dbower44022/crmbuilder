#!/usr/bin/env python3
"""
Diagnostic: planning_items status distribution and resolution mechanism
in the crmbuilder V2 SQLite database.

Usage:
    python3 diagnose_planning_items.py /path/to/crmbuilder.db

Prints, in order:
    1. planning_items table schema (column list)
    2. references table schema (column list)
    3. status distribution across all planning_items
    4. full detail of every non-open planning item
    5. relationship_kind distribution for references targeting planning_items
    6. raw reference rows pointing at planning items (up to 30)
    7. all relationship_kinds in the references table (top 20, for context)

Defensive about schema — if column names or target_type values differ
from assumptions, the output will still show what is actually in the DB.
"""

import sqlite3
import sys


def show_schema(cur: sqlite3.Cursor, table: str) -> None:
    print(f"--- {table} schema ---")
    cur.execute(f"PRAGMA table_info({table})")
    cols = cur.fetchall()
    if not cols:
        print(f"  (table {table!r} not found)\n")
        return
    for c in cols:
        print(f"  {c['name']:30s} {c['type']}")
    print()


def main(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print(f"=== Database: {db_path} ===\n")

    # 1 & 2. Schemas
    show_schema(cur, "planning_items")
    show_schema(cur, "references")

    # 3. Status distribution
    print("--- planning_items status distribution ---")
    cur.execute(
        """
        SELECT status, COUNT(*) AS n
        FROM planning_items
        GROUP BY status
        ORDER BY n DESC
        """
    )
    rows = cur.fetchall()
    total = sum(r["n"] for r in rows)
    for r in rows:
        print(f"  {str(r['status']):20s} {r['n']:4d}")
    print(f"  {'TOTAL':20s} {total:4d}\n")

    # 4. All non-open planning items, full detail
    print("--- non-open planning items (full detail) ---")
    cur.execute(
        """
        SELECT *
        FROM planning_items
        WHERE status != 'open'
        ORDER BY status
        """
    )
    rows = cur.fetchall()
    if not rows:
        print("  (none)\n")
    else:
        for r in rows:
            keys = r.keys()
            ident = r["identifier"] if "identifier" in keys else "(no identifier col)"
            title = r["title"] if "title" in keys else ""
            status = r["status"] if "status" in keys else ""
            print(f"  {ident}: {title}")
            print(f"    status: {status}")
            for k in keys:
                if k in ("identifier", "title", "status"):
                    continue
                val = r[k]
                if val is None or val == "":
                    continue
                sval = str(val)
                if len(sval) > 100:
                    sval = sval[:97] + "..."
                print(f"    {k}: {sval}")
            print()

    # 5. relationship_kind distribution for references targeting planning_items
    print("--- relationship_kind for references targeting planning_items ---")
    cur.execute(
        """
        SELECT relationship_kind, COUNT(*) AS n
        FROM "references"
        WHERE target_type = 'planning_item'
        GROUP BY relationship_kind
        ORDER BY n DESC
        """
    )
    rows = cur.fetchall()
    if not rows:
        print("  (none with target_type='planning_item' — checking alternates)")
        cur.execute(
            """
            SELECT target_type, COUNT(*) AS n
            FROM "references"
            WHERE target_type LIKE '%planning%'
            GROUP BY target_type
            """
        )
        for r in cur.fetchall():
            print(f"    found target_type={r['target_type']!r} with {r['n']} rows")
        print()
    else:
        for r in rows:
            print(f"  {str(r['relationship_kind']):30s} {r['n']:4d}")
        print()

    # 6. Raw reference rows targeting planning items
    print("--- references targeting planning items (up to 30) ---")
    cur.execute(
        """
        SELECT source_type, source_id, target_type, target_id, relationship_kind
        FROM "references"
        WHERE target_type LIKE '%planning%'
        ORDER BY relationship_kind, source_type
        LIMIT 30
        """
    )
    rows = cur.fetchall()
    if not rows:
        print("  (none)\n")
    else:
        for r in rows:
            print(
                f"  {r['source_type']:15s} {str(r['source_id']):20s} "
                f"-> {r['target_type']:15s} {str(r['target_id']):20s} "
                f"[{r['relationship_kind']}]"
            )
        print()

    # 7. All relationship_kinds in use
    print("--- all relationship_kinds in references table (top 20) ---")
    cur.execute(
        """
        SELECT relationship_kind, COUNT(*) AS n
        FROM "references"
        GROUP BY relationship_kind
        ORDER BY n DESC
        LIMIT 20
        """
    )
    for r in cur.fetchall():
        print(f"  {str(r['relationship_kind']):30s} {r['n']:4d}")
    print()

    conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 diagnose_planning_items.py /path/to/crmbuilder.db")
        sys.exit(1)
    main(sys.argv[1])
