"""The Client Management methods of the desktop storage client
(PI-508 / REQ-591). ``ui.client.StorageClient`` is composed from every
segment's mixin plus the transport base, so these methods keep their names
and callers see no change. The mixin relies on the base's ``_request``.
"""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.ui.exceptions import (
    ServerError,
)


class ClientManagementMethods:
    """Engagement, participant and client calls; mixed into ``StorageClient``."""

    _request: Any  # supplied by the transport base

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
        optional ``engagement_status`` / ``engagement_identifier``).
        Raises ``RequestShapeError`` on 422
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

    # Participants (methodology entity — REL-040 / PI-094, REQ-412)
    # ------------------------------------------------------------------

    def list_participants(
        self, *, include_deleted: bool = False
    ) -> list[dict[str, Any]]:
        """Return all participants as a list of dicts.

        Shape matches ``crmbuilder_v2/api/routers/participant.py``. With
        ``include_deleted=True`` soft-deleted participants are included;
        otherwise the API filters them out.
        """
        path = "/participants"
        if include_deleted:
            path = "/participants?include_deleted=true"
        result = self._request("GET", path)
        if not isinstance(result, list):
            return []
        return result

    def get_participant(self, identifier: str) -> dict[str, Any]:
        """Return a single participant by identifier (e.g. ``"PTC-001"``).

        Raises ``NotFoundError`` if the participant does not exist (or is
        soft-deleted — the API 404s soft-deleted rows by default).
        """
        result = self._request("GET", f"/participants/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for get_participant",
            )
        return result

    def create_participant(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /participants. Returns the created record dict.

        The body uses the parent-prefixed field names
        (``participant_name``, ``participant_role_kind``, optional
        ``participant_affiliation`` / ``participant_contact`` /
        ``participant_notes`` / ``participant_status``).
        ``participant_identifier`` is server-assigned when omitted. The
        persona-backing link is NOT inlined — attach it afterwards via
        ``create_reference`` with the ``persona_backed_by_participant``
        kind (source persona → target participant).

        Raises ``RequestShapeError`` on 422 (identifier-format /
        name-uniqueness / status-enum), ``ConflictError`` on 409
        (explicit-identifier collision).
        """
        result = self._request("POST", "/participants", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for create_participant",
            )
        return result

    def update_participant(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT /participants/{identifier} — full record replace.

        The body is the full record; ``participant_identifier`` in the
        body must match the path. Raises ``NotFoundError`` on 404,
        ``RequestShapeError`` on 422 (identifier mismatch, validation,
        or invalid status transition).
        """
        result = self._request(
            "PUT", f"/participants/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for update_participant",
            )
        return result

    def patch_participant(
        self, identifier: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH /participants/{identifier} — partial update.

        Body should contain only the changed fields. Raises
        ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (validation or invalid status transition).
        """
        result = self._request(
            "PATCH", f"/participants/{identifier}", json_body=body
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for patch_participant",
            )
        return result

    def delete_participant(self, identifier: str) -> Any:
        """DELETE /participants/{identifier}. Soft-deletes; idempotent.

        Returns the API's response data. Raises ``NotFoundError`` on
        404. The outbound ``persona_backed_by_participant`` reference
        persists.
        """
        return self._request("DELETE", f"/participants/{identifier}")

    def restore_participant(self, identifier: str) -> dict[str, Any]:
        """POST /participants/{identifier}/restore. Clears the soft-delete.

        Raises ``NotFoundError`` on 404, ``RequestShapeError`` on 422
        (the record is not soft-deleted).
        """
        result = self._request(
            "POST", f"/participants/{identifier}/restore"
        )
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200,
                errors=[],
                message="Expected dict body for restore_participant",
            )
        return result

    def next_participant_identifier(self) -> str:
        """GET /participants/next-identifier. Returns the next ``PTC-NNN``."""
        result = self._request("GET", "/participants/next-identifier")
        if isinstance(result, dict) and isinstance(result.get("next"), str):
            return result["next"]
        raise ServerError(
            status_code=200,
            errors=[],
            message=(
                "Expected {'next': str} body for next_participant_identifier"
            ),
        )

    # Clients (PI-512 / REQ-589): the organisation above the engagement
    # ------------------------------------------------------------------

    def list_clients(self, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        """GET /clients. Each record carries its engagement identifiers."""
        path = "/clients?include_deleted=true" if include_deleted else "/clients"
        result = self._request("GET", path)
        return result if isinstance(result, list) else []

    def get_client(self, identifier: str) -> dict[str, Any]:
        """GET /clients/{identifier}. Raises ``NotFoundError`` when absent."""
        result = self._request("GET", f"/clients/{identifier}")
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200, errors=[], message="Expected dict body for get_client"
            )
        return result

    def next_client_identifier(self) -> str:
        """GET /clients/next-identifier."""
        result = self._request("GET", "/clients/next-identifier")
        if isinstance(result, dict) and isinstance(result.get("next"), str):
            return result["next"]
        raise ServerError(
            status_code=200, errors=[], message="Expected {next: str} body"
        )

    def create_client(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST /clients with the ``client_*`` field names."""
        result = self._request("POST", "/clients", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=201, errors=[], message="Expected dict body for create_client"
            )
        return result

    def update_client(self, identifier: str, body: dict[str, Any]) -> dict[str, Any]:
        """PUT /clients/{identifier}, a full replace."""
        result = self._request("PUT", f"/clients/{identifier}", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200, errors=[], message="Expected dict body for update_client"
            )
        return result

    def patch_client(self, identifier: str, body: dict[str, Any]) -> dict[str, Any]:
        """PATCH /clients/{identifier}, a partial update."""
        result = self._request("PATCH", f"/clients/{identifier}", json_body=body)
        if not isinstance(result, dict):
            raise ServerError(
                status_code=200, errors=[], message="Expected dict body for patch_client"
            )
        return result

    def delete_client(self, identifier: str) -> dict[str, Any]:
        """DELETE /clients/{identifier}; refused while it holds engagements."""
        result = self._request("DELETE", f"/clients/{identifier}")
        return result if isinstance(result, dict) else {}

    def restore_client(self, identifier: str) -> dict[str, Any]:
        """POST /clients/{identifier}/restore."""
        result = self._request("POST", f"/clients/{identifier}/restore")
        return result if isinstance(result, dict) else {}

    def list_client_engagements(self, identifier: str) -> list[dict[str, Any]]:
        """GET /clients/{identifier}/engagements."""
        result = self._request("GET", f"/clients/{identifier}/engagements")
        return result if isinstance(result, list) else []

    def get_engagement_clients(self, engagement_identifier: str) -> dict[str, Any]:
        """GET /engagements/{identifier}/clients: ``clients`` and ``primary``."""
        result = self._request("GET", f"/engagements/{engagement_identifier}/clients")
        return result if isinstance(result, dict) else {"clients": [], "primary": None}

    def set_engagement_clients(
        self,
        engagement_identifier: str,
        clients: list[str],
        *,
        primary: str | None = None,
    ) -> dict[str, Any]:
        """PUT /engagements/{identifier}/clients, replacing the whole set."""
        result = self._request(
            "PUT",
            f"/engagements/{engagement_identifier}/clients",
            json_body={"clients": clients, "primary": primary},
        )
        return result if isinstance(result, dict) else {"clients": [], "primary": None}


MIXIN = ClientManagementMethods
