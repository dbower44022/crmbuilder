"""Migration resets a sequence for EVERY id-table — PI-377 (REQ-438).

Runs in the default suite (no Postgres needed): it asserts the table set the
migration resets is derived from the model metadata and covers every table with
a surrogate ``id`` column. The 06-29 live failure was a hardcoded 10-entry list
that missed 34 of 44 id-tables, so their sequences stayed at 1 and new inserts
collided (instance_memberships, reconcile_transactions, catalog_*, release_*).
"""

from __future__ import annotations

from crmbuilder_v2.access.models import Base
from crmbuilder_v2.migration.sqlite_to_postgres import _id_pk_tables


def _all_id_tables() -> set[str]:
    return {t.name for t in Base.metadata.tables.values() if "id" in t.columns}


def test_reset_covers_every_id_table_from_metadata():
    """The reset set equals every model table with an id column — not a subset."""
    covered = set(_id_pk_tables())
    assert covered == _all_id_tables()
    # Far more than the old hand-maintained 10-entry list.
    assert len(covered) >= 40


def test_previously_missed_tables_are_covered():
    """The exact tables that collided on the live store must be in the reset set."""
    covered = set(_id_pk_tables())
    for table in (
        "instance_memberships",
        "reconcile_transactions",
        "catalog_attribute",
        "catalog_attribute_presence",
        "release_signoffs",
        "resource_locks",
        "review_signoffs",
        "mapping_candidates",
    ):
        assert table in covered, table
