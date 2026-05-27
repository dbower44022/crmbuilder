"""Alembic environment.

The configured DB URL comes from ``crmbuilder_v2.config`` rather than
``alembic.ini``, so a single command works regardless of which DB the
operator has configured via ``CRMBUILDER_V2_DB_PATH``.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, event

from crmbuilder_v2.access.models import Base
from crmbuilder_v2.config import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.db_url)

target_metadata = Base.metadata


def _migration_connect_pragmas(dbapi_conn, _conn_record) -> None:
    """Connect-time pragmas for migrations.

    Mirrors ``crmbuilder_v2.access.db._enable_sqlite_pragmas`` but
    leaves ``foreign_keys=OFF`` for the duration of the migration.
    SQLite batch_alter_table copies and drops tables; the drop trips
    FK enforcement on self-referencing FKs (e.g.
    ``decisions.supersedes_id``). Schema-DDL migrations don't need
    FK enforcement during the transaction; the engine's normal
    ``foreign_keys=ON`` posture takes over on the next connection.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=OFF")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
    dbapi_conn.isolation_level = None


def _build_migration_engine(url: str):
    engine = create_engine(url, future=True)
    event.listen(engine, "connect", _migration_connect_pragmas)
    # Mirror the runtime BEGIN IMMEDIATE behavior so concurrent writers
    # queue cleanly while the migration is in flight.
    event.listen(
        engine,
        "begin",
        lambda conn: conn.exec_driver_sql("BEGIN IMMEDIATE"),
    )
    return engine


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
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
    connectable = _build_migration_engine(settings.db_url)
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
