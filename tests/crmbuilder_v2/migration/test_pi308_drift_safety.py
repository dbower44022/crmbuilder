"""PI-308 / REQ-343 — migration-drift detection + honest schema-apply.

Covers the honest ``bootstrap_database`` (un-stamped DB -> create_all+stamp
heads; stamped DB -> upgrade heads), the ``assert_schema_current`` drift gate,
and ``run_api``'s refuse-to-serve-on-drift behaviour — against Postgres, the
one migration tree since PI-503 (REQ-593 / DEC-1082). The SQLite-facing parts
assert the refusal: bootstrap and the API start path turn a SQLite URL away
with a message naming the local dev container.

Since PI-507 (REQ-592 / DEC-1079) the tree has one head per owner branch, so
"at head" means the stamped set equals the head set: the gate refuses a
database missing any branch head or carrying a stale non-head revision, and
the bootstrap makes ``alembic_version.version_num`` 255 wide on a fresh
database. Part 3 is the acceptance proof that two lanes each adding a
migration on different branches merge without renumbering.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from crmbuilder_v2.access.db import (
    bootstrap_database,
    reset_engine_cache,
)
from crmbuilder_v2.access.models import Base
from crmbuilder_v2.config import reset_settings_cache
from crmbuilder_v2.migration.version_info import (
    BRANCH_LABELS,
    LOCAL_POSTGRES_CONTAINER,
    VERSION_NUM_WIDTH,
    SchemaDriftError,
    SqliteRefusedError,
    assert_schema_current,
    ensure_version_table_wide,
    make_alembic_config,
    refuse_sqlite,
    schema_version,
)
from sqlalchemy import create_engine, inspect, text

from tests.crmbuilder_v2.migration._pg_chain import (
    ALEMBIC_INI,
    all_heads,
    fresh_db,
    plain_url,
    requires_postgres,
)

TRUNK_HEAD = "0097_pi_471_transitions"


def _version_num_width(url: str) -> int | None:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT character_maximum_length FROM information_schema.columns "
                    "WHERE table_name = 'alembic_version' AND column_name = 'version_num'"
                )
            ).scalar()
    finally:
        engine.dispose()


def _point_settings(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    """Force the configured unified DB at ``url`` for this test."""
    monkeypatch.setenv("CRMBUILDER_V2_DATABASE_URL", url)
    reset_settings_cache()
    reset_engine_cache()


@pytest.fixture
def pg_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A wiped migrations database, configured as the unified DB."""
    url = plain_url(fresh_db())
    _point_settings(monkeypatch, url)
    try:
        yield url
    finally:
        reset_engine_cache()
        reset_settings_cache()


# --------------------------------------------------------------------------
# Part 0 — one chain, and the SQLite refusal
# --------------------------------------------------------------------------


def test_make_alembic_config_points_at_the_postgres_tree() -> None:
    # Whatever the URL, the environment is the Postgres tree: there is no
    # other chain to resolve a head from (the PI-308 dialect switch is gone).
    for url in ("sqlite:////tmp/x.db", "postgresql+psycopg://u@h/d"):
        cfg = make_alembic_config(url)
        assert cfg.get_main_option("script_location").endswith("migrations/pg")


def test_refuse_sqlite_names_the_dev_container() -> None:
    with pytest.raises(SqliteRefusedError) as ei:
        refuse_sqlite("sqlite:////tmp/x.db", "probe")
    message = str(ei.value)
    assert "probe" in message
    assert LOCAL_POSTGRES_CONTAINER in message
    assert "docker compose -f crmbuilder-v2/docker-compose.dev.yml up -d" in message
    refuse_sqlite("postgresql+psycopg://u@h/d", "probe")  # no raise


