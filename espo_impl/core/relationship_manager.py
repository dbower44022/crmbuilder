"""Relationship management — check, create, and verify entity relationships.

Confirmed API endpoints:
  Check:  GET  /api/v1/Metadata?key=entityDefs.{entity}.links.{link}
  Create: POST /api/v1/EntityManager/action/createLink
  Delete: POST /api/v1/EntityManager/action/removeLink (not used in normal flow)
"""

import logging
from collections.abc import Callable
from typing import Any

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.models import (
    RelationshipDefinition,
    RelationshipResult,
    RelationshipStatus,
)
from espo_impl.ui.confirm_delete_dialog import get_espo_entity_name

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]

LINK_TYPE_TO_METADATA: dict[str, str] = {
    "oneToMany": "hasMany",
    "manyToOne": "belongsTo",
    "manyToMany": "hasMany",
}


class RelationshipManagerError(Exception):
    """Raised when the API returns 401 Unauthorized."""


class RelationshipManager:
    """Orchestrates relationship check/create/verify operations.

    :param client: EspoCRM admin API client.
    :param output_fn: Callback for emitting output messages (message, color).
    """

    def __init__(
        self,
        client: EspoAdminClient,
        output_fn: OutputCallback,
    ) -> None:
        self.client = client
        self.output_fn = output_fn

    def process_relationships(
        self,
        relationships: list[RelationshipDefinition],
    ) -> list[RelationshipResult]:
        """Process all relationships.

        :param relationships: List of relationship definitions.
        :returns: List of relationship results.
        """
        results: list[RelationshipResult] = []

        for rel in relationships:
            try:
                result = self._process_one(rel)
            except RelationshipManagerError:
                self.output_fn(
                    "[ERROR]   Authentication failed (HTTP 401) — aborting",
                    "red",
                )
                results.append(RelationshipResult(
                    name=rel.name,
                    entity=rel.entity,
                    entity_foreign=rel.entity_foreign,
                    link=rel.link,
                    status=RelationshipStatus.ERROR,
                    message="Authentication failed (HTTP 401)",
                ))
                return results
            else:
                results.append(result)

        return results

    def _process_one(
        self, rel: RelationshipDefinition
    ) -> RelationshipResult:
        """Process a single relationship.

        :param rel: Relationship definition.
        :returns: RelationshipResult.
        :raises RelationshipManagerError: If 401 received.
        """
        prefix = f"{rel.entity} \u2192 {rel.entity_foreign} ({rel.link})"

        # Skip if action is "skip"
        if rel.action == "skip":
            self.output_fn(
                f"[RELATIONSHIP]  {prefix} ... SKIP (manual)", "gray"
            )
            return RelationshipResult(
                name=rel.name,
                entity=rel.entity,
                entity_foreign=rel.entity_foreign,
                link=rel.link,
                status=RelationshipStatus.SKIPPED,
                message="Already exists (manual)",
            )

        # Check
        self.output_fn(
            f"[RELATIONSHIP]  {prefix} ... CHECKING", "white"
        )
        espo_entity = get_espo_entity_name(rel.entity)
        espo_entity_foreign = get_espo_entity_name(rel.entity_foreign)

        existing = self._check_link_exists(espo_entity, rel.link)

        if existing is not None:
            # Compare
            if self._compare_link(existing, rel, espo_entity_foreign):
                self.output_fn(
                    f"[RELATIONSHIP]  {prefix} ... EXISTS", "gray"
                )
                self.output_fn(
                    f"[RELATIONSHIP]  {prefix} ... NO CHANGES NEEDED",
                    "gray",
                )
                return RelationshipResult(
                    name=rel.name,
                    entity=rel.entity,
                    entity_foreign=rel.entity_foreign,
                    link=rel.link,
                    status=RelationshipStatus.SKIPPED,
                )
            else:
                self.output_fn(
                    f"[RELATIONSHIP]  {prefix} ... EXISTS BUT DIFFERS "
                    f"(manual correction needed)",
                    "yellow",
                )
                return RelationshipResult(
                    name=rel.name,
                    entity=rel.entity,
                    entity_foreign=rel.entity_foreign,
                    link=rel.link,
                    status=RelationshipStatus.WARNING,
                    message="Exists but differs from spec",
                )

        # Create
        self.output_fn(
            f"[RELATIONSHIP]  {prefix} ... MISSING", "white"
        )
        self.output_fn(
            f"[RELATIONSHIP]  {prefix} ... CREATING", "white"
        )

        payload = self._build_payload(rel)
        status_code, body = self.client.create_link(payload)

        if status_code == 401:
            raise RelationshipManagerError()

        if status_code < 0 or status_code >= 400:
            self.output_fn(
                f"[RELATIONSHIP]  {prefix} ... ERROR (HTTP {status_code})",
                "red",
            )
            if body:
                msg = (
                    body.get("message", "")
                    if isinstance(body, dict)
                    else str(body)
                )
                if msg:
                    self.output_fn(f"              {msg}", "red")
            return RelationshipResult(
                name=rel.name,
                entity=rel.entity,
                entity_foreign=rel.entity_foreign,
                link=rel.link,
                status=RelationshipStatus.ERROR,
                message=f"HTTP {status_code}",
            )

        self.output_fn(
            f"[RELATIONSHIP]  {prefix} ... CREATED OK", "green"
        )

        # Verify
        verify = self._check_link_exists(espo_entity, rel.link)
        if verify is not None and self._compare_link(
            verify, rel, espo_entity_foreign
        ):
            self.output_fn(
                f"[RELATIONSHIP]  {prefix} ... VERIFIED", "green"
            )
            return RelationshipResult(
                name=rel.name,
                entity=rel.entity,
                entity_foreign=rel.entity_foreign,
                link=rel.link,
                status=RelationshipStatus.CREATED,
                verified=True,
            )

        self.output_fn(
            f"[RELATIONSHIP]  {prefix} ... VERIFY FAILED", "yellow"
        )
        return RelationshipResult(
            name=rel.name,
            entity=rel.entity,
            entity_foreign=rel.entity_foreign,
            link=rel.link,
            status=RelationshipStatus.CREATED,
            verified=False,
            message="Verification failed",
        )

    def _check_link_exists(
        self, espo_entity: str, link: str
    ) -> dict | None:
        """Fetch link metadata.

        :param espo_entity: EspoCRM entity name.
        :param link: Link name.
        :returns: Link dict if exists, None if not.
        :raises RelationshipManagerError: If 401 received.
        """
        status_code, body = self.client.get_link(espo_entity, link)

        if status_code == 401:
            raise RelationshipManagerError()

        if status_code == 200 and isinstance(body, dict) and body:
            return body

        return None

    def _compare_link(
        self,
        existing: dict,
        rel: RelationshipDefinition,
        espo_entity_foreign: str,
    ) -> bool:
        """Compare existing link to spec.

        :param existing: Existing link metadata from API.
        :param rel: Relationship definition.
        :param espo_entity_foreign: Resolved foreign entity name.
        :returns: True if matches.
        """
        expected_type = LINK_TYPE_TO_METADATA.get(rel.link_type)
        if existing.get("type") != expected_type:
            return False
        if existing.get("entity") != espo_entity_foreign:
            return False
        if existing.get("foreign") != rel.link_foreign:
            return False
        return True

    def _build_payload(
        self, rel: RelationshipDefinition
    ) -> dict[str, Any]:
        """Build the createLink API payload.

        :param rel: Relationship definition.
        :returns: API payload dict.
        """
        return {
            "entity": get_espo_entity_name(rel.entity),
            "entityForeign": get_espo_entity_name(rel.entity_foreign),
            "link": rel.link,
            "linkForeign": rel.link_foreign,
            "label": rel.label,
            "labelForeign": rel.label_foreign,
            "linkType": rel.link_type,
            "relationName": rel.relation_name,
            "linkMultipleField": False,
            "linkMultipleFieldForeign": False,
            "audited": rel.audited,
            "auditedForeign": rel.audited_foreign,
            "layout": None,
            "layoutForeign": None,
            "selectFilter": None,
            "selectFilterForeign": None,
        }
