"""PI-365 (REQ-425) — widen four VARCHAR columns that overran on Postgres.

The Postgres cutover (REQ-425) surfaced four columns whose live SQLite data
exceeds their declared VARCHAR length — SQLite never enforced the cap, Postgres
does: ``planning_items.resolution_reference`` (VARCHAR(64), data to 244),
``refs.source_id`` / ``refs.target_id`` (VARCHAR(64), data to 176/121), and
``artifact_versions.artifact_identifier`` (VARCHAR(32), data to 52). The model
now declares all four as ``Text`` (the same fix PI-α applied to its six widened
columns), so ``create_all`` and the one-shot SQLite→PG migration build them wide.

This SQLite-chain step is a **documented no-op**: SQLite does not enforce VARCHAR
length (both ``VARCHAR(n)`` and ``TEXT`` are TEXT affinity), so the existing rows
already fit and an in-place type change would be functionally inert. Forcing it
would require a batch table-recreate of ``refs`` / ``planning_items`` whose
reflected CHECKs and indexes the recreate would drop — risk with no gain. The
enforcement that matters lives on Postgres: companion ``migrations/pg/versions/
0059_...`` ALTERs the four columns to ``TEXT`` there.

SQLite chain head 0101 -> 0102.
"""

from collections.abc import Sequence

revision: str = "0102_pi_365_widen_overflow_columns"
down_revision: str | None = "0101_pi_364_project_run_claim"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # No-op on SQLite (VARCHAR length is not enforced; the model + create_all and
    # the PG companion carry the widening). See the module docstring.
    pass


def downgrade() -> None:
    pass
