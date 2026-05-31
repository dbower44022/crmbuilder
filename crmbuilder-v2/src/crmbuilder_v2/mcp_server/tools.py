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

    # Declaration-ordered surface. Adding a tool = define it above and
    # append it here; both the MCP server and the chat dispatcher pick it
    # up automatically.
    funcs: list[Callable[..., Any]] = [
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
