"""Commit repository — the seventh governance entity type (UI v0.8, PI-029 slice B).

Per ``governance-schema-specs/commit.md`` v1.0. Status-free documentary
lifecycle — no status field, no transitions, soft-delete-with-restore as
the only state-change mechanism (DEC-198). FK column for the producing
conversation rather than references-edge per DEC-199's frequency
-justified deviation from DEC-124.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import asc, desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    get_by_identifier,
    next_prefixed_identifier,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Commit
from crmbuilder_v2.access.models import Session as SessionModel
from crmbuilder_v2.access.repositories import _governance as gov

_ENTITY_TYPE = "commit"
_IDENTIFIER_PREFIX = "CM"
_IDENTIFIER_RE = re.compile(r"^CM-\d{4}$")
_IDENTIFIER_WIDTH = 4
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA_PREFIX_RE = re.compile(r"^[0-9a-f]{4,40}$")  # for by-sha endpoint
_MIN_SHA_PREFIX_LENGTH = 4
_REPOSITORY_INVALID_CHARS_RE = re.compile(r"[\s/\\]")
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_MAX_AUTOASSIGN_ATTEMPTS = 50

_PATCHABLE_FIELDS = frozenset({
    "commit_message_first_line",
    "commit_message_full",
    "commit_author_name",
    "commit_author_email",
    "commit_committed_at",
    "commit_repository",
    "commit_branch",
    "commit_parent_shas",
    "commit_files_changed_count",
    "commit_session_id",
})

# columns that may appear in ?sort=<column>; locked to a known-safe set.
_SORTABLE_COLUMNS = frozenset({
    "commit_identifier",
    "commit_committed_at",
    "commit_repository",
    "commit_created_at",
    "commit_updated_at",
})


# ---------------------------------------------------------------------------
# Field validators
# ---------------------------------------------------------------------------


def _require_sha(value: object, *, field: str = "commit_sha") -> str:
    if not isinstance(value, str) or not _SHA_RE.match(value):
        raise UnprocessableError([
            FieldError(field, "invalid_sha_format",
                       "must be a lowercase 40-character hex SHA")
        ])
    return value


def _require_sha_prefix(value: object, *, field: str = "sha") -> str:
    """Validate input to the by-sha lookup endpoint.

    Accepts any prefix of length 4-40 of lowercase hex; lowercases the
    input before checking per DEC-213(b). Returns the lowercased prefix.
    """
    if not isinstance(value, str):
        raise UnprocessableError([
            FieldError(field, "invalid_sha_prefix",
                       "sha prefix must be a string")
        ])
    normalized = value.lower()
    if len(normalized) < _MIN_SHA_PREFIX_LENGTH:
        raise UnprocessableError([
            FieldError(field, "prefix_too_short",
                       f"sha prefix must be at least "
                       f"{_MIN_SHA_PREFIX_LENGTH} hex characters")
        ])
    if not _SHA_PREFIX_RE.match(normalized):
        raise UnprocessableError([
            FieldError(field, "invalid_sha_prefix",
                       "sha prefix must be lowercase hex (4-40 chars)")
        ])
    return normalized


def _require_parent_shas(value: object) -> list[str]:
    if not isinstance(value, list):
        raise UnprocessableError([
            FieldError("commit_parent_shas", "invalid_array",
                       "must be a JSON array of 0, 1, or 2 SHA strings")
        ])
    if len(value) > 2:
        raise UnprocessableError([
            FieldError("commit_parent_shas", "too_many_parents",
                       "merge commits have at most 2 parents; "
                       f"got {len(value)}")
        ])
    for idx, sha in enumerate(value):
        if not isinstance(sha, str) or not _SHA_RE.match(sha):
            raise UnprocessableError([
                FieldError(f"commit_parent_shas[{idx}]",
                           "invalid_sha_format",
                           "each parent must be a lowercase 40-char hex SHA")
            ])
    return list(value)


def _require_repository(value: object) -> str:
    repo = gov.require_nonempty(value, field="commit_repository")
    if _REPOSITORY_INVALID_CHARS_RE.search(repo):
        raise UnprocessableError([
            FieldError("commit_repository", "invalid_repository",
                       "must not contain whitespace or path separators")
        ])
    if _SCHEME_RE.match(repo):
        raise UnprocessableError([
            FieldError("commit_repository", "invalid_repository",
                       "must be a bare repo name, not a URL")
        ])
    return repo


def _require_session_exists(session: Session, session_id: str) -> None:
    if get_by_identifier(session, SessionModel, SessionModel.session_identifier, session_id) is None:
        raise UnprocessableError([
            FieldError("commit_session_id",
                       "commit_session_id_not_found",
                       f"session {session_id!r} does not exist")
        ])


def _require_files_changed_count(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise UnprocessableError([
            FieldError("commit_files_changed_count",
                       "invalid_count",
                       "must be a non-negative integer")
        ])
    return value


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_row(session: Session, identifier: str) -> Commit:
    row = get_by_identifier(session, Commit, Commit.commit_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:0{_IDENTIFIER_WIDTH}d}"


def _existing_for_sha(session: Session, sha: str) -> Commit | None:
    stmt = select(Commit).where(Commit.commit_sha == sha)
    return session.scalars(stmt).first()


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_commits(
    session: Session,
    *,
    include_deleted: bool = False,
    commit_repository: str | None = None,
    commit_session_id: str | None = None,
    sort: str = "commit_committed_at",
    order: str = "desc",
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    if sort not in _SORTABLE_COLUMNS:
        raise UnprocessableError([
            FieldError("sort", "invalid_sort_column",
                       f"must be one of {sorted(_SORTABLE_COLUMNS)}")
        ])
    if order not in ("asc", "desc"):
        raise UnprocessableError([
            FieldError("order", "invalid_order",
                       "must be 'asc' or 'desc'")
        ])
    direction = desc if order == "desc" else asc
    stmt = select(Commit).order_by(direction(getattr(Commit, sort)))
    if not include_deleted:
        stmt = stmt.where(Commit.commit_deleted_at.is_(None))
    if commit_repository is not None:
        stmt = stmt.where(Commit.commit_repository == commit_repository)
    if commit_session_id is not None:
        stmt = stmt.where(
            Commit.commit_session_id == commit_session_id
        )
    if offset:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_commit(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(session, Commit, Commit.commit_identifier, identifier)
    if row is None:
        return None
    if row.commit_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_commit_identifier(session: Session) -> str:
    identifiers = session.scalars(select(Commit.commit_identifier)).all()
    return next_prefixed_identifier(
        identifiers, _IDENTIFIER_PREFIX, width=_IDENTIFIER_WIDTH
    )


def find_by_sha(
    session: Session, sha_or_prefix: str, *, include_deleted: bool = False
) -> dict | list[str] | None:
    """Look up commit(s) by full SHA or prefix.

    Returns:
        - dict for an unambiguous hit (full SHA or unambiguous prefix)
        - list[str] of candidate full SHAs for an ambiguous-prefix hit
          (caller maps this to HTTP 409 at the router layer)
        - None for a miss (caller maps to HTTP 404)
    """
    normalized = _require_sha_prefix(sha_or_prefix)
    stmt = select(Commit).where(Commit.commit_sha.startswith(normalized))
    if not include_deleted:
        stmt = stmt.where(Commit.commit_deleted_at.is_(None))
    rows = list(session.scalars(stmt).all())
    if len(rows) == 0:
        return None
    if len(rows) == 1:
        return to_dict(rows[0])
    # ambiguous prefix
    return [r.commit_sha for r in rows]


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(
    identifier: str,
    sha: str,
    message_first_line: str,
    message_full: str,
    author_name: str,
    author_email: str,
    committed_at: str,
    repository: str,
    branch: str,
    parent_shas: list[str],
    files_changed_count: int,
    session_id: str,
) -> Commit:
    return Commit(
        commit_identifier=identifier,
        commit_sha=sha,
        commit_message_first_line=message_first_line,
        commit_message_full=message_full,
        commit_author_name=author_name,
        commit_author_email=author_email,
        commit_committed_at=committed_at,
        commit_repository=repository,
        commit_branch=branch,
        commit_parent_shas=parent_shas,
        commit_files_changed_count=files_changed_count,
        commit_session_id=session_id,
    )


def _insert_with_autoassign(session: Session, **kwargs) -> Commit:
    candidate = next_commit_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(identifier=candidate, **kwargs)
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            savepoint.rollback()
            # Distinguish identifier collision (rare; retry) from
            # sha uniqueness violation (caller's data issue; surface).
            msg = str(exc.orig).lower()
            if "commit_sha" in msg:
                existing = _existing_for_sha(session, kwargs["sha"])
                existing_id = (
                    existing.commit_identifier if existing else "unknown"
                )
                raise ConflictError(
                    f"commit_sha {kwargs['sha']!r} already exists "
                    f"(existing identifier: {existing_id})"
                ) from exc
            candidate = _increment_identifier(candidate)
            continue
        savepoint.commit()
        return row
    raise ConflictError(
        "could not assign a unique commit identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_commit(
    session: Session,
    *,
    sha: str,
    message_first_line: str,
    message_full: str,
    author_name: str,
    author_email: str,
    committed_at: str,
    repository: str,
    parent_shas: list,
    files_changed_count: int,
    session_id: str,
    branch: str = "main",
    identifier: str | None = None,
    references: list[dict] | None = None,
    timestamps: dict | None = None,
) -> dict:
    sha = _require_sha(sha)
    message_first_line = gov.require_nonempty(
        message_first_line, field="commit_message_first_line"
    )
    if "\n" in message_first_line or "\r" in message_first_line:
        raise UnprocessableError([
            FieldError("commit_message_first_line",
                       "embedded_newline",
                       "first line must not contain newlines")
        ])
    message_full = gov.require_nonempty(message_full, field="commit_message_full")
    author_name = gov.require_nonempty(author_name, field="commit_author_name")
    author_email = gov.require_nonempty(author_email, field="commit_author_email")
    if "@" not in author_email:
        raise UnprocessableError([
            FieldError("commit_author_email", "invalid_email",
                       "must contain '@'")
        ])
    committed_at = gov.require_nonempty(committed_at, field="commit_committed_at")
    repository = _require_repository(repository)
    branch = gov.require_nonempty(branch, field="commit_branch")
    parent_shas = _require_parent_shas(parent_shas)
    files_changed_count = _require_files_changed_count(files_changed_count)
    session_id = gov.require_nonempty(
        session_id, field="commit_session_id"
    )
    _require_session_exists(session, session_id)

    # SHA uniqueness pre-check for a clean error envelope; the DB CHECK
    # is the canonical guard, but pre-checking lets us return a 409 with
    # the existing identifier without trapping IntegrityError contextually.
    existing = _existing_for_sha(session, sha)
    if existing is not None:
        raise ConflictError(
            f"commit_sha {sha!r} already exists "
            f"(existing identifier: {existing.commit_identifier})"
        )

    row_kwargs = {
        "sha": sha,
        "message_first_line": message_first_line,
        "message_full": message_full,
        "author_name": author_name,
        "author_email": author_email,
        "committed_at": committed_at,
        "repository": repository,
        "branch": branch,
        "parent_shas": parent_shas,
        "files_changed_count": files_changed_count,
        "session_id": session_id,
    }

    if identifier is None:
        row = _insert_with_autoassign(session, **row_kwargs)
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE,
            field="commit_identifier", example="CM-0001",
        )
        if get_by_identifier(session, Commit, Commit.commit_identifier, identifier) is not None:
            raise ConflictError(f"commit {identifier!r} already exists")
        row = _new_row(identifier=identifier, **row_kwargs)
        session.add(row)
        session.flush()

    gov.apply_timestamps(row, timestamps)
    session.flush()
    gov.apply_reference_list(session, references)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.commit_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_commit(
    session: Session,
    identifier: str,
    *,
    commit_identifier: str | None = None,
    commit_sha: str | None = None,
    message_first_line: str | None = None,
    message_full: str | None = None,
    author_name: str | None = None,
    author_email: str | None = None,
    committed_at: str | None = None,
    repository: str | None = None,
    branch: str | None = None,
    parent_shas: list | None = None,
    files_changed_count: int | None = None,
    session_id: str | None = None,
    references: list[dict] | None = None,
) -> dict:
    row = _get_row(session, identifier)
    if commit_identifier is not None and commit_identifier != identifier:
        raise UnprocessableError([
            FieldError("commit_identifier", "path_mismatch",
                       "identifier in body must match the path")
        ])
    if commit_sha is not None and commit_sha != row.commit_sha:
        raise UnprocessableError([
            FieldError("commit_sha", "field_not_updatable",
                       "commit_sha is an identity field "
                       "and cannot be modified")
        ])
    before = to_dict(row)

    # Validate every field (PUT is full replace)
    message_first_line = gov.require_nonempty(
        message_first_line, field="commit_message_first_line"
    )
    if "\n" in message_first_line or "\r" in message_first_line:
        raise UnprocessableError([
            FieldError("commit_message_first_line",
                       "embedded_newline",
                       "first line must not contain newlines")
        ])
    message_full = gov.require_nonempty(message_full, field="commit_message_full")
    author_name = gov.require_nonempty(author_name, field="commit_author_name")
    author_email = gov.require_nonempty(author_email, field="commit_author_email")
    if "@" not in author_email:
        raise UnprocessableError([
            FieldError("commit_author_email", "invalid_email",
                       "must contain '@'")
        ])
    committed_at = gov.require_nonempty(committed_at, field="commit_committed_at")
    repository = _require_repository(repository)
    branch = gov.require_nonempty(branch, field="commit_branch")
    parent_shas = _require_parent_shas(parent_shas)
    files_changed_count = _require_files_changed_count(files_changed_count)
    session_id = gov.require_nonempty(
        session_id, field="commit_session_id"
    )
    if session_id != row.commit_session_id:
        _require_session_exists(session, session_id)

    row.commit_message_first_line = message_first_line
    row.commit_message_full = message_full
    row.commit_author_name = author_name
    row.commit_author_email = author_email
    row.commit_committed_at = committed_at
    row.commit_repository = repository
    row.commit_branch = branch
    row.commit_parent_shas = parent_shas
    row.commit_files_changed_count = files_changed_count
    row.commit_session_id = session_id
    session.flush()

    gov.apply_reference_list(session, references)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def patch_commit(
    session: Session,
    identifier: str,
    *,
    references: list[dict] | None = None,
    **fields,
) -> dict:
    # Reject attempts to patch identity fields
    if "commit_identifier" in fields:
        raise UnprocessableError([
            FieldError("commit_identifier", "field_not_updatable",
                       "commit_identifier is an identity field "
                       "and cannot be modified")
        ])
    if "commit_sha" in fields:
        raise UnprocessableError([
            FieldError("commit_sha", "field_not_updatable",
                       "commit_sha is an identity field "
                       "and cannot be modified")
        ])
    unknown = set(fields) - _PATCHABLE_FIELDS
    if unknown:
        raise UnprocessableError([
            FieldError("fields", "unknown_field",
                       f"unknown patchable fields: {sorted(unknown)}")
        ])
    row = _get_row(session, identifier)
    before = to_dict(row)

    if "commit_message_first_line" in fields:
        mfl = gov.require_nonempty(
            fields["commit_message_first_line"],
            field="commit_message_first_line",
        )
        if "\n" in mfl or "\r" in mfl:
            raise UnprocessableError([
                FieldError("commit_message_first_line",
                           "embedded_newline",
                           "first line must not contain newlines")
            ])
        row.commit_message_first_line = mfl
    if "commit_message_full" in fields:
        row.commit_message_full = gov.require_nonempty(
            fields["commit_message_full"], field="commit_message_full"
        )
    if "commit_author_name" in fields:
        row.commit_author_name = gov.require_nonempty(
            fields["commit_author_name"], field="commit_author_name"
        )
    if "commit_author_email" in fields:
        email = gov.require_nonempty(
            fields["commit_author_email"], field="commit_author_email"
        )
        if "@" not in email:
            raise UnprocessableError([
                FieldError("commit_author_email", "invalid_email",
                           "must contain '@'")
            ])
        row.commit_author_email = email
    if "commit_committed_at" in fields:
        row.commit_committed_at = gov.require_nonempty(
            fields["commit_committed_at"], field="commit_committed_at"
        )
    if "commit_repository" in fields:
        row.commit_repository = _require_repository(fields["commit_repository"])
    if "commit_branch" in fields:
        row.commit_branch = gov.require_nonempty(
            fields["commit_branch"], field="commit_branch"
        )
    if "commit_parent_shas" in fields:
        row.commit_parent_shas = _require_parent_shas(fields["commit_parent_shas"])
    if "commit_files_changed_count" in fields:
        row.commit_files_changed_count = _require_files_changed_count(
            fields["commit_files_changed_count"]
        )
    if "commit_session_id" in fields:
        conv_id = gov.require_nonempty(
            fields["commit_session_id"], field="commit_session_id"
        )
        if conv_id != row.commit_session_id:
            _require_session_exists(session, conv_id)
            row.commit_session_id = conv_id

    session.flush()
    gov.apply_reference_list(session, references)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def delete_commit(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.commit_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.commit_deleted_at = datetime.now(UTC)
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def restore_commit(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.commit_deleted_at is None:
        raise UnprocessableError([
            FieldError("commit_deleted_at", "not_deleted",
                       "commit is not soft-deleted")
        ])
    before = to_dict(row)
    row.commit_deleted_at = None
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after
