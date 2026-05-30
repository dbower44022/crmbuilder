"""Driver glue tests for the orchestrator (PI-081).

Two layers:

* The pure planning/rendering glue in ``run.py`` (no API, git, or
  subprocesses) — wave planning, plan summary, child-kickoff rendering.
* The live ``_execute`` dispatch glue, exercised with the API, git, and
  subprocess seams monkeypatched out (no real network, repo, or agents).

Loaded by file path so the script (which isn't on the package path) is
importable the same way the production CLI runs it.
"""

from __future__ import annotations

import importlib.util
import io
import sys
import types
from pathlib import Path

import pytest

_MOD = (
    Path(__file__).resolve().parents[3]
    / "crmbuilder-v2"
    / "scripts"
    / "orchestrator"
    / "run.py"
)
_spec = importlib.util.spec_from_file_location("orch_run", _MOD)
run = importlib.util.module_from_spec(_spec)
sys.modules["orch_run"] = run
_spec.loader.exec_module(run)


def _item(ident, area, **extra):
    base = {
        "identifier": ident,
        "title": f"title {ident}",
        "executive_summary": "exec summary",
        "area": area,
        "claimed_by": None,
    }
    base.update(extra)
    return base


_READY = {
    "batches": [
        {"depth": 0, "items": [_item("PI-001", ["v2-api"]), _item("PI-002", ["v2-ui"])]},
        {"depth": 1, "items": [_item("PI-003", ["v2-storage"])]},
    ],
    "cyclic": [],
    "warnings": [],
}


# ---------------------------------------------------------------------------
# Pure-core tests (no I/O)
# ---------------------------------------------------------------------------


def test_plan_waves_produces_disjoint_clusters():
    waves = run.plan_waves(_READY)
    assert [w.depth for w in waves] == [0, 1]
    # depth 0: two disjoint areas -> two parallel children
    assert len(waves[0].clusters) == 2
    # depth 1: one child
    assert len(waves[1].clusters) == 1


def test_summarize_plan_mentions_each_wave():
    waves = run.plan_waves(_READY)
    summary = run.summarize_plan(_READY, waves)
    assert "depth 0" in summary
    assert "depth 1" in summary
    assert "PI-001" in summary


def test_render_child_kickoff_matches_template_contract():
    waves = run.plan_waves(_READY)
    cluster = waves[0].clusters[0]
    body = run._load_template()
    text = run.render_child_kickoff(
        body,
        cluster=cluster,
        session_identifier="SES-200",
        conversation_identifier="CNV-200",
        orchestrator_conversation="CNV-199",
        branch_name="orch-wave0-child1",
        engagement_code="CRMBUILDER",
        workstream_identifier="WS-012",
        workstream_title="Parallel agent orchestrator",
        api_base="http://127.0.0.1:8765",
    )
    # The driver's substitution set must satisfy every template placeholder.
    assert "{{" not in text and "}}" not in text
    assert "SES-200" in text
    assert "ses_200.json" in text


def test_child_succeeded_predicate():
    assert run.child_succeeded(0, True) is True
    assert run.child_succeeded(1, True) is False
    assert run.child_succeeded(0, False) is False
    assert run.child_succeeded(None, True) is False


def test_child_branch_name_is_deterministic():
    assert run.child_branch_name(0, 1) == "orch-wave0-child1"
    assert run.child_branch_name(2, 3) == "orch-wave2-child3"


# ---------------------------------------------------------------------------
# Execute-glue harness
# ---------------------------------------------------------------------------


class _FakeProc:
    """Stand-in for subprocess.Popen — wait() returns a fixed exit code."""

    def __init__(self, code: int) -> None:
        self._code = code

    def wait(self) -> int:
        return self._code


class _FakeAPI:
    """Records every call and answers the endpoints ``_execute`` touches."""

    def __init__(self, events: list) -> None:
        self.events = events
        self._counters = {"session": 200, "conversation": 300}

    def __call__(self, method, api_base, path, *, json_body=None, params=None):
        self.events.append(("api", method, path, json_body))
        if method == "POST" and path == "/identifiers/reserve":
            et = json_body["entity_type"]
            n = self._counters[et]
            self._counters[et] += 1
            prefix = {"session": "SES", "conversation": "CNV"}[et]
            return 201, {"data": {"reserved": [f"{prefix}-{n}"], "head_after": ""}}
        if method == "POST" and path.endswith("/claim"):
            return 200, {"data": {}}
        if method == "POST" and path == "/sessions":
            return 201, {"data": {"session_identifier": json_body["session_identifier"]}}
        if method == "POST" and path == "/conversations":
            return 201, {
                "data": {"conversation_identifier": json_body["conversation_identifier"]}
            }
        if method == "PATCH":
            return 200, {"data": {}}
        if method == "POST" and path == "/references":
            return 201, {"data": {}}
        if method == "GET" and path.startswith("/sessions/"):
            sid = path.rsplit("/", 1)[-1]
            return 200, {"data": {"session_identifier": sid, "session_status": "complete"}}
        if method == "GET" and path.startswith("/planning-items/"):
            pid = path.rsplit("/", 1)[-1]
            return 200, {"data": {"identifier": pid, "status": "Resolved"}}
        return 200, {"data": {}}


