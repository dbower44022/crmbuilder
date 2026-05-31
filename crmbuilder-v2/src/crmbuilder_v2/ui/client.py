"""Typed HTTP client over the v2 storage REST API.

Wired in slice C. Wraps the storage system REST endpoints, parses the
``{data, meta, errors}`` envelope, and surfaces validation/conflict/
not-found errors as typed exceptions. Pure Python, no Qt dependencies.
Per DEC-019 the UI consumes the API exclusively through this client.

Slice C exposed read methods for the smoke-grade Decisions panel.
Slice D added sessions, risks, and references-touching for the round-1
read-only views. Slice E adds versioned reads for charter and status,
plus topics, planning items, and the full references list. Slice G
adds decision write methods (create, update, delete). v0.2 slice B
adds risk write methods (create, update, delete). v0.2 slice C adds
planning-item write methods (create, update, delete). v0.2 slice D
adds topic write methods (create, update, delete).
"""

from __future__ import annotations

import json
import logging
from types import TracebackType
from typing import Any

import httpx

from crmbuilder_v2.ui.exceptions import (
    ServerError,
    StorageConnectionError,
    from_response,
)

_log = logging.getLogger("crmbuilder_v2.ui.client")

_DEFAULT_TIMEOUT = 5.0


class StorageClient:
    """Synchronous HTTP client for the v2 storage REST API.

    Construct with a base URL (e.g. ``http://127.0.0.1:8765``). All
    requests go through the internal ``_request`` helper which:

    1. Catches network-level errors and raises ``StorageConnectionError``.
    2. On 2xx, parses the envelope and returns the ``data`` payload.
    3. On non-2xx, maps via ``exceptions.from_response`` to a typed
       ``StorageClientError`` subclass.

    Either pass a pre-built ``httpx.Client`` (caller owns it; this
    class will not close it), or omit ``client`` and the ``StorageClient``
    will construct and own its own client (closed via ``close()`` or
    the context-manager exit).
    """

    def __init__(
        self,
        base_url: str,
        client: httpx.Client | None = None,
        request_timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        if client is None:
            self._client = httpx.Client(
                base_url=self._base_url, timeout=request_timeout
            )
            self._owns_client = True
        else:
            self._client = client
            self._owns_client = False

    def close(self) -> None:
        """Close the owned httpx.Client (no-op if caller owns the client)."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> StorageClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def health(self) -> dict[str, Any]:
        """GET /health — liveness probe.

        Returns the health payload (e.g. ``{"ok": True}``) on success.
        Raises :class:`StorageConnectionError` when the API is
        unreachable (the signal the heartbeat acts on). Used by the main
        window's periodic heartbeat to detect an API that has gone away
        between user actions (PI-111).
        """
        result = self._request("GET", "/health")
        return result if isinstance(result, dict) else {}

    def list_decisions(
        self, *, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """Return all decisions as a list of dicts (one per decision record).

        Shape matches the API's response model in
        ``crmbuilder_v2/api/routers/decisions.py``. When ``include_deleted``
        is True, soft-deleted decisions are also returned (``status="Deleted"``);
        without it, the API filters them out (default behavior from v0.1
        slice H).
        """
        path = "/decisions"
        if include_deleted:
            path = "/decisions?include_deleted=true"
        result = self._request("GET", path)
        if not isinstance(result, list):
            return []
        return result

    def restore_decision(self, identifier: str) -> dict[str, Any]:
        """Restore a soft-deleted decision by PATCHing status back to Active.

        Convenience method around ``update_decision`` with the same on-the-wire
        call; the named method makes the restore intent explicit at call sites.
        """
        return self.update_decision(identifier, {"status": "Active"})

    def get_decision(self, identifier: str) -> dict[str, Any]:
        """Return a single decision by identifier (e.g. ``"DEC-019"``).

        Raises ``NotFoundError`` if the decision does not exist.
        """
        result = self._request("GET", f"/decisions/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_decision",
            )
        return result

    def create_decision(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /decisions. Returns the created record dict.

        Raises ``ValidationError`` on 400, ``ConflictError`` on 409
        (duplicate identifier), other ``StorageClientError`` subclasses
        per the standard error matrix.
        """
        result = self._request("POST", "/decisions", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_decision",
            )
        return result

    def update_decision(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /decisions/{identifier}. Body should contain only the
        fields that changed. Returns the updated record dict.

        Raises ``ValidationError`` on 400, ``NotFoundError`` on 404
        (decision was deleted by another writer between read and
        update), ``ConflictError`` on 409 (e.g., supersedes target
        doesn't exist).
        """
        result = self._request(
            "PATCH", f"/decisions/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for update_decision",
            )
        return result

    def delete_decision(self, identifier: str) -> Any:
        """DELETE /decisions/{identifier}. Returns the API's response data.

        Raises ``NotFoundError`` on 404, ``ConflictError`` on 409
        (decision is referenced by other records).
        """
        return self._request("DELETE", f"/decisions/{identifier}")

    def list_sessions(
        self,
        *,
        include_deleted: bool = False,
        status: str | None = None,
        medium: str | None = None,
        project_identifier: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return sessions as a list of dicts.

        Redesigned in PI-073 / DEC-314 — sessions are the medium-agnostic
        communication container. Filters: ``status`` (planned, in_flight,
        complete, cancelled, not_started, superseded), ``medium`` (chat,
        email, phone, zoom, in_person, slack, other), ``project_identifier``
        (filters via the session_belongs_to_project edge).
        """
        query: list[str] = []
        if include_deleted:
            query.append("include_deleted=true")
        if status is not None:
            query.append(f"status={status}")
        if medium is not None:
            query.append(f"medium={medium}")
        if project_identifier is not None:
            query.append(f"project_identifier={project_identifier}")
        path = "/sessions" + ("?" + "&".join(query) if query else "")
        result = self._request("GET", path)
        if not isinstance(result, list):
            return []
        return result

    def get_session(self, identifier: str) -> dict[str, Any]:
        """Return a single session by identifier (e.g. ``"SES-004"``).

        Raises ``NotFoundError`` if the session does not exist.
        """
        result = self._request("GET", f"/sessions/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_session",
            )
        return result

    def next_session_identifier(self) -> str:
        """Return the next available ``SES-NNN`` identifier."""
        result = self._request("GET", "/sessions/next-identifier")
        if isinstance(result, dict):
            nxt = result.get("next")
            if isinstance(nxt, str):
                return nxt
        raise ServerError(
            status_code=200,
            errors=[],
            message="Expected {'next': 'SES-NNN'} body for next_session_identifier",
        )

    def create_session(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /sessions. Returns the created record dict.

        Body shape (PI-073 / DEC-314): session_title, session_description,
        session_medium (required); plus optional session_identifier,
        session_notes, session_status (default 'planned'),
        session_scheduled_for, session_started_at, session_ended_at,
        session_participants (JSON array), session_medium_metadata (JSON
        object), references (array of GovernanceEdgeIn dicts), timestamps.
        """
        result = self._request("POST", "/sessions", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_session",
            )
        return result

    def patch_session(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /sessions/{identifier}. Partial update of mutable fields."""
        result = self._request(
            "PATCH", f"/sessions/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for patch_session",
            )
        return result

    def delete_session(self, identifier: str) -> dict[str, Any]:
        """DELETE /sessions/{identifier}. Soft-delete."""
        result = self._request("DELETE", f"/sessions/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for delete_session",
            )
        return result

    def restore_session(self, identifier: str) -> dict[str, Any]:
        """POST /sessions/{identifier}/restore. Reverse soft-delete."""
        result = self._request(
            "POST", f"/sessions/{identifier}/restore"
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for restore_session",
            )
        return result

    def list_risks(self) -> list[dict[str, Any]]:
        """Return all risks as a list of dicts.

        Shape matches ``crmbuilder_v2/api/routers/risks.py``.
        """
        result = self._request("GET", "/risks")
        if not isinstance(result, list):
            return []
        return result

    def get_risk(self, identifier: str) -> dict[str, Any]:
        """Return a single risk by identifier (e.g. ``"RSK-001"``).

        Raises ``NotFoundError`` if the risk does not exist.
        """
        result = self._request("GET", f"/risks/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_risk",
            )
        return result

    def create_risk(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /risks. Returns the created record dict.

        Raises ``ValidationError`` on 400, ``ConflictError`` on 409
        (duplicate identifier), other ``StorageClientError`` subclasses
        per the standard error matrix.
        """
        result = self._request("POST", "/risks", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_risk",
            )
        return result

    def update_risk(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /risks/{identifier}. Body should contain only the fields
        that changed. Returns the updated record dict.

        Raises ``ValidationError`` on 400, ``NotFoundError`` on 404
        (risk was deleted by another writer between read and update).
        """
        result = self._request(
            "PATCH", f"/risks/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for update_risk",
            )
        return result

    def delete_risk(self, identifier: str) -> Any:
        """DELETE /risks/{identifier}. Returns the API's response data.

        Raises ``NotFoundError`` on 404, ``ConflictError`` on 409
        (risk is referenced by other records).
        """
        return self._request("DELETE", f"/risks/{identifier}")

    # ------------------------------------------------------------------
    # Charter (versioned read)
    # ------------------------------------------------------------------

    def list_charter_versions(self) -> list[dict[str, Any]]:
        """Return all charter versions newest-first."""
        result = self._request("GET", "/charter/versions")
        if not isinstance(result, list):
            return []
        return result

    def get_charter_version(self, version: int) -> dict[str, Any]:
        """Return a single charter version. Raises ``NotFoundError`` if missing."""
        result = self._request("GET", f"/charter/versions/{version}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_charter_version",
            )
        return result

    def replace_charter(self, payload: dict[str, Any]) -> dict[str, Any]:
        """PUT /charter. Creates a new charter version with the given payload.

        Returns the new version record.
        """
        result = self._request("PUT", "/charter", json_body={"payload": payload})
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for replace_charter",
            )
        return result

    def make_charter_version_current(
        self, version: int
    ) -> dict[str, Any]:
        """PATCH /charter/versions/{n}/make-current. Flips ``is_current``
        to the named version. Returns the updated version record.

        Raises :class:`NotFoundError` if no version with that number exists.
        """
        result = self._request(
            "PATCH", f"/charter/versions/{version}/make-current"
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for make_charter_version_current",
            )
        return result

    # ------------------------------------------------------------------
    # Status (versioned read)
    # ------------------------------------------------------------------

    def list_status_versions(self) -> list[dict[str, Any]]:
        """Return all status versions newest-first."""
        result = self._request("GET", "/status/versions")
        if not isinstance(result, list):
            return []
        return result

    def get_status_version(self, version: int) -> dict[str, Any]:
        """Return a single status version. Raises ``NotFoundError`` if missing."""
        result = self._request("GET", f"/status/versions/{version}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_status_version",
            )
        return result

    def replace_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        """PUT /status. Creates a new status version with the given payload.

        Returns the new version record.
        """
        result = self._request("PUT", "/status", json_body={"payload": payload})
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for replace_status",
            )
        return result

    def make_status_version_current(
        self, version: int
    ) -> dict[str, Any]:
        """PATCH /status/versions/{n}/make-current. Flips ``is_current``
        to the named version. Returns the updated version record.

        Raises :class:`NotFoundError` if no version with that number exists.
        """
        result = self._request(
            "PATCH", f"/status/versions/{version}/make-current"
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for make_status_version_current",
            )
        return result

    # ------------------------------------------------------------------
    # Topics
    # ------------------------------------------------------------------

    def list_topics(self) -> list[dict[str, Any]]:
        result = self._request("GET", "/topics")
        if not isinstance(result, list):
            return []
        return result

    def get_topic(self, identifier: str) -> dict[str, Any]:
        """Return a single topic. Raises ``NotFoundError`` if missing."""
        result = self._request("GET", f"/topics/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_topic",
            )
        return result

    def create_topic(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /topics. Returns the created record dict.

        Raises ``ValidationError`` on 400, ``ConflictError`` on 409
        (duplicate identifier), other ``StorageClientError`` subclasses
        per the standard error matrix.
        """
        result = self._request("POST", "/topics", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_topic",
            )
        return result

    def update_topic(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /topics/{identifier}. Body should contain only the fields
        that changed. Returns the updated record dict.

        Raises ``ValidationError`` on 400, ``NotFoundError`` on 404
        (topic was deleted by another writer between read and update).
        """
        result = self._request(
            "PATCH", f"/topics/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for update_topic",
            )
        return result

    def delete_topic(self, identifier: str) -> Any:
        """DELETE /topics/{identifier}. Returns the API's response data.

        Raises ``NotFoundError`` on 404, ``ConflictError`` on 409
        (topic is referenced by other records or has children).
        """
        return self._request("DELETE", f"/topics/{identifier}")

    # ------------------------------------------------------------------
    # Planning items
    # ------------------------------------------------------------------

    def list_planning_items(self) -> list[dict[str, Any]]:
        result = self._request("GET", "/planning-items")
        if not isinstance(result, list):
            return []
        return result

    def get_planning_item(self, identifier: str) -> dict[str, Any]:
        """Return a single planning item. Raises ``NotFoundError`` if missing."""
        result = self._request("GET", f"/planning-items/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_planning_item",
            )
        return result

    def create_planning_item(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /planning-items. Returns the created record dict.

        Raises ``ValidationError`` on 400, ``ConflictError`` on 409
        (duplicate identifier), other ``StorageClientError`` subclasses
        per the standard error matrix.
        """
        result = self._request("POST", "/planning-items", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_planning_item",
            )
        return result

    def update_planning_item(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /planning-items/{identifier}. Body should contain only
        the fields that changed. Returns the updated record dict.

        Raises ``ValidationError`` on 400, ``NotFoundError`` on 404
        (planning item was deleted by another writer between read and
        update).
        """
        result = self._request(
            "PATCH", f"/planning-items/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for update_planning_item",
            )
        return result

    def delete_planning_item(self, identifier: str) -> Any:
        """DELETE /planning-items/{identifier}. Returns the API's response data.

        Raises ``NotFoundError`` on 404, ``ConflictError`` on 409
        (planning item is referenced by other records).
        """
        return self._request("DELETE", f"/planning-items/{identifier}")

    # ------------------------------------------------------------------
    # Domains (methodology entity — UI v0.4 slice B)
    # ------------------------------------------------------------------

    def list_domains(
        self, *, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """Return all domains as a list of dicts.

        Shape matches ``crmbuilder_v2/api/routers/domains.py``. With
        ``include_deleted=True`` soft-deleted domains are included;
        otherwise the API filters them out.
        """
        path = "/domains"
        if include_deleted:
            path = "/domains?include_deleted=true"
        result = self._request("GET", path)
        if not isinstance(result, list):
            return []
        return result

    def get_domain(self, identifier: str) -> dict[str, Any]:
        """Return a single domain by identifier (e.g. ``"DOM-001"``).

        Raises ``NotFoundError`` if the domain does not exist (or is
        soft-deleted — the API 404s soft-deleted rows by default).
        """
        result = self._request("GET", f"/domains/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_domain",
            )
        return result

    def create_domain(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /domains. Returns the created record dict.

        The body uses the parent-prefixed field names
        (``domain_name``, ``domain_purpose``, ``domain_description``,
        optional ``domain_notes`` / ``domain_status``). ``domain_identifier``
        is server-assigned when omitted. Raises ``RequestShapeError`` on
        422 (identifier-format / name-uniqueness / status-enum),
        ``ConflictError`` on 409 (explicit-identifier collision).
        """
        result = self._request("POST", "/domains", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_domain",
            )
        return result

    def update_domain(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT /domains/{identifier} — full record replace.

        The body is the full record; ``domain_identifier`` in the body
        must match the path. Raises ``NotFoundError`` on 404,
        ``RequestShapeError`` on 422 (identifier mismatch, validation,
        or invalid status transition).
        """
        result = self._request(
            "PUT", f"/domains/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for update_domain",
            )
        return result

    def patch_domain(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /domains/{identifier} — partial update.

        Body should contain only the changed fields. Raises
        ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (validation or invalid status transition).
        """
        result = self._request(
            "PATCH", f"/domains/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for patch_domain",
            )
        return result

    def delete_domain(self, identifier: str) -> Any:
        """DELETE /domains/{identifier}. Soft-deletes; idempotent.

        Returns the API's response data. Raises ``NotFoundError`` on 404.
        """
        return self._request("DELETE", f"/domains/{identifier}")

    def restore_domain(self, identifier: str) -> dict[str, Any]:
        """POST /domains/{identifier}/restore. Clears the soft-delete.

        Raises ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (the record is not soft-deleted).
        """
        result = self._request(
            "POST", f"/domains/{identifier}/restore"
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for restore_domain",
            )
        return result

    def next_domain_identifier(self) -> str:
        """GET /domains/next-identifier. Returns the next ``DOM-NNN``."""
        result = self._request("GET", "/domains/next-identifier")
        if isinstance(result, dict) and isinstance(result.get("next"), str):
            return result["next"]
        raise ServerError(
            status_code=200,
            errors=[],
            message="Expected {'next': str} body for next_domain_identifier",
        )

    # ------------------------------------------------------------------
    # Entities (methodology entity — UI v0.4 slice C)
    # ------------------------------------------------------------------

    def list_entities(
        self, *, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """Return all entities as a list of dicts.

        Shape matches ``crmbuilder_v2/api/routers/entities.py``. With
        ``include_deleted=True`` soft-deleted entities are included;
        otherwise the API filters them out.
        """
        path = "/entities"
        if include_deleted:
            path = "/entities?include_deleted=true"
        result = self._request("GET", path)
        if not isinstance(result, list):
            return []
        return result

    def get_entity(self, identifier: str) -> dict[str, Any]:
        """Return a single entity by identifier (e.g. ``"ENT-001"``).

        Raises ``NotFoundError`` if the entity does not exist (or is
        soft-deleted — the API 404s soft-deleted rows by default).
        """
        result = self._request("GET", f"/entities/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_entity",
            )
        return result

    def create_entity(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /entities. Returns the created record dict.

        The body uses the parent-prefixed field names (``entity_name``,
        ``entity_description``, optional ``entity_notes`` /
        ``entity_status``). ``entity_identifier`` is server-assigned
        when omitted. Domain affiliations are NOT inlined — attach them
        afterwards via ``create_reference`` with the
        ``entity_scopes_to_domain`` kind. Raises ``RequestShapeError``
        on 422 (identifier-format / name-uniqueness / status-enum),
        ``ConflictError`` on 409 (explicit-identifier collision).
        """
        result = self._request("POST", "/entities", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_entity",
            )
        return result

    def update_entity(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT /entities/{identifier} — full record replace.

        The body is the full record; ``entity_identifier`` in the body
        must match the path. Raises ``NotFoundError`` on 404,
        ``RequestShapeError`` on 422 (identifier mismatch, validation,
        or invalid status transition).
        """
        result = self._request(
            "PUT", f"/entities/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for update_entity",
            )
        return result

    def patch_entity(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /entities/{identifier} — partial update.

        Body should contain only the changed fields. Raises
        ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (validation or invalid status transition).
        """
        result = self._request(
            "PATCH", f"/entities/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for patch_entity",
            )
        return result

    def delete_entity(self, identifier: str) -> Any:
        """DELETE /entities/{identifier}. Soft-deletes; idempotent.

        Returns the API's response data. Raises ``NotFoundError`` on
        404. Outbound ``entity_scopes_to_domain`` references persist
        per ``entity.md`` section 3.4.6.
        """
        return self._request("DELETE", f"/entities/{identifier}")

    def restore_entity(self, identifier: str) -> dict[str, Any]:
        """POST /entities/{identifier}/restore. Clears the soft-delete.

        Raises ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (the record is not soft-deleted).
        """
        result = self._request(
            "POST", f"/entities/{identifier}/restore"
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for restore_entity",
            )
        return result

    def next_entity_identifier(self) -> str:
        """GET /entities/next-identifier. Returns the next ``ENT-NNN``."""
        result = self._request("GET", "/entities/next-identifier")
        if isinstance(result, dict) and isinstance(result.get("next"), str):
            return result["next"]
        raise ServerError(
            status_code=200,
            errors=[],
            message="Expected {'next': str} body for next_entity_identifier",
        )

    # ------------------------------------------------------------------
    # Requirements (methodology entity — PI-004 cohort, v0.5+)
    # ------------------------------------------------------------------

    def list_requirements(
        self, *, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """Return all requirements as a list of dicts.

        Shape matches ``crmbuilder_v2/api/routers/requirements.py``.
        With ``include_deleted=True`` soft-deleted requirements are
        included; otherwise the API filters them out. Per
        ``requirement.md`` §3.5.1.
        """
        path = "/requirements"
        if include_deleted:
            path = "/requirements?include_deleted=true"
        result = self._request("GET", path)
        if not isinstance(result, list):
            return []
        return result

    def get_requirement(self, identifier: str) -> dict[str, Any]:
        """Return a single requirement by identifier (e.g. ``"REQ-001"``).

        Raises ``NotFoundError`` if the requirement does not exist (or
        is soft-deleted — the API 404s soft-deleted rows by default).
        Per ``requirement.md`` §3.5.1.
        """
        result = self._request("GET", f"/requirements/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_requirement",
            )
        return result

    def create_requirement(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /requirements. Returns the created record dict.

        The body uses the parent-prefixed field names
        (``requirement_name``, ``requirement_description``,
        ``requirement_acceptance_summary``, optional
        ``requirement_priority`` / ``requirement_notes`` /
        ``requirement_status``). ``requirement_identifier`` is
        server-assigned when omitted. References (all five outbound
        kinds) are NOT inlined — attach them afterwards via
        ``create_reference``. Per ``requirement.md`` §3.5.5.

        Raises ``RequestShapeError`` on 422 (identifier-format /
        name-uniqueness / priority-enum / status-enum),
        ``ConflictError`` on 409 (explicit-identifier collision).
        """
        result = self._request("POST", "/requirements", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_requirement",
            )
        return result

    def update_requirement(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT /requirements/{identifier} — full record replace.

        The body is the full record; ``requirement_identifier`` in the
        body must match the path. Raises ``NotFoundError`` on 404,
        ``RequestShapeError`` on 422.
        """
        result = self._request(
            "PUT", f"/requirements/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for update_requirement",
            )
        return result

    def patch_requirement(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /requirements/{identifier} — partial update.

        Body should contain only the changed fields. Raises
        ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (validation or invalid status transition).
        """
        result = self._request(
            "PATCH", f"/requirements/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for patch_requirement",
            )
        return result

    def delete_requirement(self, identifier: str) -> Any:
        """DELETE /requirements/{identifier}. Soft-deletes; idempotent.

        Returns the API's response data. Raises ``NotFoundError`` on
        404. Outbound references (all five kinds) persist per
        ``requirement.md`` §3.4.7.
        """
        return self._request("DELETE", f"/requirements/{identifier}")

    def restore_requirement(self, identifier: str) -> dict[str, Any]:
        """POST /requirements/{identifier}/restore. Clears the soft-delete.

        Raises ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (the record is not soft-deleted).
        """
        result = self._request(
            "POST", f"/requirements/{identifier}/restore"
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for restore_requirement",
            )
        return result

    def next_requirement_identifier(self) -> str:
        """GET /requirements/next-identifier. Returns the next ``REQ-NNN``."""
        result = self._request("GET", "/requirements/next-identifier")
        if isinstance(result, dict) and isinstance(result.get("next"), str):
            return result["next"]
        raise ServerError(
            status_code=200,
            errors=[],
            message=(
                "Expected {'next': str} body for next_requirement_identifier"
            ),
        )

    # ------------------------------------------------------------------
    # Manual Configs (methodology entity — PI-004 cohort, v0.5+)
    # ------------------------------------------------------------------

    def list_manual_configs(
        self, *, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """Return all manual_configs as a list of dicts.

        Shape matches ``crmbuilder_v2/api/routers/manual_configs.py``.
        With ``include_deleted=True`` soft-deleted manual_configs are
        included; otherwise the API filters them out. Per
        ``manual_config.md`` §3.5.1.
        """
        path = "/manual-configs"
        if include_deleted:
            path = "/manual-configs?include_deleted=true"
        result = self._request("GET", path)
        if not isinstance(result, list):
            return []
        return result

    def get_manual_config(self, identifier: str) -> dict[str, Any]:
        """Return a single manual_config by identifier (e.g. ``"MCF-001"``).

        Raises ``NotFoundError`` if the manual_config does not exist (or
        is soft-deleted — the API 404s soft-deleted rows by default).
        Per ``manual_config.md`` §3.5.1.
        """
        result = self._request("GET", f"/manual-configs/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_manual_config",
            )
        return result

    def create_manual_config(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /manual-configs. Returns the created record dict.

        The body uses the parent-prefixed field names
        (``manual_config_name``, ``manual_config_category``,
        ``manual_config_description``, ``manual_config_instructions``,
        optional ``manual_config_notes`` / ``manual_config_status`` /
        ``manual_config_completed_at`` / ``manual_config_completed_by``).
        ``manual_config_identifier`` is server-assigned when omitted.
        References (all four outbound kinds) are NOT inlined — attach
        them afterwards via ``create_reference``. Per
        ``manual_config.md`` §3.5.4.

        Raises ``RequestShapeError`` on 422 (identifier-format /
        name-uniqueness / category-enum / status-enum / completed-
        fields-required), ``ConflictError`` on 409 (explicit-identifier
        collision).
        """
        result = self._request("POST", "/manual-configs", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_manual_config",
            )
        return result

    def update_manual_config(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT /manual-configs/{identifier} — full record replace.

        The body is the full record; ``manual_config_identifier`` in
        the body must match the path. Raises ``NotFoundError`` on 404,
        ``RequestShapeError`` on 422 (validation, status transition,
        or completion-field-population invariant).
        """
        result = self._request(
            "PUT", f"/manual-configs/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for update_manual_config",
            )
        return result

    def patch_manual_config(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /manual-configs/{identifier} — partial update.

        Body should contain only the changed fields. Raises
        ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (validation, invalid status transition, or the §3.5.3 cross-
        field invariant on transition into ``completed``).
        """
        result = self._request(
            "PATCH", f"/manual-configs/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for patch_manual_config",
            )
        return result

    def delete_manual_config(self, identifier: str) -> Any:
        """DELETE /manual-configs/{identifier}. Soft-deletes; idempotent.

        Returns the API's response data. Raises ``NotFoundError`` on
        404. Outbound references (all four kinds) persist per
        ``manual_config.md`` §3.4.6.
        """
        return self._request("DELETE", f"/manual-configs/{identifier}")

    def restore_manual_config(self, identifier: str) -> dict[str, Any]:
        """POST /manual-configs/{identifier}/restore. Clears the soft-delete.

        Raises ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (the record is not soft-deleted).
        """
        result = self._request(
            "POST", f"/manual-configs/{identifier}/restore"
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for restore_manual_config",
            )
        return result

    def next_manual_config_identifier(self) -> str:
        """GET /manual-configs/next-identifier. Returns the next ``MCF-NNN``."""
        result = self._request("GET", "/manual-configs/next-identifier")
        if isinstance(result, dict) and isinstance(result.get("next"), str):
            return result["next"]
        raise ServerError(
            status_code=200,
            errors=[],
            message=(
                "Expected {'next': str} body for "
                "next_manual_config_identifier"
            ),
        )

    # ------------------------------------------------------------------
    # Test Specs (methodology entity — PI-004 cohort closer, v0.5+)
    # ------------------------------------------------------------------

    def list_test_specs(
        self, *, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """Return all test_specs as a list of dicts.

        Shape matches ``crmbuilder_v2/api/routers/test_specs.py``. With
        ``include_deleted=True`` soft-deleted test_specs are included;
        otherwise the API filters them out. Per ``test_spec.md`` §3.5.1.
        """
        path = "/test-specs"
        if include_deleted:
            path = "/test-specs?include_deleted=true"
        result = self._request("GET", path)
        if not isinstance(result, list):
            return []
        return result

    def get_test_spec(self, identifier: str) -> dict[str, Any]:
        """Return a single test_spec by identifier (e.g. ``"TST-001"``).

        Raises ``NotFoundError`` if the test_spec does not exist (or is
        soft-deleted — the API 404s soft-deleted rows by default). Per
        ``test_spec.md`` §3.5.1.
        """
        result = self._request("GET", f"/test-specs/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_test_spec",
            )
        return result

    def create_test_spec(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /test-specs. Returns the created record dict.

        The body uses the parent-prefixed field names
        (``test_spec_name``, ``test_spec_description``,
        ``test_spec_steps``, ``test_spec_expected``, optional
        ``test_spec_setup`` / ``test_spec_notes`` / ``test_spec_status``
        / ``test_spec_last_run_outcome`` / ``test_spec_last_run_at`` /
        ``test_spec_last_run_notes``). ``test_spec_identifier`` is
        server-assigned when omitted. References (all three outbound
        kinds) are NOT inlined — attach them afterwards via
        ``create_reference``. Per ``test_spec.md`` §3.5.4.

        Raises ``RequestShapeError`` on 422 (identifier-format /
        name-uniqueness / status-enum / outcome-enum / cross-field
        invariant), ``ConflictError`` on 409 (explicit-identifier
        collision).
        """
        result = self._request("POST", "/test-specs", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_test_spec",
            )
        return result

    def update_test_spec(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT /test-specs/{identifier} — full record replace.

        The body is the full record; ``test_spec_identifier`` in the
        body must match the path. Raises ``NotFoundError`` on 404,
        ``RequestShapeError`` on 422 (validation, status transition,
        or §3.4.4 cross-field invariant).
        """
        result = self._request(
            "PUT", f"/test-specs/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for update_test_spec",
            )
        return result

    def patch_test_spec(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /test-specs/{identifier} — partial update.

        Body should contain only the changed fields. Raises
        ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (validation, invalid status transition — methodology-lifecycle
        field only; outcome is unrestricted — or the §3.4.4 cross-field
        invariant).
        """
        result = self._request(
            "PATCH", f"/test-specs/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for patch_test_spec",
            )
        return result

    def delete_test_spec(self, identifier: str) -> Any:
        """DELETE /test-specs/{identifier}. Soft-deletes; idempotent.

        Returns the API's response data. Raises ``NotFoundError`` on
        404. Outbound references (all three kinds) persist per
        ``test_spec.md`` §3.4.6.
        """
        return self._request("DELETE", f"/test-specs/{identifier}")

    def restore_test_spec(self, identifier: str) -> dict[str, Any]:
        """POST /test-specs/{identifier}/restore. Clears the soft-delete.

        Raises ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (the record is not soft-deleted).
        """
        result = self._request(
            "POST", f"/test-specs/{identifier}/restore"
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for restore_test_spec",
            )
        return result

    def next_test_spec_identifier(self) -> str:
        """GET /test-specs/next-identifier. Returns the next ``TST-NNN``."""
        result = self._request("GET", "/test-specs/next-identifier")
        if isinstance(result, dict) and isinstance(result.get("next"), str):
            return result["next"]
        raise ServerError(
            status_code=200,
            errors=[],
            message=(
                "Expected {'next': str} body for next_test_spec_identifier"
            ),
        )

    def record_test_spec_run(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """POST /test-specs/{identifier}/record-run — convenience endpoint.

        Per ``test_spec.md`` §3.8.1. Body shape:
        ``{"outcome": "passing", "notes": "...", "at": "2026-..."}``
        with ``notes`` and ``at`` optional. The §3.4.4 cross-field
        invariant applies — outcome=not_run clears last_run_at and
        last_run_notes; outcome in run states server-defaults
        last_run_at when ``at`` is omitted.
        """
        result = self._request(
            "POST",
            f"/test-specs/{identifier}/record-run",
            json_body=body,
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for record_test_spec_run",
            )
        return result

    # ------------------------------------------------------------------
    # Personas (methodology entity — v0.5+)
    # ------------------------------------------------------------------

    def list_personas(
        self, *, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """Return all personas as a list of dicts.

        Shape matches ``crmbuilder_v2/api/routers/persona.py``. With
        ``include_deleted=True`` soft-deleted personas are included;
        otherwise the API filters them out. Per ``persona.md`` §3.5.1.
        """
        path = "/personas"
        if include_deleted:
            path = "/personas?include_deleted=true"
        result = self._request("GET", path)
        if not isinstance(result, list):
            return []
        return result

    def get_persona(self, identifier: str) -> dict[str, Any]:
        """Return a single persona by identifier (e.g. ``"PER-001"``).

        Raises ``NotFoundError`` if the persona does not exist (or is
        soft-deleted — the API 404s soft-deleted rows by default).
        Per ``persona.md`` §3.5.1.
        """
        result = self._request("GET", f"/personas/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_persona",
            )
        return result

    def create_persona(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /personas. Returns the created record dict.

        The body uses the parent-prefixed field names
        (``persona_name``, ``persona_role_summary``, optional
        ``persona_responsibilities`` / ``persona_notes`` /
        ``persona_status``). ``persona_identifier`` is server-assigned
        when omitted. Domain affiliations and entity realizations are
        NOT inlined — attach them afterwards via ``create_reference``
        with the ``persona_scopes_to_domain`` /
        ``persona_realized_as_entity`` kinds. Per ``persona.md`` §3.5.4.

        Raises ``RequestShapeError`` on 422 (identifier-format /
        name-uniqueness / status-enum), ``ConflictError`` on 409
        (explicit-identifier collision).
        """
        result = self._request("POST", "/personas", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_persona",
            )
        return result

    def update_persona(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT /personas/{identifier} — full record replace.

        The body is the full record; ``persona_identifier`` in the
        body must match the path. Raises ``NotFoundError`` on 404,
        ``RequestShapeError`` on 422 (identifier mismatch, validation,
        or invalid status transition). Per ``persona.md`` §3.5.1.
        """
        result = self._request(
            "PUT", f"/personas/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for update_persona",
            )
        return result

    def patch_persona(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /personas/{identifier} — partial update.

        Body should contain only the changed fields. Raises
        ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (validation or invalid status transition).
        Per ``persona.md`` §3.5.1.
        """
        result = self._request(
            "PATCH", f"/personas/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for patch_persona",
            )
        return result

    def delete_persona(self, identifier: str) -> Any:
        """DELETE /personas/{identifier}. Soft-deletes; idempotent.

        Returns the API's response data. Raises ``NotFoundError`` on
        404. Outbound ``persona_scopes_to_domain`` and
        ``persona_realized_as_entity`` references persist per
        ``persona.md`` §3.4.6.
        """
        return self._request("DELETE", f"/personas/{identifier}")

    def restore_persona(self, identifier: str) -> dict[str, Any]:
        """POST /personas/{identifier}/restore. Clears the soft-delete.

        Raises ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (the record is not soft-deleted). Per ``persona.md`` §3.5.1.
        """
        result = self._request(
            "POST", f"/personas/{identifier}/restore"
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for restore_persona",
            )
        return result

    def next_persona_identifier(self) -> str:
        """GET /personas/next-identifier. Returns the next ``PER-NNN``.

        Per ``persona.md`` §3.5.2.
        """
        result = self._request("GET", "/personas/next-identifier")
        if isinstance(result, dict) and isinstance(result.get("next"), str):
            return result["next"]
        raise ServerError(
            status_code=200,
            errors=[],
            message="Expected {'next': str} body for next_persona_identifier",
        )

    # ------------------------------------------------------------------
    # Fields (methodology entity — v0.5+, PI-004 first slice)
    # ------------------------------------------------------------------

    def list_fields(
        self,
        *,
        entity_identifier: str | None = None,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        """Return all fields as a list of dicts.

        Shape matches ``crmbuilder_v2/api/routers/field.py``. With
        ``include_deleted=True`` soft-deleted fields are included;
        otherwise the API filters them out. With
        ``entity_identifier`` supplied, only fields whose live
        ``field_belongs_to_entity`` edge points to the supplied
        entity are returned (spec §3.5.5).
        """
        params = []
        if entity_identifier is not None:
            params.append(f"entity_identifier={entity_identifier}")
        if include_deleted:
            params.append("include_deleted=true")
        path = "/fields"
        if params:
            path = path + "?" + "&".join(params)
        result = self._request("GET", path)
        if not isinstance(result, list):
            return []
        return result

    def get_field(self, identifier: str) -> dict[str, Any]:
        """Return a single field by identifier (e.g. ``"FLD-001"``).

        Raises ``NotFoundError`` if the field does not exist (or is
        soft-deleted — the API 404s soft-deleted rows by default).
        Per ``field.md`` §3.5.1.
        """
        result = self._request("GET", f"/fields/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_field",
            )
        return result

    def create_field(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /fields. Returns the created record dict.

        The body uses the parent-prefixed field names (``field_name``,
        ``field_description``, ``field_type``,
        ``field_belongs_to_entity_identifier``, optional
        ``field_required`` / ``field_notes`` / ``field_status``).
        ``field_identifier`` is server-assigned when omitted.

        **Atomic POST per ``field.md`` §3.5.4**: the
        ``field_belongs_to_entity_identifier`` body key is REQUIRED;
        the access layer creates the field row, the
        ``field_belongs_to_entity`` edge, and the change-log emit in
        one transaction.

        Raises ``RequestShapeError`` on 422 (identifier-format /
        per-entity name uniqueness / status-enum / type-enum /
        invalid-parent-entity), ``ConflictError`` on 409
        (explicit-identifier collision).
        """
        result = self._request("POST", "/fields", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_field",
            )
        return result

    def update_field(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT /fields/{identifier} — full record replace.

        The body is the full record; ``field_identifier`` in the body
        must match the path. Does NOT accept
        ``field_belongs_to_entity_identifier`` — re-parenting requires
        explicit edge management per ``field.md`` §3.5.4. Raises
        ``NotFoundError`` on 404, ``RequestShapeError`` on 422.
        """
        result = self._request(
            "PUT", f"/fields/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for update_field",
            )
        return result

    def patch_field(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /fields/{identifier} — partial update.

        Body should contain only the changed fields. Does NOT accept
        ``field_belongs_to_entity_identifier``. Raises
        ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (validation or invalid status transition).
        """
        result = self._request(
            "PATCH", f"/fields/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for patch_field",
            )
        return result

    def delete_field(self, identifier: str) -> Any:
        """DELETE /fields/{identifier}. Soft-deletes; idempotent.

        Returns the API's response data. Raises ``NotFoundError`` on
        404. Atomically detaches the outgoing
        ``field_belongs_to_entity`` edge per ``field.md`` §3.4.6.
        """
        return self._request("DELETE", f"/fields/{identifier}")

    def restore_field(self, identifier: str) -> dict[str, Any]:
        """POST /fields/{identifier}/restore. Clears the soft-delete.

        Atomically restores the previously-attached
        ``field_belongs_to_entity`` edge. Raises ``NotFoundError`` on
        404, ``RequestShapeError`` on 422 (record not soft-deleted, or
        previously-attached parent entity itself soft-deleted).
        """
        result = self._request(
            "POST", f"/fields/{identifier}/restore"
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for restore_field",
            )
        return result

    def next_field_identifier(self) -> str:
        """GET /fields/next-identifier. Returns the next ``FLD-NNN``.

        Per ``field.md`` §3.5.2.
        """
        result = self._request("GET", "/fields/next-identifier")
        if isinstance(result, dict) and isinstance(result.get("next"), str):
            return result["next"]
        raise ServerError(
            status_code=200,
            errors=[],
            message="Expected {'next': str} body for next_field_identifier",
        )

    # ------------------------------------------------------------------
    # Processes (methodology entity — UI v0.4 slice D)
    # ------------------------------------------------------------------

    def list_processes(
        self, *, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """Return all processes as a list of dicts.

        Shape matches ``crmbuilder_v2/api/routers/processes.py``. With
        ``include_deleted=True`` soft-deleted processes are included;
        otherwise the API filters them out.
        """
        path = "/processes"
        if include_deleted:
            path = "/processes?include_deleted=true"
        result = self._request("GET", path)
        if not isinstance(result, list):
            return []
        return result

    def get_process(self, identifier: str) -> dict[str, Any]:
        """Return a single process by identifier (e.g. ``"PROC-001"``).

        Raises ``NotFoundError`` if the process does not exist (or is
        soft-deleted — the API 404s soft-deleted rows by default).
        """
        result = self._request("GET", f"/processes/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_process",
            )
        return result

    def create_process(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /processes. Returns the created record dict.

        The body uses the parent-prefixed field names
        (``process_name``, ``process_domain_identifier``,
        ``process_purpose``, optional ``process_classification`` /
        ``process_classification_rationale`` / ``process_notes``).
        ``process_identifier`` is server-assigned when omitted.
        ``process_domain_identifier`` is a required FK validated against
        live domains. Handoffs are NOT inlined — attach them afterwards
        via ``create_reference`` with the ``process_hands_off_to_process``
        kind. Raises ``RequestShapeError`` on 422 (identifier-format,
        name-uniqueness, classification-enum, classification-transition,
        or invalid-domain-reference), ``ConflictError`` on 409
        (explicit-identifier collision).
        """
        result = self._request("POST", "/processes", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_process",
            )
        return result

    def update_process(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT /processes/{identifier} — full record replace.

        The body is the full record; ``process_identifier`` in the body
        must match the path. Raises ``NotFoundError`` on 404,
        ``RequestShapeError`` on 422 (identifier mismatch, validation,
        invalid classification transition, or invalid domain reference).
        """
        result = self._request(
            "PUT", f"/processes/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for update_process",
            )
        return result

    def patch_process(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /processes/{identifier} — partial update.

        Body should contain only the changed fields. Raises
        ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (validation, invalid classification transition, or invalid
        domain reference).
        """
        result = self._request(
            "PATCH", f"/processes/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for patch_process",
            )
        return result

    def delete_process(self, identifier: str) -> Any:
        """DELETE /processes/{identifier}. Soft-deletes; idempotent.

        Returns the API's response data. Raises ``NotFoundError`` on
        404. Inbound and outbound ``process_hands_off_to_process``
        references persist per ``process.md`` section 3.4.5.
        """
        return self._request("DELETE", f"/processes/{identifier}")

    def restore_process(self, identifier: str) -> dict[str, Any]:
        """POST /processes/{identifier}/restore. Clears the soft-delete.

        Raises ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (the record is not soft-deleted).
        """
        result = self._request(
            "POST", f"/processes/{identifier}/restore"
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for restore_process",
            )
        return result

    def next_process_identifier(self) -> str:
        """GET /processes/next-identifier. Returns the next ``PROC-NNN``."""
        result = self._request("GET", "/processes/next-identifier")
        if isinstance(result, dict) and isinstance(result.get("next"), str):
            return result["next"]
        raise ServerError(
            status_code=200,
            errors=[],
            message="Expected {'next': str} body for next_process_identifier",
        )

    # ------------------------------------------------------------------
    # CRM Candidates (methodology entity — UI v0.4 slice E)
    # ------------------------------------------------------------------

    def list_crm_candidates(
        self, *, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """Return all crm_candidates as a list of dicts.

        Shape matches ``crmbuilder_v2/api/routers/crm_candidates.py``.
        With ``include_deleted=True`` soft-deleted records are
        included; otherwise the API filters them out.
        """
        path = "/crm_candidates"
        if include_deleted:
            path = "/crm_candidates?include_deleted=true"
        result = self._request("GET", path)
        if not isinstance(result, list):
            return []
        return result

    def get_crm_candidate(self, identifier: str) -> dict[str, Any]:
        """Return a single crm_candidate by identifier (e.g. ``"CRM-001"``).

        Raises ``NotFoundError`` if the record does not exist (or is
        soft-deleted — the API 404s soft-deleted rows by default).
        """
        result = self._request("GET", f"/crm_candidates/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_crm_candidate",
            )
        return result

    def create_crm_candidate(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /crm_candidates. Returns the created record dict.

        The body uses the parent-prefixed field names
        (``crm_candidate_name``, ``crm_candidate_fit_reason``, optional
        ``crm_candidate_notes`` / ``crm_candidate_status``).
        ``crm_candidate_identifier`` is server-assigned when omitted.
        Raises ``RequestShapeError`` on 422 (identifier-format,
        name-uniqueness, status-enum, invalid status transition, or
        singleton-``selected`` conflict), ``ConflictError`` on 409
        (explicit-identifier collision).
        """
        result = self._request(
            "POST", "/crm_candidates", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_crm_candidate",
            )
        return result

    def update_crm_candidate(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT /crm_candidates/{identifier} — full record replace.

        The body is the full record; ``crm_candidate_identifier`` in
        the body must match the path. Raises ``NotFoundError`` on 404,
        ``RequestShapeError`` on 422 (identifier mismatch, validation,
        invalid status transition, or singleton-``selected`` conflict).
        """
        result = self._request(
            "PUT", f"/crm_candidates/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for update_crm_candidate",
            )
        return result

    def patch_crm_candidate(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /crm_candidates/{identifier} — partial update.

        Body should contain only the changed fields. Raises
        ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (validation, invalid status transition, or singleton-
        ``selected`` conflict).
        """
        result = self._request(
            "PATCH", f"/crm_candidates/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for patch_crm_candidate",
            )
        return result

    def delete_crm_candidate(self, identifier: str) -> Any:
        """DELETE /crm_candidates/{identifier}. Soft-deletes; idempotent.

        Returns the API's response data. Raises ``NotFoundError`` on
        404. Soft-deleting a ``selected`` record frees the singleton
        slot for a different record per spec section 3.4.3.
        """
        return self._request("DELETE", f"/crm_candidates/{identifier}")

    def restore_crm_candidate(self, identifier: str) -> dict[str, Any]:
        """POST /crm_candidates/{identifier}/restore. Clears the soft-delete.

        Raises ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (the record is not soft-deleted, or restoring a ``selected``
        record would violate the singleton-``selected`` constraint).
        """
        result = self._request(
            "POST", f"/crm_candidates/{identifier}/restore"
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for restore_crm_candidate",
            )
        return result

    def next_crm_candidate_identifier(self) -> str:
        """GET /crm_candidates/next-identifier. Returns the next ``CRM-NNN``."""
        result = self._request("GET", "/crm_candidates/next-identifier")
        if isinstance(result, dict) and isinstance(result.get("next"), str):
            return result["next"]
        raise ServerError(
            status_code=200,
            errors=[],
            message=(
                "Expected {'next': str} body for "
                "next_crm_candidate_identifier"
            ),
        )

    # ------------------------------------------------------------------
    # Engagements (meta DB; UI v0.5 slice B)
    # ------------------------------------------------------------------

    def list_engagements(
        self, *, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """GET /engagements. List engagements (default excludes soft-deleted)."""
        path = "/engagements"
        if include_deleted:
            path = "/engagements?include_deleted=true"
        result = self._request("GET", path)
        if not isinstance(result, list):
            return []
        return result

    def get_engagement(self, identifier: str) -> dict[str, Any]:
        """GET /engagements/{identifier}.

        Raises ``NotFoundError`` if the engagement does not exist.
        Includes soft-deleted records (the engagement endpoint
        returns deleted engagements directly).
        """
        result = self._request("GET", f"/engagements/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_engagement",
            )
        return result

    def create_engagement(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /engagements. Returns the created engagement record.

        Body uses the parent-prefixed field names
        (``engagement_code``, ``engagement_name``, ``engagement_purpose``,
        optional ``engagement_status`` / ``engagement_export_dir`` /
        ``engagement_identifier``). Raises ``RequestShapeError`` on 422
        (code/name/format validation), ``ConflictError`` on 409
        (explicit-identifier collision).
        """
        result = self._request("POST", "/engagements", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_engagement",
            )
        return result

    def update_engagement(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT /engagements/{identifier} — full record replace."""
        result = self._request(
            "PUT", f"/engagements/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for update_engagement",
            )
        return result

    def patch_engagement(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /engagements/{identifier} — partial update."""
        result = self._request(
            "PATCH", f"/engagements/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for patch_engagement",
            )
        return result

    def delete_engagement(self, identifier: str) -> dict[str, Any]:
        """DELETE /engagements/{identifier}. Soft-delete; idempotent."""
        result = self._request("DELETE", f"/engagements/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for delete_engagement",
            )
        return result

    def restore_engagement(self, identifier: str) -> dict[str, Any]:
        """POST /engagements/{identifier}/restore. Clears soft-delete.

        Raises ``RequestShapeError`` on 422 when the engagement is not
        soft-deleted.
        """
        result = self._request(
            "POST", f"/engagements/{identifier}/restore"
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for restore_engagement",
            )
        return result

    def next_engagement_identifier(self) -> str:
        """GET /engagements/next-identifier. Returns the next ``ENG-NNN``."""
        result = self._request("GET", "/engagements/next-identifier")
        if isinstance(result, dict) and isinstance(result.get("next"), str):
            return result["next"]
        raise ServerError(
            status_code=200,
            errors=[],
            message=(
                "Expected {'next': str} body for next_engagement_identifier"
            ),
        )

    # ------------------------------------------------------------------
    # Admin — connection introspection + in-process engagement re-routing
    # ------------------------------------------------------------------

    def connection_info(self) -> dict[str, Any]:
        """GET /admin/connection. Report the DB the live API is bound to."""
        result = self._request("GET", "/admin/connection")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for connection_info",
            )
        return result

    def version_info(self) -> dict[str, Any]:
        """GET /admin/version. API version + DB schema versions."""
        result = self._request("GET", "/admin/version")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for version_info",
            )
        return result

    def route_active_engagement(self, engagement_code: str) -> dict[str, Any]:
        """POST /admin/active-engagement. Re-route the live API in-process.

        Returns the post-switch connection info. Raises ``NotFoundError``
        if the code is unknown to the meta DB, ``StorageConnectionError``
        if the API is unreachable.
        """
        result = self._request(
            "POST",
            "/admin/active-engagement",
            json_body={"engagement_code": engagement_code},
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for route_active_engagement",
            )
        return result

    # ------------------------------------------------------------------
    # References (full list)
    # ------------------------------------------------------------------

    def list_references(self) -> list[dict[str, Any]]:
        """Return all references as a flat list of dicts.

        Each record carries ``source_type``, ``source_id``, ``target_type``,
        ``target_id``, ``relationship``.
        """
        result = self._request("GET", "/references")
        if not isinstance(result, list):
            return []
        return result

    def create_reference(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /references. Returns the created reference dict.

        v0.3 slice C — DEC-033. The body shape is
        ``{source_type, source_id, target_type, target_id, relationship}``.
        Raises ``ValidationError`` on 400, ``ConflictError`` on 409
        (the (source, target, relationship) tuple is uniquely indexed).
        """
        result = self._request("POST", "/references", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_reference",
            )
        return result

    def delete_reference(self, reference_id: int) -> None:
        """DELETE /references/{id}. Hard-deletes by integer primary key.

        v0.3 slice C — DEC-033. References are immutable identity-wise;
        "edit" is delete + create. Raises ``NotFoundError`` if the id
        doesn't exist (e.g., a stale UI view tried to delete a
        reference another writer already removed).
        """
        self._request("DELETE", f"/references/{reference_id}")

    def list_references_touching(
        self, entity_type: str, entity_id: str
    ) -> dict[str, list[dict[str, Any]]]:
        """Return references where ``entity_id`` appears as source or target.

        ``entity_type`` is one of: charter, status, decision, session,
        risk, planning_item, topic. ``entity_id`` is the entity's
        identifier (e.g., ``"DEC-018"``).

        The API returns a dict shaped ``{"as_source": [...], "as_target":
        [...]}``. Each reference has keys: source_type, source_id,
        target_type, target_id, relationship.
        """
        result = self._request(
            "GET",
            f"/references/touching/{entity_type}/{entity_id}",
        )
        if not isinstance(result, dict):
            return {"as_source": [], "as_target": []}
        # Defensive: ensure both keys exist with list values.
        return {
            "as_source": list(result.get("as_source") or []),
            "as_target": list(result.get("as_target") or []),
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        _log.debug("%s %s", method, path)
        try:
            resp = self._client.request(method, path, json=json_body)
        except (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.ReadError,
            httpx.NetworkError,
        ) as exc:
            raise StorageConnectionError(
                message=str(exc) or exc.__class__.__name__,
                original=exc,
            ) from exc

        if 200 <= resp.status_code < 300:
            try:
                body = resp.json()
            except (json.JSONDecodeError, ValueError) as exc:
                raise ServerError(
                    status_code=resp.status_code,
                    errors=[],
                    message="Response body was not parseable JSON",
                ) from exc
            if isinstance(body, dict) and "data" in body:
                return body["data"]
            return body

        # Non-2xx: log and raise a typed exception.
        _log.info(
            "%s %s -> %d", method, path, resp.status_code
        )
        raise from_response(resp)

    # ------------------------------------------------------------------
    # Governance entities (UI v0.7). Six new entity types: workstream,
    # conversation, reference_book, work_ticket, close_out_payload, and
    # deposit_event (POST + GET only, no PUT/PATCH/DELETE/restore).
    # ------------------------------------------------------------------

    def _expect_dict(self, result: Any, *, op: str) -> dict[str, Any]:
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200, errors=[], message=f"Expected dict body for {op}"
            )
        return result

    def _expect_list(self, result: Any) -> list[dict[str, Any]]:
        return result if isinstance(result, list) else []

    def _next_identifier_for(self, plural_path: str, op: str) -> str:
        result = self._request("GET", f"/{plural_path}/next-identifier")
        if isinstance(result, dict) and isinstance(result.get("next"), str):
            return result["next"]
        raise ServerError(
            status_code=200, errors=[], message=f"Expected {{'next': str}} body for {op}"
        )

    # ----- workstreams ------------------------------------------------------

    def list_projects(self, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        path = "/projects" + ("?include_deleted=true" if include_deleted else "")
        return self._expect_list(self._request("GET", path))

    def get_project(self, identifier: str) -> dict[str, Any]:
        return self._expect_dict(
            self._request("GET", f"/projects/{identifier}"), op="get_project"
        )

    def create_project(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._expect_dict(
            self._request("POST", "/projects", json_body=body), op="create_project"
        )

    def update_project(self, identifier: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._expect_dict(
            self._request("PUT", f"/projects/{identifier}", json_body=body),
            op="update_project",
        )

    def patch_project(self, identifier: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._expect_dict(
            self._request("PATCH", f"/projects/{identifier}", json_body=body),
            op="patch_project",
        )

    def delete_project(self, identifier: str) -> Any:
        return self._request("DELETE", f"/projects/{identifier}")

    def restore_project(self, identifier: str) -> dict[str, Any]:
        return self._expect_dict(
            self._request("POST", f"/projects/{identifier}/restore"),
            op="restore_project",
        )

    def next_project_identifier(self) -> str:
        return self._next_identifier_for("projects", "next_project_identifier")

    # ----- conversations ----------------------------------------------------

    def list_conversations(
        self,
        *,
        include_deleted: bool = False,
        status: str | None = None,
        session_identifier: str | None = None,
    ) -> list[dict[str, Any]]:
        """List conversations.

        PI-073 / DEC-314 — conversations belong to sessions (not directly
        to workstreams). The ``project_identifier`` filter is removed;
        use ``session_identifier`` instead, or traverse via sessions to
        get all conversations under a workstream.
        """
        params: list[str] = []
        if include_deleted:
            params.append("include_deleted=true")
        if status:
            params.append(f"status={status}")
        if session_identifier:
            params.append(f"session_identifier={session_identifier}")
        path = "/conversations" + ("?" + "&".join(params) if params else "")
        return self._expect_list(self._request("GET", path))

    def get_conversation(self, identifier: str) -> dict[str, Any]:
        return self._expect_dict(
            self._request("GET", f"/conversations/{identifier}"), op="get_conversation"
        )

    def create_conversation(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._expect_dict(
            self._request("POST", "/conversations", json_body=body),
            op="create_conversation",
        )

    def update_conversation(self, identifier: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._expect_dict(
            self._request("PUT", f"/conversations/{identifier}", json_body=body),
            op="update_conversation",
        )

    def patch_conversation(self, identifier: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._expect_dict(
            self._request("PATCH", f"/conversations/{identifier}", json_body=body),
            op="patch_conversation",
        )

    def delete_conversation(self, identifier: str) -> Any:
        return self._request("DELETE", f"/conversations/{identifier}")

    def restore_conversation(self, identifier: str) -> dict[str, Any]:
        return self._expect_dict(
            self._request("POST", f"/conversations/{identifier}/restore"),
            op="restore_conversation",
        )

    def next_conversation_identifier(self) -> str:
        return self._next_identifier_for("conversations", "next_conversation_identifier")

    # ----- reference_books --------------------------------------------------

    def list_reference_books(
        self, *, include_deleted: bool = False, kind: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        params: list[str] = []
        if include_deleted:
            params.append("include_deleted=true")
        if kind:
            params.append(f"kind={kind}")
        if status:
            params.append(f"status={status}")
        path = "/reference-books" + ("?" + "&".join(params) if params else "")
        return self._expect_list(self._request("GET", path))

    def get_reference_book(self, identifier: str) -> dict[str, Any]:
        return self._expect_dict(
            self._request("GET", f"/reference-books/{identifier}"),
            op="get_reference_book",
        )

    def create_reference_book(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._expect_dict(
            self._request("POST", "/reference-books", json_body=body),
            op="create_reference_book",
        )

    def update_reference_book(self, identifier: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._expect_dict(
            self._request("PUT", f"/reference-books/{identifier}", json_body=body),
            op="update_reference_book",
        )

    def patch_reference_book(self, identifier: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._expect_dict(
            self._request("PATCH", f"/reference-books/{identifier}", json_body=body),
            op="patch_reference_book",
        )

    def delete_reference_book(self, identifier: str) -> Any:
        return self._request("DELETE", f"/reference-books/{identifier}")

    def restore_reference_book(self, identifier: str) -> dict[str, Any]:
        return self._expect_dict(
            self._request("POST", f"/reference-books/{identifier}/restore"),
            op="restore_reference_book",
        )

    def next_reference_book_identifier(self) -> str:
        return self._next_identifier_for(
            "reference-books", "next_reference_book_identifier"
        )

    def list_reference_book_versions(self, identifier: str) -> list[dict[str, Any]]:
        return self._expect_list(
            self._request("GET", f"/reference-books/{identifier}/versions")
        )

    def create_reference_book_version(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        return self._expect_dict(
            self._request(
                "POST", f"/reference-books/{identifier}/versions", json_body=body
            ),
            op="create_reference_book_version",
        )

    def get_reference_book_version_at(
        self, identifier: str, as_of: str
    ) -> dict[str, Any] | None:
        result = self._request(
            "GET", f"/reference-books/{identifier}/version-at?as_of={as_of}"
        )
        return result if isinstance(result, dict) else None

    # ----- work_tickets -----------------------------------------------------

    def list_work_tickets(
        self, *, include_deleted: bool = False, kind: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        params: list[str] = []
        if include_deleted:
            params.append("include_deleted=true")
        if kind:
            params.append(f"kind={kind}")
        if status:
            params.append(f"status={status}")
        path = "/work-tickets" + ("?" + "&".join(params) if params else "")
        return self._expect_list(self._request("GET", path))

    def get_work_ticket(self, identifier: str) -> dict[str, Any]:
        return self._expect_dict(
            self._request("GET", f"/work-tickets/{identifier}"), op="get_work_ticket"
        )

    def create_work_ticket(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._expect_dict(
            self._request("POST", "/work-tickets", json_body=body),
            op="create_work_ticket",
        )

    def update_work_ticket(self, identifier: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._expect_dict(
            self._request("PUT", f"/work-tickets/{identifier}", json_body=body),
            op="update_work_ticket",
        )

    def patch_work_ticket(self, identifier: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._expect_dict(
            self._request("PATCH", f"/work-tickets/{identifier}", json_body=body),
            op="patch_work_ticket",
        )

    def delete_work_ticket(self, identifier: str) -> Any:
        return self._request("DELETE", f"/work-tickets/{identifier}")

    def restore_work_ticket(self, identifier: str) -> dict[str, Any]:
        return self._expect_dict(
            self._request("POST", f"/work-tickets/{identifier}/restore"),
            op="restore_work_ticket",
        )

    def next_work_ticket_identifier(self) -> str:
        return self._next_identifier_for("work-tickets", "next_work_ticket_identifier")

    # ----- close_out_payloads -----------------------------------------------

    def list_close_out_payloads(
        self, *, include_deleted: bool = False, status: str | None = None
    ) -> list[dict[str, Any]]:
        params: list[str] = []
        if include_deleted:
            params.append("include_deleted=true")
        if status:
            params.append(f"status={status}")
        path = "/close-out-payloads" + ("?" + "&".join(params) if params else "")
        return self._expect_list(self._request("GET", path))

    def get_close_out_payload(self, identifier: str) -> dict[str, Any]:
        return self._expect_dict(
            self._request("GET", f"/close-out-payloads/{identifier}"),
            op="get_close_out_payload",
        )

    def create_close_out_payload(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._expect_dict(
            self._request("POST", "/close-out-payloads", json_body=body),
            op="create_close_out_payload",
        )

    def update_close_out_payload(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        return self._expect_dict(
            self._request(
                "PUT", f"/close-out-payloads/{identifier}", json_body=body
            ),
            op="update_close_out_payload",
        )

    def patch_close_out_payload(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        return self._expect_dict(
            self._request(
                "PATCH", f"/close-out-payloads/{identifier}", json_body=body
            ),
            op="patch_close_out_payload",
        )

    def delete_close_out_payload(self, identifier: str) -> Any:
        return self._request("DELETE", f"/close-out-payloads/{identifier}")

    def restore_close_out_payload(self, identifier: str) -> dict[str, Any]:
        return self._expect_dict(
            self._request("POST", f"/close-out-payloads/{identifier}/restore"),
            op="restore_close_out_payload",
        )

    def next_close_out_payload_identifier(self) -> str:
        return self._next_identifier_for(
            "close-out-payloads", "next_close_out_payload_identifier"
        )

    # ----- deposit_events (POST + GET only) ---------------------------------

    def list_deposit_events(self, *, outcome: str | None = None) -> list[dict[str, Any]]:
        path = "/deposit-events" + (f"?outcome={outcome}" if outcome else "")
        return self._expect_list(self._request("GET", path))

    def get_deposit_event(self, identifier: str) -> dict[str, Any]:
        return self._expect_dict(
            self._request("GET", f"/deposit-events/{identifier}"),
            op="get_deposit_event",
        )

    def create_deposit_event(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._expect_dict(
            self._request("POST", "/deposit-events", json_body=body),
            op="create_deposit_event",
        )

    def next_deposit_event_identifier(self) -> str:
        return self._next_identifier_for(
            "deposit-events", "next_deposit_event_identifier"
        )

    # ----- commits (read-only in the UI; ingested via close-out) ------------
    # PI-031: the Commits panel browses commits and the planning_items
    # resolution chain walks session -> commits. Commits are documentary
    # records ingested through close-out payloads (DEC-185); the UI exposes
    # no write path, only these read accessors.

    def list_commits(
        self,
        *,
        include_deleted: bool = False,
        commit_repository: str | None = None,
        commit_session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return commits, newest first (API default sort per DEC-214).

        ``commit_repository`` / ``commit_session_id`` map to the server-side
        list filters; the Commits panel additionally filters client-side.
        """
        params: list[str] = []
        if include_deleted:
            params.append("include_deleted=true")
        if commit_repository:
            params.append(f"commit_repository={commit_repository}")
        if commit_session_id:
            params.append(f"commit_session_id={commit_session_id}")
        path = "/commits" + ("?" + "&".join(params) if params else "")
        return self._expect_list(self._request("GET", path))

    def get_commit(self, identifier: str) -> dict[str, Any]:
        return self._expect_dict(
            self._request("GET", f"/commits/{identifier}"),
            op="get_commit",
        )

    def list_commits_for_session(
        self, session_identifier: str
    ) -> list[dict[str, Any]]:
        """Commits attributed to a session (PI-073 session-grain, DEC-211 successor)."""
        return self._expect_list(
            self._request("GET", f"/sessions/{session_identifier}/commits")
        )

    def find_commit_by_sha(self, sha: str) -> tuple[str, Any]:
        """Natural-key SHA lookup with four-case behavior (DEC-213).

        Returns one of:

        * ``("found", record)`` — full-SHA hit or unambiguous prefix
        * ``("not_found", None)`` — 404 miss
        * ``("ambiguous", candidates)`` — 409, ``candidates`` is the list
          of candidate SHA strings (possibly empty if the body omits them)

        Implemented against the raw client because the ``/by-sha`` endpoint
        returns FastAPI's ``{"detail": ...}`` shape (status-bearing,
        non-envelope), so the typed-exception path would discard the
        409 candidate list.
        """
        try:
            resp = self._client.request("GET", f"/commits/by-sha/{sha}")
        except (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.ReadError,
            httpx.NetworkError,
        ) as exc:
            raise StorageConnectionError(
                message=str(exc) or exc.__class__.__name__, original=exc
            ) from exc
        if resp.status_code == 404:
            return ("not_found", None)
        if resp.status_code == 409:
            candidates: list[str] = []
            try:
                detail = resp.json().get("detail") or {}
                if isinstance(detail, dict):
                    candidates = list(detail.get("candidates") or [])
            except (json.JSONDecodeError, ValueError):
                candidates = []
            return ("ambiguous", candidates)
        if 200 <= resp.status_code < 300:
            try:
                body = resp.json()
            except (json.JSONDecodeError, ValueError) as exc:
                raise ServerError(
                    status_code=resp.status_code,
                    errors=[],
                    message="by-sha body was not parseable JSON",
                ) from exc
            record = body.get("data") if isinstance(body, dict) else None
            return ("found", record)
        raise from_response(resp)
