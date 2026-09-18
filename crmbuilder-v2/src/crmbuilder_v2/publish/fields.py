"""Applying declared fields to a live CRM system (REQ-608 / PI-521).

The heart of the apply engine. A field is applied in three steps — find it,
compare it, write it — and each step exists because of a way the platform
behaves rather than by design:

*Find it.* The platform stores a custom field on a native object type under
a prefixed name, so a field the design calls ``contactType`` is
``cContactType`` on the instance. Looking under the design's name alone
finds nothing and creates a duplicate on every run.

*Compare it.* A re-run that changes nothing must write nothing; the
comparison in :mod:`crmbuilder_v2.publish.field_compare` decides that, and
names what differs when something does.

*Write it.* A creation can still collide with a field already stored under
the prefixed name, and the platform answers that collision with the name it
already has — so the creation becomes an update instead of failing the run.

A rule the platform cannot express is dropped from what is sent and reported
for manual configuration, rather than being silently lost: the field still
deploys, and the operator is told what the instance will not do.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from crmbuilder_v2.introspect.espo_client import format_error_detail
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.espo_write_client import EspoWriteClient
from crmbuilder_v2.publish.field_compare import FieldComparison, compare_field

#: What happened to a field.
CREATED = "created"
UPDATED = "updated"
SKIPPED = "skipped"
KIND_CONFLICT = "kind_conflict"
FAILED = "failed"
PREVIEWED = "previewed"

#: The payload key carrying the rule that decides when a field is shown.
VISIBILITY_RULE = "dynamicLogicVisible"

#: Condition references that name a person's role. The platform's visibility
#: rules cannot test one, so a rule that does is reported rather than sent.
_ROLE_REFERENCES = frozenset({"role", "roles", "userRole", "user.roles"})


@dataclass(frozen=True)
class FieldIntent:
    """One field as the design declares it.

    :ivar name: The design's name for the field.
    :ivar payload: The field in the platform's own property names, as it
        would be sent — the translation from the design's vocabulary belongs
        to the adapter that generated it, not here.
    """

    name: str
    payload: Mapping[str, Any]


@dataclass
class FieldOutcome:
    """What happened to one field.

    :ivar entity: The platform's name for the object type it belongs to.
    :ivar name: The design's name for the field.
    :ivar wire_name: The name the instance stores it under, once known.
    :ivar status: One of :data:`CREATED`, :data:`UPDATED`, :data:`SKIPPED`,
        :data:`KIND_CONFLICT`, :data:`FAILED`, :data:`PREVIEWED`.
    :ivar detail: What a person needs to read about it.
    :ivar differences: The properties that differed, when any did.
    :ivar manual_config: What the instance will not do, which somebody must
        now configure by hand.
    """

    entity: str
    name: str
    wire_name: str
    status: str
    detail: str = ""
    differences: list[str] = dataclass_field(default_factory=list)
    manual_config: list[str] = dataclass_field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.status == FAILED

    @property
    def wrote(self) -> bool:
        return self.status in {CREATED, UPDATED}


def prefixed_name(name: str) -> str:
    """The name the platform gives a custom field: ``c`` and a capital.

    ``contactType`` becomes ``cContactType``.
    """
    if not name:
        return name
    return f"c{name[0].upper()}{name[1:]}"


def mentions_a_role(node: Any) -> bool:
    """Whether a condition tests a person's role, at any depth.

    The platform's visibility rules have no role test, so a rule that needs
    one cannot be sent. Finding it here — rather than trusting the generator
    to have caught it — matters because a declaration may not have come from
    version 2's own generator.
    """
    if isinstance(node, Mapping):
        reference = node.get("field") or node.get("attribute")
        if isinstance(reference, str) and reference in _ROLE_REFERENCES:
            return True
        return any(mentions_a_role(value) for value in node.values())
    if isinstance(node, (list, tuple)):
        return any(mentions_a_role(item) for item in node)
    return False


def _sendable(intent: FieldIntent) -> tuple[dict[str, Any], list[str]]:
    """The payload as it will be sent, and what had to be left out.

    :returns: ``(payload, manual_config)``. The payload never contains a
        rule the platform cannot honour; each one left out is described in
        the second value so the run can tell the operator.
    """
    payload = dict(intent.payload)
    manual: list[str] = []
    rule = payload.get(VISIBILITY_RULE)
    if rule is not None and mentions_a_role(rule):
        payload.pop(VISIBILITY_RULE)
        manual.append(
            f"{intent.name}: the rule that hides this field depends on the "
            f"viewer's role, which the platform's own visibility rules "
            f"cannot express. The field is deployed without it; set the "
            f"restriction by hand, or express it through roles and layouts."
        )
    return payload, manual


def _raise_if_unauthenticated(status: int) -> None:
    if status == 401:
        raise AuthenticationRejected(
            "the instance rejected the credential (401); nothing further "
            "can be applied"
        )


def find_field(
    client: EspoWriteClient, entity: str, name: str
) -> tuple[int, dict[str, Any] | None, str]:
    """Find a declared field on the instance, under either name it may have.

    The prefixed name is tried first because that is where a custom field
    lives; the design's own name is the fallback, which is where a built-in
    field lives.

    :returns: ``(status, field, name_it_is_stored_under)``. When neither
        name finds it, the status is the prefixed attempt's, since that is
        the one a creation will follow.
    """
    prefixed = prefixed_name(name)
    status, body = client.get_field(entity, prefixed)
    _raise_if_unauthenticated(status)
    if status == 200 and body is not None:
        return status, body, prefixed

    raw_status, raw_body = client.get_field(entity, name)
    _raise_if_unauthenticated(raw_status)
    if raw_status == 200 and raw_body is not None:
        return raw_status, raw_body, name

    return status, body, prefixed


def _name_from_conflict(body: Any) -> str | None:
    """The existing field's name, out of the platform's conflict answer.

    The platform reports a collision by naming the field it already has,
    which is what lets a creation become an update.
    """
    if not isinstance(body, Mapping):
        return None
    try:
        name = body["messageTranslation"]["data"]["field"]
    except (KeyError, TypeError):
        return None
    return name if isinstance(name, str) and name else None


def apply_field(
    client: EspoWriteClient,
    entity: str,
    intent: FieldIntent,
    *,
    preview: bool = False,
) -> FieldOutcome:
    """Apply one declared field to an object type on the instance.

    :param client: A write-capable client for the target instance.
    :param entity: The platform's name for the object type.
    :param intent: The field as declared.
    :param preview: When true, report what would happen and write nothing.
    :returns: What happened.
    :raises AuthenticationRejected: If the instance rejects the credential.
    """
    payload, manual = _sendable(intent)
    status, live, stored_as = find_field(client, entity, intent.name)

    if status < 0:
        return FieldOutcome(
            entity,
            intent.name,
            stored_as,
            FAILED,
            f"the instance could not be reached: {format_error_detail(live)}",
            manual_config=manual,
        )
    if status == 403:
        return FieldOutcome(
            entity,
            intent.name,
            stored_as,
            FAILED,
            "the credential may not read this field (403), so it cannot be "
            "applied safely",
            manual_config=manual,
        )

    if status == 200 and live is not None:
        return _update_existing(
            client, entity, intent, payload, manual, live, stored_as, preview
        )
    return _create_missing(
        client, entity, intent, payload, manual, stored_as, preview
    )


def _update_existing(
    client: EspoWriteClient,
    entity: str,
    intent: FieldIntent,
    payload: dict[str, Any],
    manual: list[str],
    live: Mapping[str, Any],
    stored_as: str,
    preview: bool,
) -> FieldOutcome:
    comparison: FieldComparison = compare_field(payload, live)

    if comparison.kind_conflict:
        return FieldOutcome(
            entity,
            intent.name,
            stored_as,
            KIND_CONFLICT,
            comparison.detail_text,
            differences=comparison.differences,
            manual_config=manual,
        )
    if comparison.matches:
        return FieldOutcome(
            entity,
            intent.name,
            stored_as,
            SKIPPED,
            "already as declared",
            manual_config=manual,
        )
    if preview:
        return FieldOutcome(
            entity,
            intent.name,
            stored_as,
            PREVIEWED,
            f"would be updated: {comparison.detail_text}",
            differences=comparison.differences,
            manual_config=manual,
        )

    status, body = client.update_field(entity, stored_as, payload)
    _raise_if_unauthenticated(status)
    if status == 200:
        return FieldOutcome(
            entity,
            intent.name,
            stored_as,
            UPDATED,
            comparison.detail_text,
            differences=comparison.differences,
            manual_config=manual,
        )
    return FieldOutcome(
        entity,
        intent.name,
        stored_as,
        FAILED,
        f"the instance refused the update ({status}): "
        f"{format_error_detail(body)}",
        differences=comparison.differences,
        manual_config=manual,
    )


def _create_missing(
    client: EspoWriteClient,
    entity: str,
    intent: FieldIntent,
    payload: dict[str, Any],
    manual: list[str],
    stored_as: str,
    preview: bool,
) -> FieldOutcome:
    if preview:
        return FieldOutcome(
            entity,
            intent.name,
            stored_as,
            PREVIEWED,
            "would be created",
            manual_config=manual,
        )

    status, body = client.create_field(entity, payload)
    _raise_if_unauthenticated(status)
    if status == 200:
        return FieldOutcome(
            entity, intent.name, stored_as, CREATED, manual_config=manual
        )

    if status == 409:
        existing = _name_from_conflict(body)
        if existing:
            update_status, update_body = client.update_field(
                entity, existing, payload
            )
            _raise_if_unauthenticated(update_status)
            if update_status == 200:
                return FieldOutcome(
                    entity,
                    intent.name,
                    existing,
                    UPDATED,
                    f"already present as {existing}; updated instead of "
                    f"created",
                    manual_config=manual,
                )
            return FieldOutcome(
                entity,
                intent.name,
                existing,
                FAILED,
                f"already present as {existing}, and the instance refused "
                f"the update ({update_status}): "
                f"{format_error_detail(update_body)}",
                manual_config=manual,
            )

    return FieldOutcome(
        entity,
        intent.name,
        stored_as,
        FAILED,
        f"the instance refused the creation ({status}): "
        f"{format_error_detail(body)}",
        manual_config=manual,
    )


def apply_fields(
    client: EspoWriteClient,
    entity: str,
    intents: Iterable[FieldIntent],
    *,
    preview: bool = False,
) -> list[FieldOutcome]:
    """Apply every declared field on one object type, in the order given.

    One field's failure does not stop the others: an operator is better
    served by one run that reports every outcome than by one that stops at
    the first refusal.
    """
    return [
        apply_field(client, entity, intent, preview=preview)
        for intent in intents
    ]
