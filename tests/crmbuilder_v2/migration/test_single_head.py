"""The migration tree has exactly one head per branch — a commit-time fork guard.

Until PI-507 the tree was one line and this test asserted a single head, because
three forks arose in one day from sessions computing ``down_revision`` against a
head that moved before they committed. Since PI-507 (REQ-592 / DEC-1079) the
tree forks after the trunk into one labelled branch per owner of the
record-type-to-segment map, so the invariant is now: every branch label from
``version_info.BRANCH_LABELS`` has exactly one head, every head sits on exactly
one of those branches, and no unlabelled head exists. Two lanes that each add a
migration on *different* branches keep this true without renumbering; two on
the *same* branch that take the same parent still fork it, and this test still
catches that in seconds. It walks the revision files directly — no database,
no alembic environment.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from crmbuilder_v2.migration.version_info import BRANCH_LABELS

_REPO_ROOT = Path(__file__).resolve().parents[3]
VERSIONS = _REPO_ROOT / "crmbuilder-v2" / "migrations" / "pg" / "versions"
TRUNK_HEAD = "0097_pi_471_transitions"

_ASSIGN_RE = re.compile(
    r"^(revision|down_revision|branch_labels)\s*(?::[^=]+)?=\s*(.+?)\s*$",
    re.MULTILINE,
)


def _tree(directory: Path) -> tuple[dict[str, str | None], dict[str, str]]:
    """``({revision: down_revision}, {revision: branch_label})`` from the files."""
    graph: dict[str, str | None] = {}
    labels: dict[str, str] = {}
    for path in sorted(directory.glob("*.py")):
        if path.name == "__init__.py":
            continue
        found: dict[str, object] = {}
        for match in _ASSIGN_RE.finditer(path.read_text()):
            try:
                found[match.group(1)] = ast.literal_eval(match.group(2))
            except (ValueError, SyntaxError):
                continue
        assert "revision" in found, f"{path.name}: no revision assignment"
        assert "down_revision" in found, f"{path.name}: no down_revision assignment"
        rev = found["revision"]
        assert isinstance(rev, str)
        assert rev not in graph, f"duplicate revision id {rev!r} ({path.name})"
        graph[rev] = found["down_revision"]  # type: ignore[assignment]
        raw = found.get("branch_labels")
        if raw:
            names = (raw,) if isinstance(raw, str) else tuple(raw)
            assert len(names) == 1, f"{path.name}: one branch label per revision"
            labels[rev] = names[0]
    return graph, labels


def _branch_of(rev: str, graph: dict[str, str | None], labels: dict[str, str]) -> str | None:
    """The label of the branch ``rev`` sits on, walking down to the fork revision."""
    seen: set[str] = set()
    cur: str | None = rev
    while cur is not None and cur not in seen:
        seen.add(cur)
        if cur in labels:
            return labels[cur]
        cur = graph.get(cur)
    return None


def test_every_branch_has_exactly_one_head() -> None:
    graph, labels = _tree(VERSIONS)
    assert graph, "no migrations found"
    parents = {p for p in graph.values() if p is not None}
    missing = parents - set(graph)
    assert not missing, f"down_revision points at unknown revision(s): {sorted(missing)}"

    assert set(labels.values()) == set(BRANCH_LABELS), (
        "the branch labels in the tree must be exactly version_info.BRANCH_LABELS: "
        f"tree={sorted(set(labels.values()))} expected={sorted(BRANCH_LABELS)}"
    )
    forks = {rev for rev, lab in labels.items()}
    assert all(graph[f] == TRUNK_HEAD for f in forks), (
        f"every branch forks from the trunk head {TRUNK_HEAD}: "
        f"{ {f: graph[f] for f in forks} }"
    )

    heads = sorted(set(graph) - parents)
    by_branch: dict[str | None, list[str]] = {}
    for h in heads:
        by_branch.setdefault(_branch_of(h, graph, labels), []).append(h)

    assert None not in by_branch, (
        f"unlabelled head(s) {by_branch.get(None)}: a revision must sit on one of "
        f"the owner branches ({', '.join(BRANCH_LABELS)}); its down_revision "
        "must descend from that branch's *_0001_branch fork revision"
    )
    for label in BRANCH_LABELS:
        hs = by_branch.get(label, [])
        assert len(hs) == 1, (
            f"branch {label!r}: {len(hs)} heads — {hs}. Two sessions took the same "
            "parent on this branch; re-point one down_revision at the other's "
            "head (renumbering the file to match) so the branch is linear again."
        )


def test_branch_revisions_follow_the_naming_convention() -> None:
    """``<owner>_<nnnn>_<slug>``: the owner prefix names the branch the file is on."""
    graph, labels = _tree(VERSIONS)
    for rev in graph:
        branch = _branch_of(rev, graph, labels)
        if branch is None:
            assert re.fullmatch(r"\d{4}_[a-z0-9_]+", rev), f"trunk revision {rev!r}"
            continue
        assert re.fullmatch(rf"{branch}_\d{{4}}_[a-z0-9_]+", rev), (
            f"{rev!r} sits on branch {branch!r} but is not named "
            f"{branch}_<nnnn>_<slug>"
        )