def test_bootstrap_refuses_a_sqlite_url(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CRMBUILDER_V2_DATABASE_URL", "")
    monkeypatch.setenv("CRMBUILDER_V2_DB_PATH", str(tmp_path / "v2.db"))
    reset_settings_cache()
    reset_engine_cache()
    try:
        with pytest.raises(SqliteRefusedError):
            bootstrap_database()
        assert not (tmp_path / "v2.db").exists()
    finally:
        reset_engine_cache()
        reset_settings_cache()


def test_run_api_refuses_a_sqlite_url(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("CRMBUILDER_V2_DATABASE_URL", "")
    monkeypatch.setenv("CRMBUILDER_V2_DB_PATH", str(tmp_path / "v2.db"))
    reset_settings_cache()
    monkeypatch.setattr("sys.argv", ["crmbuilder-v2-api", "--check-only"])
    from crmbuilder_v2 import cli

    try:
        with pytest.raises(SystemExit) as ei:
            cli.run_api()
    finally:
        reset_settings_cache()
    assert ei.value.code == 2  # _fail_loud exits 2 before any uvicorn start
    assert LOCAL_POSTGRES_CONTAINER in capsys.readouterr().err


# --------------------------------------------------------------------------
# Part 1 — honest bootstrap_database (Postgres)
# --------------------------------------------------------------------------


@requires_postgres
def test_bootstrap_fresh_db_creates_and_stamps_every_head(pg_db) -> None:
    bootstrap_database()
    sv = schema_version()
    assert sv.is_up_to_date, (sv.applied, sv.heads)
    assert sv.applied == all_heads()
    assert len(sv.heads) == len(BRANCH_LABELS)
    # A head-only table materialised (not just stamped).
    tabs = set(inspect(create_engine(pg_db)).get_table_names())
    assert "field_permission_rules" in tabs  # from migration 0043 on this chain
    assert "alembic_version" in tabs


@requires_postgres
def test_bootstrap_creates_the_version_table_wide(pg_db) -> None:
    # fresh_db pre-creates the table wide for the alembic-subprocess tests;
    # drop it so this test sees what bootstrap does on a truly fresh database.
    engine = create_engine(pg_db)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE alembic_version"))
    engine.dispose()
    assert _version_num_width(pg_db) is None
    bootstrap_database()
    assert _version_num_width(pg_db) == VERSION_NUM_WIDTH
    assert schema_version().is_up_to_date


@requires_postgres
def test_ensure_version_table_wide_widens_a_narrow_table(pg_db) -> None:
    # An earlier bootstrap could have let Alembic create the 32-wide default.
    engine = create_engine(pg_db)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE alembic_version"))
        conn.execute(
            text(
                "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, "
                "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
            )
        )
    engine.dispose()
    ensure_version_table_wide(pg_db)
    assert _version_num_width(pg_db) == VERSION_NUM_WIDTH
    ensure_version_table_wide(pg_db)  # idempotent
    assert _version_num_width(pg_db) == VERSION_NUM_WIDTH


@requires_postgres
def test_bootstrap_at_heads_is_idempotent_noop(pg_db) -> None:
    bootstrap_database()
    assert schema_version().is_up_to_date
    # Second call is a no-op upgrade (stamped DB -> upgrade heads), still current.
    bootstrap_database()
    assert schema_version().is_up_to_date


@requires_postgres
def test_bootstrap_stamped_at_trunk_upgrades_every_branch(pg_db) -> None:
    # create_all gives the head schema; stamp it at the trunk head, which is
    # behind on every branch, so bootstrap takes the upgrade path and applies
    # each branch's fork revision.
    engine = create_engine(pg_db)
    Base.metadata.create_all(engine)
    engine.dispose()
    command.stamp(make_alembic_config(pg_db), TRUNK_HEAD)
    sv = schema_version()
    assert sv.applied == (TRUNK_HEAD,)
    assert set(sv.missing) == set(sv.heads)
    bootstrap_database()
    assert schema_version().is_up_to_date


@requires_postgres
def test_bootstrap_missing_one_branch_head_applies_only_that_branch(pg_db) -> None:
    bootstrap_database()
    engine = create_engine(pg_db)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM alembic_version WHERE version_num = 'operate_0002_deploy_needs_action'"))
    engine.dispose()
    sv = schema_version()
    assert sv.missing == ("operate_0002_deploy_needs_action",)
    assert not sv.is_up_to_date
    bootstrap_database()
    assert schema_version().is_up_to_date


# --------------------------------------------------------------------------
# Part 2 — the assert_schema_current gate
# --------------------------------------------------------------------------


@requires_postgres
def test_assert_schema_current_passes_at_every_head(pg_db) -> None:
    bootstrap_database()
    assert_schema_current()  # no raise


@requires_postgres
def test_assert_schema_current_raises_when_unstamped(pg_db) -> None:
    # fresh_db leaves an empty version table: no row, no revision.
    with pytest.raises(SchemaDriftError) as ei:
        assert_schema_current()
    assert ei.value.applied == () and ei.value.current is None
    assert set(ei.value.missing) == set(all_heads())


@requires_postgres
def test_assert_schema_current_raises_when_behind(pg_db) -> None:
    bootstrap_database()
    # Re-stamp to a value that merely differs from the heads (stale, not a head).
    # Whichever revision heads the build branch today (PI-509 moved it past
    # the fork revision); the test must not pin a head that lanes advance.
    build_head = next(h for h in all_heads() if h.startswith("build_"))
    engine = create_engine(pg_db)
    with engine.begin() as conn:
        conn.execute(text("UPDATE alembic_version SET version_num='0001_pg_baseline' "
                          "WHERE version_num = :h"), {"h": build_head})
    engine.dispose()
    with pytest.raises(SchemaDriftError) as ei:
        assert_schema_current()
    assert ei.value.missing == (build_head,)
    assert ei.value.stale == ("0001_pg_baseline",)


@requires_postgres
def test_assert_schema_current_raises_when_one_branch_head_is_missing(pg_db) -> None:
    bootstrap_database()
    engine = create_engine(pg_db)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM alembic_version WHERE version_num = 'discovery_0001_branch'"))
    engine.dispose()
    with pytest.raises(SchemaDriftError) as ei:
        assert_schema_current()
    assert ei.value.missing == ("discovery_0001_branch",)
    assert ei.value.stale == ()
    assert "missing=['discovery_0001_branch']" in str(ei.value)


def test_schema_version_to_dict_carries_both_sets() -> None:
    from crmbuilder_v2.migration.version_info import SchemaVersion

    sv = SchemaVersion(applied=("a_0001_branch",), heads=("a_0001_branch", "b_0001_branch"))
    d = sv.to_dict()
    assert d["current"] == "a_0001_branch"
    assert d["head"] == "a_0001_branch, b_0001_branch"
    assert d["missing"] == ["b_0001_branch"]
    assert d["up_to_date"] is False
    assert SchemaVersion(applied=(), heads=()).is_up_to_date is False


# --------------------------------------------------------------------------
# Part 3 — acceptance: two lanes, two branches, no renumbering
# --------------------------------------------------------------------------


def _tree_copy_with_two_lanes(tmp_path: Path) -> Config:
    """A copy of the migration tree with one new revision on each of two branches.

    Models what two worktrees each produce and what main holds after both merge:
    ``build_9999_widen_x`` on the build branch and ``operate_9999_add_y`` on the
    operate branch. Neither knew about the other; neither is renumbered.
    """
    src = ALEMBIC_INI.parent
    dst = tmp_path / "pg"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
    # Each lane appends to whatever heads its branch today, not to the fork
    # revision: the branches have moved on since PI-507 (build has, from PI-509).
    heads_now = all_heads()
    for label, rev, slug in (("build", "build_9999_widen_x", "lane A"), ("operate", "operate_9999_add_y", "lane B")):
        parent = next(h for h in heads_now if h.startswith(f"{label}_"))
        (dst / "versions" / f"{rev}.py").write_text(
            f'"""{slug}: a throwaway revision on the {label} branch (test only)."""\n'
            "from __future__ import annotations\n\n"
            f'revision = "{rev}"\n'
            f'down_revision = "{parent}"\n'
            "branch_labels = None\n"
            "depends_on = None\n\n\n"
            "def upgrade() -> None:\n    pass\n\n\n"
            "def downgrade() -> None:\n    pass\n"
        )
    cfg = Config(str(dst / "alembic.ini"))
    cfg.set_main_option("script_location", str(dst))
    return cfg


def test_two_lanes_on_different_branches_merge_without_renumbering(tmp_path) -> None:
    cfg = _tree_copy_with_two_lanes(tmp_path)
    heads = sorted(ScriptDirectory.from_config(cfg).get_heads())
    # Still one head per branch: the two new revisions replaced their branch
    # heads and nothing forked.
    assert len(heads) == len(BRANCH_LABELS)
    assert "build_9999_widen_x" in heads and "operate_9999_add_y" in heads
    assert not any(h.startswith(("build_", "operate_")) and not h.endswith(("_widen_x", "_add_y")) for h in heads)


@requires_postgres
def test_two_lanes_upgrade_heads_applies_both(pg_db, tmp_path, monkeypatch) -> None:
    cfg = _tree_copy_with_two_lanes(tmp_path)
    cfg.set_main_option("sqlalchemy.url", pg_db)
    engine = create_engine(pg_db)
    Base.metadata.create_all(engine)
    engine.dispose()
    command.stamp(cfg, TRUNK_HEAD)
    command.upgrade(cfg, "heads")
    engine = create_engine(pg_db)
    try:
        with engine.connect() as conn:
            stamped = sorted(r[0] for r in conn.execute(text("SELECT version_num FROM alembic_version")))
    finally:
        engine.dispose()
    assert stamped == sorted(ScriptDirectory.from_config(cfg).get_heads())
    assert "build_9999_widen_x" in stamped and "operate_9999_add_y" in stamped


# --------------------------------------------------------------------------
# run_api refuse-to-serve on drift (acceptance #1)
# --------------------------------------------------------------------------


@requires_postgres
def test_run_api_refuses_to_start_on_drift(pg_db, monkeypatch) -> None:
    # un-stamped -> drift; the SQLite refusal does not fire on a Postgres URL.
    monkeypatch.setattr("sys.argv", ["crmbuilder-v2-api", "--check-only"])
    from crmbuilder_v2 import cli

    with pytest.raises(SystemExit) as ei:
        cli.run_api()
    assert ei.value.code == 2  # _fail_loud exits 2 before any uvicorn start
