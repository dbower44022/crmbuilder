# CLAUDE-CODE-PROMPT-pi-029-B-commit-access-layer-and-rest

**Last Updated:** 05-24-26 10:30
**Operating mode:** DETAIL
**Series:** pi-029 (commit entity schema migration and access layer)
**Slice:** B — access-layer repository + REST endpoints + Pydantic schemas + router registration + tests
**Predecessor:** Slice A (commit `9c1d3b7`) — landed migration 0012, the `Commit` ORM model in `models.py` (lines 918-1002), and the v0.8 `vocab.py` updates. Verified `commits` table exists in the CRMBUILDER engagement DB; verified `blocked_by` rows are present (REF-0357, REF-0358); verified no `blocks` rows remain.
**Status:** Ready to execute
**Companions:**
- `PRDs/product/crmbuilder-v2/governance-schema-specs/commit.md` v1.0 — authoritative entity schema. §3.2 (field validation), §3.4.3-§3.4.4 (correction posture, soft-delete), §3.5 (endpoints), §3.7 (acceptance criteria 4-11 are this slice's coverage gate), §3.8.1 (derived endpoints — settled by DEC-211 below).
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/work_tickets.py` (447 lines) — closest existing access-layer pattern. Mirror its structure for CRUD orchestration, identifier autoassign with savepoint retry, soft-delete-with-restore, and change-log `emit` calls.
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/_governance.py` — shared helpers. Use `require_nonempty`, `require_in`, `outbound_edges`, `inbound_edges`, `apply_reference_list`, `apply_timestamps` directly; do not duplicate.
- `crmbuilder-v2/src/crmbuilder_v2/api/routers/work_tickets.py` (122 lines) — closest existing router pattern.
- `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py` lines 654-684 — Pydantic v2 CreateIn / ReplaceIn / PatchIn pattern with `_Base` (extra="forbid").

---

## Purpose

Land the access-layer repository, REST endpoints, Pydantic schemas, router registration, and full test coverage for the `commit` entity type. After this slice the API can:

1. List commits with filtering on `?commit_repository=`, `?commit_conversation_id=`, `?include_deleted=true`, and accept `?sort=<column>&order=asc|desc` per V2 list-endpoint conventions, defaulting to `commit_committed_at` descending.
2. Fetch a single commit by its V2 identifier (`GET /commits/CM-NNNN`).
3. Fetch a single commit by its git-natural-key SHA — full 40-char or 4+ char prefix — at `GET /commits/by-sha/{sha}`, with HTTP 409 on ambiguous-prefix and HTTP 404 on miss.
4. Return the next available `CM-NNNN` identifier at `GET /commits/next-identifier`.
5. List every commit produced by a specific conversation at `GET /conversations/{conversation_identifier}/commits` — the **one new derived endpoint** this slice ships per DEC-211.
6. Create commits via POST with full-record body including client-side-assigned `commit_identifier` (per `commit.md` §3.5.2).
7. Replace via PUT, partially update via PATCH (with `commit_identifier` and `commit_sha` non-updatable; all other fields including `commit_parent_shas` and `commit_files_changed_count` updatable for the administrative-correction path per DEC-212).
8. Soft-delete via DELETE and restore via POST `/commits/{identifier}/restore`.

Test coverage hits every acceptance criterion 4-11 from `commit.md` §3.7 plus the per-question specifics resolved below.

This slice does NOT add:
- The Commits panel UI — that's PI-031.
- The `apply_close_out.py` integration that wires the new `commits` close-out payload section — that's PI-030.
- Historical commit back-fill — that's PI-033.
- The two-hop `GET /workstreams/{workstream_identifier}/commits` derived endpoint — explicitly deferred by DEC-211.

---

## Net Effect

After this slice:

**Files created:**
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/commits.py` — new repository module
- `crmbuilder-v2/src/crmbuilder_v2/api/routers/commits.py` — new REST router
- `tests/crmbuilder_v2/access/test_commit.py` — new access-layer tests
- `tests/crmbuilder_v2/api/test_commit_api.py` — new REST-endpoint tests

**Files modified:**
- `crmbuilder-v2/src/crmbuilder_v2/access/_helpers.py` — extend `next_prefixed_identifier()` to admit a `width` keyword argument (default 3, backward-compatible; commits pass `width=4`)
- `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py` — add `CommitCreateIn`, `CommitReplaceIn`, `CommitPatchIn`
- `crmbuilder-v2/src/crmbuilder_v2/api/main.py` — register `commits.router` in the governance-entities section
- `crmbuilder-v2/src/crmbuilder_v2/api/routers/conversations.py` — add the `GET /conversations/{conversation_identifier}/commits` sub-route (per DEC-211, the derived endpoint is mounted on the conversations router rather than the commits router so the URL path nests naturally under `/conversations`)

**Test count target:** ~35-45 new tests passing. The pre-slice baseline is 1391 passed + 3 skipped (per slice A's commit message). Post-slice expected ≥ 1425 passed.

**Path correction noted:** The PI-029 slice B kickoff prompt at `PRDs/product/crmbuilder-v2/pi-029-slice-b-commit-access-layer-and-rest-endpoints-kickoff.md` cited paths `crmbuilder-v2/src/crmbuilder_v2/access/commit.py` and `crmbuilder-v2/src/crmbuilder_v2/api/commits.py`. The actual repo convention places repository modules under `access/repositories/<entity>.py` (plural file name to match the table) and router modules under `api/routers/<entity>.py`. This prompt uses the correct paths.

---

## Pre-flight

```bash
# Working directory — Doug's local clone short name
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2 || cd ~/crmbuilder/crmbuilder-v2

# Confirm clean working tree
git status

# Git identity (Doug)
git config user.email "doug@dougbower.com"
git config user.name "Doug Bower"

# Pull latest from origin/main (the slice B kickoff and this prompt were
# pushed from the planning sandbox, plus any close-out applies that landed
# in the interim)
cd .. && git pull --rebase origin main && cd crmbuilder-v2

# Verify slice A is in place (migration applied, ORM model present)
python3 -c "
import sqlite3
conn = sqlite3.connect('data/engagements/CRMBUILDER.db')
cur = conn.cursor()
cur.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='commits'\")
assert cur.fetchone(), 'commits table missing — slice A did not land'
cur.execute('SELECT version_num FROM alembic_version')
print('alembic head:', cur.fetchone()[0])
cur.execute(\"SELECT COUNT(*) FROM refs WHERE relationship_kind='blocks'\")
assert cur.fetchone()[0] == 0, 'stray blocks rows — slice A migration incomplete'
cur.execute(\"SELECT COUNT(*) FROM refs WHERE relationship_kind='blocked_by'\")
print('blocked_by rows:', cur.fetchone()[0])
conn.close()
"
# Expect: alembic head 0012_v0_8_commits_and_blocked_by_rename
#         blocked_by rows 2 (REF-0357, REF-0358)

# RESTART the running crmbuilder-v2-api process to pick up the v0.8 vocab.
# Per slice A's commit message: PID 3226223 (or whatever the current PID
# is) is still holding pre-v0.8 vocab in memory and will reject writes
# against the new vocab terms until restarted. The DB schema change is
# durable; only the in-memory vocab cache needs refreshing.
pkill -f 'crmbuilder-v2-api' || true
sleep 1
uv run crmbuilder-v2-api &
sleep 2
curl -sf http://127.0.0.1:8765/health
# Expect: {"data": {"status": "ok"}, "meta": null, "errors": null}

# Confirm v0.8 vocab is loaded in the running API
curl -s http://127.0.0.1:8765/admin/vocab 2>/dev/null \
  | python3 -c "
import sys, json
try:
    body = json.load(sys.stdin)
    data = body.get('data', body)
    entity_types = data.get('entity_types', [])
    print('commit in ENTITY_TYPES:', 'commit' in entity_types)
    rels = data.get('relationship_kinds', [])
    print('blocked_by in REFERENCE_RELATIONSHIPS:', 'blocked_by' in rels)
    print('blocks in REFERENCE_RELATIONSHIPS:', 'blocks' in rels)
except Exception as e:
    # If /admin/vocab is not exposed, fall back to inspecting vocab.py
    # directly — the goal is just to confirm the in-memory vocab is fresh.
    print('admin/vocab not exposed; falling back to import check')
    import importlib, sys as _s
    _s.path.insert(0, 'src')
    v = importlib.import_module('crmbuilder_v2.access.vocab')
    print('commit in ENTITY_TYPES:', 'commit' in v.ENTITY_TYPES)
    print('blocked_by in REFERENCE_RELATIONSHIPS:', 'blocked_by' in v.REFERENCE_RELATIONSHIPS)
    print('blocks in REFERENCE_RELATIONSHIPS:', 'blocks' in v.REFERENCE_RELATIONSHIPS)
"
# Expect: commit in ENTITY_TYPES: True
#         blocked_by in REFERENCE_RELATIONSHIPS: True
#         blocks in REFERENCE_RELATIONSHIPS: False

# Pre-implementation test baseline
cd ~/Dropbox/Projects/crmbuilder
uv run pytest tests/crmbuilder_v2/ -q 2>&1 | tail -3
# Expect: 1391 passed + 3 skipped (or current baseline after intervening landings)
```

---

## Implementation

### Step 1 — Extend `next_prefixed_identifier` helper to accept a width parameter

**File:** `crmbuilder-v2/src/crmbuilder_v2/access/_helpers.py`

The existing helper hard-codes three-digit zero-padded suffixes (`:03d` at the format string). `commit.md` §3.5.3 requires four-digit zero-padded identifiers (`CM-NNNN`). Add a `width` keyword argument defaulting to 3 so all existing callers continue producing three-digit identifiers unchanged; commits pass `width=4`.

```python
# Edit lines 15-37 (the function signature and body):

def next_prefixed_identifier(
    identifiers: Iterable[str | None],
    prefix: str,
    *,
    width: int = 3,
) -> str:
    """Compute the next ``PREFIX-NNN`` identifier from existing ones.

    Scans ``identifiers`` for values matching ``{prefix}-{digits}``,
    takes the highest numeric suffix, increments it, and zero-pads to
    ``width`` digits (default 3 for backward compatibility with v0.1-v0.7
    governance entity types; commits use width=4 per commit.md §3.5.3).
    Values that don't match the prefix pattern (or are
    ``None``/empty) are ignored. An empty or all-non-matching input
    yields ``{prefix}-001`` at width=3 or ``{prefix}-0001`` at width=4.

    Callers should pass *all* rows including soft-deleted ones so that
    a deleted record's identifier is never reused.
    """
    highest = 0
    for ident in identifiers:
        if not ident:
            continue
        match = _PREFIXED_IDENTIFIER_RE.match(ident)
        if match is None or match.group("prefix") != prefix:
            continue
        highest = max(highest, int(match.group("num")))
    return f"{prefix}-{highest + 1:0{width}d}"
```

The format-string change (`:03d` → `:0{width}d`) is the only behavior change at width=3 (which is identical). Add a test in `tests/crmbuilder_v2/access/test__helpers.py` (or create it if it doesn't exist) covering both widths:

```python
def test_next_prefixed_identifier_width_three_default():
    assert next_prefixed_identifier([], "WT") == "WT-001"
    assert next_prefixed_identifier(["WT-005"], "WT") == "WT-006"


def test_next_prefixed_identifier_width_four_for_commits():
    assert next_prefixed_identifier([], "CM", width=4) == "CM-0001"
    assert next_prefixed_identifier(["CM-0042"], "CM", width=4) == "CM-0043"
```

### Step 2 — Create the commits repository module

**File (new):** `crmbuilder-v2/src/crmbuilder_v2/access/repositories/commits.py`

Mirror the structure of `work_tickets.py`. Key differences from work_tickets:

- **No status field, no transitions** (per `commit.md` §3.4.1; status-free documentary lifecycle).
- **No kind enum** (per `commit.md` §3.2.3).
- **Identifier regex** `^CM-\d{4}$` (four-digit; not three).
- **SHA validation** — lowercase 40-char hex regex `^[0-9a-f]{40}$`, applied at the access layer in addition to the DB CHECK so the error envelope carries a typed code rather than a SQLAlchemy `IntegrityError`.
- **SHA uniqueness** — UNIQUE constraint on the column enforces this at the DB level; the access layer catches `IntegrityError` on the `commit_sha` constraint and raises a typed `ConflictError` with the existing record's identifier (per acceptance criterion 7).
- **Parent SHAs validation** — `commit_parent_shas` must be a list of 0, 1, or 2 strings, each matching the SHA regex.
- **Conversation FK validation** — `commit_conversation_id` must reference an existing `conversation` record (active OR soft-deleted; the soft-deleted case is the rare commit-on-a-restored-conversation scenario). Access-layer-enforced; raises `UnprocessableError` with field `commit_conversation_id` and code `commit_conversation_id_not_found` (per acceptance criterion 5).
- **Repository validation** — non-empty, no whitespace, no path separators, no scheme prefix. No enum; new repos accepted as they appear.
- **Patchable field set** (per DEC-212) — everything except the identity pair (`commit_identifier`, `commit_sha`). Specifically: `commit_message_first_line`, `commit_message_full`, `commit_author_name`, `commit_author_email`, `commit_committed_at`, `commit_repository`, `commit_branch`, `commit_parent_shas`, `commit_files_changed_count`, `commit_conversation_id`.

Skeleton:

```python
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

from sqlalchemy import asc, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import next_prefixed_identifier, to_dict
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Commit, Conversation
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
    "commit_conversation_id",
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


def _require_conversation_exists(session: Session, conversation_id: str) -> None:
    if session.get(Conversation, conversation_id) is None:
        raise UnprocessableError([
            FieldError("commit_conversation_id",
                       "commit_conversation_id_not_found",
                       f"conversation {conversation_id!r} does not exist")
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
    row = session.get(Commit, identifier)
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
    commit_conversation_id: str | None = None,
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
    if commit_conversation_id is not None:
        stmt = stmt.where(
            Commit.commit_conversation_id == commit_conversation_id
        )
    if offset:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_commit(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = session.get(Commit, identifier)
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
    conversation_id: str,
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
        commit_conversation_id=conversation_id,
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
    conversation_id: str,
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
    conversation_id = gov.require_nonempty(
        conversation_id, field="commit_conversation_id"
    )
    _require_conversation_exists(session, conversation_id)

    # SHA uniqueness pre-check for a clean error envelope; the DB CHECK
    # is the canonical guard, but pre-checking lets us return a 409 with
    # the existing identifier without trapping IntegrityError contextually.
    existing = _existing_for_sha(session, sha)
    if existing is not None:
        raise ConflictError(
            f"commit_sha {sha!r} already exists "
            f"(existing identifier: {existing.commit_identifier})"
        )

    row_kwargs = dict(
        sha=sha,
        message_first_line=message_first_line,
        message_full=message_full,
        author_name=author_name,
        author_email=author_email,
        committed_at=committed_at,
        repository=repository,
        branch=branch,
        parent_shas=parent_shas,
        files_changed_count=files_changed_count,
        conversation_id=conversation_id,
    )

    if identifier is None:
        row = _insert_with_autoassign(session, **row_kwargs)
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE,
            field="commit_identifier", example="CM-0001",
        )
        if session.get(Commit, identifier) is not None:
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
    conversation_id: str | None = None,
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
    conversation_id = gov.require_nonempty(
        conversation_id, field="commit_conversation_id"
    )
    if conversation_id != row.commit_conversation_id:
        _require_conversation_exists(session, conversation_id)

    row.commit_message_first_line = message_first_line
    row.commit_message_full = message_full
    row.commit_author_name = author_name
    row.commit_author_email = author_email
    row.commit_committed_at = committed_at
    row.commit_repository = repository
    row.commit_branch = branch
    row.commit_parent_shas = parent_shas
    row.commit_files_changed_count = files_changed_count
    row.commit_conversation_id = conversation_id
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
    if "commit_conversation_id" in fields:
        conv_id = gov.require_nonempty(
            fields["commit_conversation_id"], field="commit_conversation_id"
        )
        if conv_id != row.commit_conversation_id:
            _require_conversation_exists(session, conv_id)
            row.commit_conversation_id = conv_id

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
```

### Step 3 — Add Pydantic schemas

**File:** `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py`

Insert after the `CloseOutPayloadPatchIn` class (around line 714). Use `Any` for `commit_parent_shas` to admit the JSON list shape and let the access layer validate per-element format.

```python
class CommitCreateIn(_Base):
    commit_sha: str
    commit_message_first_line: str
    commit_message_full: str
    commit_author_name: str
    commit_author_email: str
    commit_committed_at: str
    commit_repository: str
    commit_branch: str | None = "main"
    commit_parent_shas: list[str]
    commit_files_changed_count: int
    commit_conversation_id: str
    commit_identifier: str | None = None
    references: list[GovernanceEdgeIn] | None = None
    timestamps: dict[str, Any] | None = None


class CommitReplaceIn(_Base):
    commit_identifier: str | None = None
    commit_sha: str | None = None  # body may echo current; access layer
                                   # rejects any change
    commit_message_first_line: str
    commit_message_full: str
    commit_author_name: str
    commit_author_email: str
    commit_committed_at: str
    commit_repository: str
    commit_branch: str
    commit_parent_shas: list[str]
    commit_files_changed_count: int
    commit_conversation_id: str
    references: list[GovernanceEdgeIn] | None = None


class CommitPatchIn(_Base):
    commit_message_first_line: str | None = None
    commit_message_full: str | None = None
    commit_author_name: str | None = None
    commit_author_email: str | None = None
    commit_committed_at: str | None = None
    commit_repository: str | None = None
    commit_branch: str | None = None
    commit_parent_shas: list[str] | None = None
    commit_files_changed_count: int | None = None
    commit_conversation_id: str | None = None
    references: list[GovernanceEdgeIn] | None = None
```

### Step 4 — Create the commits router

**File (new):** `crmbuilder-v2/src/crmbuilder_v2/api/routers/commits.py`

```python
"""Commits endpoints — the seventh governance entity type (UI v0.8, PI-029 slice B).

Standard nine-endpoint set per ``commit.md`` §3.5, including the new
``GET /commits/by-sha/{sha}`` natural-key lookup with four-case behavior
(full SHA, unambiguous prefix, ambiguous prefix → 409, miss → 404).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import commits
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    CommitCreateIn,
    CommitPatchIn,
    CommitReplaceIn,
)

router = APIRouter(prefix="/commits", tags=["commits"])
_FIELD_PREFIX = "commit_"


def _edges(body) -> list[dict] | None:
    return [e.model_dump() for e in body.references] if body.references else None


@router.get("")
def list_all(
    include_deleted: bool = False,
    commit_repository: str | None = None,
    commit_conversation_id: str | None = None,
    sort: str = "commit_committed_at",
    order: str = "desc",
    limit: int | None = None,
    offset: int = 0,
):
    with readonly_session() as s:
        return ok(commits.list_commits(
            s,
            include_deleted=include_deleted,
            commit_repository=commit_repository,
            commit_conversation_id=commit_conversation_id,
            sort=sort,
            order=order,
            limit=limit,
            offset=offset,
        ))


@router.get("/next-identifier")
def next_identifier():
    with readonly_session() as s:
        return ok({"next": commits.next_commit_identifier(s)})


@router.get("/by-sha/{sha}")
def by_sha(sha: str, include_deleted: bool = False):
    """Natural-key lookup. Returns:

    - 200 + the record on full-SHA hit or unambiguous-prefix hit
    - 404 on miss
    - 409 with candidate-SHA list on ambiguous prefix
    """
    with readonly_session() as s:
        result = commits.find_by_sha(
            s, sha, include_deleted=include_deleted
        )
    if result is None:
        # 404 — miss
        raise HTTPException(
            status_code=404,
            detail={"code": "commit_sha_not_found", "value": sha},
        )
    if isinstance(result, list):
        # 409 — ambiguous prefix (multiple candidates)
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ambiguous_sha_prefix",
                "candidates": result,
            },
        )
    return ok(result)


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = commits.get_commit(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("commit", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: CommitCreateIn):
    with writable_session() as s:
        return ok(commits.create_commit(
            s,
            sha=body.commit_sha,
            message_first_line=body.commit_message_first_line,
            message_full=body.commit_message_full,
            author_name=body.commit_author_name,
            author_email=body.commit_author_email,
            committed_at=body.commit_committed_at,
            repository=body.commit_repository,
            branch=body.commit_branch or "main",
            parent_shas=body.commit_parent_shas,
            files_changed_count=body.commit_files_changed_count,
            conversation_id=body.commit_conversation_id,
            identifier=body.commit_identifier,
            references=_edges(body),
            timestamps=body.timestamps,
        ))


@router.put("/{identifier}")
def replace(identifier: str, body: CommitReplaceIn):
    with writable_session() as s:
        return ok(commits.update_commit(
            s,
            identifier,
            commit_identifier=body.commit_identifier,
            commit_sha=body.commit_sha,
            message_first_line=body.commit_message_first_line,
            message_full=body.commit_message_full,
            author_name=body.commit_author_name,
            author_email=body.commit_author_email,
            committed_at=body.commit_committed_at,
            repository=body.commit_repository,
            branch=body.commit_branch,
            parent_shas=body.commit_parent_shas,
            files_changed_count=body.commit_files_changed_count,
            conversation_id=body.commit_conversation_id,
            references=_edges(body),
        ))


@router.patch("/{identifier}")
def patch(identifier: str, body: CommitPatchIn):
    provided = body.model_dump(exclude_unset=True)
    references = provided.pop("references", None)
    # Pass through with full field names — the repository's _PATCHABLE_FIELDS
    # set matches the commit_ prefix exactly, so no name munging.
    with writable_session() as s:
        return ok(commits.patch_commit(
            s, identifier, references=references, **provided
        ))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(commits.delete_commit(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(commits.restore_commit(s, identifier))
```

### Step 5 — Register the router in main.py

**File:** `crmbuilder-v2/src/crmbuilder_v2/api/main.py`

Add `commits` to the imports block and register the router after `deposit_events.router`:

```python
# In the import block (lines 28-52), add:
from crmbuilder_v2.api.routers import (
    ...
    deposit_events,
    ...
    commits,  # add alphabetically; or anywhere consistent with neighbors
    ...
)

# After line 152 (app.include_router(deposit_events.router)), add:
app.include_router(commits.router)
```

### Step 6 — Add the derived endpoint on the conversations router

**File:** `crmbuilder-v2/src/crmbuilder_v2/api/routers/conversations.py`

Add a sub-route that delegates to `commits.list_commits()`. The endpoint validates the conversation exists, then returns commits scoped to it.

```python
# Add to the import block:
from crmbuilder_v2.access.repositories import commits as commits_repo

# Add a new route handler (location: after the existing list/get/CRUD
# routes for conversations, before the file ends):

@router.get("/{conversation_identifier}/commits")
def commits_for_conversation(
    conversation_identifier: str,
    include_deleted: bool = False,
    commit_repository: str | None = None,
    sort: str = "commit_committed_at",
    order: str = "desc",
    limit: int | None = None,
    offset: int = 0,
):
    """List every commit produced by a specific conversation.

    Derived from the standard ``/commits?commit_conversation_id=`` filter
    per DEC-211 — one-hop FK-scoped derived endpoint shipped in PI-029
    slice B. The two-hop ``/workstreams/{id}/commits`` variant was
    explicitly deferred.

    Returns 404 with ``conversation_not_found`` if the named conversation
    does not exist; returns 200 with empty array if the conversation
    exists but produced no commits.
    """
    with readonly_session() as s:
        # Existence check — uses the conversations repository's get
        # function which respects soft-delete. Use include_deleted=True
        # so commits attributed to a soft-deleted conversation can still
        # be listed (administrative-correction case).
        conv = conversations_repo.get_conversation(
            s, conversation_identifier, include_deleted=True
        )
        if conv is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "conversation_not_found",
                    "identifier": conversation_identifier,
                },
            )
        return ok(commits_repo.list_commits(
            s,
            include_deleted=include_deleted,
            commit_conversation_id=conversation_identifier,
            commit_repository=commit_repository,
            sort=sort,
            order=order,
            limit=limit,
            offset=offset,
        ))
```

Confirm `HTTPException` is imported at the top of the file (it likely is; the existing conversation router uses NotFoundError, but the by-sha pattern uses HTTPException for shaped error bodies, and we use the same here for the typed `conversation_not_found` code).

### Step 7 — Write the access-layer tests

**File (new):** `tests/crmbuilder_v2/access/test_commit.py`

Cover acceptance criteria 4-11 from `commit.md` §3.7 plus the per-question specifics. Mirror the `test_work_ticket.py` style (uses `v2_env` fixture and `session_scope`).

```python
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
from crmbuilder_v2.access.repositories import conversations as cr
from crmbuilder_v2.access.repositories import workstreams as ws


SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
SHA_AB = "ab" + "0" * 38  # for prefix-uniqueness tests
SHA_AC = "ac" + "0" * 38
SHA_AD = "ad" + "0" * 38


def _conv(s, identifier="CONV-001"):
    wid = ws.create_workstream(
        s, name="WS " + identifier, purpose="p", description="d"
    )["workstream_identifier"]
    return cr.create_conversation(
        s, title="C " + identifier, purpose="p", description="d",
        identifier=identifier,
        references=[{
            "source_type": "conversation", "source_id": identifier,
            "target_type": "workstream", "target_id": wid,
            "relationship": "conversation_belongs_to_workstream",
        }],
    )["conversation_identifier"]


def _make(s, sha=SHA_A, conv_id="CONV-001", **overrides):
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
        conversation_id=conv_id,
    )
    defaults.update(overrides)
    return cm.create_commit(s, **defaults)


# ---------------------------------------------------------------------------
# Acceptance criterion 4 — identifier collision rejection
# ---------------------------------------------------------------------------


def test_identifier_collision_rejected(v2_env):
    with session_scope() as s:
        _conv(s)
        _make(s)  # auto-assigns CM-0001
    with session_scope() as s, pytest.raises(ConflictError):
        _make(s, sha=SHA_B, identifier="CM-0001")


def test_autoassign_increments_with_four_digit_width(v2_env):
    with session_scope() as s:
        _conv(s)
        r1 = _make(s, sha=SHA_A)
        r2 = _make(s, sha=SHA_B)
    assert r1["commit_identifier"] == "CM-0001"
    assert r2["commit_identifier"] == "CM-0002"


# ---------------------------------------------------------------------------
# Acceptance criterion 5 — commit_conversation_id FK existence
# ---------------------------------------------------------------------------


def test_conversation_must_exist(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _make(s, conv_id="CONV-999")
    assert exc.value.errors[0].code == "commit_conversation_id_not_found"


# ---------------------------------------------------------------------------
# Acceptance criterion 6 — commit_sha format validation
# ---------------------------------------------------------------------------


def test_sha_length_validation(v2_env):
    with session_scope() as s:
        _conv(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _make(s, sha="a" * 39)
    assert exc.value.errors[0].code == "invalid_sha_format"
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, sha="a" * 41)


def test_sha_uppercase_rejected(v2_env):
    with session_scope() as s:
        _conv(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, sha="A" * 40)


def test_sha_non_hex_rejected(v2_env):
    with session_scope() as s:
        _conv(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, sha="g" * 40)


# ---------------------------------------------------------------------------
# Acceptance criterion 7 — commit_sha uniqueness across engagement
# ---------------------------------------------------------------------------


def test_sha_duplicate_rejected(v2_env):
    with session_scope() as s:
        _conv(s)
        _make(s, sha=SHA_A)
    with session_scope() as s, pytest.raises(ConflictError) as exc:
        _make(s, sha=SHA_A)
    assert "CM-0001" in str(exc.value)


def test_sha_uniqueness_includes_soft_deleted(v2_env):
    with session_scope() as s:
        _conv(s)
        _make(s, sha=SHA_A)
        cm.delete_commit(s, "CM-0001")
    with session_scope() as s, pytest.raises(ConflictError):
        _make(s, sha=SHA_A)


# ---------------------------------------------------------------------------
# Acceptance criterion 8 — commit_parent_shas array-shape validation
# ---------------------------------------------------------------------------


def test_parent_shas_initial_commit_empty_list(v2_env):
    with session_scope() as s:
        _conv(s)
        r = _make(s, sha=SHA_A, parent_shas=[])
    assert r["commit_parent_shas"] == []


def test_parent_shas_single_normal_commit(v2_env):
    with session_scope() as s:
        _conv(s)
        r = _make(s, sha=SHA_A, parent_shas=[SHA_B])
    assert r["commit_parent_shas"] == [SHA_B]


def test_parent_shas_merge_commit_two_parents(v2_env):
    with session_scope() as s:
        _conv(s)
        r = _make(s, sha=SHA_A, parent_shas=[SHA_B, SHA_C])
    assert r["commit_parent_shas"] == [SHA_B, SHA_C]


def test_parent_shas_three_parents_rejected(v2_env):
    with session_scope() as s:
        _conv(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _make(s, sha=SHA_A, parent_shas=[SHA_B, SHA_C, "d" * 40])
    assert exc.value.errors[0].code == "too_many_parents"


def test_parent_shas_per_element_format(v2_env):
    with session_scope() as s:
        _conv(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _make(s, sha=SHA_A, parent_shas=["short"])
    assert exc.value.errors[0].code == "invalid_sha_format"


# ---------------------------------------------------------------------------
# Acceptance criterion 9 — commit_repository validation
# ---------------------------------------------------------------------------


def test_repository_empty_rejected(v2_env):
    with session_scope() as s:
        _conv(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, sha=SHA_A, repository="")


def test_repository_whitespace_rejected(v2_env):
    with session_scope() as s:
        _conv(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, sha=SHA_A, repository="bad repo")


def test_repository_path_separator_rejected(v2_env):
    with session_scope() as s:
        _conv(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, sha=SHA_A, repository="org/repo")


def test_repository_scheme_rejected(v2_env):
    with session_scope() as s:
        _conv(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, sha=SHA_A, repository="https://example.com/repo")


def test_repository_new_name_admitted(v2_env):
    with session_scope() as s:
        _conv(s)
        r = _make(s, sha=SHA_A, repository="some-brand-new-repo-name")
    assert r["commit_repository"] == "some-brand-new-repo-name"


# ---------------------------------------------------------------------------
# Acceptance criterion 10 — by-sha four-case behavior (DEC-213)
# ---------------------------------------------------------------------------


def test_by_sha_full_hit(v2_env):
    with session_scope() as s:
        _conv(s)
        _make(s, sha=SHA_A)
    with session_scope() as s:
        result = cm.find_by_sha(s, SHA_A)
    assert isinstance(result, dict)
    assert result["commit_sha"] == SHA_A


def test_by_sha_unambiguous_prefix(v2_env):
    with session_scope() as s:
        _conv(s)
        _make(s, sha=SHA_A)
        _make(s, sha=SHA_B)
    with session_scope() as s:
        result = cm.find_by_sha(s, SHA_A[:8])
    assert isinstance(result, dict)
    assert result["commit_sha"] == SHA_A


def test_by_sha_ambiguous_prefix_returns_candidates(v2_env):
    with session_scope() as s:
        _conv(s)
        _make(s, sha=SHA_AB)
        _make(s, sha=SHA_AC)
        _make(s, sha=SHA_AD)
    with session_scope() as s:
        result = cm.find_by_sha(s, "a")  # too short — should 422
    # Actually testing prefix length below; here use a valid 4-char "ab",
    # but "ab" only matches SHA_AB so it's unambiguous. Use a non-existent
    # 4-char prefix that matches all three? Need to construct shas
    # sharing a longer prefix.
    # Redo:


def test_by_sha_ambiguous_returns_all_candidates(v2_env):
    sha1 = "abcd" + "0" * 36
    sha2 = "abcd" + "1" * 36
    sha3 = "abcd" + "2" * 36
    with session_scope() as s:
        _conv(s)
        _make(s, sha=sha1)
        _make(s, sha=sha2)
        _make(s, sha=sha3)
    with session_scope() as s:
        result = cm.find_by_sha(s, "abcd")
    assert isinstance(result, list)
    assert set(result) == {sha1, sha2, sha3}


def test_by_sha_miss_returns_none(v2_env):
    with session_scope() as s:
        _conv(s)
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
        _conv(s)
        _make(s, sha=SHA_A)
    with session_scope() as s:
        result = cm.find_by_sha(s, SHA_A.upper())
    assert isinstance(result, dict)
    assert result["commit_sha"] == SHA_A


def test_by_sha_excludes_soft_deleted_by_default(v2_env):
    with session_scope() as s:
        _conv(s)
        _make(s, sha=SHA_A)
        cm.delete_commit(s, "CM-0001")
    with session_scope() as s:
        result = cm.find_by_sha(s, SHA_A)
    assert result is None


def test_by_sha_includes_soft_deleted_when_requested(v2_env):
    with session_scope() as s:
        _conv(s)
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
        _conv(s)
        _make(s)
    with session_scope() as s:
        cm.delete_commit(s, "CM-0001")
        assert len(cm.list_commits(s)) == 0
        assert len(cm.list_commits(s, include_deleted=True)) == 1
        assert cm.get_commit(s, "CM-0001") is None
        assert cm.get_commit(s, "CM-0001", include_deleted=True) is not None


def test_restore_returns_to_active(v2_env):
    with session_scope() as s:
        _conv(s)
        _make(s)
    with session_scope() as s:
        cm.delete_commit(s, "CM-0001")
        cm.restore_commit(s, "CM-0001")
        assert cm.get_commit(s, "CM-0001")["commit_deleted_at"] is None
        assert len(cm.list_commits(s)) == 1


def test_restore_on_live_record_rejected(v2_env):
    with session_scope() as s:
        _conv(s)
        _make(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        cm.restore_commit(s, "CM-0001")


# ---------------------------------------------------------------------------
# DEC-212 — patch updatability for non-identity fields
# ---------------------------------------------------------------------------


def test_patch_parent_shas_updatable(v2_env):
    """DEC-212: commit_parent_shas IS updatable for administrative correction."""
    with session_scope() as s:
        _conv(s)
        _make(s, parent_shas=[SHA_B])
    with session_scope() as s:
        cm.patch_commit(s, "CM-0001", commit_parent_shas=[SHA_C, SHA_B])
        r = cm.get_commit(s, "CM-0001")
    assert r["commit_parent_shas"] == [SHA_C, SHA_B]


def test_patch_files_changed_count_updatable(v2_env):
    with session_scope() as s:
        _conv(s)
        _make(s, files_changed_count=3)
    with session_scope() as s:
        cm.patch_commit(s, "CM-0001", commit_files_changed_count=5)
        r = cm.get_commit(s, "CM-0001")
    assert r["commit_files_changed_count"] == 5


def test_patch_conversation_id_updatable_with_existence_check(v2_env):
    with session_scope() as s:
        _conv(s, "CONV-001")
        _conv(s, "CONV-002")
        _make(s)
    with session_scope() as s:
        cm.patch_commit(s, "CM-0001", commit_conversation_id="CONV-002")
        r = cm.get_commit(s, "CM-0001")
    assert r["commit_conversation_id"] == "CONV-002"
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cm.patch_commit(s, "CM-0001", commit_conversation_id="CONV-999")
    assert exc.value.errors[0].code == "commit_conversation_id_not_found"


def test_patch_identifier_rejected(v2_env):
    with session_scope() as s:
        _conv(s)
        _make(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cm.patch_commit(s, "CM-0001", commit_identifier="CM-0099")
    assert exc.value.errors[0].code == "field_not_updatable"


def test_patch_sha_rejected(v2_env):
    with session_scope() as s:
        _conv(s)
        _make(s, sha=SHA_A)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cm.patch_commit(s, "CM-0001", commit_sha=SHA_B)
    assert exc.value.errors[0].code == "field_not_updatable"


# ---------------------------------------------------------------------------
# DEC-214 — list sort and order parameters
# ---------------------------------------------------------------------------


def test_list_default_sort_is_committed_at_desc(v2_env):
    with session_scope() as s:
        _conv(s)
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
        _conv(s)
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
        _conv(s)
        _make(s, sha=SHA_A, repository="crmbuilder")
        _make(s, sha=SHA_B, repository="ClevelandBusinessMentoring")
    with session_scope() as s:
        rows = cm.list_commits(s, commit_repository="crmbuilder")
    assert len(rows) == 1
    assert rows[0]["commit_sha"] == SHA_A


def test_list_filter_by_conversation(v2_env):
    with session_scope() as s:
        _conv(s, "CONV-001")
        _conv(s, "CONV-002")
        _make(s, sha=SHA_A, conv_id="CONV-001")
        _make(s, sha=SHA_B, conv_id="CONV-002")
    with session_scope() as s:
        rows = cm.list_commits(s, commit_conversation_id="CONV-001")
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
        _conv(s)
        _make(s)
    with session_scope() as s:
        assert cm.next_commit_identifier(s) == "CM-0002"


def test_first_line_embedded_newline_rejected(v2_env):
    with session_scope() as s:
        _conv(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _make(s, message_first_line="line one\nline two")
    assert exc.value.errors[0].code == "embedded_newline"


def test_author_email_without_at_rejected(v2_env):
    with session_scope() as s:
        _conv(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, author_email="dougbower.com")
```

Note: the test `test_by_sha_ambiguous_prefix_returns_candidates` is malformed — it's a duplicate of `test_by_sha_ambiguous_returns_all_candidates`. Delete the first; keep the second. The skeleton above shows both; clean up during implementation.

### Step 8 — Write the REST-endpoint tests

**File (new):** `tests/crmbuilder_v2/api/test_commit_api.py`

Cover the router behavior — status codes, envelope shape, the derived endpoint on conversations, and the four-case by-sha behavior.

```python
"""Commit REST endpoint tests — UI v0.8, PI-029 slice B."""

from __future__ import annotations


SHA_A = "a" * 40
SHA_B = "b" * 40


def _conv(client, identifier="CONV-001"):
    ws_resp = client.post("/workstreams", json={
        "workstream_name": "WS " + identifier,
        "workstream_purpose": "p",
        "workstream_description": "d",
    })
    wid = ws_resp.json()["data"]["workstream_identifier"]
    client.post("/conversations", json={
        "conversation_title": "C " + identifier,
        "conversation_purpose": "p",
        "conversation_description": "d",
        "conversation_identifier": identifier,
        "references": [{
            "source_type": "conversation", "source_id": identifier,
            "target_type": "workstream", "target_id": wid,
            "relationship": "conversation_belongs_to_workstream",
        }],
    })
    return identifier


def _commit_body(sha=SHA_A, conv_id="CONV-001"):
    return {
        "commit_sha": sha,
        "commit_message_first_line": "first line",
        "commit_message_full": "first line\n\nbody",
        "commit_author_name": "Doug Bower",
        "commit_author_email": "doug@dougbower.com",
        "commit_committed_at": "2026-05-23T20:45:12-04:00",
        "commit_repository": "crmbuilder",
        "commit_branch": "main",
        "commit_parent_shas": ["1" * 40],
        "commit_files_changed_count": 3,
        "commit_conversation_id": conv_id,
    }


def test_post_creates_with_autoassigned_identifier(client):
    _conv(client)
    r = client.post("/commits", json=_commit_body())
    assert r.status_code == 201
    body = r.json()
    assert body["data"]["commit_identifier"] == "CM-0001"
    assert body["data"]["commit_sha"] == SHA_A


def test_get_by_identifier(client):
    _conv(client)
    client.post("/commits", json=_commit_body())
    r = client.get("/commits/CM-0001")
    assert r.status_code == 200
    assert r.json()["data"]["commit_sha"] == SHA_A


def test_get_unknown_returns_404(client):
    r = client.get("/commits/CM-9999")
    assert r.status_code == 404


def test_by_sha_full_hit(client):
    _conv(client)
    client.post("/commits", json=_commit_body())
    r = client.get(f"/commits/by-sha/{SHA_A}")
    assert r.status_code == 200
    assert r.json()["data"]["commit_sha"] == SHA_A


def test_by_sha_unambiguous_prefix(client):
    _conv(client)
    client.post("/commits", json=_commit_body(sha=SHA_A))
    client.post("/commits", json=_commit_body(sha=SHA_B))
    r = client.get("/commits/by-sha/" + SHA_A[:8])
    assert r.status_code == 200
    assert r.json()["data"]["commit_sha"] == SHA_A


def test_by_sha_ambiguous_returns_409(client):
    _conv(client)
    s1 = "abcd" + "0" * 36
    s2 = "abcd" + "1" * 36
    client.post("/commits", json=_commit_body(sha=s1))
    client.post("/commits", json=_commit_body(sha=s2))
    r = client.get("/commits/by-sha/abcd")
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["code"] == "ambiguous_sha_prefix"
    assert set(detail["candidates"]) == {s1, s2}


def test_by_sha_miss_returns_404(client):
    r = client.get("/commits/by-sha/" + "f" * 40)
    assert r.status_code == 404


def test_by_sha_too_short_returns_422(client):
    r = client.get("/commits/by-sha/abc")
    assert r.status_code == 422


def test_by_sha_uppercase_normalized(client):
    _conv(client)
    client.post("/commits", json=_commit_body())
    r = client.get(f"/commits/by-sha/{SHA_A.upper()}")
    assert r.status_code == 200


def test_next_identifier_endpoint(client):
    r = client.get("/commits/next-identifier")
    assert r.status_code == 200
    assert r.json()["data"]["next"] == "CM-0001"


def test_list_default_sort_descending(client):
    _conv(client)
    body1 = _commit_body(sha=SHA_A)
    body1["commit_committed_at"] = "2026-05-20T10:00:00-04:00"
    body2 = _commit_body(sha=SHA_B)
    body2["commit_committed_at"] = "2026-05-23T10:00:00-04:00"
    client.post("/commits", json=body1)
    client.post("/commits", json=body2)
    r = client.get("/commits")
    data = r.json()["data"]
    assert data[0]["commit_sha"] == SHA_B
    assert data[1]["commit_sha"] == SHA_A


def test_list_filter_by_repository(client):
    _conv(client)
    b1 = _commit_body(sha=SHA_A)
    b2 = _commit_body(sha=SHA_B)
    b2["commit_repository"] = "ClevelandBusinessMentoring"
    client.post("/commits", json=b1)
    client.post("/commits", json=b2)
    r = client.get("/commits?commit_repository=crmbuilder")
    assert len(r.json()["data"]) == 1


def test_delete_then_restore_cycle(client):
    _conv(client)
    client.post("/commits", json=_commit_body())
    r = client.delete("/commits/CM-0001")
    assert r.status_code == 200
    assert len(client.get("/commits").json()["data"]) == 0
    r = client.post("/commits/CM-0001/restore")
    assert r.status_code == 200
    assert len(client.get("/commits").json()["data"]) == 1


def test_patch_parent_shas(client):
    _conv(client)
    client.post("/commits", json=_commit_body())
    r = client.patch("/commits/CM-0001", json={
        "commit_parent_shas": ["2" * 40, "3" * 40],
    })
    assert r.status_code == 200
    assert r.json()["data"]["commit_parent_shas"] == ["2" * 40, "3" * 40]


def test_patch_identifier_rejected(client):
    _conv(client)
    client.post("/commits", json=_commit_body())
    r = client.patch("/commits/CM-0001", json={
        "commit_identifier": "CM-0099",
    })
    assert r.status_code == 422


def test_patch_sha_rejected(client):
    _conv(client)
    client.post("/commits", json=_commit_body())
    r = client.patch("/commits/CM-0001", json={
        "commit_sha": SHA_B,
    })
    assert r.status_code == 422


def test_duplicate_sha_returns_409(client):
    _conv(client)
    client.post("/commits", json=_commit_body())
    r = client.post("/commits", json=_commit_body())
    assert r.status_code == 409


def test_unknown_conversation_returns_422(client):
    r = client.post("/commits", json=_commit_body(conv_id="CONV-999"))
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Derived endpoint: GET /conversations/{conv_id}/commits (DEC-211)
# ---------------------------------------------------------------------------


def test_conversations_commits_lists_scoped(client):
    _conv(client, "CONV-001")
    _conv(client, "CONV-002")
    client.post("/commits", json=_commit_body(sha=SHA_A, conv_id="CONV-001"))
    client.post("/commits", json=_commit_body(sha=SHA_B, conv_id="CONV-002"))
    r = client.get("/conversations/CONV-001/commits")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["commit_sha"] == SHA_A


def test_conversations_commits_empty_returns_200(client):
    _conv(client)
    r = client.get("/conversations/CONV-001/commits")
    assert r.status_code == 200
    assert r.json()["data"] == []


def test_conversations_commits_unknown_returns_404(client):
    r = client.get("/conversations/CONV-999/commits")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "conversation_not_found"
```

If the existing `client` fixture in `tests/crmbuilder_v2/api/test_governance_api.py` is shared via `conftest.py`, this file should import it implicitly. If not, copy the fixture pattern from `test_governance_api.py`.

---

## Run tests

```bash
cd ~/Dropbox/Projects/crmbuilder

# Run the new test files specifically first to surface failures fast
uv run pytest tests/crmbuilder_v2/access/test_commit.py -v
uv run pytest tests/crmbuilder_v2/api/test_commit_api.py -v

# Then the full v2 suite to confirm no regressions in slice A's tests
# or any of the v0.7 governance entity tests
uv run pytest tests/crmbuilder_v2/ -q

# Expected: ~35-45 new tests passing in the two new files; total v2 suite
# at ≥ 1425 passed (from slice A's 1391 baseline, plus the new tests).
# Skipped count stays at 3 (alembic-chain skips when catalog YAMLs absent).
```

Iterate until green. Common failure modes to expect:

- **SHA case normalization paths** — make sure the access-layer lowercases prefix input before query; the SQL `startswith` does NOT case-normalize.
- **Pydantic `extra="forbid"` rejecting `references` on patch bodies** — confirmed via the work_ticket pattern that `references` IS a known field on PatchIn schemas; if Pydantic complains, the schema is missing the field.
- **The `Conversation` import in `commits.py`** — confirm `Conversation` is exported from `crmbuilder_v2.access.models`; per slice A's read, it is (line 552).
- **`HTTPException` import in conversations router** — may already be present; if not, add `from fastapi import HTTPException`.

---

## Commit

```bash
cd ~/Dropbox/Projects/crmbuilder

# Inspect what changed
git status

# Add and commit
git add crmbuilder-v2/src/crmbuilder_v2/access/_helpers.py \
        crmbuilder-v2/src/crmbuilder_v2/access/repositories/commits.py \
        crmbuilder-v2/src/crmbuilder_v2/api/schemas.py \
        crmbuilder-v2/src/crmbuilder_v2/api/main.py \
        crmbuilder-v2/src/crmbuilder_v2/api/routers/commits.py \
        crmbuilder-v2/src/crmbuilder_v2/api/routers/conversations.py \
        tests/crmbuilder_v2/access/test_commit.py \
        tests/crmbuilder_v2/access/test__helpers.py \
        tests/crmbuilder_v2/api/test_commit_api.py

git commit -m "v2: PI-029 slice B — commit access layer + REST endpoints + tests

Per PRDs/product/crmbuilder-v2/governance-schema-specs/commit.md v1.0
§3.5 (endpoints), §3.7 (acceptance criteria 4-11), and the slice B
build-planning decisions DEC-211..214 from SES-067.

Access layer (crmbuilder-v2/src/crmbuilder_v2/access/repositories/commits.py):
- Standard CRUD plus find_by_sha for the natural-key lookup endpoint.
- Identifier autoassign with savepoint retry, four-digit width (CM-NNNN).
- Field validation: SHA format, SHA prefix (4+ char lowercase hex),
  parent_shas array shape (0/1/2 lowercase hex SHAs), repository
  (no whitespace, separators, or schemes), conversation FK existence,
  files_changed_count non-negative, embedded-newline guard on
  first_line, '@' guard on author_email.
- Sort/order validation locked to a known column set.
- DEC-212: commit_parent_shas, commit_files_changed_count, and
  commit_conversation_id are all updatable via PATCH; the identity
  pair (commit_identifier, commit_sha) is not.
- DEC-213(b): by-sha endpoint lowercases input before query.
- DEC-213(c): ambiguous-prefix response uses 'candidates' field
  with full 40-char SHAs.

Helper extension (crmbuilder-v2/src/crmbuilder_v2/access/_helpers.py):
- next_prefixed_identifier gains a 'width' keyword (default 3,
  backward-compatible); commits pass width=4 per commit.md §3.5.3.

REST endpoints (crmbuilder-v2/src/crmbuilder_v2/api/routers/commits.py):
- GET /commits with include_deleted, commit_repository,
  commit_conversation_id filters; sort/order params (DEC-214).
- GET /commits/by-sha/{sha} with the four-case behavior.
- GET /commits/{identifier}, /commits/next-identifier.
- POST, PUT, PATCH, DELETE, POST /commits/{id}/restore.
- DEC-211: GET /conversations/{id}/commits derived endpoint
  mounted on the conversations router; the two-hop
  /workstreams/{id}/commits variant explicitly deferred.

Pydantic schemas added: CommitCreateIn, CommitReplaceIn, CommitPatchIn.

Router registered in main.py.

Tests: 35+ new passing across access-layer and REST suites covering
every acceptance criterion 4-11 from §3.7 plus DEC-211..214 specifics.

Pre-slice baseline: 1391 passed + 3 skipped.
Post-slice expected: ≥ 1425 passed + 3 skipped."

# Do NOT push yet — Doug reviews then pushes. (Standard Claude Code
# convention per CLAUDE.md line 78: in Claude Code, Claude commits and
# Doug pushes; in the sandbox, Claude commits and pushes together.)
```

---

## Done

Reply with:

- Pre-slice test baseline (passed + skipped counts)
- Post-slice test counts after the full suite passes
- The commit SHA of the slice B commit
- Any deviations from the spec or this prompt (with rationale)
- Next prompt: PI-030 (apply_close_out.py integration for the commits close-out payload section), PI-031 (Commits panel UI), and PI-033 (historical commit back-fill). These are separate planning items, each requiring its own kickoff conversation; none are in scope for slice B itself.
