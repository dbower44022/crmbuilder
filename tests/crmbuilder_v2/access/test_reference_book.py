"""Reference book repository tests — UI v0.7 Slice A."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import reference_books as rb
from sqlalchemy import inspect


def _make(s, title="RB A", kind="schema_specification", **kw):
    return rb.create_reference_book(
        s, title=title, description="d", kind=kind,
        file_path="PRDs/x.md", **kw,
    )


def test_tables_exist(v2_env):
    names = inspect(get_engine()).get_table_names()
    assert "reference_books" in names
    assert "reference_book_versions" in names


def test_kind_enum_enforced(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, kind="not_a_kind")


def test_file_path_validation(v2_env):
    for bad in ("/abs.md", "../up.md", "https://x/y.md"):
        with session_scope() as s, pytest.raises(UnprocessableError):
            rb.create_reference_book(
                s, title="bad", description="d", kind="other", file_path=bad
            )


def test_versions_and_current_pointer(v2_env):
    with session_scope() as s:
        r = _make(s, versions=[
            {"version_label": "1.0", "version_date": "2026-05-11T00:00:00"}
        ])
        rid = r["reference_book_identifier"]
        assert r["reference_book_current_version_label"] == "1.0"
        rb.create_reference_book_version(
            s, rid, version_label="1.1", version_date="2026-05-12T00:00:00"
        )
        assert rb.get_reference_book(s, rid)[
            "reference_book_current_version_label"
        ] == "1.1"
        assert len(rb.list_reference_book_versions(s, rid)) == 2
        # duplicate label
        with pytest.raises(UnprocessableError):
            rb.create_reference_book_version(
                s, rid, version_label="1.0", version_date="2026-05-11T00:00:00"
            )


def test_version_at_in_force_query(v2_env):
    with session_scope() as s:
        r = _make(s, versions=[
            {"version_label": "1.0", "version_date": "2026-05-11T00:00:00"},
            {"version_label": "1.1", "version_date": "2026-05-12T00:00:00"},
        ])
        rid = r["reference_book_identifier"]
        assert rb.get_reference_book_version_at(s, rid, "2026-05-11")[
            "reference_book_version_label"
        ] == "1.0"
        assert rb.get_reference_book_version_at(s, rid, "2026-05-12")[
            "reference_book_version_label"
        ] == "1.1"
        assert rb.get_reference_book_version_at(s, rid, "2026-05-10") is None


def test_documentary_lifecycle_terminal(v2_env):
    with session_scope() as s:
        _make(s)
        rb.patch_reference_book(s, "RB-001", status="archived")
    with session_scope() as s, pytest.raises(StatusTransitionError):
        rb.patch_reference_book(s, "RB-001", status="active")


def test_supersession_requires_edge(v2_env):
    with session_scope() as s:
        _make(s, title="A")
        _make(s, title="B")  # RB-002
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        rb.patch_reference_book(s, "RB-001", status="superseded")
    assert exc.value.errors[0].code == "supersession_requires_successor_edge"
    with session_scope() as s:
        rb.patch_reference_book(
            s, "RB-001", status="superseded",
            references=[{
                "source_type": "reference_book", "source_id": "RB-001",
                "target_type": "reference_book", "target_id": "RB-002",
                "relationship": "supersedes",
            }],
        )
        assert rb.get_reference_book(s, "RB-001")["reference_book_status"] == "superseded"


def test_soft_delete_preserves_versions(v2_env):
    with session_scope() as s:
        r = _make(s, versions=[
            {"version_label": "1.0", "version_date": "2026-05-11T00:00:00"}
        ])
        rid = r["reference_book_identifier"]
        rb.delete_reference_book(s, rid)
        assert rb.get_reference_book(s, rid) is None
        rb.restore_reference_book(s, rid)
        assert len(rb.list_reference_book_versions(s, rid)) == 1


def test_list_kind_filter(v2_env):
    with session_scope() as s:
        _make(s, title="A", kind="schema_specification")
        _make(s, title="B", kind="product_requirements_document")
        assert len(rb.list_reference_books(s, kind="schema_specification")) == 1
