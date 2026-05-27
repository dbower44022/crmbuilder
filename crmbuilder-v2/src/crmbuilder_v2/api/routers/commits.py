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
    commit_session_id: str | None = None,
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
            commit_session_id=commit_session_id,
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
        raise HTTPException(
            status_code=404,
            detail={"code": "commit_sha_not_found", "value": sha},
        )
    if isinstance(result, list):
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
            session_id=body.commit_session_id,
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
            session_id=body.commit_session_id,
            references=_edges(body),
        ))


@router.patch("/{identifier}")
def patch(identifier: str, body: CommitPatchIn):
    provided = body.model_dump(exclude_unset=True)
    references = provided.pop("references", None)
    # The repository's _PATCHABLE_FIELDS set uses the full commit_ prefix
    # exactly, so pass-through without name munging.
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
