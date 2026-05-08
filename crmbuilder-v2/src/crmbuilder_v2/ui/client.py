"""Typed HTTP client over the v2 storage REST API.

Wired in slice C. Wraps the storage system REST endpoints, parses the
``{data, meta, errors}`` envelope, and surfaces validation/conflict/
not-found errors as typed exceptions. Pure Python, no Qt dependencies.
Per DEC-019 the UI consumes the API exclusively through this client.

Slice C exposed read methods for the smoke-grade Decisions panel.
Slice D added sessions, risks, and references-touching for the round-1
read-only views. Slice E adds versioned reads for charter and status,
plus topics, planning items, and the full references list.
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

    def list_decisions(self) -> list[dict[str, Any]]:
        """Return all decisions as a list of dicts (one per decision record).

        Shape matches the API's response model in
        ``crmbuilder_v2/api/routers/decisions.py``.
        """
        result = self._request("GET", "/decisions")
        if not isinstance(result, list):
            return []
        return result

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
