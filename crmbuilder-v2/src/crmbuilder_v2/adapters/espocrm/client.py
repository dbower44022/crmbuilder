"""GET-only design client for the EspoCRM adapter (design §10).

Mirrors the established renderer shape
(``render/baseline_report.py::RestRenderClient``): a read-only client
protocol the impure fetch path drives, plus a REST implementation that
sends the ``X-Engagement`` header (PI-β) and unwraps the
``{data, meta, errors}`` envelope. The client never constructs a
write-capable surface — the read-only invariant is structural.

The three reads are exactly the design-record inputs the adapter
consumes: ``/entities`` (with intrinsic neutral attributes),
``/fields`` (with embedded ``field_options``, each annotated with its
``parent_entity_identifier`` resolved from the
``field_belongs_to_entity`` edge), and ``/engine-overrides`` (the sparse
per-engine override layer).
"""

from __future__ import annotations

import json
from urllib import error as urllib_error
from urllib import request as urllib_request


class DesignClient:
    """GET-only client protocol the adapter's fetch path drives.

    Defines no mutating method — the read-only invariant is structural.
    :class:`RestDesignClient` is the production implementation; tests
    supply an access-layer-backed fake.
    """

    def list_entities(self) -> list[dict]:
        raise NotImplementedError

    def list_fields(self) -> list[dict]:
        """Field records each carrying ``field_options`` (embedded) and
        ``parent_entity_identifier`` (from the parent edge)."""
        raise NotImplementedError

    def list_engine_overrides(self) -> list[dict]:
        raise NotImplementedError

    def list_associations(self) -> list[dict]:
        """Association records — the ``relationships:`` block source."""
        raise NotImplementedError

    def list_rules(self) -> list[dict]:
        """Field/entity rule records carrying a neutral condition AST."""
        raise NotImplementedError

    def list_views(self) -> list[dict]:
        """View records — the ``savedViews:`` block source (slice 3)."""
        raise NotImplementedError

    def list_automations(self) -> list[dict]:
        """Automation records — the ``workflows:`` block source (slice 3)."""
        raise NotImplementedError

    def list_dedup_rules(self) -> list[dict]:
        """Dedup-rule records — the ``duplicateChecks:`` source (slice 3)."""
        raise NotImplementedError

    def list_message_templates(self) -> list[dict]:
        """Message-template records — the ``emailTemplates:`` source (slice 3)."""
        raise NotImplementedError

    def list_field_permission_rules(self) -> list[dict]:
        """Field-permission-rule records — the ``fieldPermissions:`` source
        (PI-051 / REQ-129)."""
        raise NotImplementedError

    def list_field_visibility_rules(self) -> list[dict]:
        """Field-visibility-rule records — the ``fieldVisibility:`` source
        (PI-051 / REQ-128)."""
        raise NotImplementedError

    def list_roles(self) -> list[dict]:
        """Role records — resolves a rule's ``ROL-NNN`` to its ``role_name``
        for the emitted security blocks (PI-051)."""
        raise NotImplementedError

    def list_teams(self) -> list[dict]:
        """Team records, for the security program's ``teams:`` block.

        Roles were already read here to resolve a rule's role name; teams were
        not read at all, because nothing emitted them until DEC-998 (PI-417)."""
        raise NotImplementedError

    def list_filtered_tabs(self) -> list[dict]:
        """Filtered-tab records, for each entity's ``filteredTabs:`` block.

        Entity-bound, unlike roles and teams (DEC-998 names them as the case
        that files normally), so they were never part of the security program
        question — but nothing read them either until the block was emitted
        (PI-417 / REQ-519)."""
        raise NotImplementedError

    def list_layouts(self) -> list[dict]:
        """Layout records, for each entity's ``layout:`` block (PI-427 /
        REQ-519, DEC-951).

        Entity-bound like a filtered tab, so a layout files with its entity's
        program. The audit captured and compared layouts long before anything
        emitted them; until this reader existed a designed layout could be
        seen to differ from an instance but never pushed to one."""
        raise NotImplementedError

    def list_system_settings(self) -> list[dict]:
        """Active governed system-setting records (PI-406 / REQ-485)."""
        raise NotImplementedError

    def list_system_setting_values(self, instance_identifier: str) -> list[dict]:
        """The per-instance declared values for ``instance_identifier``.

        Only declared rows — an undeclared setting has no row, which is the
        not-captured state and must stay distinguishable from a declared
        empty value."""
        raise NotImplementedError


