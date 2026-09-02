"""Every migration chain has exactly one head — a commit-time fork guard.

Three chain forks arose in one day, each from a session computing its
``down_revision`` against a head that moved before it committed, and each
surfaced only when the next ten-minute chain walk refused with
``MultipleHeads``. This test walks the revision files directly — no database,
no alembic environment — so any suite slice catches a fork in seconds.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CHAINS = {
    "sqlite": _REPO_ROOT / "crmbuilder-v2" / "migrations" / "versions",
    "postgres": _REPO_ROOT / "crmbuilder-v2" / "migrations" / "pg" / "versions",
}

_ASSIGN_RE = re.compile(
    r"^(revision|down_revision)\s*(?::[^=]+)?=\s*(.+?)\s*$", re.MULTILINE
)


def _chain(directory: Path) -> dict[str, str | None]:
    """``{revision: down_revision}`` parsed from the chain's files."""
    graph: dict[str, str | None] = {}
    for path in sorted(directory.glob("[0-9]*.py")):
        found: dict[str, str | None] = {}
        for match in _ASSIGN_RE.finditer(path.read_text()):
            try:
                found[match.group(1)] = ast.literal_eval(match.group(2))
            except (ValueError, SyntaxError):
                continue
        assert "revision" in found, f"{path.name}: no revision assignment"
        assert "down_revision" in found, (
            f"{path.name}: no down_revision assignment"
        )
        assert found["revision"] not in graph, (
            f"duplicate revision id {found['revision']!r} ({path.name})"
        )
        graph[found["revision"]] = found["down_revision"]
    return graph


@pytest.mark.parametrize("chain", sorted(_CHAINS))
def test_the_chain_has_exactly_one_head(chain: str) -> None:
    graph = _chain(_CHAINS[chain])
    assert graph, f"{chain}: no migrations found"
    parents = {p for p in graph.values() if p is not None}
    missing = parents - set(graph)
    assert not missing, (
        f"{chain}: down_revision points at unknown revision(s): "
        f"{sorted(missing)}"
    )
    heads = sorted(set(graph) - parents)
    assert len(heads) == 1, (
        f"{chain}: {len(heads)} heads — {heads}. Two sessions took the same "
        "parent in parallel; re-point one down_revision at the other's head "
        "(renumbering the file to match) so the chain is linear again."
    )
