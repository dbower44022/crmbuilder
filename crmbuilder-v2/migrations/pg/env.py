"""Alembic environment for the Postgres store (PI-alpha, D1/D5).

The **only** Alembic chain since PI-503 (REQ-593 / DEC-1082). It began as a
separate chain from the SQLite per-engagement chain that lived at
``crmbuilder-v2/migrations/``: that chain was batch-mode DDL encoding
SQLite-shaped intermediate states and was never replayed on Postgres, which
starts from a single baseline materialised directly from the ORM models
(``pi-alpha-postgres-foundation-architecture.md`` §5) and grows this chain.
The SQLite chain was removed once the SQLite store was retired.

The DB URL comes from ``crmbuilder_v2.config`` (set
``CRMBUILDER_V2_DATABASE_URL`` to the Postgres URL), so:

    CRMBUILDER_V2_DATABASE_URL='postgresql+psycopg://user:pw@host:5432/db' \\
        uv run alembic -c migrations/pg/alembic.ini upgrade head
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from crmbuilder_v2.access.models import Base
from crmbuilder_v2.config import get_settings
from sqlalchemy import create_engine, make_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

url = get_settings().db_url
if make_url(url).get_backend_name() == "sqlite":
    raise RuntimeError(
        "the Alembic tree requires a Postgres URL; set "
        "CRMBUILDER_V2_DATABASE_URL (for local work: docker compose -f "
        "crmbuilder-v2/docker-compose.dev.yml up -d, then "
        "postgresql+psycopg://crmb:crmb@localhost:55432/crmbuilder_v2). "
        "There is no SQLite chain (PI-503)."
    )
config.set_main_option("sqlalchemy.url", url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(url, future=True)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
