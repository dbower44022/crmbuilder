"""PI-196 (PG chain) — admit 'basic' as an instance auth method.

Companion to the SQLite-chain ``0074``. Rebuilds the ``instances``
``ck_instance_auth_method`` CHECK to admit ``basic`` on Postgres deployments
materialised from an earlier baseline. Same-text no-op on a fresh
create_all baseline; a real change on a pre-existing store. Superset, no row
invalidated. Never replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.vocab import INSTANCE_AUTH_METHODS, _check_in

revision: str = "0031_pi_196_instance_basic_auth"
down_revision: str | None = "0030_pi_217_release_demands"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = frozenset({"api_key", "hmac"})


def _rebuild(methods: frozenset[str]) -> None:
    op.drop_constraint("ck_instance_auth_method", "instances", type_="check")
    op.create_check_constraint(
        "ck_instance_auth_method", "instances",
        _check_in("instance_auth_method", methods),
    )


def upgrade() -> None:
    _rebuild(INSTANCE_AUTH_METHODS)


def downgrade() -> None:
    op.execute("DELETE FROM instances WHERE instance_auth_method = 'basic'")
    _rebuild(_OLD)
