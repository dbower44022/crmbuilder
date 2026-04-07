"""CLI script to initialize a fresh client database.

Usage:
    uv run python -m automation.db.init_db /path/to/client.db
"""

import argparse
import sys
from pathlib import Path

from automation.db.migrations import run_client_migrations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Initialize a new CRM Builder Automation client database.",
    )
    parser.add_argument(
        "db_path",
        help="Path where the new client database file will be created.",
    )
    args = parser.parse_args(argv)

    db_path = Path(args.db_path)
    if db_path.exists():
        print(f"Error: file already exists: {db_path}", file=sys.stderr)
        return 1

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = run_client_migrations(str(db_path))
    conn.close()

    print(f"Client database created: {db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
