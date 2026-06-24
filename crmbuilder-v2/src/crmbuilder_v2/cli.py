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

    import uvicorn

    from crmbuilder_v2.api.main import create_app
    from crmbuilder_v2.config import get_settings

    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-api",
        description=(
            "Start the crmbuilder_v2 REST API over the unified database. The "
            "active engagement is selected per request by the X-Engagement "
            "header (PI-β); there is no process-level active engagement."
        ),
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help=(
            "Print the resolved unified DB path, then exit 0 without starting "
            "uvicorn."
        ),
    )
    args = parser.parse_args()

    settings = get_settings()

    # PI-308 / REQ-343 — active startup drift gate. Refuse to serve a DB whose
    # schema is behind the code (or un-stamped): silently serving it risks a
    # 500 on the first query that hits a not-yet-migrated table or column. This
    # fails at cold start (before first-ready), so it routes to app.py's fatal
    # startup dialog, NOT the desktop's post-first-ready auto-restart loop.
    # Covers --check-only too (a cheap diagnostic).
    from crmbuilder_v2.migration.version_info import (
        SchemaDriftError,
        assert_schema_current,
    )

    try:
        assert_schema_current()
    except SchemaDriftError as exc:
        _fail_loud(
            "REFUSING TO START: database schema is behind the code.\n"
            f"  applied revision: {exc.current or '(un-stamped / empty DB)'}\n"
            f"  code expects head: {exc.head}\n"
            "  remedy: run  crmbuilder-v2-bootstrap-db  to apply pending "
            "migrations,\n"
            "          then relaunch."
        )

    if args.check_only:
        print(f"OK: unified DB at db_path={settings.db_path}")
        return

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


def run_prune_events() -> None:
    """``crmbuilder-v2-prune-events`` — enforce the pipeline-event retention bound (REQ-316).

    Deletes ``pipeline_events`` older than the configured retention bound
    (``CRMBUILDER_V2_PIPELINE_EVENT_RETENTION_DAYS``; default 90), across all
    engagements, so the durable pipeline-progress log does not accumulate without
    end. Intended for an operator or a scheduled job. ``--dry-run`` reports the
    count without deleting; ``--days`` overrides the configured bound.
    """
    import argparse
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func, select

    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.models import PipelineEvent
    from crmbuilder_v2.access.repositories import pipeline_events
    from crmbuilder_v2.config import get_settings

    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-prune-events",
        description=(
            "Delete pipeline_events older than the retention bound, across all "
            "engagements, so the durable pipeline-progress log does not grow "
            "without end (REQ-316)."
        ),
    )
    parser.add_argument(
        "--days", type=int, default=None,
        help="Override the retention bound (days). Default: the configured value.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report how many events WOULD be pruned, without deleting.",
    )
    args = parser.parse_args()

    keep_days = (
        args.days if args.days is not None
        else get_settings().pipeline_event_retention_days
    )
    if args.dry_run:
        with session_scope() as s:
            if keep_days <= 0:
                n = 0
            else:
                cutoff = datetime.now(UTC) - timedelta(days=keep_days)
                n = s.scalar(
                    select(func.count(PipelineEvent.id)).where(
                        PipelineEvent.pipeline_event_created_at < cutoff
                    )
                ) or 0
        print(f"DRY RUN: would prune {n} pipeline event(s) older than "
              f"{keep_days} day(s).")
        return
    with session_scope() as s:
        deleted = pipeline_events.prune(s, keep_days=keep_days)
    print(f"Pruned {deleted} pipeline event(s) older than {keep_days} day(s).")


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


def run_token_admin() -> int:
    """``crmbuilder-v2-token`` — provision principals + bearer tokens (PI-γ).

    A thin local admin CLI over the access layer (it opens the unified DB
    directly, not the REST API, so it works before any token exists). The
    minted token plaintext is printed once.

    Subcommands::

        crmbuilder-v2-token bootstrap-owner --identity doug@x.com [--engagement ENG-001]
        crmbuilder-v2-token mint --principal PRN-001 [--label cli]
        crmbuilder-v2-token list [--principal PRN-001]
        crmbuilder-v2-token revoke --token TOK-0001
    """
    import argparse

    from crmbuilder_v2.access import principal as P
    from crmbuilder_v2.access.db import session_scope

    parser = argparse.ArgumentParser(prog="crmbuilder-v2-token")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_boot = sub.add_parser(
        "bootstrap-owner",
        help="Create (or reuse) an owner principal and mint its first token.",
    )
    p_boot.add_argument("--identity", required=True, help="Owner email/identity.")
    p_boot.add_argument("--display-name", default=None)
    p_boot.add_argument(
        "--engagement",
        default=None,
        help="If set, assign the owner role on this engagement (ENG-NNN).",
    )

    p_mint = sub.add_parser("mint", help="Mint a token for an existing principal.")
    p_mint.add_argument("--principal", required=True)
    p_mint.add_argument("--label", default="")

    p_list = sub.add_parser("list", help="List tokens (optionally by principal).")
    p_list.add_argument("--principal", default=None)

    p_revoke = sub.add_parser("revoke", help="Revoke a token by id.")
    p_revoke.add_argument("--token", required=True)

    args = parser.parse_args()

    if args.cmd == "bootstrap-owner":
        with session_scope() as s:
            owner = P.get_or_create_owner(
                s, identity=args.identity, display_name=args.display_name
            )
            if args.engagement:
                P.assign_role(
                    s,
                    principal_id=owner.principal_id,
                    engagement_id=args.engagement,
                    role="owner",
                )
            minted = P.mint_token(
                s, principal_id=owner.principal_id, label="bootstrap"
            )
            print(f"owner principal: {owner.principal_id} ({owner.identity})")
            print(f"token id:        {minted.token_id}")
            print(f"token (once):    {minted.plaintext}")
        return 0

    if args.cmd == "mint":
        with session_scope() as s:
            minted = P.mint_token(
                s, principal_id=args.principal, label=args.label
            )
            print(f"token id:     {minted.token_id}")
            print(f"token (once): {minted.plaintext}")
        return 0

    if args.cmd == "list":
        with session_scope() as s:
            for t in P.list_tokens(s, principal_id=args.principal):
                state = "revoked" if t.revoked_at else "active"
                print(f"{t.token_id}  {t.principal_id}  [{state}]  {t.label}")
        return 0

    if args.cmd == "revoke":
        with session_scope() as s:
            P.revoke_token(s, args.token)
            print(f"revoked {args.token}")
        return 0

    return 2
