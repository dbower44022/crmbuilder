"""Alembic environment for the Postgres store (PI-alpha, D1/D5).

A **separate** Alembic chain from the SQLite per-engagement chain at
``crmbuilder-v2/migrations/``. The SQLite chain (0001-0039) is batch-mode DDL
encoding SQLite-shaped intermediate states and is **not** replayed on Postgres;
Postgres starts from a single baseline materialised directly from the ORM models
(``pi-alpha-postgres-foundation-architecture.md`` §5) and grows its own chain.

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
        "the Postgres Alembic tree requires a Postgres URL; set "
        "CRMBUILDER_V2_DATABASE_URL (the SQLite chain lives at "
        "crmbuilder-v2/migrations/)."
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