def _args(**over):
    ns = types.SimpleNamespace(
        api_base="http://127.0.0.1:8765",
        engagement_code="CRMBUILDER",
        workstream="WS-012",
        max_depth=0,
        area=None,
    )
    for k, v in over.items():
        setattr(ns, k, v)
    return ns


def _wire(monkeypatch, tmp_path, *, ready, fail_branches=()):
    """Monkeypatch every I/O seam and return the shared event log."""
    events: list = []

    monkeypatch.setattr(run, "preflight", lambda *a, **k: None)
    monkeypatch.setattr(run, "_git", lambda *a, **k: "")
    monkeypatch.setattr(run, "fetch_ready_batches", lambda *a, **k: ready)
    monkeypatch.setattr(run, "_api", _FakeAPI(events))
    monkeypatch.setattr(run, "_WORKTREE_ROOT", tmp_path / "wt")
    monkeypatch.setattr(run, "_LOG_ROOT", tmp_path / "logs")
    monkeypatch.setattr(run, "_CLOSEOUT_DIR", tmp_path / "closeouts")

    def _fake_worktree(branch, path, *, base="origin/main"):
        events.append(("worktree", branch, base))
        Path(path).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(run, "_create_worktree", _fake_worktree)

    def _fake_spawn(kickoff_path, cwd, log_path):
        events.append(("spawn", str(cwd), Path(kickoff_path).name))
        code = 1 if any(fb in str(cwd) for fb in fail_branches) else 0
        return _FakeProc(code), io.StringIO()

    monkeypatch.setattr(run, "_spawn_child", _fake_spawn)

    def _fake_apply(payload_path, *, skip_validation=False):
        events.append(("apply", str(payload_path), skip_validation))
        return 0

    monkeypatch.setattr(run, "_run_apply", _fake_apply)
    return events


def _kinds(events):
    return [e[0] for e in events]


def _api_paths(events):
    return [(e[1], e[2]) for e in events if e[0] == "api"]


# ---------------------------------------------------------------------------
# Execute-glue tests
# ---------------------------------------------------------------------------


def test_execute_dispatches_one_child_per_cluster():
    """Two area-disjoint clusters in the depth-0 wave -> two children."""
    ready = {
        "batches": [
            {"depth": 0, "items": [_item("PI-001", ["v2-api"]), _item("PI-002", ["v2-ui"])]}
        ],
        "cyclic": [],
        "warnings": [],
    }

    with pytest.MonkeyPatch.context() as mp:
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        events = _wire(mp, tmp, ready=ready)
        rc = run._execute(_args())

    assert rc == 0
    # one worktree + one spawn per cluster
    assert _kinds(events).count("worktree") == 2
    assert _kinds(events).count("spawn") == 2
    # one orchestrator session + conversation created
    api = _api_paths(events)
    assert ("POST", "/sessions") in api
    assert ("POST", "/conversations") in api
    # the supervising close-out was applied once
    assert _kinds(events).count("apply") == 1


def test_execute_reserve_before_claim_before_spawn(tmp_path, monkeypatch):
    ready = {
        "batches": [{"depth": 0, "items": [_item("PI-001", ["v2-api"])]}],
        "cyclic": [],
        "warnings": [],
    }
    events = _wire(monkeypatch, tmp_path, ready=ready)
    rc = run._execute(_args())
    assert rc == 0

    # Ordering within the single child's dispatch: a reserve, then the
    # claim, then the worktree, then the spawn.
    seq = []
    for e in events:
        if e[0] == "api" and e[2] == "/identifiers/reserve":
            seq.append("reserve")
        elif e[0] == "api" and e[2].endswith("/claim"):
            seq.append("claim")
        elif e[0] == "worktree":
            seq.append("worktree")
        elif e[0] == "spawn":
            seq.append("spawn")
    # last reserve before the claim, claim before worktree before spawn
    claim_i = seq.index("claim")
    spawn_i = seq.index("spawn")
    wt_i = seq.index("worktree")
    assert seq[:claim_i].count("reserve") >= 1
    assert claim_i < wt_i < spawn_i


def test_execute_spawns_whole_wave_before_joining(tmp_path, monkeypatch):
    """Both children are spawned (Popen) before either is joined — i.e. the
    two spawns are adjacent, with no apply/edge interleaved between them."""
    ready = {
        "batches": [
            {"depth": 0, "items": [_item("PI-001", ["v2-api"]), _item("PI-002", ["v2-ui"])]}
        ],
        "cyclic": [],
        "warnings": [],
    }
    events = _wire(monkeypatch, tmp_path, ready=ready)
    rc = run._execute(_args())
    assert rc == 0
    spawn_idx = [i for i, e in enumerate(events) if e[0] == "spawn"]
    assert len(spawn_idx) == 2
    # Nothing from the join/verify/edge/apply phase happens between the two
    # spawns — the wave is fully dispatched first.
    between = events[spawn_idx[0] + 1 : spawn_idx[1]]
    assert all(e[0] != "apply" for e in between)
    assert all(
        not (e[0] == "api" and e[2] == "/references") for e in between
    )


