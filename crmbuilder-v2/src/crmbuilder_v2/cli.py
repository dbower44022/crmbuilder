"""Console-script entry points for crmbuilder_v2.

These are wired into ``[project.scripts]`` in ``pyproject.toml``:

* ``crmbuilder-v2-api`` — start the FastAPI REST server
* ``crmbuilder-v2-mcp`` — start the MCP server over stdio
* ``crmbuilder-v2-bootstrap-db`` — apply Alembic migrations to the configured DB
* ``crmbuilder-v2-bootstrap`` — import the four bootstrap markdown files
"""

from __future__ import annotations


def run_api() -> None:
    import uvicorn

    from crmbuilder_v2.api.main import create_app
    from crmbuilder_v2.config import get_settings

    settings = get_settings()
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
