"""PI-273 — pipeline-event capture is best-effort and never breaks the work.

Observability must not raise on the scheduler's hot path: a bad event or an
unreachable store is swallowed and logged, not propagated.
"""

from __future__ import annotations

from crmbuilder_v2.scheduler import event_capture


def test_emit_persists_an_event(v2_env):
    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.repositories import pipeline_events

    event_capture.emit(None, kind="dispatch", work_task="WTK-1", area="storage")
    with session_scope() as s:
        rows = pipeline_events.recent(s, work_task="WTK-1")
    assert len(rows) == 1
    assert rows[0]["event_kind"] == "dispatch"


def test_emit_swallows_a_bad_kind(v2_env):
    # An invalid kind would raise inside record(); emit must swallow it.
    event_capture.emit(None, kind="not-a-kind", work_task="WTK-1")
    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.repositories import pipeline_events

    with session_scope() as s:
        assert pipeline_events.recent(s, work_task="WTK-1") == []


def test_emit_swallows_a_store_failure(monkeypatch):
    # No DB configured / store blows up → emit returns quietly (no raise).
    import crmbuilder_v2.access.db as db

    def _boom(*a, **k):
        raise RuntimeError("store down")

    monkeypatch.setattr(db, "session_scope", _boom)
    event_capture.emit(None, kind="dispatch", work_task="WTK-1")  # must not raise
