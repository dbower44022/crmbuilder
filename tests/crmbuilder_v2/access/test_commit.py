"""Commit repository tests — UI v0.8, PI-029 slice B.

Covers commit.md §3.7 acceptance criteria 4-11 plus the build-planning
decisions DEC-211 (derived endpoint scope), DEC-212 (parent_shas
updatable), DEC-213 (by-sha specifics), DEC-214 (sort params).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import commits as cm
from crmbuilder_v2.access.repositories import sessions as sr
from crmbuilder_v2.access.repositories import workstreams as ws


SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
SHA_AB = "ab" + "0" * 38
SHA_AC = "ac" + "0" * 38
SHA_AD = "ad" + "0" * 38

# A 200-800 char audience-facing summary required on every session
# (PI-074 / PI-075). Reused verbatim across the session fixtures.
_EXEC_SUMMARY = (
    "This planning item reconciles stale test fixtures with the current "
    "governance schema so the suite validates real behavior; it carries no "
    "production code change and exists purely to keep the regression net "
    "aligned with the PI-073 and PI-102 data-model decisions now in effect."
)


def _session(s, identifier="SES-001"):
    """Create a workstream + session and return the session identifier.

    Under the PI-073 redesign a commit's FK (``commit_session_id``)
    targets a SESSION, not a conversation. Each session needs exactly one
    outbound ``session_belongs_to_workstream`` edge to be valid.
    """
    wid = ws.create_workstream(
        s, name="WS " + identifier, purpose="p", description="d"
    )["workstream_identifier"]
    return sr.create_session(
        s, title="S " + identifier, description="d",
        medium="chat", executive_summary=_EXEC_SUMMARY,
        identifier=identifier,
        references=[{
            "source_type": "session", "source_id": identifier,
            "target_type": "workstream", "target_id": wid,
            "relationship": "session_belongs_to_workstream",
        }],
    )["session_identifier"]


def _make(s, sha=SHA_A, session_id="SES-001", **overrides):
    """Create a commit with sensible defaults; overrides win."""
    defaults = dict(
        sha=sha,
        message_first_line="first line",
        message_full="first line\n\nfull body",
        author_name="Doug Bower",
        author_email="doug@dougbower.com",
        committed_at="2026-05-23T20:45:12-04:00",
        repository="crmbuilder",
        parent_shas=["1" * 40],
        files_changed_count=3,
        session_id=session_id,
    )
    defaults.update(overrides)
    return cm.create_commit(s, **defaults)


# ---------------------------------------------------------------------------
# Acceptance criterion 4 — identifier collision rejection
# ---------------------------------------------------------------------------


def test_identifier_collision_rejected(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s)  # auto-assigns CM-0001
    with session_scope() as s, pytest.raises(ConflictError):
        _make(s, sha=SHA_B, identifier="CM-0001")


def test_autoassign_increments_with_four_digit_width(v2_env):
    with session_scope() as s:
        _session(s)
        r1 = _make(s, sha=SHA_A)
        r2 = _make(s, sha=SHA_B)
    assert r1["commit_identifier"] == "CM-0001"
    assert r2["commit_identifier"] == "CM-0002"


# ---------------------------------------------------------------------------
# Acceptance criterion 5 — commit_session_id FK existence
# ---------------------------------------------------------------------------


def test_session_must_exist(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _make(s, session_id="SES-999")
    assert exc.value.errors[0].code == "commit_session_id_not_found"


# ---------------------------------------------------------------------------
# Acceptance criterion 6 — commit_sha format validation
# ---------------------------------------------------------------------------


def test_sha_length_validation(v2_env):
    with session_scope() as s:
        _session(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _make(s, sha="a" * 39)
    assert exc.value.errors[0].code == "invalid_sha_format"
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, sha="a" * 41)


def test_sha_uppercase_rejected(v2_env):
    with session_scope() as s:
        _session(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, sha="A" * 40)


def test_sha_non_hex_rejected(v2_env):
    with session_scope() as s:
        _session(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, sha="g" * 40)


# ---------------------------------------------------------------------------
# Acceptance criterion 7 — commit_sha uniqueness across engagement
# ---------------------------------------------------------------------------


def test_sha_duplicate_rejected(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s, sha=SHA_A)
    with session_scope() as s, pytest.raises(ConflictError) as exc:
        _make(s, sha=SHA_A)
    assert "CM-0001" in str(exc.value)


def test_sha_uniqueness_includes_soft_deleted(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s, sha=SHA_A)
        cm.delete_commit(s, "CM-0001")
    with session_scope() as s, pytest.raises(ConflictError):
        _make(s, sha=SHA_A)


# ---------------------------------------------------------------------------
# Acceptance criterion 8 — commit_parent_shas array-shape validation
# ---------------------------------------------------------------------------


def test_parent_shas_initial_commit_empty_list(v2_env):
    with session_scope() as s:
        _session(s)
        r = _make(s, sha=SHA_A, parent_shas=[])
    assert r["commit_parent_shas"] == []


def test_parent_shas_single_normal_commit(v2_env):
    with session_scope() as s:
        _session(s)
        r = _make(s, sha=SHA_A, parent_shas=[SHA_B])
    assert r["commit_parent_shas"] == [SHA_B]


def test_parent_shas_merge_commit_two_parents(v2_env):
    with session_scope() as s:
        _session(s)
        r = _make(s, sha=SHA_A, parent_shas=[SHA_B, SHA_C])
    assert r["commit_parent_shas"] == [SHA_B, SHA_C]


def test_parent_shas_three_parents_rejected(v2_env):
    with session_scope() as s:
        _session(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _make(s, sha=SHA_A, parent_shas=[SHA_B, SHA_C, "d" * 40])
    assert exc.value.errors[0].code == "too_many_parents"


def test_parent_shas_per_element_format(v2_env):
    with session_scope() as s:
        _session(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _make(s, sha=SHA_A, parent_shas=["short"])
    assert exc.value.errors[0].code == "invalid_sha_format"


# ---------------------------------------------------------------------------
# Acceptance criterion 9 — commit_repository validation
# ---------------------------------------------------------------------------


def test_repository_empty_rejected(v2_env):
    with session_scope() as s:
        _session(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, sha=SHA_A, repository="")


def test_repository_whitespace_rejected(v2_env):
    with session_scope() as s:
        _session(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, sha=SHA_A, repository="bad repo")


def test_repository_path_separator_rejected(v2_env):
    with session_scope() as s:
        _session(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, sha=SHA_A, repository="org/repo")


def test_repository_scheme_rejected(v2_env):
    with session_scope() as s:
        _session(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, sha=SHA_A, repository="https://example.com/repo")


def test_repository_new_name_admitted(v2_env):
    with session_scope() as s:
        _session(s)
        r = _make(s, sha=SHA_A, repository="some-brand-new-repo-name")
    assert r["commit_repository"] == "some-brand-new-repo-name"


# ---------------------------------------------------------------------------
# Acceptance criterion 10 — by-sha four-case behavior (DEC-213)
# ---------------------------------------------------------------------------


def test_by_sha_full_hit(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s, sha=SHA_A)
    with session_scope() as s:
        result = cm.find_by_sha(s, SHA_A)
    assert isinstance(result, dict)
    assert result["commit_sha"] == SHA_A


def test_by_sha_unambiguous_prefix(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s, sha=SHA_A)
        _make(s, sha=SHA_B)
    with session_scope() as s:
        result = cm.find_by_sha(s, SHA_A[:8])
    assert isinstance(result, dict)
    assert result["commit_sha"] == SHA_A


def test_by_sha_ambiguous_returns_all_candidates(v2_env):
    sha1 = "abcd" + "0" * 36
    sha2 = "abcd" + "1" * 36
    sha3 = "abcd" + "2" * 36
    with session_scope() as s:
        _session(s)
        _make(s, sha=sha1)
        _make(s, sha=sha2)
        _make(s, sha=sha3)
    with session_scope() as s:
        result = cm.find_by_sha(s, "abcd")
    assert isinstance(result, list)
    assert set(result) == {sha1, sha2, sha3}


def test_by_sha_miss_returns_none(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s, sha=SHA_A)
    with session_scope() as s:
        result = cm.find_by_sha(s, "f" * 40)
    assert result is None


def test_by_sha_prefix_too_short(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cm.find_by_sha(s, "abc")
    assert exc.value.errors[0].code == "prefix_too_short"


def test_by_sha_uppercase_normalized(v2_env):
    """DEC-213(b): uppercase input is lowercased before query, not rejected."""
    with session_scope() as s:
        _session(s)
        _make(s, sha=SHA_A)
    with session_scope() as s:
        result = cm.find_by_sha(s, SHA_A.upper())
    assert isinstance(result, dict)
    assert result["commit_sha"] == SHA_A


def test_by_sha_excludes_soft_deleted_by_default(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s, sha=SHA_A)
        cm.delete_commit(s, "CM-0001")
    with session_scope() as s:
        result = cm.find_by_sha(s, SHA_A)
    assert result is None


def test_by_sha_includes_soft_deleted_when_requested(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s, sha=SHA_A)
        cm.delete_commit(s, "CM-0001")
    with session_scope() as s:
        result = cm.find_by_sha(s, SHA_A, include_deleted=True)
    assert isinstance(result, dict)
    assert result["commit_deleted_at"] is not None


# ---------------------------------------------------------------------------
# Acceptance criterion 11 — soft-delete and restore cycle
# ---------------------------------------------------------------------------


def test_soft_delete_excludes_from_list(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s)
    with session_scope() as s:
        cm.delete_commit(s, "CM-0001")
        assert len(cm.list_commits(s)) == 0
        assert len(cm.list_commits(s, include_deleted=True)) == 1
        assert cm.get_commit(s, "CM-0001") is None
        assert cm.get_commit(s, "CM-0001", include_deleted=True) is not None


def test_restore_returns_to_active(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s)
    with session_scope() as s:
        cm.delete_commit(s, "CM-0001")
        cm.restore_commit(s, "CM-0001")
        assert cm.get_commit(s, "CM-0001")["commit_deleted_at"] is None
        assert len(cm.list_commits(s)) == 1


def test_restore_on_live_record_rejected(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        cm.restore_commit(s, "CM-0001")


# ---------------------------------------------------------------------------
# DEC-212 — patch updatability for non-identity fields
# ---------------------------------------------------------------------------


def test_patch_parent_shas_updatable(v2_env):
    """DEC-212: commit_parent_shas IS updatable for administrative correction."""
    with session_scope() as s:
        _session(s)
        _make(s, parent_shas=[SHA_B])
    with session_scope() as s:
        cm.patch_commit(s, "CM-0001", commit_parent_shas=[SHA_C, SHA_B])
        r = cm.get_commit(s, "CM-0001")
    assert r["commit_parent_shas"] == [SHA_C, SHA_B]


def test_patch_files_changed_count_updatable(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s, files_changed_count=3)
    with session_scope() as s:
        cm.patch_commit(s, "CM-0001", commit_files_changed_count=5)
        r = cm.get_commit(s, "CM-0001")
    assert r["commit_files_changed_count"] == 5


def test_patch_session_id_updatable_with_existence_check(v2_env):
    with session_scope() as s:
        _session(s, "SES-001")
        _session(s, "SES-002")
        _make(s)
    with session_scope() as s:
        cm.patch_commit(s, "CM-0001", commit_session_id="SES-002")
        r = cm.get_commit(s, "CM-0001")
    assert r["commit_session_id"] == "SES-002"
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cm.patch_commit(s, "CM-0001", commit_session_id="SES-999")
    assert exc.value.errors[0].code == "commit_session_id_not_found"


def test_patch_identifier_rejected(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cm.patch_commit(s, "CM-0001", commit_identifier="CM-0099")
    assert exc.value.errors[0].code == "field_not_updatable"


def test_patch_sha_rejected(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s, sha=SHA_A)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cm.patch_commit(s, "CM-0001", commit_sha=SHA_B)
    assert exc.value.errors[0].code == "field_not_updatable"


# ---------------------------------------------------------------------------
# DEC-214 — list sort and order parameters
# ---------------------------------------------------------------------------


def test_list_default_sort_is_committed_at_desc(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s, sha=SHA_A, committed_at="2026-05-20T10:00:00-04:00")
        _make(s, sha=SHA_B, committed_at="2026-05-23T10:00:00-04:00")
        _make(s, sha=SHA_C, committed_at="2026-05-21T10:00:00-04:00")
    with session_scope() as s:
        rows = cm.list_commits(s)
    # Most recent first
    assert rows[0]["commit_sha"] == SHA_B
    assert rows[1]["commit_sha"] == SHA_C
    assert rows[2]["commit_sha"] == SHA_A


def test_list_sort_asc_reverses(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s, sha=SHA_A, committed_at="2026-05-20T10:00:00-04:00")
        _make(s, sha=SHA_B, committed_at="2026-05-23T10:00:00-04:00")
    with session_scope() as s:
        rows = cm.list_commits(s, order="asc")
    assert rows[0]["commit_sha"] == SHA_A
    assert rows[1]["commit_sha"] == SHA_B


def test_list_invalid_sort_column_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cm.list_commits(s, sort="commit_message_first_line")
    assert exc.value.errors[0].code == "invalid_sort_column"


def test_list_invalid_order_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cm.list_commits(s, order="sideways")
    assert exc.value.errors[0].code == "invalid_order"


def test_list_filter_by_repository(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s, sha=SHA_A, repository="crmbuilder")
        _make(s, sha=SHA_B, repository="ClevelandBusinessMentoring")
    with session_scope() as s:
        rows = cm.list_commits(s, commit_repository="crmbuilder")
    assert len(rows) == 1
    assert rows[0]["commit_sha"] == SHA_A


def test_list_filter_by_session(v2_env):
    with session_scope() as s:
        _session(s, "SES-001")
        _session(s, "SES-002")
        _make(s, sha=SHA_A, session_id="SES-001")
        _make(s, sha=SHA_B, session_id="SES-002")
    with session_scope() as s:
        rows = cm.list_commits(s, commit_session_id="SES-001")
    assert len(rows) == 1
    assert rows[0]["commit_sha"] == SHA_A


# ---------------------------------------------------------------------------
# Misc: next-identifier helper, embedded-newline guard, email guard
# ---------------------------------------------------------------------------


def test_next_identifier_empty_db(v2_env):
    with session_scope() as s:
        assert cm.next_commit_identifier(s) == "CM-0001"


def test_next_identifier_after_first_insert(v2_env):
    with session_scope() as s:
        _session(s)
        _make(s)
    with session_scope() as s:
        assert cm.next_commit_identifier(s) == "CM-0002"


def test_first_line_embedded_newline_rejected(v2_env):
    with session_scope() as s:
        _session(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _make(s, message_first_line="line one\nline two")
    assert exc.value.errors[0].code == "embedded_newline"


def test_author_email_without_at_rejected(v2_env):
    with session_scope() as s:
        _session(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, author_email="dougbower.com")
