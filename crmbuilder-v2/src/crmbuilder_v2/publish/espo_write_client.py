"""The write half of the EspoCRM client (REQ-605 / PI-518).

Version 2 could read a live CRM system and generate a declaration for it,
but it could not write to one: every write on the publish path went through
the version 1 client. This module is version 2's own write-capable client.

It extends :class:`~crmbuilder_v2.introspect.espo_client.EspoIntrospectionClient`
rather than replacing it, because applying a declaration is check-then-write:
the publish path needs the reads and the writes through one connection, one
authentication and one transport. The read client's ``_request`` already
returns ``(status_code, body)`` and turns a dropped connection, a timeout or
a non-JSON body into a sentinel body instead of an exception, so a failed
write is diagnosable rather than raised; every method here inherits that.

The method names match the version 1 client they replace, so the managers
that are absorbed next can call them without translation.

**Nothing here logs a payload.** A field payload carries no secret, but a
record payload can (an instance's administrator password is written through
``patch_record``), so the sentinel bodies the transport returns are the only
thing that reaches a log, and the caller decides what to show. The deploy
runner's log masks values registered on its ``masks`` list, which a caller
can append to mid-run when it mints a secret.
"""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.introspect.espo_client import EspoIntrospectionClient

#: Layout types the platform stores per entity, addressed as
#: ``/{entity}/layout/{layout_type}`` on write.
_LAYOUT_PATH = "{api}/{entity}/layout/{layout_type}"


