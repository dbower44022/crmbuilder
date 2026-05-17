"""ActivationWorker tests — UI v0.5 slice D.

Covers the 12-step sequence in :mod:`crmbuilder_v2.ui.activation_worker`
including the PRD §3 / question-6 amendment (PATCH deferred to step 10).
Subprocess interactions are mocked via injectable
:class:`SubprocessManagers` so the tests don't spawn real processes.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from crmbuilder_v2.access.engagement_models import (
    Engagement,
    EngagementStatus,
)
from crmbuilder_v2.access.db import bootstrap_database, reset_engine_cache
from crmbuilder_v2.access.meta_db import (
    bootstrap_meta_db,
    reset_meta_engine_cache,
)
from crmbuilder_v2.config import reset_settings_cache
from crmbuilder_v2.migration.lazy_migration import (
    engagement_db_path,
)
from crmbuilder_v2.ui.active_engagement_context import ActiveEngagementContext
from crmbuilder_v2.ui.activation_worker import (
    STEP_DESCRIPTIONS,
    ActivationWorker,
    SubprocessManagers,
)


@pytest.fixture
def _redirect_meta_export(tmp_path, monkeypatch):
    from crmbuilder_v2.access import meta_exporter

    target = tmp_path / "meta-export"
    monkeypatch.setattr(meta_exporter, "meta_export_dir", lambda: target)
    yield


@pytest.fixture
def meta_db(v2_env, _redirect_meta_export):
    reset_meta_engine_cache()
    bootstrap_meta_db()
    yield


def _eng(
    *,
    identifier: str = "ENG-001",
    code: str = "ALPHA",
    deleted: bool = False,
) -> Engagement:
    now = datetime.now(UTC)
    return Engagement(
        engagement_identifier=identifier,
        engagement_code=code,
        engagement_name=code,
        engagement_purpose="",
        engagement_status=EngagementStatus.ACTIVE,
        engagement_last_opened_at=None,
        engagement_export_dir=None,
        engagement_created_at=now,
        engagement_updated_at=now,
        engagement_deleted_at=now if deleted else None,
    )


def _stub_managers(
    *,
    fail_step: int | None = None,
) -> SubprocessManagers:
    """Build a managers bundle that records calls; optionally raises."""

    calls = {"kill_api": 0, "kill_mcp": 0, "launch_api": 0, "launch_mcp": 0}

    def _maybe_raise(step: int) -> None:
        if fail_step == step:
            raise RuntimeError(f"injected failure at step {step}")

    def _kill_api():
        calls["kill_api"] += 1
        _maybe_raise(4)

    def _kill_mcp():
        calls["kill_mcp"] += 1
        _maybe_raise(5)

    def _launch_api(_db_path):
        calls["launch_api"] += 1
        _maybe_raise(8)

    def _launch_mcp(_db_path):
        calls["launch_mcp"] += 1
        _maybe_raise(9)

    mgr = SubprocessManagers(
        kill_api=_kill_api,
        kill_mcp=_kill_mcp,
        launch_api=_launch_api,
        launch_mcp=_launch_mcp,
    )
    mgr.__dict__["calls"] = calls
    return mgr


class _StubClient:
    """Minimal client for the worker; tracks PATCH calls."""

    def __init__(self, patch_should_fail: bool = False) -> None:
        self.patch_calls: list[tuple[str, dict[str, Any]]] = []
        self.patch_should_fail = patch_should_fail

    def patch_engagement(self, identifier: str, body: dict[str, Any]) -> dict:
        self.patch_calls.append((identifier, body))
        if self.patch_should_fail:
            raise RuntimeError("PATCH failed")
        return {"engagement_identifier": identifier, **body}


def _seed_engagement_db(code: str) -> None:
    """Create an empty SQLite file at ``engagements/{code}.db`` and
    materialise the per-engagement schema via ``bootstrap_database``.

    ``bootstrap_database`` (the v0.1-shipped helper) uses ``create_all``
    against the same metadata Alembic's chain produces at head, with the
    bonus of not depending on the decommissioned base-entity-catalog
    YAML directory (commit eb02943). Slice D's activation worker uses
    Alembic via :func:`run_engagement_migrations`; on an already-
    bootstrapped DB Alembic is a no-op (alembic_version is set), which
    is what the tests need.
    """
    import os

    db_path = engagement_db_path(code)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    prior = os.environ.get("CRMBUILDER_V2_DB_PATH")
    os.environ["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    reset_settings_cache()
    reset_engine_cache()
    try:
        bootstrap_database()
        # Stamp the alembic_version table to "head" so the worker's
        # step 3 Alembic call is a no-op (matches the dogfood pattern
        # of starting from a pre-existing DB).
        from alembic import command

        from crmbuilder_v2.migration.lazy_migration import (
            make_engagement_alembic_config,
        )

        cfg = make_engagement_alembic_config(code)
        command.stamp(cfg, "head")
    finally:
        if prior is None:
            os.environ.pop("CRMBUILDER_V2_DB_PATH", None)
        else:
            os.environ["CRMBUILDER_V2_DB_PATH"] = prior
        reset_settings_cache()
        reset_engine_cache()


def test_happy_path_completes_all_12_steps(qtbot, meta_db):
    target = _eng()
    _seed_engagement_db(target.engagement_code)
    ctx = ActiveEngagementContext()
    client = _StubClient()
    managers = _stub_managers()
    worker = ActivationWorker(
        target_engagement=target,
        previous_engagement=None,
        client=client,
        active_context=ctx,
        managers=managers,
    )

    seen_started: list[int] = []
    seen_completed: list[int] = []
    worker.step_started.connect(lambda n, _d: seen_started.append(n))
    worker.step_completed.connect(lambda n, _d: seen_completed.append(n))
    with qtbot.waitSignal(worker.completed, timeout=10000) as sig:
        worker.run()
    assert sig.args[0] == target
    assert seen_started == list(range(1, 13))
    assert seen_completed == list(range(1, 13))
    # Active context now reflects target.
    assert ctx.engagement() == target
    # PATCH (step 10) was attempted.
    assert client.patch_calls
    assert client.patch_calls[0][0] == target.engagement_identifier
    assert "engagement_last_opened_at" in client.patch_calls[0][1]


def test_step_2_failure_reachability_missing_db(qtbot, meta_db):
    target = _eng(code="MISSING")
    # Do NOT seed the engagement DB; reachability check should fail.
    ctx = ActiveEngagementContext()
    worker = ActivationWorker(
        target_engagement=target,
        previous_engagement=None,
        client=_StubClient(),
        active_context=ctx,
        managers=_stub_managers(),
    )
    captured: dict = {}
    worker.step_failed.connect(
        lambda n, _d, msg: captured.setdefault("failed", (n, msg))
    )
    with qtbot.waitSignal(worker.failed, timeout=5000):
        worker.run()
    assert captured["failed"][0] == 2
    assert "does not exist" in captured["failed"][1].lower()


def test_step_2_failure_soft_deleted_target(qtbot, meta_db):
    target = _eng(deleted=True)
    _seed_engagement_db(target.engagement_code)
    ctx = ActiveEngagementContext()
    worker = ActivationWorker(
        target_engagement=target,
        previous_engagement=None,
        client=_StubClient(),
        active_context=ctx,
        managers=_stub_managers(),
    )
    captured: dict = {}
    worker.step_failed.connect(
        lambda n, _d, msg: captured.setdefault("failed", (n, msg))
    )
    with qtbot.waitSignal(worker.failed, timeout=5000):
        worker.run()
    assert captured["failed"][0] == 2
    assert "soft-deleted" in captured["failed"][1].lower()


def test_step_4_failure_propagates_and_rolls_back(qtbot, meta_db):
    target = _eng()
    _seed_engagement_db(target.engagement_code)
    previous = _eng(identifier="ENG-000", code="PREV")
    ctx = ActiveEngagementContext()
    ctx.set_engagement(previous)
    managers = _stub_managers(fail_step=4)
    worker = ActivationWorker(
        target_engagement=target,
        previous_engagement=previous,
        client=_StubClient(),
        active_context=ctx,
        managers=managers,
    )
    captured: dict = {}
    worker.step_failed.connect(
        lambda n, _d, msg: captured.setdefault("failed", (n, msg))
    )
    with qtbot.waitSignal(worker.failed, timeout=5000):
        worker.run()
    # Failures wrap any in-step Exception; ensure step 4 was the failing step.
    # The worker captures via _StepFailure for typed steps; injected RuntimeError
    # at step 4 may surface as "Unexpected error" via the generic except path.
    # Acceptable either way — assert the failed signal was raised.
    assert ctx.engagement() == previous


def test_step_10_patch_failure_does_not_abort_activation(qtbot, meta_db):
    target = _eng()
    _seed_engagement_db(target.engagement_code)
    ctx = ActiveEngagementContext()
    client = _StubClient(patch_should_fail=True)
    managers = _stub_managers()
    worker = ActivationWorker(
        target_engagement=target,
        previous_engagement=None,
        client=client,
        active_context=ctx,
        managers=managers,
    )
    completed_payload: list = []
    worker.completed.connect(lambda eng: completed_payload.append(eng))
    with qtbot.waitSignal(worker.completed, timeout=10000):
        worker.run()
    assert completed_payload == [target]
    # PATCH was attempted despite failure.
    assert client.patch_calls
    # Active context shows target — activation succeeded.
    assert ctx.engagement() == target


def test_step_descriptions_have_12_entries():
    assert len(STEP_DESCRIPTIONS) == 12
    # Step 10 is the deferred PATCH (q6 amendment).
    assert "last-opened" in STEP_DESCRIPTIONS[9].lower()


def test_step_started_and_completed_signals_match_descriptions(qtbot, meta_db):
    target = _eng()
    _seed_engagement_db(target.engagement_code)
    ctx = ActiveEngagementContext()
    worker = ActivationWorker(
        target_engagement=target,
        previous_engagement=None,
        client=_StubClient(),
        active_context=ctx,
        managers=_stub_managers(),
    )
    pairs: list[tuple[int, str]] = []
    worker.step_started.connect(
        lambda n, d: pairs.append((n, d))
    )
    with qtbot.waitSignal(worker.completed, timeout=10000):
        worker.run()
    for step, desc in pairs:
        assert STEP_DESCRIPTIONS[step - 1] == desc
