"""CLI entry point for the CBM PRD importer.

Usage:
    python -m automation.cbm_import \\
        --cbm-repo /path/to/ClevelandBusinessMentoring \\
        --client-db /path/to/cbm-client.db \\
        --master-db /path/to/master.db \\
        [--dry-run]
"""

from __future__ import annotations

import argparse
import sys

from automation.cbm_import.importer import CBMImporter


def main() -> None:
    """Run the CBM import from the command line."""
    parser = argparse.ArgumentParser(
        description="Import CBM PRD documents into a client database."
    )
    parser.add_argument(
        "--cbm-repo",
        required=True,
        help="Path to the ClevelandBusinessMentoring repository.",
    )
    parser.add_argument(
        "--client-db",
        required=True,
        help="Path to the CBM client SQLite database.",
    )
    parser.add_argument(
        "--master-db",
        required=True,
        help="Path to the master SQLite database.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate without writing to the database.",
    )

    args = parser.parse_args()

    importer = CBMImporter(
        client_db_path=args.client_db,
        master_db_path=args.master_db,
        cbm_repo_path=args.cbm_repo,
    )

    print(f"{'DRY RUN: ' if args.dry_run else ''}Importing CBM PRDs...")
    print(f"  CBM repo:  {args.cbm_repo}")
    print(f"  Client DB: {args.client_db}")
    print(f"  Master DB: {args.master_db}")
    print()

    report = importer.import_all(dry_run=args.dry_run)
    print(report.summary())

    if report.errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
