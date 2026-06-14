"""MCP tool definitions.

Each tool wraps a single REST API endpoint via the supplied
``httpx.AsyncClient``. The MCP layer holds no business logic; validation,
vocabulary checks, and state lookups all happen in the access layer behind
the REST API.

Tool naming uses verbs Claude can match from a natural-language prompt
("get the current charter", "create a decision", "what decisions did
session SES-001 cover").
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# Name-prefix → write classification (design §4). Consumed by the chat
# tool dispatcher's mode toggle (Full / Read-only / Ask before write).
_WRITE_PREFIXES = ("create_", "update_", "delete_", "add_", "replace_")


def _is_write(name: str) -> bool:
    return name.startswith(_WRITE_PREFIXES)


@dataclass(frozen=True)
class ToolDefinition:
    """One governance tool: name, async callable, cleaned docstring, and
    read/write classification.

    The single source of truth shared by the MCP stdio/HTTP server
    (:func:`register_tools`) and the chat UI's ``ChatToolDispatcher``
    (Anthropic Messages API), so the two surfaces never drift.
    """

    name: str
    func: Callable[..., Any]
    description: str
    is_write: bool


async def _unwrap(response: httpx.Response) -> Any:
    """Pull the envelope's ``data`` field, or raise on error envelopes."""
    response.raise_for_status()
    body = response.json()
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body.get("data")


