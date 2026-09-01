"""Governance gate: store configuration is found from any checkout (REQ-555 / PI-457).

The gate's store address and token live in a gitignored data file inside the
maintained checkout. A linked ``git worktree`` has no such file, so the gate
used to fall back to a local development address — and reported real planning
items missing. It now looks in this checkout, then the main worktree, then a
per-user file; when nothing is found it says so and applies the mode.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crmbuilder_v2 import governance_gate
from crmbuilder_v2.governance_gate import (
    GateDecision,
    StoreConfigurationNotFound,
    _api_config,
    _emit,
    _env_file_candidates,
    guarded_evaluate,
)

CODE = ["crmbuilder-v2/src/crmbuilder_v2/x.py"]


@pytest.fixture
def no_env_vars(monkeypatch: pytest.MonkeyPatch):
    for var in (
        "CRMBUILDER_V2_API_BASE",
        "CRMBUILDER_V2_GATE_TOKEN",
        "CRMBUILDER_V2_GATE_ENGAGEMENT",
    ):
        monkeypatch.delenv(var, raising=False)


def test_candidates_cover_this_checkout_then_main_worktree_then_user(monkeypatch):
    monkeypatch.setattr(
        governance_gate, "_this_checkout_root", lambda: Path("/wt/linked")
    )
    monkeypatch.setattr(
        governance_gate, "_main_worktree_root", lambda: Path("/repo/main")
    )
    cands = _env_file_candidates()
    assert cands[0] == Path("/wt/linked/crmbuilder-v2/data/crmbuilder.env")
    assert cands[1] == Path("/repo/main/crmbuilder-v2/data/crmbuilder.env")
    assert cands[2] == Path("~/.config/crmbuilder/crmbuilder.env").expanduser()


def test_candidates_deduplicate_when_this_is_the_main_worktree(monkeypatch):
    monkeypatch.setattr(
        governance_gate, "_this_checkout_root", lambda: Path("/repo/main")
    )
    monkeypatch.setattr(
        governance_gate, "_main_worktree_root", lambda: Path("/repo/main")
    )
    cands = _env_file_candidates()
    assert cands.count(Path("/repo/main/crmbuilder-v2/data/crmbuilder.env")) == 1


def test_main_worktree_root_resolves_relative_common_dir(monkeypatch):
    def fake_git(*args: str) -> str:
        if args == ("rev-parse", "--git-common-dir"):
            return ".git\n"
        if args == ("rev-parse", "--show-toplevel"):
            return "/repo/main\n"
        raise AssertionError(args)

    monkeypatch.setattr(governance_gate, "_git", fake_git)
    assert governance_gate._main_worktree_root() == Path("/repo/main").resolve()


def test_main_worktree_root_from_a_linked_worktree(monkeypatch):
    def fake_git(*args: str) -> str:
        if args == ("rev-parse", "--git-common-dir"):
            return "/repo/main/.git\n"
        raise AssertionError(args)

    monkeypatch.setattr(governance_gate, "_git", fake_git)
    assert governance_gate._main_worktree_root() == Path("/repo/main").resolve()


def test_api_config_reads_the_main_worktree_env_file(
    tmp_path: Path, monkeypatch, no_env_vars
):
    env_file = tmp_path / "crmbuilder.env"
    env_file.write_text(
        "CRMBUILDER_V2_API_BASE_URL=https://store.example\n"
        "CRMBUILDER_V2_API_TOKEN=tok-from-main-worktree\n"
    )
    monkeypatch.setattr(
        governance_gate,
        "_env_file_candidates",
        lambda: [tmp_path / "missing-in-linked-worktree.env", env_file],
    )
    base, token, engagement = _api_config()
    assert base == "https://store.example"
    assert token == "tok-from-main-worktree"
    assert engagement  # a value is always supplied for the header


def test_api_config_raises_when_nothing_is_configured(
    tmp_path: Path, monkeypatch, no_env_vars
):
    monkeypatch.setattr(
        governance_gate, "_env_file_candidates", lambda: [tmp_path / "absent.env"]
    )
    with pytest.raises(StoreConfigurationNotFound) as exc:
        _api_config()
    # The message names where it looked, and no development address is implied.
    assert "absent.env" in str(exc.value)
    assert "127.0.0.1" not in str(exc.value)


def test_explicit_env_var_wins_without_any_file(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CRMBUILDER_V2_API_BASE", "https://explicit.example")
    monkeypatch.setenv("CRMBUILDER_V2_GATE_TOKEN", "t")
    monkeypatch.setenv("CRMBUILDER_V2_GATE_ENGAGEMENT", "ENG-001")
    monkeypatch.setattr(
        governance_gate, "_env_file_candidates", lambda: [tmp_path / "absent.env"]
    )
    assert _api_config() == ("https://explicit.example", "t", "ENG-001")


def test_guarded_evaluate_reports_missing_configuration_and_applies_mode():
    def unconfigured(path: str):
        raise StoreConfigurationNotFound("no crmbuilder.env found (looked in: /x)")

    warn = guarded_evaluate(
        "feat\n\nGoverned-By: PI-457", CODE, get_json=unconfigured, mode="warn"
    )
    assert warn.allow is True
    assert any("configuration not found" in w for w in warn.warnings)
    assert not any("unreachable" in w for w in warn.warnings)
    enforce = guarded_evaluate(
        "feat\n\nGoverned-By: PI-457", CODE, get_json=unconfigured, mode="enforce"
    )
    assert enforce.allow is False
    assert any("configuration not found" in r for r in enforce.reasons)


def test_emit_says_allowed_but_unvalidated_out_loud(capsys):
    d = GateDecision(
        allow=True,
        warnings=["governance store configuration not found (x) — cannot validate"],
    )
    assert _emit(d, "warn", context="commit-msg") == 0
    err = capsys.readouterr().err
    assert "[governance-gate] NOTE (commit-msg)" in err
    assert "configuration not found" in err


def test_emit_stays_silent_on_a_clean_pass(capsys):
    assert (
        _emit(
            GateDecision(allow=True, governed_pis=["PI-457"]),
            "warn",
            context="commit-msg",
        )
        == 0
    )
    assert capsys.readouterr().err == ""