def test_execute_records_one_orchestrates_edge_per_child(tmp_path, monkeypatch):
    ready = {
        "batches": [
            {"depth": 0, "items": [_item("PI-001", ["v2-api"]), _item("PI-002", ["v2-ui"])]}
        ],
        "cyclic": [],
        "warnings": [],
    }
    events = _wire(monkeypatch, tmp_path, ready=ready)
    rc = run._execute(_args())
    assert rc == 0
    orchestrates = [
        e
        for e in events
        if e[0] == "api"
        and e[2] == "/references"
        and (e[3] or {}).get("relationship") == "conversation_orchestrates_conversation"
    ]
    assert len(orchestrates) == 2
    # source is the orchestrator conversation, target each child conversation
    srcs = {(e[3] or {}).get("source_id") for e in orchestrates}
    assert len(srcs) == 1  # single orchestrator conversation
    tgts = {(e[3] or {}).get("target_id") for e in orchestrates}
    assert len(tgts) == 2  # two distinct children


def test_execute_halts_on_child_failure(tmp_path, monkeypatch):
    """A non-zero child exit halts the run: no further waves, no orchestrates
    edges, claims left in place (no release), non-zero return."""
    ready = {
        "batches": [
            {"depth": 0, "items": [_item("PI-001", ["v2-api"]), _item("PI-002", ["v2-ui"])]},
            {"depth": 1, "items": [_item("PI-003", ["v2-storage"])]},
        ],
        "cyclic": [],
        "warnings": [],
    }
    # child1 lives in the orch-wave0-child1 worktree -> force its exit code 1.
    events = _wire(
        monkeypatch, tmp_path, ready=ready, fail_branches=["orch-wave0-child1"]
    )
    rc = run._execute(_args(max_depth=None))

    assert rc == 1
    # No orchestrates edge written (the wave failed before edge recording).
    assert not [
        e
        for e in events
        if e[0] == "api"
        and e[2] == "/references"
        and (e[3] or {}).get("relationship") == "conversation_orchestrates_conversation"
    ]
    # No supervising close-out applied.
    assert _kinds(events).count("apply") == 0
    # The second wave's item (PI-003) was never claimed -> no further wave.
    claims = [
        e[2] for e in events if e[0] == "api" and e[2].endswith("/claim")
    ]
    assert "/planning-items/PI-003/claim" not in claims
    # Claims are never released on failure (forensic-hold).
    assert not [e for e in events if e[0] == "api" and e[2].endswith("/release")]
    # The orchestrator was moved to a terminal (cancelled) state.
    cancels = [
        e
        for e in events
        if e[0] == "api"
        and e[1] == "PATCH"
        and (e[3] or {}).get(
            "session_status", (e[3] or {}).get("conversation_status")
        )
        == "cancelled"
    ]
    assert cancels


def test_execute_second_wave_after_first_completes(tmp_path, monkeypatch):
    """Wave 1 is only dispatched after wave 0's edges are recorded."""
    ready = {
        "batches": [
            {"depth": 0, "items": [_item("PI-001", ["v2-api"]), _item("PI-002", ["v2-ui"])]},
            {"depth": 1, "items": [_item("PI-003", ["v2-storage"])]},
        ],
        "cyclic": [],
        "warnings": [],
    }
    events = _wire(monkeypatch, tmp_path, ready=ready)
    rc = run._execute(_args(max_depth=None))
    assert rc == 0
    # Three children total (2 in wave 0, 1 in wave 1).
    assert _kinds(events).count("spawn") == 3
    # The wave-1 worktree is created only after the first orchestrates edge.
    wave1_wt = next(
        i for i, e in enumerate(events) if e[0] == "worktree" and "wave1" in e[1]
    )
    first_edge = next(
        i
        for i, e in enumerate(events)
        if e[0] == "api"
        and e[2] == "/references"
        and (e[3] or {}).get("relationship") == "conversation_orchestrates_conversation"
    )
    assert first_edge < wave1_wt


def test_spawn_child_uses_skip_permissions(tmp_path, monkeypatch):
    """The real ``_spawn_child`` passes --dangerously-skip-permissions and
    runs in the child's worktree as cwd."""
    captured = {}

    class _Popen:
        def __init__(self, cmd, *, cwd, stdout, stderr, text):
            captured["cmd"] = cmd
            captured["cwd"] = cwd

        def wait(self):  # pragma: no cover - not used here
            return 0

    monkeypatch.setattr(run.subprocess, "Popen", _Popen)
    kickoff = tmp_path / "k.md"
    kickoff.write_text("hi", encoding="utf-8")
    proc, handle = run._spawn_child(kickoff, tmp_path / "tree", tmp_path / "log.log")
    handle.close()
    assert "--dangerously-skip-permissions" in captured["cmd"]
    assert captured["cmd"][0] == "claude"
    assert captured["cwd"] == str(tmp_path / "tree")
