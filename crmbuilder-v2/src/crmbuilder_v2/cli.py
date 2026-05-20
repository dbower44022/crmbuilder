"""Console-script entry points for crmbuilder_v2.

These are wired into ``[project.scripts]`` in ``pyproject.toml``:

* ``crmbuilder-v2-api`` — start the FastAPI REST server
* ``crmbuilder-v2-mcp`` — start the MCP server over stdio
* ``crmbuilder-v2-bootstrap-db`` — apply Alembic migrations to the configured DB
* ``crmbuilder-v2-bootstrap`` — import the four bootstrap markdown files
* ``crmbuilder-v2-ui`` — launch the v2 desktop UI (PySide6)
"""

from __future__ import annotations

import sys


def _fail_loud(message: str) -> None:
    """Print a configuration error to stderr and stdout, then exit 2.

    Stdout is included so a UI subprocess that only captures stdout still
    sees the reason the API refused to start (DEC-108).
    """
    print(message, file=sys.stderr)
    print(message)
    sys.exit(2)


def run_api() -> None:
    import argparse
    import logging

    import uvicorn

    from crmbuilder_v2.api.main import create_app
    from crmbuilder_v2.config import get_settings
    from crmbuilder_v2.migration.dogfood_v0_5 import (
        needs_migration,
        run_dogfood_migration,
    )
    from crmbuilder_v2.runtime.engagement_routing import (
        resolve_active_engagement,
        route_settings_to_engagement,
    )
    from crmbuilder_v2.runtime.exceptions import UnknownEngagementError

    _log = logging.getLogger("crmbuilder_v2.cli")

    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-api",
        description=(
            "Start the crmbuilder_v2 REST API against the active engagement. "
            "The active engagement comes from current_engagement.json "
            "(written by the desktop UI's Engagements panel) unless "
            "--engagement is passed."
        ),
    )
    parser.add_argument(
        "--engagement",
        default=None,
        metavar="CODE",
        help=(
            "Route the API at engagement CODE for this process, overriding "
            "current_engagement.json. Ephemeral: does not persist to the "
            "marker file."
        ),
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help=(
            "Resolve and route to the active engagement, print the resolved "
            "DB and export directory, then exit 0 without starting uvicorn."
        ),
    )
    args = parser.parse_args()

    # v0.5 slice A: detect the migration-needed state and run the
    # one-shot dogfood migration before the API starts serving
    # requests. Idempotent on rerun; fresh-install is a no-op.
    if needs_migration():
        _log.info("v0.5 dogfood migration: triggering")
        result = run_dogfood_migration()
        if not result.success:
            _log.error(
                "v0.5 dogfood migration failed: %s "
                "(backup preserved at v2.db.pre-v0.5-backup); aborting",
                result.error,
            )
            raise SystemExit(1)
        _log.info(
            "v0.5 dogfood migration: completed steps=%s",
            ",".join(result.steps_completed),
        )

    # Determine the active engagement. The --engagement flag wins over the
    # marker file (DEC-111); when neither is available, fail loud (DEC-108).
    marker_code = resolve_active_engagement()
    if args.engagement:
        active_code = args.engagement
        from_flag = True
        if marker_code and marker_code != active_code:
            line = (
                f"--engagement {active_code} overrides "
                f"current_engagement.json ({marker_code})"
            )
            if sys.stderr.isatty():
                line = f"\033[33m{line}\033[0m"
            print(line, file=sys.stderr)
    else:
        active_code = marker_code
        from_flag = False

    if not active_code:
        _fail_loud(
            "No active engagement. Activate one via the desktop UI's "
            "Engagements panel, or pass --engagement <code> when running "
            "the API standalone."
        )

    try:
        route_settings_to_engagement(active_code)
    except UnknownEngagementError as exc:
        if from_flag:
            _fail_loud(str(exc))
        else:
            _fail_loud(
                f"Active engagement '{active_code}' not found in meta DB. "
                "Activate a valid engagement via the desktop UI or pass "
                "--engagement <code>."
            )

    settings = get_settings()

    if args.check_only:
        print(
            f"OK: active engagement {active_code} "
            f"(db_path={settings.db_path}, export_dir={settings.export_dir})"
        )
        return

    uvicorn.run(create_app(), host=settings.api_host, port=settings.api_port)


def run_mcp() -> None:
    from crmbuilder_v2.mcp_server.server import main as mcp_main

    mcp_main()


def bootstrap_db() -> None:
    from crmbuilder_v2.access.db import bootstrap_database

    bootstrap_database()
    print("Schema initialised.")


def bootstrap_content() -> None:
    from crmbuilder_v2.bootstrap.migrate import migrate_default

    summary = migrate_default()
    print(summary)


def run_ui() -> int:
    from crmbuilder_v2.ui.app import main as ui_main

    return ui_main(sys.argv)
