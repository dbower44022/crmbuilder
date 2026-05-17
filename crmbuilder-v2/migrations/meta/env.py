"""Alembic environment for the v0.5 meta DB.

A separate Alembic chain from the per-engagement chain at
``crmbuilder-v2/migrations/``. The meta DB holds the ``engagements``
registry table at ``crmbuilder-v2/data/engagements.db`` — see
``multi-engagement-architecture.md`` §3.1.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from crmbuilder_v2.access.db import _build_engine
from crmbuilder_v2.access.meta_db import meta_db_url
from crmbuilder_v2.access.meta_models import MetaBase

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

url = meta_db_url()
config.set_main_option("sqlalchemy.url", url)

target_metadata = MetaBase.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = _build_engine(url)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
