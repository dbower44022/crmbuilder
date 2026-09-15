"""PI-509 (REQ-601, DEC-1089): retire the ``service`` reference type and its
two kinds from the ``refs`` CHECK constraints.

The ``services`` table is dropped on the ``solution_design`` branch. The
``refs`` table is Shared Core plumbing, so narrowing its three CHECKs
(``ck_ref_source_type``, ``ck_ref_target_type``, ``ck_ref_relationship``) to
the live vocabulary, which no longer contains ``service``,
``process_consumes_service`` or ``service_owns_entity``, lands here.

Nothing is deleted. A reference that names a record type with no table is a
dangling reference the product owner must see, so the upgrade refuses if any
``refs`` row still names the retired type or kinds; rehearsal on a clone of
the live store surfaces that before a deploy. The change-log CHECK is left
alone on purpose: ``CHANGE_LOG_ENTITY_TYPES`` keeps ``service`` admissible
because the change log is history and its rows are never removed.

Downgrade widens the three CHECKs again to admit the retired values.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import (
    ENTITY_TYPES,
    REFERENCE_RELATIONSHIPS,
    _check_in,
)
from crmbuilder_v2.migration.retired_tables import (
    SERVICE_ENTITY_TYPE,
    SERVICE_REFERENCE_KINDS,
)

revision: str = "shared_core_0002_retire_service_reference_type"
down_revision: str | None = "shared_core_0001_branch"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen as they stand on the day of this revision (lesson LSN-062): the live
# sets, which already exclude the retired values, and the same sets widened.
_TYPES_NEW = frozenset(ENTITY_TYPES)
_TYPES_OLD = _TYPES_NEW | {SERVICE_ENTITY_TYPE}
_KINDS_NEW = frozenset(REFERENCE_RELATIONSHIPS)
_KINDS_OLD = _KINDS_NEW | SERVICE_REFERENCE_KINDS


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild(types: frozenset[str], kinds: frozenset[str]) -> None:
    if "refs" not in _tables():
        return
    with op.batch_alter_table("refs") as batch:
        batch.drop_constraint("ck_ref_source_type", type_="check")
        batch.create_check_constraint(
            "ck_ref_source_type", _check_in("source_type", types)
        )
        batch.drop_constraint("ck_ref_target_type", type_="check")
        batch.create_check_constraint(
            "ck_ref_target_type", _check_in("target_type", types)
        )
        batch.drop_constraint("ck_ref_relationship", type_="check")
        batch.create_check_constraint(
            "ck_ref_relationship", _check_in("relationship_kind", kinds)
        )


def _rows_naming_retired_values() -> int:
    if "refs" not in _tables():
        return 0
    kinds = ", ".join(f"'{k}'" for k in sorted(SERVICE_REFERENCE_KINDS))
    return int(
        op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM refs WHERE source_type = :t "
                "OR target_type = :t "
                f"OR relationship_kind IN ({kinds})"
            ),
            {"t": SERVICE_ENTITY_TYPE},
        )
        .scalar_one()
    )


def upgrade() -> None:
    dangling = _rows_naming_retired_values()
    if dangling:
        raise RuntimeError(
            f"{dangling} refs row(s) still name the retired reference type "
            f"'{SERVICE_ENTITY_TYPE}' or its kinds {sorted(SERVICE_REFERENCE_KINDS)}; "
            "nothing was changed. The services table has no rows, so these "
            "references are dangling: the product owner decides their fate "
            "(retain-not-delete), then this revision is re-run."
        )
    _rebuild(_TYPES_NEW, _KINDS_NEW)


def downgrade() -> None:
    _rebuild(_TYPES_OLD, _KINDS_OLD)
