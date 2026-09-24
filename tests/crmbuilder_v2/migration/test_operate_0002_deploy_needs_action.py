"""PI-571 — ``operate_0002_deploy_needs_action`` widens the deploy-run CHECKs
and adds the instance's open items; its downgrade narrows them again.

Head shape via create_all, stamp every head, downgrade the ``operate`` branch
to its fork (the old CHECKs refuse ``needs_action`` and the column is gone),
then ``upgrade heads`` (a ``needs_action`` run on a ``check_dns`` step is
accepted and the column is back). A downgrade over such a row is refused.
"""

from __future__ import annotations

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import fresh_db, requires_postgres, stamp_heads

pytestmark = requires_postgres

_FORK = "operate_0001_branch"
_INSERT = text(
    "INSERT INTO deploy_runs (engagement_id, deploy_run_identifier, deploy_run_status, "
    "deploy_run_phase, created_at, updated_at) VALUES ('ENG-001', 'DEP-001', "
    "'needs_action', 'check_dns', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
)


def _columns(db: str) -> set[str]:
    eng = create_engine(db)
    try:
        return {c["name"] for c in inspect(eng).get_columns("instance_deploy_configs")}
    finally:
        eng.dispose()


def _insert(db: str) -> bool:
    eng = create_engine(db)
    try:
        with eng.begin() as c:
            c.execute(_INSERT)
        return True
    except IntegrityError:
        return False
    finally:
        eng.dispose()


def test_needs_action_status_new_steps_and_open_items() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    engine.dispose()
    assert stamp_heads(db).returncode == 0

    down = _alembic(["downgrade", f"operate@{_FORK}"], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert "open_items" not in _columns(db)
    assert _insert(db) is False, "the old CHECKs must refuse needs_action on check_dns"

    up = _alembic(["upgrade", "heads"], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert "open_items" in _columns(db)
    assert _insert(db) is True

    refused = _alembic(["downgrade", f"operate@{_FORK}"], db)
    assert refused.returncode != 0 and "needs_action" in (refused.stdout + refused.stderr)
