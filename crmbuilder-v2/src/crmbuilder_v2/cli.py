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


def _build_api_log_config() -> tuple[object, dict]:
    """Return ``(log_path, dict_config)`` for the API process logging.

    The dict is uvicorn's default ``LOGGING_CONFIG`` extended with a
    ``RotatingFileHandler``, wired into the root logger and the uvicorn
    loggers so *everything* — application logs (``crmbuilder_v2.*``),
    startup tracebacks, and access logs — lands in the rotating file as
    well as the console. uvicorn calls ``logging.config.dictConfig`` on
    this when passed as ``log_config=``, so handlers are installed once,
    consistently, for both standalone and UI-spawned launches.

    Built just before ``uvicorn.run`` so the ``--check-only`` and
    fail-loud paths (which return earlier) create no log file. Rotation
    keeps post-mortems possible after a crash — the gap that made the
    05-30 outage undiagnosable.
    """
    import copy

    from uvicorn.config import LOGGING_CONFIG

    from crmbuilder_v2.config import api_log_path

    log_path = api_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cfg = copy.deepcopy(LOGGING_CONFIG)
    cfg.setdefault("formatters", {})["file"] = {
        "format": "%(asctime)s %(levelname)s %(name)s — %(message)s",
    }
    cfg.setdefault("handlers", {})["file"] = {
        "formatter": "file",
        "class": "logging.handlers.RotatingFileHandler",
        "filename": str(log_path),
        "maxBytes": 2_000_000,
        "backupCount": 5,
        "encoding": "utf-8",
    }
    # A plain console handler for the root logger so application logs are
    # visible on stdout/stderr (uvicorn's own console handlers cover only
    # its loggers). The UI captures this stream as crash diagnostics.
    cfg["handlers"]["console"] = {
        "formatter": "file",
        "class": "logging.StreamHandler",
        "stream": "ext://sys.stderr",
    }
    # Tee the uvicorn loggers (uvicorn.error propagates through "uvicorn")
    # and the access logger into the file alongside their console output.
    for logger_name in ("uvicorn", "uvicorn.access"):
        handlers = cfg.setdefault("loggers", {}).setdefault(
            logger_name, {}
        ).setdefault("handlers", [])
        if "file" not in handlers:
            handlers.append("file")
    # Root captures application loggers (crmbuilder_v2.*) that propagate up.
    cfg["root"] = {"level": "INFO", "handlers": ["console", "file"]}
    return log_path, cfg


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

    from crmbuilder_v2.api.marker_guard import set_marker_at_start

    # DEC-205: capture the marker now so the middleware can detect mid-
    # process drift. set_marker_at_start writes to a module-level constant
    # read by EngagementMarkerGuardMiddleware on every non-exempt request.
    set_marker_at_start(active_code)

    log_path, log_config = _build_api_log_config()
    # Printed before uvicorn configures logging so the operator sees the
    # log location at startup (uvicorn.run blocks until shutdown).
    print(f"crmbuilder-v2-api: logging to {log_path} (rotating)")
    uvicorn.run(
        create_app(),
        host=settings.api_host,
        port=settings.api_port,
        log_config=log_config,
    )


def run_mcp() -> None:
    import argparse

    from crmbuilder_v2.config import get_settings
    from crmbuilder_v2.mcp_server.server import main as mcp_main

    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-mcp",
        description=(
            "Start the crmbuilder_v2 MCP server. Default transport is "
            "stdio (Claude Desktop pipes here). Use --transport "
            "streamable-http to bind the FastMCP HTTP transport for "
            "cloudflared / Cloudflare Tunnel ingress."
        ),
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        metavar="PORT",
        help=(
            "Override CRMBUILDER_V2_MCP_HTTP_PORT for the running process. "
            "Only meaningful when --transport=streamable-http."
        ),
    )
    args = parser.parse_args()

    port = args.port if args.port is not None else get_settings().mcp_http_port
    mcp_main(transport=args.transport, port=port)


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
