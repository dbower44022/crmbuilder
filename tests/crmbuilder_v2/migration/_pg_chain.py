"""Shared helpers for the migration tests — Postgres only (PI-503 / REQ-593 / DEC-1082).

There is one migration chain, the Postgres tree at ``crmbuilder-v2/migrations/pg``,
so the tests that exercise a revision's real ``downgrade`` / ``upgrade`` code run
only against Postgres. Set ``CRMBUILDER_V2_TEST_PG_URL`` (for local work the dev
container from ``crmbuilder-v2/docker-compose.dev.yml``:
``postgresql+psycopg://crmb:crmb@localhost:55432/crmbuilder_v2``); without it every
test in this package is skipped, and the everyday suite — which builds per-test
SQLite files straight from the models — is unaffected.

The tests churn the schema (drop everything, ``create_all``, stamp, downgrade,
upgrade), so they never touch the suite's shared test database: :func:`fresh_db`
works in a sibling database ``<name>_migrations`` on the same server, created on
demand, and wipes its ``public`` schema before every test.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

_REPO_ROOT = Path(__file__).resolve().parents[3]
CRMBUILDER_V2_DIR = _REPO_ROOT / "crmbuilder-v2"
ALEMBIC_INI = CRMBUILDER_V2_DIR / "migrations" / "pg" / "alembic.ini"
_TEST_PG_URL = os.environ.get("CRMBUILDER_V2_TEST_PG_URL") or ""

#: Module-level ``pytestmark`` for every test that runs the chain.
requires_postgres = pytest.mark.skipif(
    not _TEST_PG_URL,
    reason=(
        "migration tests run only against Postgres (PI-503 / DEC-1082): set "
        "CRMBUILDER_V2_TEST_PG_URL, e.g. to the dev container "
        "postgresql+psycopg://crmb:crmb@localhost:55432/crmbuilder_v2"
    ),
)


def migrations_db_url() -> str:
    """URL of the sibling ``<name>_migrations`` database, creating it if absent."""
    url = make_url(_TEST_PG_URL)
    name = f"{url.database}_migrations"
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        admin.dispose()
    return url.set(database=name).render_as_string(hide_password=False)


def fresh_db() -> str:
    """Wipe the migrations database and return its URL.

    Every other session on that database is terminated first so a connection a
    previous test left open cannot block the ``DROP SCHEMA``. The caller builds
    whatever schema it needs (``Base.metadata.create_all`` for the head shape,
    exactly as the SQLite-file tests did).
    """
    url = migrations_db_url()
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND pid <> pg_backend_pid()"
                )
            )
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            # Alembic creates ``alembic_version.version_num`` as VARCHAR(32)
            # when the table is absent, and forty of this chain's revision ids
            # are longer than that (``0096_pi_488_session_opening_fields`` is
            # 34 characters); on Postgres, unlike SQLite, the length is
            # enforced. Pre-create the table wide, as the live store has it,
            # so ``checkfirst`` leaves it alone and every stamp / downgrade /
            # upgrade can write its revision id.
            conn.execute(
                text(
                    "CREATE TABLE alembic_version ("
                    "version_num VARCHAR(255) NOT NULL, "
                    "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
                )
            )
    finally:
        engine.dispose()
    # Test connections run with foreign-key triggers off — the posture the
    # SQLite-file tests had by default (a plain ``create_engine`` never turned
    # ``PRAGMA foreign_keys`` on), so raw fixture rows need no parent rows.
    # ``options`` is a libpq connection parameter psycopg passes through.
    # :func:`alembic` strips it: the chain itself runs as production does.
    return (
        make_url(url)
        .update_query_dict({"options": "-c session_replication_role=replica"})
        .render_as_string(hide_password=False)
    )


def plain_url(db_url: str) -> str:
    """``db_url`` without the test-only ``options`` parameter.

    For code paths that build their own engine from ``Settings`` (bootstrap,
    the drift gate): they must see the store as production does, and Alembic's
    config parser cannot take the ``%``-encoded option string anyway.
    """
    return make_url(db_url).difference_update_query(["options"]).render_as_string(hide_password=False)


def alembic(args: list[str], db_url: str) -> subprocess.CompletedProcess:
    """Run ``alembic -c migrations/pg/alembic.ini <args>`` against ``db_url``.

    The subprocess imports the checkout under test, not the venv's editable
    install (lesson LSN-080): migrations that rebuild a CHECK from
    ``crmbuilder_v2.access.vocab`` must see this tree's vocabulary.
    """
    env = os.environ.copy()
    env["CRMBUILDER_V2_DATABASE_URL"] = plain_url(db_url)
    env.pop("CRMBUILDER_V2_DB_PATH", None)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(CRMBUILDER_V2_DIR / "src"), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *args],
        cwd=str(CRMBUILDER_V2_DIR),
        env=env,
        capture_output=True,
        text=True,
    )
