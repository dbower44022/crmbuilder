"""Storage-substrate concurrency validation — REQ-255 / PI-100.

REQ-255: before the production storage substrate is made the default it must hold
at the expected peak number of concurrent writers, without **lost** or
**corrupted** writes or **unacceptable contention**. This test proves all three
against the *configured* store — SQLite (WAL + ``BEGIN IMMEDIATE`` + 5 s
``busy_timeout``) per-test by default, or Postgres (``QueuePool``) when
``CRMBUILDER_V2_TEST_PG_URL`` is set — so one proof covers both dialects.

The write path under test is ``decisions.create`` because its server-assigned
``DEC-NNN`` identifier runs through the SAVEPOINT-retry auto-assign helper, which
is exactly the piece that must be safe under concurrent writers (CLAUDE.md). Many
writers minting identifiers at once is the sharpest concurrency stress in the
substrate.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from crmbuilder_v2.access import engagement_scope
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import decisions

from tests.crmbuilder_v2.conftest import DEFAULT_ENGAGEMENT_ID

#: Peak concurrent writers + writes each. 16 × 8 = 128 contended commits — well
#: above the dogfood's real peak (the ADO fleet's max-concurrent agents + API +
#: UI), small enough to stay fast.
WRITERS = 16
PER_WRITER = 8
_SUMMARY = "PI-100 storage concurrency validation decision body. " * 5  # 200-800


def _writer(worker_id: int, errors: list[str]) -> None:
    # ContextVars do NOT propagate into a freshly-spawned thread, so each worker
    # re-establishes the active engagement + enforcement it writes under (else the
    # write-stamp/read-filter sees no active engagement and fails loud).
    engagement_scope.set_active_engagement(DEFAULT_ENGAGEMENT_ID)
    engagement_scope.set_enforcement(True)
    for i in range(PER_WRITER):
        try:
            with session_scope() as s:
                decisions.create(
                    s,
                    title=f"conc-w{worker_id}-{i}",
                    decision_date="2026-06-30",
                    status="Active",
                    executive_summary=_SUMMARY,
                )
        except Exception as exc:  # noqa: BLE001 — collect, assert none below
            errors.append(f"w{worker_id}-{i}: {exc!r}")


def test_concurrent_writers_hold_without_loss_or_corruption(v2_env):
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=WRITERS) as ex:
        list(ex.map(lambda w: _writer(w, errors), range(WRITERS)))

    # (1) Acceptable contention: no writer errored / timed out / deadlocked.
    assert errors == [], (
        f"{len(errors)}/{WRITERS * PER_WRITER} concurrent writes errored "
        f"(unacceptable contention): {errors[:5]}"
    )

    with session_scope() as s:
        mine = [r for r in decisions.list_all(s) if r["title"].startswith("conc-w")]

    # (2) No lost writes: every committed write is durably present.
    assert len(mine) == WRITERS * PER_WRITER, (
        f"lost writes: expected {WRITERS * PER_WRITER}, found {len(mine)}"
    )
    # (3) No corruption: server-assigned identifiers are all unique (the
    #     SAVEPOINT-retry auto-assign held — no two writers minted the same id).
    ids = [r["identifier"] for r in mine]
    assert len(set(ids)) == len(ids), "duplicate identifiers — auto-assign raced"
    # (4) No torn/garbled write: every title round-trips intact, exactly once.
    assert {r["title"] for r in mine} == {
        f"conc-w{w}-{i}" for w in range(WRITERS) for i in range(PER_WRITER)
    }


def test_single_writer_baseline(v2_env):
    """Sanity floor: the same write path with one writer (isolates a concurrency
    failure above from a plain create failure)."""
    errors: list[str] = []
    _writer(0, errors)
    assert errors == []
    with session_scope() as s:
        mine = [r for r in decisions.list_all(s) if r["title"].startswith("conc-w0-")]
    assert len(mine) == PER_WRITER