class RestDesignClient(DesignClient):
    """REST client of the live V2 API — GET requests only.

    Every request sends the ``X-Engagement`` header and unwraps the
    ``{data, meta, errors}`` envelope; a non-2xx body (which may bypass
    the envelope, see ``api/errors.py``) is surfaced verbatim in the
    raised error.
    """

    def __init__(
        self, base_url: str = "http://127.0.0.1:8765", engagement: str | None = None
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.engagement = engagement

    def _get(self, path: str):
        url = f"{self.base_url}{path}"
        req = urllib_request.Request(url, method="GET")
        if self.engagement:
            req.add_header("X-Engagement", self.engagement)
        try:
            with urllib_request.urlopen(req) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            raise RuntimeError(
                f"GET {path} -> HTTP {exc.code}: "
                f"{exc.read().decode('utf-8', errors='replace')}"
            ) from exc
        if payload.get("errors"):
            raise RuntimeError(f"GET {path} -> errors: {payload['errors']}")
        return payload["data"]

    def list_entities(self) -> list[dict]:
        return self._get("/entities")

    def list_fields(self) -> list[dict]:
        fields = self._get("/fields")
        refs = self._get(
            "/references?source_type=field"
            "&relationship_kind=field_belongs_to_entity"
        )
        # The query already narrows to the kind we want; the serialized row calls
        # the edge kind ``relationship``, not ``relationship_kind``. Re-filtering
        # on the wrong key silently emptied this map, so *every* field came back
        # with no parent entity — 0 of 254 on CBM (REQ-482). Trust the query.
        parent_by_field = {r["source_id"]: r["target_id"] for r in refs}
        for row in fields:
            row["parent_entity_identifier"] = parent_by_field.get(
                row["field_identifier"]
            )
        return fields

    def list_engine_overrides(self) -> list[dict]:
        return self._get("/engine-overrides")

    def list_associations(self) -> list[dict]:
        return self._get("/associations")

    def list_rules(self) -> list[dict]:
        return self._get("/rules")

    def list_views(self) -> list[dict]:
        return self._get("/views")

    def list_automations(self) -> list[dict]:
        return self._get("/automations")

    def list_dedup_rules(self) -> list[dict]:
        return self._get("/dedup-rules")

    def list_message_templates(self) -> list[dict]:
        return self._get("/message-templates")

    def list_field_permission_rules(self) -> list[dict]:
        return self._get("/field-permission-rules")

    def list_field_visibility_rules(self) -> list[dict]:
        return self._get("/field-visibility-rules")

    def list_roles(self) -> list[dict]:
        return self._get("/roles")

    def list_teams(self) -> list[dict]:
        return self._get("/teams")

    def list_filtered_tabs(self) -> list[dict]:
        return self._get("/filtered-tabs")

    def list_layouts(self) -> list[dict]:
        return self._get("/layouts")

    def list_system_settings(self) -> list[dict]:
        return self._get("/system-settings?status=confirmed")

    def list_system_setting_values(self, instance_identifier: str) -> list[dict]:
        # There is no all-values-for-one-instance endpoint; each setting lists
        # its declared values and the instance's rows are filtered out here.
        values: list[dict] = []
        for setting in self.list_system_settings():
            identifier = setting["system_setting_identifier"]
            for row in self._get(f"/system-settings/{identifier}/values"):
                if row.get("instance_identifier") == instance_identifier:
                    values.append(row)
        return values


class AccessDesignClient(DesignClient):
    """Design client reading straight from the access layer — REQ-482 / PI-403.

    The in-process counterpart to :class:`RestDesignClient`. Use this whenever the
    service itself is serving the request; use the REST client only from *outside*
    the service (the export and render CLIs).

    Why it exists: the publish path used to build a ``RestDesignClient`` against
    the service's own ``api_base_url`` and call its own endpoints. On a host with
    ``PRINCIPAL_AUTH_ENABLED`` and no credential of its own, the service's request
    to itself is rejected — publish failed with an opaque 500 wrapping
    ``HTTPError 401``. Reading the design directly removes the dependency rather
    than satisfying it: no token to issue, rotate, or have expire, and no HTTP
    round-trip per list call.

    Reads are wrapped in :func:`active_engagement` so row-level scoping applies
    exactly as the ``X-Engagement`` header applies it on the REST path.

    **Shape parity is the contract.** Every method must return what the REST
    client returns for the same store, since both feed the same generator. The
    endpoints are themselves thin wrappers over these repositories, so parity is
    structural for all but ``list_fields`` — see that method.
    """

    def __init__(self, engagement: str | None = None) -> None:
        self.engagement = engagement

    def _scope(self):
        """Apply the engagement scope for the duration of a read."""
        from contextlib import nullcontext

        from crmbuilder_v2.access.engagement_scope import active_engagement

        return active_engagement(self.engagement) if self.engagement else nullcontext()

    def _rows(self, fn, **kwargs) -> list[dict]:
        from crmbuilder_v2.access.db import session_scope

        with self._scope():
            with session_scope() as s:
                return fn(s, **kwargs)

    def list_entities(self) -> list[dict]:
        from crmbuilder_v2.access.repositories import entity

        return self._rows(entity.list_entities)

    def list_fields(self) -> list[dict]:
        """Every field, each stamped with its parent entity.

        Deliberately mirrors ``RestDesignClient.list_fields``: take *all* fields,
        then resolve parents from the ``field_belongs_to_entity`` edges. Walking
        entities and collecting their fields instead — the shape the test fake
        used — would silently drop any field lacking a parent edge, where the REST
        path keeps it with a ``None`` parent. Same records, same order, either way.
        """
        from crmbuilder_v2.access.db import session_scope
        from crmbuilder_v2.access.repositories import field, references

        with self._scope():
            with session_scope() as s:
                fields = field.list_fields(s)
                refs = references.list_references(
                    s,
                    source_type="field",
                    relationship_kind="field_belongs_to_entity",
                )
        parent_by_field = {r["source_id"]: r["target_id"] for r in refs}
        for row in fields:
            row["parent_entity_identifier"] = parent_by_field.get(
                row["field_identifier"]
            )
        return fields

    def list_engine_overrides(self) -> list[dict]:
        from crmbuilder_v2.access.repositories import engine_override

        return self._rows(engine_override.list_engine_overrides)

    def list_associations(self) -> list[dict]:
        from crmbuilder_v2.access.repositories import association

        return self._rows(association.list_associations)

    def list_rules(self) -> list[dict]:
        from crmbuilder_v2.access.repositories import rule

        return self._rows(rule.list_rules)

    def list_views(self) -> list[dict]:
        from crmbuilder_v2.access.repositories import view

        return self._rows(view.list_views)

    def list_automations(self) -> list[dict]:
        from crmbuilder_v2.access.repositories import automation

        return self._rows(automation.list_automations)

    def list_dedup_rules(self) -> list[dict]:
        from crmbuilder_v2.access.repositories import dedup_rule

        return self._rows(dedup_rule.list_dedup_rules)

    def list_message_templates(self) -> list[dict]:
        from crmbuilder_v2.access.repositories import message_template

        return self._rows(message_template.list_message_templates)

    def list_field_permission_rules(self) -> list[dict]:
        from crmbuilder_v2.access.repositories import field_permission_rule

        return self._rows(field_permission_rule.list_field_permission_rules)

    def list_field_visibility_rules(self) -> list[dict]:
        from crmbuilder_v2.access.repositories import field_visibility_rule

        return self._rows(field_visibility_rule.list_field_visibility_rules)

    def list_roles(self) -> list[dict]:
        from crmbuilder_v2.access.repositories import roles

        return self._rows(roles.list_roles)

    def list_teams(self) -> list[dict]:
        from crmbuilder_v2.access.repositories import teams

        return self._rows(teams.list_teams)

    def list_filtered_tabs(self) -> list[dict]:
        from crmbuilder_v2.access.repositories import filtered_tabs

        return self._rows(filtered_tabs.list_filtered_tabs)

    def list_layouts(self) -> list[dict]:
        from crmbuilder_v2.access.repositories import layouts

        return self._rows(layouts.list_layouts)

    def list_system_settings(self) -> list[dict]:
        from crmbuilder_v2.access.repositories import system_settings

        return self._rows(system_settings.list_system_settings, status="confirmed")

    def list_system_setting_values(self, instance_identifier: str) -> list[dict]:
        from crmbuilder_v2.access.repositories import system_settings

        return self._rows(
            system_settings.list_values,
            instance_identifier=instance_identifier,
        )
