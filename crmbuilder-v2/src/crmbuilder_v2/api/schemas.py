"""Pydantic v2 request and response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- Charter / Status ----------


class CharterReplaceIn(_Base):
    payload: dict


class StatusReplaceIn(_Base):
    payload: dict


# ---------- Decisions ----------


class DecisionCreateIn(_Base):
    identifier: str
    title: str
    decision_date: str
    status: str
    context: str = ""
    decision: str = ""
    rationale: str = ""
    alternatives_considered: str = ""
    consequences: str = ""
    supersedes: str | None = None
    superseded_by: str | None = None


class DecisionUpdateIn(_Base):
    title: str | None = None
    decision_date: str | None = None
    status: str | None = None
    context: str | None = None
    decision: str | None = None
    rationale: str | None = None
    alternatives_considered: str | None = None
    consequences: str | None = None
    supersedes: str | None = None
    superseded_by: str | None = None


# ---------- Sessions ----------


class SessionCreateIn(_Base):
    identifier: str
    title: str
    session_date: str
    status: str
    conversation_reference: str = ""
    topics_covered: str = ""
    summary: str = ""
    artifacts_produced: str = ""
    in_flight_at_end: str = ""


# ---------- Risks ----------


class RiskCreateIn(_Base):
    identifier: str
    title: str
    description: str = ""
    probability: str
    impact: str
    response_plan: str = ""
    status: str


class RiskUpdateIn(_Base):
    title: str | None = None
    description: str | None = None
    probability: str | None = None
    impact: str | None = None
    response_plan: str | None = None
    status: str | None = None


# ---------- Planning items ----------


class PlanningItemCreateIn(_Base):
    identifier: str
    title: str
    item_type: str
    description: str = ""
    status: str
    resolution_reference: str | None = None


class PlanningItemUpdateIn(_Base):
    title: str | None = None
    item_type: str | None = None
    description: str | None = None
    status: str | None = None
    resolution_reference: str | None = None


# ---------- Topics ----------


class TopicCreateIn(_Base):
    identifier: str
    name: str
    description: str = ""
    parent_topic: str | None = None


class TopicUpdateIn(_Base):
    name: str | None = None
    description: str | None = None
    parent_topic: str | None = None


# ---------- References ----------


class ReferenceCreateIn(_Base):
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    relationship: str


class ReferenceDeleteIn(_Base):
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    relationship: str


# ---------- Envelope (response model used by /docs only) ----------


class Envelope(_Base):
    data: Any | None
    meta: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] | None
