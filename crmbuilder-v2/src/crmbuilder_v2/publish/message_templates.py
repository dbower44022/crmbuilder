"""Applying declared message templates (REQ-613 / PI-527).

A message template is an ordinary record on the instance rather than part of
its definition, so applying one is create-or-update by name. Two things make
it worth its own module.

First, a template is matched by name within an object type, because that is
how a design refers to one — an instance can hold two templates of the same
name for different object types, and updating the wrong one sends the wrong
message to somebody.

Second, a template on the instance that the design does not mention is
reported rather than removed. A person may have written it, and a publish
that silently deleted somebody's message would be the worst kind of quiet.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from crmbuilder_v2.introspect.espo_client import format_error_detail
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.espo_write_client import EspoWriteClient

#: What happened to a template.
CREATED = "created"
UPDATED = "updated"
SKIPPED = "skipped"
FAILED = "failed"
PREVIEWED = "previewed"

#: The record type templates are stored as.
TEMPLATE_RECORD = "EmailTemplate"

#: What is compared, and what is sent.
COMPARED_PROPERTIES: tuple[str, ...] = ("subject", "body")


@dataclass(frozen=True)
class TemplateIntent:
    """One message template, as the design declares it.

    :ivar name: The template's name, which is how the design refers to it.
    :ivar entity: The platform's name for the object type it belongs to.
    :ivar subject: The message's subject line.
    :ivar body: The message itself.
    """

    name: str
    entity: str
    subject: str = ""
    body: str = ""

    def payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "entityType": self.entity,
            "subject": self.subject,
            "body": self.body,
        }


@dataclass
class TemplateOutcome:
    """What happened to one template.

    :ivar name: The template's name.
    :ivar entity: The object type it belongs to.
    :ivar status: One of :data:`CREATED`, :data:`UPDATED`, :data:`SKIPPED`,
        :data:`FAILED`, :data:`PREVIEWED`.
    :ivar detail: What a person needs to read about it.
    """

    name: str
    entity: str
    status: str
    detail: str = ""

    @property
    def failed(self) -> bool:
        return self.status == FAILED


def _live_templates(
    client: EspoWriteClient, entity: str
) -> tuple[int, dict[str, dict[str, Any]]]:
    """Every template the instance holds for one object type, by name."""
    status, body = client.list_email_templates(entity)
    if status == 401:
        raise AuthenticationRejected(
            "the instance rejected the credential (401); nothing further "
            "can be applied"
        )
    rows: Sequence[Any] = []
    if isinstance(body, Mapping):
        rows = body.get("list") or []
    elif isinstance(body, list):
        rows = body
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, Mapping) and row.get("name"):
            found[str(row["name"])] = dict(row)
    return status, found


def differences(intent: TemplateIntent, live: Mapping[str, Any]) -> list[str]:
    """Which of a template's parts differ from the instance."""
    return [
        name
        for name in COMPARED_PROPERTIES
        if (getattr(intent, name) or "") != (live.get(name) or "")
    ]


def apply_templates(
    client: EspoWriteClient,
    entity: str,
    intents: Iterable[TemplateIntent],
    *,
    preview: bool = False,
    report_undeclared: bool = True,
) -> list[TemplateOutcome]:
    """Apply every declared template for one object type.

    :param client: A write-capable client for the target instance.
    :param entity: The platform's name for the object type.
    :param intents: The templates as declared.
    :param preview: When true, report what would happen and write nothing.
    :param report_undeclared: Whether to report templates the instance holds
        that the design does not mention. They are never removed.
    :returns: One outcome per declared template, and one per undeclared
        template found, when asked for.
    :raises AuthenticationRejected: If the instance rejects the credential.
    """
    intents = list(intents)
    status, live = _live_templates(client, entity)
    if status != 200:
        return [
            TemplateOutcome(
                intent.name,
                entity,
                FAILED,
                f"the instance did not report its templates ({status})",
            )
            for intent in intents
        ]

    outcomes = [
        _apply_one(client, entity, intent, live.get(intent.name), preview)
        for intent in intents
    ]

    if report_undeclared:
        declared = {intent.name for intent in intents}
        for name in sorted(set(live) - declared):
            outcomes.append(
                TemplateOutcome(
                    name,
                    entity,
                    SKIPPED,
                    "on the instance but not in the design; left alone",
                )
            )
    return outcomes


def _apply_one(
    client: EspoWriteClient,
    entity: str,
    intent: TemplateIntent,
    live: Mapping[str, Any] | None,
    preview: bool,
) -> TemplateOutcome:
    if live is None:
        if preview:
            return TemplateOutcome(
                intent.name, entity, PREVIEWED, "would be created"
            )
        status, body = client.create_record(TEMPLATE_RECORD, intent.payload())
        if status == 401:
            raise AuthenticationRejected(
                "the instance rejected the credential (401); nothing further "
                "can be applied"
            )
        if status == 200:
            return TemplateOutcome(intent.name, entity, CREATED)
        return TemplateOutcome(
            intent.name,
            entity,
            FAILED,
            f"the instance refused the template ({status}): "
            f"{format_error_detail(body)}",
        )

    differing = differences(intent, live)
    if not differing:
        return TemplateOutcome(
            intent.name, entity, SKIPPED, "already as declared"
        )
    if preview:
        return TemplateOutcome(
            intent.name,
            entity,
            PREVIEWED,
            f"would be updated: {', '.join(differing)}",
        )

    record_id = live.get("id")
    if not record_id:
        return TemplateOutcome(
            intent.name,
            entity,
            FAILED,
            "the instance reported this template without an identifier, so "
            "it cannot be updated",
        )
    status, body = client.patch_record(
        TEMPLATE_RECORD,
        str(record_id),
        {name: getattr(intent, name) for name in differing},
    )
    if status == 401:
        raise AuthenticationRejected(
            "the instance rejected the credential (401); nothing further "
            "can be applied"
        )
    if status == 200:
        return TemplateOutcome(
            intent.name, entity, UPDATED, f"changed: {', '.join(differing)}"
        )
    return TemplateOutcome(
        intent.name,
        entity,
        FAILED,
        f"the instance refused the update ({status}): "
        f"{format_error_detail(body)}",
    )
