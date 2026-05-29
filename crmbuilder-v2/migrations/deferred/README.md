# Deferred migrations

Migrations here are **authored but intentionally not yet active**. Alembic
only scans `migrations/versions/`, so files in this directory are not part
of the upgrade chain and `alembic upgrade head` ignores them.

A migration lands here when it is data-dependent — it cannot run until some
out-of-band data step completes — so adding it to `versions/` prematurely
would break the chain.

| File | Blocked on | Activate by |
|------|-----------|-------------|
| `0027_pi_083_planning_item_area_not_null.py` | PI-083 area backfill (`scripts/backfill_pi_083_area.py`) giving every Open planning item an `area` | `git mv` it into `../versions/`, then `alembic upgrade head` |

To activate: complete the blocking data step, `git mv` the file into
`../versions/`, then run the migration. Each file's module docstring carries
the full activation procedure.
