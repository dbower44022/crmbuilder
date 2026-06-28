"""POST /skills/scan — import local SKILL.md definitions (REQ-421 / PI-362).

Uses the shared ``client`` fixture (TestClient with X-Engagement: ENG-001).
"""

from __future__ import annotations

from pathlib import Path


def _write_skill(root: Path, slug: str, name: str) -> None:
    folder = root / slug
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Trigger for {name}.\n---\n\nBody of {name}.\n",
        encoding="utf-8",
    )


def test_scan_endpoint_imports_and_is_idempotent(client, tmp_path):
    _write_skill(tmp_path, "alpha", "skill-alpha")
    _write_skill(tmp_path, "beta", "skill-beta")

    resp = client.post("/skills/scan", json={"roots": [str(tmp_path)]})
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["counts"] == {"found": 2, "imported": 2, "skipped": 0, "errors": 0}

    # The imported skills are now real registry rows.
    names = {s["name"] for s in client.get("/skills").json()["data"]}
    assert {"skill-alpha", "skill-beta"} <= names

    # Re-scan creates no duplicates.
    again = client.post("/skills/scan", json={"roots": [str(tmp_path)]}).json()["data"]
    assert again["counts"]["imported"] == 0
    assert again["counts"]["skipped"] == 2


def test_scan_endpoint_accepts_empty_body(client):
    # No body → defaults (standard roots, system scope). It must not error even
    # when the default roots hold nothing unusual; we only assert the envelope.
    resp = client.post("/skills/scan")
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert set(data["counts"]) == {"found", "imported", "skipped", "errors"}
    assert "roots" in data
