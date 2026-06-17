"""Resource-lock tests — PI-203 (PRJ-030), §7.3 FL-1..FL-6.

Covers crmbuilder_v2.access.locks: detection rules, acquire (idempotent / forced
serial / re-acquire), all-or-nothing acquire_many, release/release_all, verify
(retroactive acquire + conflict report), and reclaim / reclaim_stale (TTL).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from crmbuilder_v2.access import locks
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from sqlalchemy import inspect


def test_table_shape(v2_env):
    cols = {c["name"] for c in inspect(get_engine()).get_columns("resource_locks")}
    assert cols == {
        "id", "engagement_id", "resource_name", "holder", "acquired_at",
        "released_at",
    }


def test_detect_resources_logical():
    out = locks.detect_resources(
        ["crmbuilder-v2/migrations/versions/0099_x.py", "espo_impl/core/models.py"]
    )
    assert "migration-chain" in out
    assert "espo_impl/core/models.py" in out
    assert "espo_impl/core/models.py" not in locks.detect_resources([]) and \
        "migration-chain" not in locks.detect_resources(["espo_impl/core/models.py"])


def test_acquire_idempotent_and_forced_serial(v2_env):
    with session_scope() as s:
        locks.acquire(s, "a.py", "agent-1")
        # same holder is idempotent
        assert locks.acquire(s, "a.py", "agent-1")["holder"] == "agent-1"
        # another holder is refused (forced serial)
        with pytest.raises(ConflictError, match="held by"):
            locks.acquire(s, "a.py", "agent-2")


def test_release_then_reacquire(v2_env):
    with session_scope() as s:
        locks.acquire(s, "a.py", "agent-1")
        locks.release(s, "a.py", "agent-1")
        # now another agent can take it
        assert locks.acquire(s, "a.py", "agent-2")["holder"] == "agent-2"


def test_release_holder_only(v2_env):
    with session_scope() as s:
        locks.acquire(s, "a.py", "agent-1")
        with pytest.raises(ConflictError, match="only the holder"):
            locks.release(s, "a.py", "agent-2")


def test_acquire_many_all_or_nothing(v2_env):
    with session_scope() as s:
        locks.acquire(s, "b.py", "agent-2")  # pre-held by another
        with pytest.raises(ConflictError):
            locks.acquire_many(s, ["a.py", "b.py", "c.py"], "agent-1")
        # none of agent-1's were left held
        assert locks.held_locks(s, holder="agent-1") == []


def test_verify_retroactive_and_conflict(v2_env):
    with session_scope() as s:
        locks.acquire(s, "declared.py", "agent-1")
        locks.acquire(s, "owned-by-other.py", "agent-2")
        out = locks.verify(
            s, "agent-1",
            ["declared.py", "undeclared.py", "owned-by-other.py"],
        )
        assert out["held"] == ["declared.py"]
        assert out["retroactively_acquired"] == ["undeclared.py"]
        assert out["conflicts"] == [
            {"resource": "owned-by-other.py", "holder": "agent-2"}
        ]


def test_reclaim_releases_dead_holder(v2_env):
    with session_scope() as s:
        locks.acquire(s, "a.py", "dead")
        locks.acquire(s, "b.py", "dead")
        reclaimed = locks.reclaim(s, "dead")
        assert len(reclaimed) == 2
        assert locks.held_locks(s, holder="dead") == []


def test_reclaim_stale_ttl(v2_env):
    from crmbuilder_v2.access.models import ResourceLock

    with session_scope() as s:
        locks.acquire(s, "old.py", "agent-1")
        locks.acquire(s, "fresh.py", "agent-1")
        # backdate one lock past the TTL
        row = s.query(ResourceLock).filter(
            ResourceLock.resource_name == "old.py"
        ).first()
        row.acquired_at = datetime.now(UTC) - timedelta(hours=2)
        s.flush()
        stale = locks.reclaim_stale(s, ttl_seconds=3600)
        assert [r["resource_name"] for r in stale] == ["old.py"]
        assert {r["resource_name"] for r in locks.held_locks(s)} == {"fresh.py"}