def tool_definitions(http: httpx.AsyncClient) -> list[ToolDefinition]:
    """Build the full governance tool surface bound to ``http``.

    Each inner coroutine wraps one REST endpoint. The list returned here
    is consumed both by :func:`register_tools` (FastMCP / Claude Desktop)
    and by the chat UI dispatcher (Anthropic Messages API), so the two
    surfaces stay in lock-step.
    """
    # ---------- Charter ----------

    async def get_current_charter() -> Any:
        """Return the current charter document (singleton, latest version)."""
        return await _unwrap(await http.get("/charter"))

    async def get_charter_version(version: int) -> Any:
        """Return a specific historical charter version."""
        return await _unwrap(await http.get(f"/charter/versions/{version}"))

    async def list_charter_versions() -> Any:
        """List all charter versions, newest first."""
        return await _unwrap(await http.get("/charter/versions"))

    async def replace_charter(payload: dict) -> Any:
        """Replace the charter, creating a new version. Previous version becomes
        historical."""
        return await _unwrap(await http.put("/charter", json={"payload": payload}))

    # ---------- Status ----------

    async def get_current_status() -> Any:
        """Return the current project status (singleton, latest version)."""
        return await _unwrap(await http.get("/status"))

    async def get_status_version(version: int) -> Any:
        """Return a specific historical status version."""
        return await _unwrap(await http.get(f"/status/versions/{version}"))

    async def list_status_versions() -> Any:
        """List all status versions, newest first."""
        return await _unwrap(await http.get("/status/versions"))

    async def replace_status(payload: dict) -> Any:
        """Replace the status, creating a new version."""
        return await _unwrap(await http.put("/status", json={"payload": payload}))

    # ---------- Decisions ----------

    async def get_decision(identifier: str) -> Any:
        """Return one decision record by its DEC-NNN identifier."""
        return await _unwrap(await http.get(f"/decisions/{identifier}"))

    async def list_decisions() -> Any:
        """List all decisions in identifier order."""
        return await _unwrap(await http.get("/decisions"))

    async def create_decision(
        identifier: str,
        title: str,
        decision_date: str,
        status: str,
        executive_summary: str,
        context: str = "",
        decision: str = "",
        rationale: str = "",
        alternatives_considered: str = "",
        consequences: str = "",
        supersedes: str | None = None,
        superseded_by: str | None = None,
    ) -> Any:
        """Create a decision record. Status must be one of Active, Superseded,
        Withdrawn. ``executive_summary`` is required (PI-075): a 200-800
        character audience-facing summary."""
        body = {
            "identifier": identifier,
            "title": title,
            "decision_date": decision_date,
            "status": status,
            "executive_summary": executive_summary,
            "context": context,
            "decision": decision,
            "rationale": rationale,
            "alternatives_considered": alternatives_considered,
            "consequences": consequences,
            "supersedes": supersedes,
            "superseded_by": superseded_by,
        }
        return await _unwrap(await http.post("/decisions", json=body))

    async def update_decision(
        identifier: str,
        title: str | None = None,
        decision_date: str | None = None,
        status: str | None = None,
        context: str | None = None,
        decision: str | None = None,
        rationale: str | None = None,
        alternatives_considered: str | None = None,
        consequences: str | None = None,
        executive_summary: str | None = None,
        supersedes: str | None = None,
        superseded_by: str | None = None,
    ) -> Any:
        """Update fields on a decision. Pass only the fields to change.

        ``executive_summary`` (PI-074/PI-075) is a 200-800 character summary
        that is required and NOT NULL — this is the path to refresh a stale one.
        """
        body = {
            k: v
            for k, v in dict(
                title=title,
                decision_date=decision_date,
                status=status,
                context=context,
                decision=decision,
                rationale=rationale,
                alternatives_considered=alternatives_considered,
                consequences=consequences,
                executive_summary=executive_summary,
                supersedes=supersedes,
                superseded_by=superseded_by,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.patch(f"/decisions/{identifier}", json=body))

    async def delete_decision(identifier: str) -> Any:
        """Delete a decision record."""
        return await _unwrap(await http.delete(f"/decisions/{identifier}"))

    # ---------- Sessions (PI-073 / DEC-314 redesign) ----------
    # Sessions are the medium-agnostic communication container — one
    # Claude.ai chat / one email / one phone call / one Zoom meeting /
    # one in-person meeting / one Slack thread = one session.
    # Schedulable (created in `planned` status) and stateful through a
    # six-status lifecycle: planned, in_flight, complete, cancelled,
    # not_started, superseded. DEC-013's append-only rule is superseded.

    async def get_session(identifier: str) -> Any:
        """Return one session record by its SES-NNN identifier."""
        return await _unwrap(await http.get(f"/sessions/{identifier}"))

    async def list_sessions(
        status: str | None = None,
        medium: str | None = None,
        project_identifier: str | None = None,
    ) -> Any:
        """List sessions. Filters: ``status`` (planned, in_flight, complete,
        cancelled, not_started, superseded), ``medium`` (chat, email, phone,
        zoom, in_person, slack, other), ``project_identifier``
        (resolves the session_belongs_to_project edge).
        """
        params = {
            k: v
            for k, v in dict(
                status=status,
                medium=medium,
                project_identifier=project_identifier,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.get("/sessions", params=params or None))

    async def list_recent_sessions(limit: int = 3) -> Any:
        """Return the most recent ``limit`` sessions (DEC-011 Tier 2 read).
        Default 3."""
        return await _unwrap(
            await http.get("/orientation/recent-sessions", params={"limit": limit})
        )

    async def create_session(
        title: str,
        description: str,
        medium: str,
        executive_summary: str,
        identifier: str | None = None,
        notes: str | None = None,
        status: str = "planned",
        scheduled_for: str | None = None,
        started_at: str | None = None,
        ended_at: str | None = None,
        participants: list | None = None,
        medium_metadata: dict | None = None,
    ) -> Any:
        """Create a session record in the redesigned shape (PI-073 / DEC-314).

        Required: ``title``, ``description``, ``medium`` (one of chat,
        email, phone, zoom, in_person, slack, other), and
        ``executive_summary`` (PI-075: a 200-800 character summary).

        Status defaults to ``planned`` — pass ``in_flight`` to mark an
        actively-happening session, or ``complete`` for one already over.
        Identifier is server-assigned (SES-NNN) when omitted.

        ``medium_metadata`` is a JSON object whose shape varies by medium
        — e.g., ``{"email_subject": ..., "email_thread_id": ...}`` for
        email; ``{"zoom_meeting_id": ..., "zoom_recording_url": ...}``
        for zoom. See session-v2.md §3.2.5 for the recommended shape per
        medium.
        """
        body = {
            k: v
            for k, v in dict(
                session_identifier=identifier,
                session_title=title,
                session_description=description,
                session_medium=medium,
                session_executive_summary=executive_summary,
                session_notes=notes,
                session_status=status,
                session_scheduled_for=scheduled_for,
                session_started_at=started_at,
                session_ended_at=ended_at,
                session_participants=participants,
                session_medium_metadata=medium_metadata,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.post("/sessions", json=body))

    async def update_session(
        identifier: str,
        title: str | None = None,
        description: str | None = None,
        medium: str | None = None,
        notes: str | None = None,
        status: str | None = None,
        scheduled_for: str | None = None,
        started_at: str | None = None,
        ended_at: str | None = None,
        participants: list | None = None,
        medium_metadata: dict | None = None,
        executive_summary: str | None = None,
    ) -> Any:
        """Update fields on a session (PATCH). Pass only the fields to change.

        Sessions are now editable throughout their lifecycle (DEC-013
        superseded by DEC-314). Lifecycle transitions are validated:
        planned → in_flight → complete, with cancelled/not_started/
        superseded as terminal alternatives. ``executive_summary``
        (PI-074/PI-075, required NOT NULL, 200-800 chars) refreshes a stale one.
        """
        body = {
            f"session_{k}": v
            for k, v in dict(
                title=title,
                description=description,
                medium=medium,
                notes=notes,
                status=status,
                scheduled_for=scheduled_for,
                started_at=started_at,
                ended_at=ended_at,
                participants=participants,
                medium_metadata=medium_metadata,
                executive_summary=executive_summary,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.patch(f"/sessions/{identifier}", json=body))

    async def delete_session(identifier: str) -> Any:
        """Soft-delete a session record."""
        return await _unwrap(await http.delete(f"/sessions/{identifier}"))

    async def list_conversations_for_session(identifier: str) -> Any:
        """List every conversation (topical sub-unit) belonging to a session.

        Replaces the legacy 1:0..1 conversation/session mapping; under
        PI-073 a session contains 1..N conversations.
        """
        return await _unwrap(
            await http.get(f"/sessions/{identifier}/conversations")
        )

    async def list_decisions_for_session(identifier: str) -> Any:
        """List the decisions referenced by a given session (DEC-011 Tier 2)."""
        return await _unwrap(
            await http.get(f"/orientation/decisions-for-session/{identifier}")
        )

    # ---------- Conversations (PI-073 / DEC-314) ----------
    # Conversations are topical sub-units within a session. New identifier
    # prefix ``CNV-NNN`` (distinct from legacy ``CONV-NNN``, which now
    # identifies sessions in the redesigned model). Six-status lifecycle:
    # planned, in_flight, complete, cancelled, not_started, superseded.

    async def get_conversation(identifier: str) -> Any:
        """Return one conversation record by its CNV-NNN identifier."""
        return await _unwrap(await http.get(f"/conversations/{identifier}"))

    async def list_conversations(
        status: str | None = None,
        session_identifier: str | None = None,
    ) -> Any:
        """List conversations. Filters: ``status``, ``session_identifier``
        (resolves the conversation_belongs_to_session edge)."""
        params = {
            k: v
            for k, v in dict(
                status=status,
                session_identifier=session_identifier,
            ).items()
            if v is not None
        }
        return await _unwrap(
            await http.get("/conversations", params=params or None)
        )

    async def create_conversation(
        title: str,
        purpose: str,
        description: str,
        identifier: str | None = None,
        summary: str | None = None,
        notes: str | None = None,
        status: str = "planned",
        executive_summary: str | None = None,
    ) -> Any:
        """Create a conversation (topical sub-unit) record.

        Required: ``title``, ``purpose``, ``description``. Identifier is
        server-assigned (CNV-NNN) when omitted. ``summary`` is the
        per-topic outcome captured at conversation close (status=complete).
        ``executive_summary`` (PI-105) is an optional 200-800 character
        summary persisted to ``conversation_executive_summary``.

        A conversation must be linked to its parent session via a
        ``conversation_belongs_to_session`` reference edge — author the
        edge separately via the references API, or include it in the
        create body's ``references`` array (not exposed in this tool yet).
        """
        body = {
            k: v
            for k, v in dict(
                conversation_identifier=identifier,
                conversation_title=title,
                conversation_purpose=purpose,
                conversation_description=description,
                conversation_summary=summary,
                conversation_notes=notes,
                conversation_status=status,
                conversation_executive_summary=executive_summary,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.post("/conversations", json=body))

    async def update_conversation(
        identifier: str,
        title: str | None = None,
        purpose: str | None = None,
        description: str | None = None,
        summary: str | None = None,
        notes: str | None = None,
        status: str | None = None,
        executive_summary: str | None = None,
    ) -> Any:
        """Update fields on a conversation (PATCH).

        ``executive_summary`` (PI-105, 200-800 chars) refreshes
        ``conversation_executive_summary``.
        """
        body = {
            f"conversation_{k}": v
            for k, v in dict(
                title=title,
                purpose=purpose,
                description=description,
                summary=summary,
                notes=notes,
                status=status,
                executive_summary=executive_summary,
            ).items()
            if v is not None
        }
        return await _unwrap(
            await http.patch(f"/conversations/{identifier}", json=body)
        )

    async def delete_conversation(identifier: str) -> Any:
        """Soft-delete a conversation record."""
        return await _unwrap(await http.delete(f"/conversations/{identifier}"))

    # ---------- Risks ----------

    async def get_risk(identifier: str) -> Any:
        """Return one risk record."""
        return await _unwrap(await http.get(f"/risks/{identifier}"))

    async def list_risks() -> Any:
        """List all risks."""
        return await _unwrap(await http.get("/risks"))

    async def create_risk(
        identifier: str,
        title: str,
        probability: str,
        impact: str,
        status: str,
        description: str = "",
        response_plan: str = "",
    ) -> Any:
        """Create a risk record. Probability and impact are Low/Medium/High;
        status is Open/Mitigated/Accepted/Closed."""
        return await _unwrap(
            await http.post(
                "/risks",
                json={
                    "identifier": identifier,
                    "title": title,
                    "description": description,
                    "probability": probability,
                    "impact": impact,
                    "response_plan": response_plan,
                    "status": status,
                },
            )
        )

    async def update_risk(
        identifier: str,
        title: str | None = None,
        description: str | None = None,
        probability: str | None = None,
        impact: str | None = None,
        response_plan: str | None = None,
        status: str | None = None,
    ) -> Any:
        """Update a risk record."""
        body = {
            k: v
            for k, v in dict(
                title=title,
                description=description,
                probability=probability,
                impact=impact,
                response_plan=response_plan,
                status=status,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.patch(f"/risks/{identifier}", json=body))

    async def delete_risk(identifier: str) -> Any:
        """Delete a risk record."""
        return await _unwrap(await http.delete(f"/risks/{identifier}"))

    # ---------- Planning items ----------

    async def get_planning_item(identifier: str) -> Any:
        """Return one planning item."""
        return await _unwrap(await http.get(f"/planning-items/{identifier}"))

    async def list_planning_items() -> Any:
        """List all planning items."""
        return await _unwrap(await http.get("/planning-items"))

    async def create_planning_item(
        identifier: str,
        title: str,
        item_type: str,
        status: str,
        executive_summary: str,
        description: str = "",
        resolution_reference: str | None = None,
    ) -> Any:
        """Create a planning item. item_type ∈ {planning_dimension, open_question,
        pending_work}; status ∈ {Open, Resolved, Deferred}. ``executive_summary``
        is required (PI-075): a 200-800 character audience-facing summary."""
        return await _unwrap(
            await http.post(
                "/planning-items",
                json={
                    "identifier": identifier,
                    "title": title,
                    "item_type": item_type,
                    "description": description,
                    "status": status,
                    "executive_summary": executive_summary,
                    "resolution_reference": resolution_reference,
                },
            )
        )

    async def update_planning_item(
        identifier: str,
        title: str | None = None,
        item_type: str | None = None,
        description: str | None = None,
        status: str | None = None,
        resolution_reference: str | None = None,
        executive_summary: str | None = None,
    ) -> Any:
        """Update a planning item.

        ``executive_summary`` (PI-074/PI-075, required NOT NULL, 200-800 chars)
        refreshes a stale summary — the gap PI-105 closed.
        """
        body = {
            k: v
            for k, v in dict(
                title=title,
                item_type=item_type,
                description=description,
                status=status,
                resolution_reference=resolution_reference,
                executive_summary=executive_summary,
            ).items()
            if v is not None
        }
        return await _unwrap(
            await http.patch(f"/planning-items/{identifier}", json=body)
        )

    async def delete_planning_item(identifier: str) -> Any:
        """Delete a planning item."""
        return await _unwrap(await http.delete(f"/planning-items/{identifier}"))

    # ---------- Topics ----------

    async def get_topic(identifier: str) -> Any:
        """Return one topic."""
        return await _unwrap(await http.get(f"/topics/{identifier}"))

    async def list_topics() -> Any:
        """List all topics."""
        return await _unwrap(await http.get("/topics"))

    async def create_topic(
        identifier: str,
        name: str,
        description: str = "",
        parent_topic: str | None = None,
    ) -> Any:
        """Create a topic. Optional parent_topic identifier supports nested
        topics."""
        return await _unwrap(
            await http.post(
                "/topics",
                json={
                    "identifier": identifier,
                    "name": name,
                    "description": description,
                    "parent_topic": parent_topic,
                },
            )
        )

    async def update_topic(
        identifier: str,
        name: str | None = None,
        description: str | None = None,
        parent_topic: str | None = None,
    ) -> Any:
        """Update a topic."""
        body = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if parent_topic is not None:
            body["parent_topic"] = parent_topic
        return await _unwrap(await http.patch(f"/topics/{identifier}", json=body))

    async def delete_topic(identifier: str) -> Any:
        """Delete a topic."""
        return await _unwrap(await http.delete(f"/topics/{identifier}"))

    # ---------- References (DEC-006) ----------

    async def list_references() -> Any:
        """List every reference in the database."""
        return await _unwrap(await http.get("/references"))

    async def add_reference(
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        relationship: str,
    ) -> Any:
        """Create a cross-entity reference. relationship ∈ {is_about, supersedes,
        decided_in, affects, covers, blocks, references}."""
        return await _unwrap(
            await http.post(
                "/references",
                json={
                    "source_type": source_type,
                    "source_id": source_id,
                    "target_type": target_type,
                    "target_id": target_id,
                    "relationship": relationship,
                },
            )
        )

    async def delete_reference(
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        relationship: str,
    ) -> Any:
        """Delete a specific reference identified by its full tuple."""
        return await _unwrap(
            await http.post(
                "/references/delete",
                json={
                    "source_type": source_type,
                    "source_id": source_id,
                    "target_type": target_type,
                    "target_id": target_id,
                    "relationship": relationship,
                },
            )
        )

    async def list_references_from(source_type: str, source_id: str) -> Any:
        """All references where the given entity is the source."""
        return await _unwrap(
            await http.get(f"/references/from/{source_type}/{source_id}")
        )

    async def list_references_to(target_type: str, target_id: str) -> Any:
        """All references where the given entity is the target."""
        return await _unwrap(
            await http.get(f"/references/to/{target_type}/{target_id}")
        )

    async def list_references_touching(entity_type: str, entity_id: str) -> Any:
        """All references where the given entity is the source OR the target.
        Returns ``{"as_source": [...], "as_target": [...]}``."""
        return await _unwrap(
            await http.get(f"/references/touching/{entity_type}/{entity_id}")
        )

    # ---------- Base entity catalog ----------

    async def catalog_search(
        query: str,
        limit: int = 10,
        include_attributes: bool = True,
        include_synonyms: bool = True,
    ) -> Any:
        """Search the base entity catalog (42 entries, 415 attributes) by text.

        Matches against entity names, attribute names, and synonyms. Returns
        a ranked list of hits with brief context for each. Use this when the
        user describes a concept ("donation", "company hierarchy", "support
        case") and you want to surface the catalog entries that match.
        """
        params = {
            "q": query,
            "limit": limit,
            "include_attributes": str(include_attributes).lower(),
            "include_synonyms": str(include_synonyms).lower(),
        }
        return await _unwrap(await http.get("/catalog/search", params=params))

    async def catalog_get_entity(catalog_id: str) -> Any:
        """Return one catalog entity with all nested data (systems, attributes,
        relationships, sources, synonyms).

        Use this once you have a catalog_id (e.g. from catalog_search) to
        pull the full entity definition — useful for reference-library
        operations during methodology entity drafting.
        """
        return await _unwrap(await http.get(f"/catalog/entities/{catalog_id}"))

    async def catalog_get_cross_system_map(
        catalog_id: str,
        target_system: str | None = None,
    ) -> Any:
        """Cross-system mapping for one catalog entity.

        Returns the entity-level name/api_name plus per-attribute name/api_name/
        status (standard|custom|absent) for either all 7 surveyed systems
        (``target_system=None``) or a single specified system. Useful at
        deployment-configuration time to translate domain entity references
        into the target CRM's native naming.
        """
        path = f"/catalog/cross-system-map/{catalog_id}"
        if target_system:
            return await _unwrap(
                await http.get(path, params={"system": target_system})
            )
        return await _unwrap(await http.get(path))

    async def catalog_gap_check(
        based_on_catalog_id: str,
        draft_attribute_names: list[str],
        min_systems: int = 5,
    ) -> Any:
        """Surface catalog attributes the draft is missing.

        Compares a draft entity's attribute list against a base catalog
        entity and returns the catalog attributes that are ``standard`` in
        ``min_systems`` or more surveyed systems but NOT in the draft. Use
        during Entity PRD drafting to prompt the operator about commonly-
        present attributes they may have overlooked.
        """
        body = {
            "based_on_catalog_id": based_on_catalog_id,
            "draft_attribute_names": draft_attribute_names,
            "min_systems": min_systems,
        }
        return await _unwrap(await http.post("/catalog/gap-check", json=body))

    # ---------- Engagement selection (PI-β follow-on A1) ----------

    async def select_engagement(engagement: str) -> Any:
        """Scope all subsequent tool calls to an engagement.

        ``engagement`` is an engagement identifier (``ENG-NNN``) or code
        (e.g. ``CRMBUILDER``). It is sent as the ``X-Engagement`` header on
        every following REST call until changed, mirroring the desktop's
        active-engagement context. Pass an empty string to clear it (leaving
        subsequent calls unscoped). The default comes from
        ``CRMBUILDER_V2_MCP_ENGAGEMENT``.
        """
        if engagement:
            http.headers["X-Engagement"] = engagement
        else:
            http.headers.pop("X-Engagement", None)
        return {"active_engagement": engagement or None}

    async def get_active_engagement() -> Any:
        """Return the engagement currently scoping tool calls.

        The value of the ``X-Engagement`` header sent on every REST call,
        or ``None`` when unscoped.
        """
        return {"active_engagement": http.headers.get("X-Engagement")}

    # ---------- Agent Profile Registry (PI-122) ----------

    async def resolve_agent_profile_contract(
        identifier: str, engagement: str | None = None
    ) -> Any:
        """Resolve an agent_profile into its effective contract.

        Returns the composed system prompt, tool set, enforced ruleset, active
        (area, tier) learnings, and a version stamp — the runtime-ready contract
        an ADO agent boots from. ``engagement`` overrides the active engagement
        for the scope merge (system rows ∪ that engagement's overlay).
        """
        params = {"engagement": engagement} if engagement else None
        return await _unwrap(
            await http.get(f"/agent-profiles/{identifier}/contract", params=params)
        )

    async def list_agent_profiles(
        area: str | None = None, tier: str | None = None, scope: str | None = None
    ) -> Any:
        """List agent profiles, optionally filtered by area / tier / scope."""
        params = {k: v for k, v in {"area": area, "tier": tier, "scope": scope}.items() if v}
        return await _unwrap(await http.get("/agent-profiles", params=params or None))

    async def create_agent_profile(
        area: str, tier: str, description: str, scope: str | None = None
    ) -> Any:
        """Create an agent profile for an (area × tier) cell."""
        body = {"area": area, "tier": tier, "description": description}
        if scope:
            body["scope"] = scope
        return await _unwrap(await http.post("/agent-profiles", json=body))

    async def list_skills(kind: str | None = None, scope: str | None = None) -> Any:
        """List registry skills, optionally filtered by kind / scope."""
        params = {k: v for k, v in {"kind": kind, "scope": scope}.items() if v}
        return await _unwrap(await http.get("/skills", params=params or None))

    async def list_governance_rules(
        enforcement: str | None = None, scope: str | None = None
    ) -> Any:
        """List governance rules, optionally filtered by enforcement / scope."""
        params = {k: v for k, v in {"enforcement": enforcement, "scope": scope}.items() if v}
        return await _unwrap(await http.get("/governance-rules", params=params or None))

    async def list_learnings(
        area: str | None = None, tier: str | None = None, status: str | None = None
    ) -> Any:
        """List learnings, optionally filtered by area / tier / status."""
        params = {k: v for k, v in {"area": area, "tier": tier, "status": status}.items() if v}
        return await _unwrap(await http.get("/learnings", params=params or None))

    async def capture_learning(
        area: str,
        tier: str,
        category: str,
        content: str,
        evidence_type: str | None = None,
        evidence_id: str | None = None,
        scope: str | None = None,
    ) -> Any:
        """Capture a learning (at Work-Task close), optionally linking evidence.

        ``category`` is one of gotcha / pattern / constraint / preference;
        ``tier`` one of architect / developer / tester. With ``evidence_type`` +
        ``evidence_id`` (a work_task / decision / test_spec) the learning starts
        at confidence 1 and gets a derived-from edge.
        """
        body = {"area": area, "tier": tier, "category": category, "content": content}
        if evidence_type and evidence_id:
            body["evidence_type"] = evidence_type
            body["evidence_id"] = evidence_id
        if scope:
            body["scope"] = scope
        return await _unwrap(await http.post("/learnings/capture", json=body))

    # ---------- Entities (methodology entity, PI-181) ----------
    # The `entity` methodology record (ENT-NNN). Domain affiliations are
    # NOT inlined on create/update — attach them via `add_reference` with
    # the `entity_scopes_to_domain` relationship kind (entity.md §3.5.4).

    async def get_entity(
        identifier: str, include_deleted: bool = False
    ) -> Any:
        """Return one entity (methodology) record by its ENT-NNN identifier."""
        params = {"include_deleted": "true"} if include_deleted else None
        return await _unwrap(
            await http.get(f"/entities/{identifier}", params=params)
        )

    async def list_entities(include_deleted: bool = False) -> Any:
        """List all entity (methodology) records in identifier order.

        Pass ``include_deleted=true`` to include soft-deleted rows.
        """
        params = {"include_deleted": "true"} if include_deleted else None
        return await _unwrap(await http.get("/entities", params=params))

    async def create_entity(
        name: str,
        description: str,
        notes: str | None = None,
        status: str | None = None,
        kind: str | None = None,
        identifier: str | None = None,
        default_sort_field: str | None = None,
        default_sort_direction: str | None = None,
        track_activity: bool | None = None,
    ) -> Any:
        """Create an entity (methodology) record.

        Required: ``name``, ``description``. ``status`` defaults to
        ``candidate`` server-side; ``kind`` is optional (operators may
        defer classification to Phase 3). Identifier is server-assigned
        (ENT-NNN) when omitted.

        PRJ-025 PI-182 — engine-neutral design intent (all optional):
        ``default_sort_field`` (the field the entity sorts by) +
        ``default_sort_direction`` (``asc``/``desc``), and
        ``track_activity`` (whether to track an activity feed).

        Domain affiliations are NOT inlined here — attach them with a
        separate ``add_reference`` call using the
        ``entity_scopes_to_domain`` relationship kind.
        """
        body = {
            k: v
            for k, v in dict(
                entity_name=name,
                entity_description=description,
                entity_notes=notes,
                entity_status=status,
                entity_kind=kind,
                entity_identifier=identifier,
                entity_default_sort_field=default_sort_field,
                entity_default_sort_direction=default_sort_direction,
                entity_track_activity=track_activity,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.post("/entities", json=body))

    async def update_entity(
        identifier: str,
        name: str | None = None,
        description: str | None = None,
        notes: str | None = None,
        status: str | None = None,
        kind: str | None = None,
        default_sort_field: str | None = None,
        default_sort_direction: str | None = None,
        track_activity: bool | None = None,
    ) -> Any:
        """Update fields on an entity record (PATCH). Pass only the fields
        to change. Lifecycle status transitions are validated by the
        access layer (e.g. candidate → confirmed).

        PRJ-025 PI-182 — the engine-neutral design-intent attributes
        ``default_sort_field`` / ``default_sort_direction`` (asc/desc) /
        ``track_activity`` are settable here too."""
        body = {
            f"entity_{k}": v
            for k, v in dict(
                name=name,
                description=description,
                notes=notes,
                status=status,
                kind=kind,
                default_sort_field=default_sort_field,
                default_sort_direction=default_sort_direction,
                track_activity=track_activity,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.patch(f"/entities/{identifier}", json=body))

    async def delete_entity(identifier: str) -> Any:
        """Soft-delete an entity record (idempotent)."""
        return await _unwrap(await http.delete(f"/entities/{identifier}"))

    async def restore_entity(identifier: str) -> Any:
        """Restore a soft-deleted entity record."""
        return await _unwrap(
            await http.post(f"/entities/{identifier}/restore")
        )

    # ---------- Fields (methodology entity, PI-181) ----------
    # The `field` methodology record (FLD-NNN). Per field.md §3.5.4 the
    # mandatory `field_belongs_to_entity` parent edge is established
    # atomically by `create_field` via the `entity_identifier` arg — the
    # access layer writes the field row + the edge in one transaction.
    # PUT/PATCH do NOT re-parent; move a field with DELETE+add_reference.

    async def get_field(
        identifier: str, include_deleted: bool = False
    ) -> Any:
        """Return one field (methodology) record by its FLD-NNN identifier."""
        params = {"include_deleted": "true"} if include_deleted else None
        return await _unwrap(
            await http.get(f"/fields/{identifier}", params=params)
        )

    async def list_fields(
        entity_identifier: str | None = None,
        include_deleted: bool = False,
    ) -> Any:
        """List field (methodology) records.

        Filter ``entity_identifier`` (ENT-NNN) returns only the fields
        whose live ``field_belongs_to_entity`` edge points to that entity.
        Pass ``include_deleted=true`` to include soft-deleted rows.
        """
        params = {
            k: v
            for k, v in dict(
                entity_identifier=entity_identifier,
                include_deleted="true" if include_deleted else None,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.get("/fields", params=params or None))

    async def create_field(
        entity_identifier: str,
        name: str,
        description: str,
        type: str,
        required: bool | None = None,
        notes: str | None = None,
        status: str | None = None,
        identifier: str | None = None,
        tooltip: str | None = None,
        usage_summary: str | None = None,
        default_value: str | None = None,
        format: str | None = None,
        numeric_scale: str | None = None,
        max_length: int | None = None,
        min: str | None = None,
        max: str | None = None,
        read_only: bool | None = None,
        unique: bool | None = None,
        externally_populated: bool | None = None,
        options: list | None = None,
    ) -> Any:
        """Create a field (methodology) record under a parent entity.

        Required: ``entity_identifier`` (the parent ENT-NNN), ``name``,
        ``description``, ``type``. The ``entity_identifier`` establishes
        the mandatory ``field_belongs_to_entity`` edge atomically with the
        field row (field.md §3.5.4) — no separate reference call is needed
        to parent a new field.

        ``status`` defaults to ``candidate`` and ``required`` to ``False``
        server-side. Identifier is server-assigned (FLD-NNN) when omitted.

        PRJ-025 PI-182 — engine-neutral design intent (all optional):
        ``tooltip`` (inline help), ``usage_summary`` (doc intent),
        ``default_value``, ``format`` (email/phone/url/percent/currency/
        date/datetime/time/multiline), ``numeric_scale`` (integer/decimal),
        ``max_length``, ``min``, ``max``, and the booleans ``read_only`` /
        ``unique`` / ``externally_populated``. ``options`` is an ordered
        list of enum/multi_enum options, each
        ``{"option_value": str, "option_label": str|None,
        "option_order": int|None}`` — supplying it populates the field's
        option set.
        """
        body = {
            k: v
            for k, v in dict(
                field_belongs_to_entity_identifier=entity_identifier,
                field_name=name,
                field_description=description,
                field_type=type,
                field_required=required,
                field_notes=notes,
                field_status=status,
                field_identifier=identifier,
                field_tooltip=tooltip,
                field_usage_summary=usage_summary,
                field_default_value=default_value,
                field_format=format,
                field_numeric_scale=numeric_scale,
                field_max_length=max_length,
                field_min=min,
                field_max=max,
                field_read_only=read_only,
                field_unique=unique,
                field_externally_populated=externally_populated,
                field_options=options,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.post("/fields", json=body))

    async def update_field(
        identifier: str,
        name: str | None = None,
        description: str | None = None,
        type: str | None = None,
        required: bool | None = None,
        notes: str | None = None,
        status: str | None = None,
        tooltip: str | None = None,
        usage_summary: str | None = None,
        default_value: str | None = None,
        format: str | None = None,
        numeric_scale: str | None = None,
        max_length: int | None = None,
        min: str | None = None,
        max: str | None = None,
        read_only: bool | None = None,
        unique: bool | None = None,
        externally_populated: bool | None = None,
        options: list | None = None,
    ) -> Any:
        """Update fields on a field record (PATCH). Pass only the fields to
        change. Does NOT re-parent — re-parenting requires DELETE of the
        old ``field_belongs_to_entity`` edge then a new ``add_reference``.

        PRJ-025 PI-182 — the engine-neutral design-intent attributes
        (``tooltip``, ``usage_summary``, ``default_value``, ``format``,
        ``numeric_scale``, ``max_length``, ``min``, ``max``, ``read_only``,
        ``unique``, ``externally_populated``) are settable here. Supplying
        ``options`` (a list) replaces the field's enum option set."""
        body = {
            f"field_{k}": v
            for k, v in dict(
                name=name,
                description=description,
                type=type,
                required=required,
                notes=notes,
                status=status,
                tooltip=tooltip,
                usage_summary=usage_summary,
                default_value=default_value,
                format=format,
                numeric_scale=numeric_scale,
                max_length=max_length,
                min=min,
                max=max,
                read_only=read_only,
                unique=unique,
                externally_populated=externally_populated,
                options=options,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.patch(f"/fields/{identifier}", json=body))

    async def delete_field(identifier: str) -> Any:
        """Soft-delete a field record (idempotent)."""
        return await _unwrap(await http.delete(f"/fields/{identifier}"))

    async def restore_field(identifier: str) -> Any:
        """Restore a soft-deleted field record."""
        return await _unwrap(
            await http.post(f"/fields/{identifier}/restore")
        )

    # --- Associations (composite design record, PRJ-025 PI-189) ---
    # An association (ASN-NNN) is the engine-neutral description of an
    # entity-to-entity link — the construct the EspoCRM adapter renders into
    # the `relationships:` block. Both endpoints are ENT-NNN identifiers
    # validated to exist and be live in the active engagement.

    async def get_association(
        identifier: str, include_deleted: bool = False
    ) -> Any:
        """Return one association (composite design) record by its ASN-NNN id."""
        params = {"include_deleted": "true"} if include_deleted else None
        return await _unwrap(
            await http.get(f"/associations/{identifier}", params=params)
        )

    async def list_associations(
        source_entity: str | None = None,
        target_entity: str | None = None,
        include_deleted: bool = False,
    ) -> Any:
        """List association records.

        Filter ``source_entity`` / ``target_entity`` (each ENT-NNN) narrows
        on the endpoint columns. Pass ``include_deleted=true`` to include
        soft-deleted rows.
        """
        params = {
            k: v
            for k, v in dict(
                source_entity=source_entity,
                target_entity=target_entity,
                include_deleted="true" if include_deleted else None,
            ).items()
            if v is not None
        }
        return await _unwrap(
            await http.get("/associations", params=params or None)
        )

    async def create_association(
        name: str,
        source_entity: str,
        target_entity: str,
        cardinality: str,
        source_role: str | None = None,
        target_role: str | None = None,
        description: str | None = None,
        notes: str | None = None,
        status: str | None = None,
        identifier: str | None = None,
    ) -> Any:
        """Create an association (engine-neutral entity-to-entity link).

        Required: ``name``, ``source_entity`` / ``target_entity`` (both
        ENT-NNN, validated live), ``cardinality`` (one_to_one / one_to_many /
        many_to_many). ``status`` defaults to ``candidate`` server-side.
        Identifier is server-assigned (ASN-NNN) when omitted. ``source_role`` /
        ``target_role`` name the two sides of the link (e.g. "mentor").
        """
        body = {
            k: v
            for k, v in dict(
                association_name=name,
                association_source_entity=source_entity,
                association_target_entity=target_entity,
                association_cardinality=cardinality,
                association_source_role=source_role,
                association_target_role=target_role,
                association_description=description,
                association_notes=notes,
                association_status=status,
                association_identifier=identifier,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.post("/associations", json=body))

    async def update_association(
        identifier: str,
        name: str | None = None,
        source_entity: str | None = None,
        target_entity: str | None = None,
        cardinality: str | None = None,
        source_role: str | None = None,
        target_role: str | None = None,
        description: str | None = None,
        notes: str | None = None,
        status: str | None = None,
    ) -> Any:
        """Update fields on an association record (PATCH). Pass only the
        fields to change. Endpoint changes are re-validated against live
        entities; a status change is transition-validated."""
        body = {
            f"association_{k}": v
            for k, v in dict(
                name=name,
                source_entity=source_entity,
                target_entity=target_entity,
                cardinality=cardinality,
                source_role=source_role,
                target_role=target_role,
                description=description,
                notes=notes,
                status=status,
            ).items()
            if v is not None
        }
        return await _unwrap(
            await http.patch(f"/associations/{identifier}", json=body)
        )

    async def delete_association(identifier: str) -> Any:
        """Soft-delete an association record (idempotent)."""
        return await _unwrap(await http.delete(f"/associations/{identifier}"))

    async def restore_association(identifier: str) -> Any:
        """Restore a soft-deleted association record."""
        return await _unwrap(
            await http.post(f"/associations/{identifier}/restore")
        )

    # --- Engine overrides (composite design record, PRJ-025 PI-189) ---
    # An engine_override (OVR-NNN) is the sparse per-engine escape hatch that
    # adjusts how one design construct (entity / field / association) renders
    # for one target engine. No status lifecycle. The (target_engine,
    # subject_type, subject_identifier, attribute) tuple is unique.

    async def get_engine_override(
        identifier: str, include_deleted: bool = False
    ) -> Any:
        """Return one engine_override record by its OVR-NNN identifier."""
        params = {"include_deleted": "true"} if include_deleted else None
        return await _unwrap(
            await http.get(f"/engine-overrides/{identifier}", params=params)
        )

    async def list_engine_overrides(
        target_engine: str | None = None,
        subject_type: str | None = None,
        subject_identifier: str | None = None,
        include_deleted: bool = False,
    ) -> Any:
        """List engine_override records.

        Filter by ``target_engine`` (espocrm / hubspot), ``subject_type``
        (entity / field / association), and/or ``subject_identifier``. Pass
        ``include_deleted=true`` to include soft-deleted rows.
        """
        params = {
            k: v
            for k, v in dict(
                target_engine=target_engine,
                subject_type=subject_type,
                subject_identifier=subject_identifier,
                include_deleted="true" if include_deleted else None,
            ).items()
            if v is not None
        }
        return await _unwrap(
            await http.get("/engine-overrides", params=params or None)
        )

    async def create_engine_override(
        target_engine: str,
        subject_type: str,
        subject_identifier: str,
        attribute: str,
        value: Any | None = None,
        notes: str | None = None,
        identifier: str | None = None,
    ) -> Any:
        """Create an engine_override (sparse per-engine override).

        Required: ``target_engine`` (espocrm / hubspot), ``subject_type``
        (entity / field / association), ``subject_identifier`` (the ENT/FLD/
        ASN id being overridden), ``attribute`` (e.g. "internal_name",
        "formula", "enum_style"). ``value`` is free JSON stored verbatim. The
        (engine, subject_type, subject_identifier, attribute) tuple is unique;
        a duplicate is refused. Identifier is server-assigned (OVR-NNN) when
        omitted.
        """
        body = {
            k: v
            for k, v in dict(
                override_target_engine=target_engine,
                override_subject_type=subject_type,
                override_subject_identifier=subject_identifier,
                override_attribute=attribute,
                override_value=value,
                override_notes=notes,
                override_identifier=identifier,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.post("/engine-overrides", json=body))

    async def update_engine_override(
        identifier: str,
        target_engine: str | None = None,
        subject_type: str | None = None,
        subject_identifier: str | None = None,
        attribute: str | None = None,
        value: Any | None = None,
        notes: str | None = None,
    ) -> Any:
        """Update fields on an engine_override record (PATCH). Pass only the
        fields to change. The uniqueness tuple is re-checked when any of its
        members change."""
        body = {
            f"override_{k}": v
            for k, v in dict(
                target_engine=target_engine,
                subject_type=subject_type,
                subject_identifier=subject_identifier,
                attribute=attribute,
                value=value,
                notes=notes,
            ).items()
            if v is not None
        }
        return await _unwrap(
            await http.patch(f"/engine-overrides/{identifier}", json=body)
        )

    async def delete_engine_override(identifier: str) -> Any:
        """Soft-delete an engine_override record (idempotent)."""
        return await _unwrap(
            await http.delete(f"/engine-overrides/{identifier}")
        )

    async def restore_engine_override(identifier: str) -> Any:
        """Restore a soft-deleted engine_override record."""
        return await _unwrap(
            await http.post(f"/engine-overrides/{identifier}/restore")
        )

    # --- Rules (condition-carrying design record, PRJ-025 PI-189) ---
    # A rule (RUL-NNN) is a required/visible/valid gate on a field or entity,
    # carrying a neutral condition AST. The subject (FLD-NNN / ENT-NNN) is
    # validated to exist, be live, and match the subject_type.

    async def get_rule(identifier: str, include_deleted: bool = False) -> Any:
        """Return one rule (condition-carrying design) record by its RUL-NNN id."""
        params = {"include_deleted": "true"} if include_deleted else None
        return await _unwrap(
            await http.get(f"/rules/{identifier}", params=params)
        )

    async def list_rules(
        subject_type: str | None = None,
        subject_identifier: str | None = None,
        effect: str | None = None,
        include_deleted: bool = False,
    ) -> Any:
        """List rule records.

        Filter ``subject_type`` (field / entity), ``subject_identifier`` (the
        FLD/ENT id), and/or ``effect`` (required_when / visible_when /
        valid_when). Pass ``include_deleted=true`` to include soft-deleted rows.
        """
        params = {
            k: v
            for k, v in dict(
                subject_type=subject_type,
                subject_identifier=subject_identifier,
                effect=effect,
                include_deleted="true" if include_deleted else None,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.get("/rules", params=params or None))

    async def create_rule(
        name: str,
        subject_type: str,
        subject_identifier: str,
        effect: str,
        condition: Any,
        message: str | None = None,
        description: str | None = None,
        notes: str | None = None,
        status: str | None = None,
        identifier: str | None = None,
    ) -> Any:
        """Create a rule (engine-neutral required/visible/valid gate).

        Required: ``name``, ``subject_type`` (field / entity),
        ``subject_identifier`` (the FLD/ENT id, validated live and type-matched),
        ``effect`` (required_when / visible_when / valid_when), and
        ``condition`` (a neutral condition AST: a leaf
        ``{"field":..., "op":..., "value":...}`` or a group
        ``{"all":[...]}`` / ``{"any":[...]}``). ``message`` is the user-facing
        validation message for a valid_when rule. ``status`` defaults to
        ``candidate``; identifier is server-assigned (RUL-NNN) when omitted.
        """
        body = {
            k: v
            for k, v in dict(
                rule_name=name,
                rule_subject_type=subject_type,
                rule_subject_identifier=subject_identifier,
                rule_effect=effect,
                rule_condition=condition,
                rule_message=message,
                rule_description=description,
                rule_notes=notes,
                rule_status=status,
                rule_identifier=identifier,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.post("/rules", json=body))

    async def update_rule(
        identifier: str,
        name: str | None = None,
        subject_type: str | None = None,
        subject_identifier: str | None = None,
        effect: str | None = None,
        condition: Any | None = None,
        message: str | None = None,
        description: str | None = None,
        notes: str | None = None,
        status: str | None = None,
    ) -> Any:
        """Update fields on a rule record (PATCH). Pass only the fields to
        change. A subject change is re-validated; a condition change is
        re-validated as a neutral AST; a status change is transition-validated."""
        body = {
            f"rule_{k}": v
            for k, v in dict(
                name=name,
                subject_type=subject_type,
                subject_identifier=subject_identifier,
                effect=effect,
                condition=condition,
                message=message,
                description=description,
                notes=notes,
                status=status,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.patch(f"/rules/{identifier}", json=body))

    async def delete_rule(identifier: str) -> Any:
        """Soft-delete a rule record (idempotent)."""
        return await _unwrap(await http.delete(f"/rules/{identifier}"))

    async def restore_rule(identifier: str) -> Any:
        """Restore a soft-deleted rule record."""
        return await _unwrap(await http.post(f"/rules/{identifier}/restore"))

    # --- Views (condition-carrying design record, PRJ-025 PI-189) ---
    # A view (VEW-NNN) is the engine-neutral description of a list view: an
    # ordered list of column field references, an optional neutral-condition
    # filter, and a default sort.

    async def get_view(identifier: str, include_deleted: bool = False) -> Any:
        """Return one view (condition-carrying design) record by its VEW-NNN id."""
        params = {"include_deleted": "true"} if include_deleted else None
        return await _unwrap(
            await http.get(f"/views/{identifier}", params=params)
        )

    async def list_views(
        entity: str | None = None, include_deleted: bool = False
    ) -> Any:
        """List view records.

        Filter ``entity`` (the ENT-NNN listed). Pass ``include_deleted=true``
        to include soft-deleted rows.
        """
        params = {
            k: v
            for k, v in dict(
                entity=entity,
                include_deleted="true" if include_deleted else None,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.get("/views", params=params or None))

    async def create_view(
        name: str,
        entity: str,
        columns: list,
        filter: Any | None = None,
        sort_field: str | None = None,
        sort_direction: str | None = None,
        description: str | None = None,
        notes: str | None = None,
        status: str | None = None,
        identifier: str | None = None,
    ) -> Any:
        """Create a view (engine-neutral list view).

        Required: ``name``, ``entity`` (the ENT-NNN listed, validated live),
        and ``columns`` (a non-empty ordered list of field references — field
        names or FLD-NNN). ``filter`` is an optional neutral condition AST;
        ``sort_field`` / ``sort_direction`` (asc / desc) set the default sort.
        ``status`` defaults to ``candidate``; identifier is server-assigned
        (VEW-NNN) when omitted.
        """
        body: dict[str, Any] = {
            "view_name": name,
            "view_entity": entity,
            "view_columns": columns,
        }
        body.update(
            {
                k: v
                for k, v in dict(
                    view_filter=filter,
                    view_sort_field=sort_field,
                    view_sort_direction=sort_direction,
                    view_description=description,
                    view_notes=notes,
                    view_status=status,
                    view_identifier=identifier,
                ).items()
                if v is not None
            }
        )
        return await _unwrap(await http.post("/views", json=body))

    async def update_view(
        identifier: str,
        name: str | None = None,
        entity: str | None = None,
        columns: list | None = None,
        filter: Any | None = None,
        sort_field: str | None = None,
        sort_direction: str | None = None,
        description: str | None = None,
        notes: str | None = None,
        status: str | None = None,
    ) -> Any:
        """Update fields on a view record (PATCH). Pass only the fields to
        change. An entity change is re-validated; a filter change is
        re-validated as a neutral AST; a status change is transition-validated."""
        body = {
            f"view_{k}": v
            for k, v in dict(
                name=name,
                entity=entity,
                columns=columns,
                filter=filter,
                sort_field=sort_field,
                sort_direction=sort_direction,
                description=description,
                notes=notes,
                status=status,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.patch(f"/views/{identifier}", json=body))

    async def delete_view(identifier: str) -> Any:
        """Soft-delete a view record (idempotent)."""
        return await _unwrap(await http.delete(f"/views/{identifier}"))

    async def restore_view(identifier: str) -> Any:
        """Restore a soft-deleted view record."""
        return await _unwrap(await http.post(f"/views/{identifier}/restore"))

    # --- Automations (condition-carrying design record, PRJ-025 PI-189) ---
    # An automation (AUT-NNN) is the engine-neutral description of a workflow
    # on one entity: a trigger, an optional neutral-condition gate, and an
    # ordered list of typed action objects.

    async def get_automation(
        identifier: str, include_deleted: bool = False
    ) -> Any:
        """Return one automation (condition-carrying design) record by its
        AUT-NNN identifier."""
        params = {"include_deleted": "true"} if include_deleted else None
        return await _unwrap(
            await http.get(f"/automations/{identifier}", params=params)
        )

    async def list_automations(
        entity: str | None = None,
        trigger: str | None = None,
        include_deleted: bool = False,
    ) -> Any:
        """List automation records.

        Filter ``entity`` (the ENT-NNN) and/or ``trigger`` (on_create /
        on_update / on_delete / scheduled / manual). Pass
        ``include_deleted=true`` to include soft-deleted rows.
        """
        params = {
            k: v
            for k, v in dict(
                entity=entity,
                trigger=trigger,
                include_deleted="true" if include_deleted else None,
            ).items()
            if v is not None
        }
        return await _unwrap(
            await http.get("/automations", params=params or None)
        )

    async def create_automation(
        name: str,
        entity: str,
        trigger: str,
        actions: list,
        condition: Any | None = None,
        description: str | None = None,
        notes: str | None = None,
        status: str | None = None,
        identifier: str | None = None,
    ) -> Any:
        """Create an automation (engine-neutral workflow).

        Required: ``name``, ``entity`` (the ENT-NNN, validated live),
        ``trigger`` (on_create / on_update / on_delete / scheduled / manual),
        and ``actions`` (a non-empty ordered list of objects each with a
        ``"type"`` in set_field / send_notification / create_record /
        update_related / webhook). ``condition`` is an optional neutral
        condition AST. ``status`` defaults to ``candidate``; identifier is
        server-assigned (AUT-NNN) when omitted.
        """
        body: dict[str, Any] = {
            "automation_name": name,
            "automation_entity": entity,
            "automation_trigger": trigger,
            "automation_actions": actions,
        }
        body.update(
            {
                k: v
                for k, v in dict(
                    automation_condition=condition,
                    automation_description=description,
                    automation_notes=notes,
                    automation_status=status,
                    automation_identifier=identifier,
                ).items()
                if v is not None
            }
        )
        return await _unwrap(await http.post("/automations", json=body))

    async def update_automation(
        identifier: str,
        name: str | None = None,
        entity: str | None = None,
        trigger: str | None = None,
        actions: list | None = None,
        condition: Any | None = None,
        description: str | None = None,
        notes: str | None = None,
        status: str | None = None,
    ) -> Any:
        """Update fields on an automation record (PATCH). Pass only the fields
        to change. An entity change is re-validated; a condition change is
        re-validated as a neutral AST; an actions change re-validates each
        action's type; a status change is transition-validated."""
        body = {
            f"automation_{k}": v
            for k, v in dict(
                name=name,
                entity=entity,
                trigger=trigger,
                actions=actions,
                condition=condition,
                description=description,
                notes=notes,
                status=status,
            ).items()
            if v is not None
        }
        return await _unwrap(
            await http.patch(f"/automations/{identifier}", json=body)
        )

    async def delete_automation(identifier: str) -> Any:
        """Soft-delete an automation record (idempotent)."""
        return await _unwrap(await http.delete(f"/automations/{identifier}"))

    async def restore_automation(identifier: str) -> Any:
        """Restore a soft-deleted automation record."""
        return await _unwrap(
            await http.post(f"/automations/{identifier}/restore")
        )

    # Declaration-ordered surface. Adding a tool = define it above and
    # append it here; both the MCP server and the chat dispatcher pick it
    # up automatically.
    funcs: list[Callable[..., Any]] = [
        select_engagement,
        get_active_engagement,
        resolve_agent_profile_contract,
        list_agent_profiles,
        create_agent_profile,
        list_skills,
        list_governance_rules,
        list_learnings,
        capture_learning,
        get_current_charter,
        get_charter_version,
        list_charter_versions,
        replace_charter,
        get_current_status,
        get_status_version,
        list_status_versions,
        replace_status,
        get_decision,
        list_decisions,
        create_decision,
        update_decision,
        delete_decision,
        get_session,
        list_sessions,
        list_recent_sessions,
        create_session,
        update_session,
        delete_session,
        list_conversations_for_session,
        list_decisions_for_session,
        get_conversation,
        list_conversations,
        create_conversation,
        update_conversation,
        delete_conversation,
        get_risk,
        list_risks,
        create_risk,
        update_risk,
        delete_risk,
        get_planning_item,
        list_planning_items,
        create_planning_item,
        update_planning_item,
        delete_planning_item,
        get_topic,
        list_topics,
        create_topic,
        update_topic,
        delete_topic,
        list_references,
        add_reference,
        delete_reference,
        list_references_from,
        list_references_to,
        list_references_touching,
        catalog_search,
        catalog_get_entity,
        catalog_get_cross_system_map,
        catalog_gap_check,
        get_entity,
        list_entities,
        create_entity,
        update_entity,
        delete_entity,
        restore_entity,
        get_field,
        list_fields,
        create_field,
        update_field,
        delete_field,
        restore_field,
        get_association,
        list_associations,
        create_association,
        update_association,
        delete_association,
        restore_association,
        get_engine_override,
        list_engine_overrides,
        create_engine_override,
        update_engine_override,
        delete_engine_override,
        restore_engine_override,
        get_rule,
        list_rules,
        create_rule,
        update_rule,
        delete_rule,
        restore_rule,
        get_view,
        list_views,
        create_view,
        update_view,
        delete_view,
        restore_view,
        get_automation,
        list_automations,
        create_automation,
        update_automation,
        delete_automation,
        restore_automation,
    ]
    return [
        ToolDefinition(
            name=f.__name__,
            func=f,
            description=inspect.getdoc(f) or "",
            is_write=_is_write(f.__name__),
        )
        for f in funcs
    ]


def register_tools(server: FastMCP, http: httpx.AsyncClient) -> None:
    """Register the full tool surface with a FastMCP server (stdio / HTTP).

    Iterates :func:`tool_definitions` so the MCP surface and the chat UI
    dispatcher stay in lock-step. FastMCP introspects each callable's
    signature to build the input schema, exactly as the prior
    per-function ``@server.tool()`` decorators did.
    """
    for td in tool_definitions(http):
        server.tool(name=td.name, description=td.description)(td.func)