class EspoWriteClient(EspoIntrospectionClient):
    """An EspoCRM client that can change the instance as well as read it.

    Every method returns ``(status_code, body)``. A status of ``-1`` means
    the request never reached the server; the body then carries the
    diagnostic sentinel described on the read client.
    """

    # --- Field Manager ---

    @property
    def _field_manager_url(self) -> str:
        """The administration field-manager base URL."""
        return f"{self.api_url}/Admin/fieldManager"

    def get_field(
        self, entity: str, field_name: str
    ) -> tuple[int, dict[str, Any] | None]:
        """Read one field's definition.

        The write path checks a single field before deciding to create or
        update it; the read client's field list answers a different
        question (every field on an entity).

        :param entity: The platform's entity name.
        :param field_name: The platform's field name.
        :returns: ``(status_code, body)``.
        """
        url = f"{self._field_manager_url}/{entity}/{field_name}"
        return self._request("GET", url)

    def create_field(
        self, entity: str, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Create a field on an entity.

        ``isCustom`` is set for the caller: a field this system creates is
        by definition not one the platform shipped, and a payload that
        omits it produces a field the platform will not let an
        administrator edit afterwards.

        :param entity: The platform's entity name.
        :param payload: The field definition.
        :returns: ``(status_code, body)``.
        """
        url = f"{self._field_manager_url}/{entity}"
        return self._request("POST", url, json={**payload, "isCustom": True})

    def update_field(
        self, entity: str, field_name: str, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Update an existing field's definition.

        :param entity: The platform's entity name.
        :param field_name: The platform's field name.
        :param payload: The updated field definition.
        :returns: ``(status_code, body)``.
        """
        url = f"{self._field_manager_url}/{entity}/{field_name}"
        return self._request("PUT", url, json=payload)

    # --- Entity Manager ---

    def create_entity(
        self, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Create a custom entity type.

        :param payload: The entity definition — its name, base kind and
            labels at least.
        :returns: ``(status_code, body)``.
        """
        url = f"{self.api_url}/EntityManager/action/createEntity"
        return self._request("POST", url, json=payload)

    def update_entity(
        self, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Update an entity type's own settings — labels, stream, sorting.

        :param payload: The update, which must name the entity.
        :returns: ``(status_code, body)``.
        """
        url = f"{self.api_url}/EntityManager/action/updateEntity"
        return self._request("POST", url, json=payload)

    def remove_entity(self, name: str) -> tuple[int, dict[str, Any] | None]:
        """Remove a custom entity type.

        :param name: The platform's entity name, which for a custom entity
            carries the platform's prefix.
        :returns: ``(status_code, body)``.
        """
        url = f"{self.api_url}/EntityManager/action/removeEntity"
        return self._request("POST", url, json={"name": name})

    def check_entity_exists(self, name: str) -> tuple[int, bool]:
        """Answer whether an entity type exists.

        :param name: The platform's entity name.
        :returns: ``(status_code, exists)``. A transport failure answers
            ``False``, so a caller that must distinguish "absent" from
            "could not tell" reads the status.
        """
        url = f"{self.api_url}/Metadata?key=scopes.{name}"
        status_code, body = self._request("GET", url)
        if status_code == 200 and isinstance(body, dict) and body:
            return status_code, True
        return status_code, False

    def rebuild(self) -> tuple[int, dict[str, Any] | None]:
        """Rebuild the platform's definition cache.

        A structural change is not visible to the rest of a run until this
        returns, and even then not immediately — the caller waits for the
        new definitions to materialise.

        :returns: ``(status_code, body)``.
        """
        return self._request("POST", f"{self.api_url}/Admin/rebuild")

    def create_link(
        self, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Create a link between two entity types.

        :param payload: The full link definition, both ends included.
        :returns: ``(status_code, body)``.
        """
        url = f"{self.api_url}/EntityManager/action/createLink"
        return self._request("POST", url, json=payload)

    # --- Layouts ---

    def save_layout(
        self, entity: str, layout_type: str, payload: Any
    ) -> tuple[int, Any]:
        """Write one layout for an entity.

        :param entity: The platform's entity name.
        :param layout_type: The layout's name on the platform.
        :param payload: The layout body — a list of panels or of columns,
            depending on the layout's shape.
        :returns: ``(status_code, body)``.
        """
        url = _LAYOUT_PATH.format(
            api=self.api_url, entity=entity, layout_type=layout_type
        )
        return self._request("PUT", url, json=payload)

    # --- Records ---

    def create_record(
        self, entity: str, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Create a record.

        :param entity: The platform's entity name.
        :param payload: The values to set.
        :returns: ``(status_code, body)``.
        """
        return self._request("POST", f"{self.api_url}/{entity}", json=payload)

    def patch_record(
        self, entity: str, record_id: str, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Update the named values on a record, leaving the rest alone.

        :param entity: The platform's entity name.
        :param record_id: The record's identifier on the platform.
        :param payload: The values to change.
        :returns: ``(status_code, body)``.
        """
        url = f"{self.api_url}/{entity}/{record_id}"
        return self._request("PATCH", url, json=payload)

    # --- Teams and roles ---

    def create_team(
        self, name: str, description: str | None = None
    ) -> tuple[int, dict[str, Any] | None]:
        """Create a team.

        :param name: The team's name, which is how a declaration refers to
            it.
        :param description: Optional description.
        :returns: ``(status_code, body)``.
        """
        payload: dict[str, Any] = {"name": name}
        if description is not None:
            payload["description"] = description
        return self.create_record("Team", payload)

    def update_team(
        self, team_id: str, description: str | None = None
    ) -> tuple[int, dict[str, Any] | None]:
        """Update a team's description.

        The name is deliberately not accepted: a declaration identifies a
        team by name, so allowing a rename here would let a publish quietly
        detach a team from the design that describes it.

        :param team_id: The team's identifier on the platform.
        :param description: The new description, or ``None`` to clear it.
        :returns: ``(status_code, body)``.
        """
        return self.patch_record("Team", team_id, {"description": description})

    def create_role(
        self, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Create a role.

        Unlike a team, a role's shape varies — it carries the per-entity
        permission map and the system permissions — so the whole payload is
        the caller's to build.

        :param payload: The full role definition.
        :returns: ``(status_code, body)``.
        """
        return self.create_record("Role", payload)

    def update_role(
        self, role_id: str, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Update the named parts of a role, leaving the rest alone.

        This is what lets a caller manage the permissions the design
        describes without disturbing those it does not.

        :param role_id: The role's identifier on the platform.
        :param payload: The parts of the role to change.
        :returns: ``(status_code, body)``.
        """
        return self.patch_record("Role", role_id, payload)

    # --- Filtered-tab filters ---

    def create_report_filter(
        self, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        """Create the stored filter behind a navigation tab.

        This endpoint belongs to a paid extension. When the extension is
        absent the platform answers 404, which the caller reads as "not
        installed" rather than as a failure of the publish.

        :param payload: The filter — its name, the entity it filters and
            the filter body.
        :returns: ``(status_code, body)``.
        """
        return self._request("POST", f"{self.api_url}/ReportFilter", json=payload)

    def delete_report_filter(
        self, filter_id: str
    ) -> tuple[int, dict[str, Any] | None]:
        """Delete a stored filter.

        :param filter_id: The filter's identifier on the platform.
        :returns: ``(status_code, body)``.
        """
        url = f"{self.api_url}/ReportFilter/{filter_id}"
        return self._request("DELETE", url)
