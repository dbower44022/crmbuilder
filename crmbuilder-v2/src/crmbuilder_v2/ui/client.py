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

    def list_sessions(self) -> list[dict[str, Any]]:
        """Return all sessions as a list of dicts.

        Shape matches ``crmbuilder_v2/api/routers/sessions.py``.
        """
        result = self._request("GET", "/sessions")
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
