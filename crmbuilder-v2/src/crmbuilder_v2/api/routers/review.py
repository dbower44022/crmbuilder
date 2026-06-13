"""Review surface endpoints (requirements-provenance Phase 6).

The topic-first review data: a topic's requirement tree, its read-back document,
and the approval / drift queues. Read-only and engagement-scoped.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access import review
from crmbuilder_v2.api.deps import readonly_session
from crmbuilder_v2.api.envelope import ok

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/topics/{topic_identifier}")
def topic_review(topic_identifier: str):
    """The topic's requirement tree with provenance + spine annotations."""
    with readonly_session() as s:
        return ok(review.topic_review(s, topic_identifier))


@router.get("/topics/{topic_identifier}/document")
def topic_document(topic_identifier: str):
    """A plain-language read-back document of the topic's requirement tree."""
    with readonly_session() as s:
        return ok(
            {
                "topic": topic_identifier,
                "document": review.topic_readback_document(s, topic_identifier),
            }
        )


@router.get("/approval-queue")
def approval_queue():
    """Candidate requirements awaiting activation, with what each still needs."""
    with readonly_session() as s:
        return ok(review.approval_queue(s))


@router.get("/drift-queue")
def drift_queue():
    """Requirements flagged needs_review by living drift."""
    with readonly_session() as s:
        return ok(review.drift_queue(s))
