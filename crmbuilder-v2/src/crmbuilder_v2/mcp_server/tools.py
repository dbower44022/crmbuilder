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

from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP


async def _unwrap(response: httpx.Response) -> Any:
    """Pull the envelope's ``data`` field, or raise on error envelopes."""
    response.raise_for_status()
    body = response.json()
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body.get("data")


def register_tools(server: FastMCP, http: httpx.AsyncClient) -> None:
    # ---------- Charter ----------

    @server.tool()
    async def get_current_charter() -> Any:
        """Return the current charter document (singleton, latest version)."""
        return await _unwrap(await http.get("/charter"))

    @server.tool()
    async def get_charter_version(version: int) -> Any:
        """Return a specific historical charter version."""
        return await _unwrap(await http.get(f"/charter/versions/{version}"))

    @server.tool()
    async def list_charter_versions() -> Any:
        """List all charter versions, newest first."""
        return await _unwrap(await http.get("/charter/versions"))

    @server.tool()
    async def replace_charter(payload: dict) -> Any:
        """Replace the charter, creating a new version. Previous version becomes
        historical."""
        return await _unwrap(await http.put("/charter", json={"payload": payload}))

    # ---------- Status ----------

    @server.tool()
    async def get_current_status() -> Any:
        """Return the current project status (singleton, latest version)."""
        return await _unwrap(await http.get("/status"))

    @server.tool()
    async def get_status_version(version: int) -> Any:
        """Return a specific historical status version."""
        return await _unwrap(await http.get(f"/status/versions/{version}"))

    @server.tool()
    async def list_status_versions() -> Any:
        """List all status versions, newest first."""
        return await _unwrap(await http.get("/status/versions"))

    @server.tool()
    async def replace_status(payload: dict) -> Any:
        """Replace the status, creating a new version."""
        return await _unwrap(await http.put("/status", json={"payload": payload}))

    # ---------- Decisions ----------

    @server.tool()
    async def get_decision(identifier: str) -> Any:
        """Return one decision record by its DEC-NNN identifier."""
        return await _unwrap(await http.get(f"/decisions/{identifier}"))

    @server.tool()
    async def list_decisions() -> Any:
        """List all decisions in identifier order."""
        return await _unwrap(await http.get("/decisions"))

    @server.tool()
    async def create_decision(
        identifier: str,
        title: str,
        decision_date: str,
        status: str,
        context: str = "",
        decision: str = "",
        rationale: str = "",
        alternatives_considered: str = "",
        consequences: str = "",
        supersedes: str | None = None,
        superseded_by: str | None = None,
    ) -> Any:
        """Create a decision record. Status must be one of Active, Superseded,
        Withdrawn."""
        body = {
            "identifier": identifier,
            "title": title,
            "decision_date": decision_date,
            "status": status,
            "context": context,
            "decision": decision,
            "rationale": rationale,
            "alternatives_considered": alternatives_considered,
            "consequences": consequences,
            "supersedes": supersedes,
            "superseded_by": superseded_by,
        }
        return await _unwrap(await http.post("/decisions", json=body))

    @server.tool()
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
        supersedes: str | None = None,
        superseded_by: str | None = None,
    ) -> Any:
        """Update fields on a decision. Pass only the fields to change."""
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
                supersedes=supersedes,
                superseded_by=superseded_by,
            ).items()
            if v is not None
        }
        return await _unwrap(await http.patch(f"/decisions/{identifier}", json=body))

    @server.tool()
    async def delete_decision(identifier: str) -> Any:
        """Delete a decision record."""
        return await _unwrap(await http.delete(f"/decisions/{identifier}"))

    # ---------- Sessions ----------

    @server.tool()
    async def get_session(identifier: str) -> Any:
        """Return one session record by its SES-NNN identifier."""
        return await _unwrap(await http.get(f"/sessions/{identifier}"))

    @server.tool()
    async def list_sessions(limit: int | None = None) -> Any:
        """List sessions, newest first. Pass ``limit`` to truncate."""
        params = {"limit": limit} if limit is not None else None
        return await _unwrap(await http.get("/sessions", params=params))

    @server.tool()
    async def list_recent_sessions(limit: int = 3) -> Any:
        """Return the most recent ``limit`` sessions (DEC-011 Tier 2 read).
        Default 3."""
        return await _unwrap(
            await http.get("/orientation/recent-sessions", params={"limit": limit})
        )

    @server.tool()
    async def create_session(
        identifier: str,
        title: str,
        session_date: str,
        status: str,
        conversation_reference: str = "",
        topics_covered: str = "",
        summary: str = "",
        artifacts_produced: str = "",
        in_flight_at_end: str = "",
    ) -> Any:
        """Create a session record. Status must be 'Complete' or 'In Progress'.
        Sessions are append-only — once written, they are not edited."""
        body = {
            "identifier": identifier,
            "title": title,
            "session_date": session_date,
            "status": status,
            "conversation_reference": conversation_reference,
            "topics_covered": topics_covered,
            "summary": summary,
            "artifacts_produced": artifacts_produced,
            "in_flight_at_end": in_flight_at_end,
        }
        return await _unwrap(await http.post("/sessions", json=body))

    @server.tool()
    async def delete_session(identifier: str) -> Any:
        """Delete a session record (rare — sessions are typically only deleted
        when written by mistake)."""
        return await _unwrap(await http.delete(f"/sessions/{identifier}"))

    @server.tool()
    async def list_decisions_for_session(identifier: str) -> Any:
        """List the decisions referenced by a given session (DEC-011 Tier 2)."""
        return await _unwrap(
            await http.get(f"/orientation/decisions-for-session/{identifier}")
        )

    # ---------- Risks ----------

    @server.tool()
    async def get_risk(identifier: str) -> Any:
        """Return one risk record."""
        return await _unwrap(await http.get(f"/risks/{identifier}"))

    @server.tool()
    async def list_risks() -> Any:
        """List all risks."""
        return await _unwrap(await http.get("/risks"))

    @server.tool()
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

    @server.tool()
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

    @server.tool()
    async def delete_risk(identifier: str) -> Any:
        """Delete a risk record."""
        return await _unwrap(await http.delete(f"/risks/{identifier}"))

    # ---------- Planning items ----------

    @server.tool()
    async def get_planning_item(identifier: str) -> Any:
        """Return one planning item."""
        return await _unwrap(await http.get(f"/planning-items/{identifier}"))

    @server.tool()
    async def list_planning_items() -> Any:
        """List all planning items."""
        return await _unwrap(await http.get("/planning-items"))

    @server.tool()
    async def create_planning_item(
        identifier: str,
        title: str,
        item_type: str,
        status: str,
        description: str = "",
        resolution_reference: str | None = None,
    ) -> Any:
        """Create a planning item. item_type ∈ {planning_dimension, open_question,
        pending_work}; status ∈ {Open, Resolved, Deferred}."""
        return await _unwrap(
            await http.post(
                "/planning-items",
                json={
                    "identifier": identifier,
                    "title": title,
                    "item_type": item_type,
                    "description": description,
                    "status": status,
                    "resolution_reference": resolution_reference,
                },
            )
        )

    @server.tool()
    async def update_planning_item(
        identifier: str,
        title: str | None = None,
        item_type: str | None = None,
        description: str | None = None,
        status: str | None = None,
        resolution_reference: str | None = None,
    ) -> Any:
        """Update a planning item."""
        body = {
            k: v
            for k, v in dict(
                title=title,
                item_type=item_type,
                description=description,
                status=status,
                resolution_reference=resolution_reference,
            ).items()
            if v is not None
        }
        return await _unwrap(
            await http.patch(f"/planning-items/{identifier}", json=body)
        )

    @server.tool()
    async def delete_planning_item(identifier: str) -> Any:
        """Delete a planning item."""
        return await _unwrap(await http.delete(f"/planning-items/{identifier}"))

    # ---------- Topics ----------

    @server.tool()
    async def get_topic(identifier: str) -> Any:
        """Return one topic."""
        return await _unwrap(await http.get(f"/topics/{identifier}"))

    @server.tool()
    async def list_topics() -> Any:
        """List all topics."""
        return await _unwrap(await http.get("/topics"))

    @server.tool()
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

    @server.tool()
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

    @server.tool()
    async def delete_topic(identifier: str) -> Any:
        """Delete a topic."""
        return await _unwrap(await http.delete(f"/topics/{identifier}"))

    # ---------- References (DEC-006) ----------

    @server.tool()
    async def list_references() -> Any:
        """List every reference in the database."""
        return await _unwrap(await http.get("/references"))

    @server.tool()
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

    @server.tool()
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

    @server.tool()
    async def list_references_from(source_type: str, source_id: str) -> Any:
        """All references where the given entity is the source."""
        return await _unwrap(
            await http.get(f"/references/from/{source_type}/{source_id}")
        )

    @server.tool()
    async def list_references_to(target_type: str, target_id: str) -> Any:
        """All references where the given entity is the target."""
        return await _unwrap(
            await http.get(f"/references/to/{target_type}/{target_id}")
        )

    @server.tool()
    async def list_references_touching(entity_type: str, entity_id: str) -> Any:
        """All references where the given entity is the source OR the target.
        Returns ``{"as_source": [...], "as_target": [...]}``."""
        return await _unwrap(
            await http.get(f"/references/touching/{entity_type}/{entity_id}")
        )
