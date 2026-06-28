"""Scan local skill-definition files into the registry (REQ-421 / PI-362).

A user-initiated *system scan* discovers skill definitions stored as local files
— the Claude Code ``SKILL.md`` form (a directory holding a ``SKILL.md`` with YAML
frontmatter carrying ``name`` + ``description`` over a markdown body) — and
imports each as a registry :class:`skill` (``SKL-``) record. Skills are registry
entities in the database, not loose files; this scan is the bridge that brings
locally-authored definitions in.

The scan is **idempotent by skill name**: a definition whose ``name`` already
names a skill in the registry is skipped, so re-running the scan creates no
duplicates. It returns a found / imported / skipped / errors summary with
per-file detail, which the desktop surfaces to the operator.

Imported skills are created as ``kind="instruction"`` at system scope by default
(``scope=None`` → ``engagement_id`` NULL), their instruction text being the
frontmatter description followed by the markdown body.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from crmbuilder_v2.access.repositories import skills

_log = logging.getLogger(__name__)

# The repo root is four parents up from this file
# (access → crmbuilder_v2 → src → crmbuilder-v2 → <repo>).
_REPO_ROOT = Path(__file__).resolve().parents[4]


def default_roots() -> list[Path]:
    """The local roots searched when the caller names none.

    The two homes the Claude Code harness reads ``SKILL.md`` from: the repo's
    project skills (``<repo>/.claude/skills``) and the user's personal skills
    (``~/.claude/skills``).
    """
    return [
        _REPO_ROOT / ".claude" / "skills",
        Path.home() / ".claude" / "skills",
    ]


@dataclass(frozen=True)
class ParsedSkill:
    """One parsed ``SKILL.md`` definition."""

    name: str
    description: str  # the frontmatter trigger description
    body: str  # the markdown instruction body
    source_path: Path

    def instruction(self) -> str:
        """The skill's instruction text: the trigger description then the body.

        Lossless — keeps the frontmatter "when to use" trigger alongside the
        instructions so nothing in the file is dropped on import.
        """
        desc = self.description.strip()
        body = self.body.strip()
        if desc and body:
            return f"{desc}\n\n{body}"
        return desc or body


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split ``---`` YAML frontmatter from the markdown body.

    Returns ``(frontmatter, body)``; ``frontmatter`` is empty when the file has
    no leading ``---`` fence (or no closing fence), in which case the whole text
    is the body.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1 :])
    return "", text  # no closing fence — treat as bodyless frontmatter


def parse_skill_file(path: Path) -> ParsedSkill:
    """Parse a ``SKILL.md`` file into a :class:`ParsedSkill`.

    A missing/blank frontmatter ``name`` falls back to the skill's directory
    name, which is the harness's own convention for a skill's identity.
    """
    text = Path(path).read_text(encoding="utf-8")
    front, body = _split_frontmatter(text)
    meta: Any = yaml.safe_load(front) if front.strip() else {}
    if not isinstance(meta, dict):
        meta = {}
    name = str(meta.get("name") or "").strip() or Path(path).parent.name
    description = str(meta.get("description") or "").strip()
    return ParsedSkill(
        name=name, description=description, body=body, source_path=Path(path)
    )


def discover_skill_files(roots: list[Path]) -> list[Path]:
    """Find every ``SKILL.md`` under the given roots (de-duplicated, sorted).

    Walks each root recursively, so both ``<root>/<skill>/SKILL.md`` and any
    deeper plugin layout are found. Roots that don't exist are silently skipped.
    """
    found: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for skill_md in sorted(root.rglob("SKILL.md")):
            resolved = skill_md.resolve()
            if resolved not in seen:
                seen.add(resolved)
                found.append(skill_md)
    return found


def scan_and_import(
    session: Session,
    *,
    roots: list[str] | list[Path] | None = None,
    scope: str | None = None,
) -> dict[str, Any]:
    """Discover local ``SKILL.md`` definitions and import each as a registry skill.

    :param session: open SQLAlchemy session.
    :param roots: local directories to search; defaults to :func:`default_roots`.
    :param scope: target skill scope — ``None`` (default) creates system skills;
        an engagement code/identifier creates engagement-scoped overlays.
    :returns: a summary ``{roots, found, imported, skipped, errors, counts}``,
        where ``imported`` / ``skipped`` / ``errors`` are per-file detail lists.
        Idempotent: a definition whose ``name`` already names a skill in the
        registry is reported under ``skipped``, never duplicated.
    """
    search_roots = [Path(r) for r in roots] if roots else default_roots()
    files = discover_skill_files(search_roots)

    # Idempotency is by skill name across the registry — a name already present
    # is left alone so a re-scan adds nothing. ``scope=None`` lists all skills.
    existing_names = {s["name"] for s in skills.list_all(session)}

    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_this_run: set[str] = set()

    for path in files:
        try:
            parsed = parse_skill_file(path)
        except Exception as exc:  # noqa: BLE001 — one bad file must not abort the scan
            _log.warning("could not parse skill file %s: %s", path, exc)
            errors.append({"path": str(path), "error": str(exc)})
            continue

        name = parsed.name
        if name in existing_names or name in seen_this_run:
            skipped.append(
                {"name": name, "path": str(path), "reason": "already in registry"}
            )
            continue

        instruction = parsed.instruction()
        if not instruction:
            errors.append(
                {"path": str(path), "name": name, "error": "no skill content"}
            )
            continue

        try:
            created = skills.create(
                session,
                name=name,
                kind="instruction",
                description=instruction,
                scope=scope,
            )
        except Exception as exc:  # noqa: BLE001 — report and keep scanning
            _log.warning("could not import skill %r from %s: %s", name, path, exc)
            errors.append({"path": str(path), "name": name, "error": str(exc)})
            continue

        seen_this_run.add(name)
        imported.append(
            {"identifier": created["identifier"], "name": name, "path": str(path)}
        )

    return {
        "roots": [str(r) for r in search_roots],
        "found": len(files),
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "counts": {
            "found": len(files),
            "imported": len(imported),
            "skipped": len(skipped),
            "errors": len(errors),
        },
    }
