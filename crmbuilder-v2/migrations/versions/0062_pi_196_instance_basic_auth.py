"""PI-196 (PRJ-027) — admit 'basic' as an instance auth method.

The instance entity (PI-186) only allowed ``api_key`` / ``hmac``, but EspoCRM
(and the CBM instances) use HTTP basic auth, which the ported introspection
client already supports. This rebuilds the ``instances``
``ck_instance_auth_method`` CHECK from the current vocab (now including
``basic``). Predicate derives from vocab; a superset so no existing row is
invalidated; inspector-guarded for mid-stream entry. SQLite head 0061 -> 0062;
companion PG delta ``migrations/pg/versions/0020_pi_196_instance_basic_auth.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import INSTANCE_AUTH_METHODS, _check_in

revision: str = "0062_pi_196_instance_basic_auth"
down_revision: str | None = "0061_pi_195_filtered_tab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = frozenset({"api_key", "hmac"})


def _rebuild(methods: frozenset[str]) -> None:
    if "instances" not in set(sa.inspect(op.get_bind()).get_table_names()):
        return
    with op.batch_alter_table("instances") as batch:
        batch.drop_constraint("ck_instance_auth_method", type_="check")
        batch.create_check_constraint(
            "ck_instance_auth_method", _check_in("instance_auth_method", methods)
        )


def upgrade() -> None:
    _rebuild(INSTANCE_AUTH_METHODS)


def downgrade() -> None:
    op.execute("DELETE FROM instances WHERE instance_auth_method = 'basic'")
    _rebuild(_OLD)
