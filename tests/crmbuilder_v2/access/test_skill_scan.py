"""Local-skill scan → registry import (REQ-421 / PI-362).

Covers SKILL.md parsing, recursive discovery, and the idempotent-by-name import:
a new definition becomes one ``instruction`` skill, a re-scan adds nothing, and a
file whose name already names a skill is reported as skipped.
"""

from __future__ import annotations

from pathlib import Path

from crmbuilder_v2.access import skill_scan
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import skills


def _write_skill(root: Path, slug: str, *, name: str, description: str, body: str) -> Path:
    folder = root / slug
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "SKILL.md"
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return path


def test_parse_skill_file_splits_frontmatter_and_body(tmp_path):
    path = _write_skill(
        tmp_path, "grids", name="desktop-ui-grids",
        description="Standards for desktop grids.", body="# Grid rules\n\nUse model/view.",
    )
    parsed = skill_scan.parse_skill_file(path)
    assert parsed.name == "desktop-ui-grids"
    assert parsed.description == "Standards for desktop grids."
    assert "Use model/view." in parsed.body
    # Instruction text keeps both the trigger description and the body.
    assert parsed.instruction().startswith("Standards for desktop grids.")
    assert "Use model/view." in parsed.instruction()


def test_parse_falls_back_to_directory_name_when_name_missing(tmp_path):
    folder = tmp_path / "my-skill"
    folder.mkdir()
    (folder / "SKILL.md").write_text("# no frontmatter here\n\nbody", encoding="utf-8")
    parsed = skill_scan.parse_skill_file(folder / "SKILL.md")
    assert parsed.name == "my-skill"
    assert parsed.description == ""
    assert "body" in parsed.body


def test_discover_finds_skill_files_recursively(tmp_path):
    _write_skill(tmp_path, "a", name="a", description="d", body="b")
    _write_skill(tmp_path / "nested", "b", name="b", description="d", body="b")
    (tmp_path / "not-a-skill").mkdir()
    (tmp_path / "not-a-skill" / "README.md").write_text("x", encoding="utf-8")
    found = skill_scan.discover_skill_files([tmp_path])
    assert len(found) == 2
    assert all(p.name == "SKILL.md" for p in found)


def test_discover_skips_missing_roots(tmp_path):
    assert skill_scan.discover_skill_files([tmp_path / "does-not-exist"]) == []


def test_scan_imports_new_skills(v2_env, tmp_path):
    _write_skill(tmp_path, "one", name="skill-one", description="One.", body="Body one.")
    _write_skill(tmp_path, "two", name="skill-two", description="Two.", body="Body two.")
    with session_scope() as s:
        result = skill_scan.scan_and_import(s, roots=[str(tmp_path)])
    assert result["counts"] == {"found": 2, "imported": 2, "skipped": 0, "errors": 0}
    with session_scope() as s:
        rows = skills.list_all(s)
    by_name = {r["name"]: r for r in rows}
    assert set(by_name) == {"skill-one", "skill-two"}
    assert by_name["skill-one"]["kind"] == "instruction"
    assert by_name["skill-one"]["scope"] == "system"
    assert "Body one." in by_name["skill-one"]["description"]


def test_scan_is_idempotent_by_name(v2_env, tmp_path):
    _write_skill(tmp_path, "one", name="skill-one", description="One.", body="Body one.")
    with session_scope() as s:
        first = skill_scan.scan_and_import(s, roots=[str(tmp_path)])
    assert first["counts"]["imported"] == 1
    # Re-running adds nothing — the existing name is skipped, not duplicated.
    with session_scope() as s:
        second = skill_scan.scan_and_import(s, roots=[str(tmp_path)])
    assert second["counts"]["imported"] == 0
    assert second["counts"]["skipped"] == 1
    assert second["skipped"][0]["name"] == "skill-one"
    with session_scope() as s:
        assert len(skills.list_all(s)) == 1


def test_scan_skips_name_already_in_registry(v2_env, tmp_path):
    with session_scope() as s:
        skills.create(s, name="skill-one", kind="instruction", description="pre-existing")
    _write_skill(tmp_path, "one", name="skill-one", description="One.", body="Body one.")
    with session_scope() as s:
        result = skill_scan.scan_and_import(s, roots=[str(tmp_path)])
    assert result["counts"]["imported"] == 0
    assert result["counts"]["skipped"] == 1
    with session_scope() as s:
        assert len(skills.list_all(s)) == 1


def test_scan_reports_empty_content_as_error(v2_env, tmp_path):
    folder = tmp_path / "empty"
    folder.mkdir()
    (folder / "SKILL.md").write_text("---\nname: empty-skill\ndescription:\n---\n", encoding="utf-8")
    with session_scope() as s:
        result = skill_scan.scan_and_import(s, roots=[str(tmp_path)])
    assert result["counts"]["imported"] == 0
    assert result["counts"]["errors"] == 1
    assert result["errors"][0]["name"] == "empty-skill"
