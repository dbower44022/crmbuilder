"""PI-031: Commits panel — browse, filters, by-SHA lookup, detail pane."""

from __future__ import annotations

from typing import Any

import httpx
from crmbuilder_v2.ui.panels.commits import CommitsPanel
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton

from .conftest import build_client, envelope_ok


def _commit(ident: str, sha: str, *, repo: str = "crmbuilder", session: str = "SES-118") -> dict[str, Any]:
    return {
        "commit_identifier": ident,
        "commit_sha": sha,
        "commit_message_first_line": f"msg {ident}",
        "commit_message_full": f"msg {ident}\n\nbody",
        "commit_author_name": "Doug Bower",
        "commit_author_email": "doug@dougbower.com",
        "commit_committed_at": "2026-05-29T23:04:42-04:00",
        "commit_repository": repo,
        "commit_branch": "main",
        "commit_parent_shas": ["abcdef1234"],
        "commit_files_changed_count": 4,
        "commit_session_id": session,
    }


_COMMITS = [
    _commit("CM-0052", "f690bde4f48c", repo="crmbuilder", session="SES-118"),
    _commit("CM-0044", "5beeaec78c5f", repo="otherrepo", session="SES-115"),
]


def _handler(commits=_COMMITS, *, by_sha=None):
    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if req.method == "GET" and path == "/commits":
            # honor server-side filters minimally for realism
            repo = req.url.params.get("commit_repository")
            recs = [c for c in commits if not repo or c["commit_repository"] == repo]
            return httpx.Response(200, json=envelope_ok(recs))
        if req.method == "GET" and path.startswith("/commits/by-sha/"):
            if by_sha is None:
                return httpx.Response(404, json={"detail": {"code": "x"}})
            status, body = by_sha
            return httpx.Response(status, json=body)
        if req.method == "GET" and path.startswith("/references/touching/commit/"):
            return httpx.Response(
                200, json=envelope_ok({"as_source": [], "as_target": []})
            )
        if req.method == "GET" and path.startswith("/commits/"):
            ident = path.rsplit("/", 1)[-1]
            for c in commits:
                if c["commit_identifier"] == ident:
                    return httpx.Response(200, json=envelope_ok(c))
            return httpx.Response(404, json={"data": None, "meta": {}, "errors": [{"code": "x"}]})
        return httpx.Response(404, json={"data": None, "meta": {}, "errors": [{"code": "x"}]})

    return handler


def test_columns_and_no_new_button(qtbot):
    panel = CommitsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    titles = [c.title for c in panel.list_columns()]
    assert titles == ["Identifier", "Repository", "Author", "Committed", "Message"]
    # Read-only: no New button.
    assert panel.findChild(QPushButton, "new_commit_button") is None


def test_committed_column_is_formatted(qtbot):
    panel = CommitsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    processed = panel._post_process_records([dict(c) for c in _COMMITS])
    assert processed[0]["commit_committed_display"] != _COMMITS[0]["commit_committed_at"]
    assert processed[0]["commit_committed_display"].count("-") >= 2


def test_repository_filter_composes(qtbot):
    panel = CommitsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    panel._post_process_records([dict(c) for c in _COMMITS])
    repo_combo = panel.findChild(type(panel._repo_filter), "commit_repository_filter")
    assert repo_combo is not None
    # Select the second repo and confirm only its commit survives.
    idx = repo_combo.findText("otherrepo")
    assert idx > 0
    repo_combo.setCurrentIndex(idx)
    assert [r["commit_identifier"] for r in panel._records] == ["CM-0044"]


def test_session_filter_composes(qtbot):
    panel = CommitsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    panel._post_process_records([dict(c) for c in _COMMITS])
    session_combo = panel.findChild(type(panel._session_filter), "commit_session_filter")
    idx = session_combo.findText("SES-115")
    session_combo.setCurrentIndex(idx)
    assert [r["commit_identifier"] for r in panel._records] == ["CM-0044"]


def test_by_sha_found_selects_record(qtbot):
    by_sha = (200, envelope_ok(_COMMITS[0]))
    panel = CommitsPanel(build_client(_handler(by_sha=by_sha)))
    qtbot.addWidget(panel)
    panel._post_process_records([dict(c) for c in _COMMITS])
    panel._sha_input.setText("f690bde4")
    panel._on_sha_lookup()
    assert "CM-0052" in panel._sha_status.text()


def test_by_sha_not_found_inline(qtbot):
    panel = CommitsPanel(build_client(_handler(by_sha=(404, {"detail": {"code": "miss"}}))))
    qtbot.addWidget(panel)
    panel._sha_input.setText("deadbeef")
    panel._on_sha_lookup()
    assert "No commit matches" in panel._sha_status.text()


def test_by_sha_ambiguous_lists_candidates(qtbot):
    body = {"detail": {"code": "ambiguous_sha_prefix", "candidates": ["aaaa1111", "aaaa2222"]}}
    panel = CommitsPanel(build_client(_handler(by_sha=(409, body))))
    qtbot.addWidget(panel)
    panel._sha_input.setText("aaaa")
    panel._on_sha_lookup()
    assert "Ambiguous" in panel._sha_status.text()
    assert "2 matches" in panel._sha_status.text()


def test_by_sha_too_short(qtbot):
    panel = CommitsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    panel._sha_input.setText("ab")
    panel._on_sha_lookup()
    assert "at least 4" in panel._sha_status.text()


def test_detail_pane_renders_producing_session_link(qtbot):
    panel = CommitsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(
        _COMMITS[0], {"references": {"as_source": [], "as_target": []}}
    )
    link = detail.findChild(QLabel, "commit_producing_session_link")
    assert link is not None
    assert 'href="session:SES-118"' in link.text()
    # SHA and message present somewhere in the detail.
    line_edits = [w.text() for w in detail.findChildren(QLineEdit)]
    assert "f690bde4f48c" in line_edits


def test_detail_pane_references_add_affordance_disabled(qtbot):
    panel = CommitsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(
        _COMMITS[0], {"references": {"as_source": [], "as_target": []}}
    )
    add_btn = detail.findChild(QPushButton, "references_section_add_button")
    # Commits are ingested via close-out (DEC-185): the Add affordance is
    # suppressed. It exists (client supplied) but is hidden.
    assert add_btn is not None
    assert add_btn.isHidden()
