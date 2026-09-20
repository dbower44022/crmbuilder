"""Applying declared links between object types (REQ-612 / PI-526).

A link is created once and then verified by reading it back, because the
platform can accept the request and still not produce the link — and a
design that believes a link exists will build layouts and fields on top of
it.

A link that already exists is compared, not overwritten. The platform gives
no way to change a link's shape without dropping it, and dropping a link
takes its data with it, so a link that differs is reported for a person to
decide about rather than silently rewritten.

Two of the platform's habits shape the comparison:

*It names the two sides of a one-to-one link differently.* The side holding
the key reads one way and the other side reads the other, and which side a
design is written from is not something the design says — the platform
decides that when the link is made. Either reading matches.

*It prefixes a link added to a native object type.* A link the design calls
``engagements`` comes back as ``cEngagements``. The prefix is applied by the
platform, so it is stripped before sending — otherwise a link captured from
an instance and redeployed acquires a second prefix and never round-trips
back to the name the design uses.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from crmbuilder_v2.introspect.audit_utils import NATIVE_ENTITIES
from crmbuilder_v2.introspect.espo_client import format_error_detail
from crmbuilder_v2.introspect.utilization import wire_entity_name
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.espo_write_client import EspoWriteClient

#: What happened to a link.
CREATED = "created"
SKIPPED = "skipped"
DIFFERS = "differs"
FAILED = "failed"
PREVIEWED = "previewed"

#: How the design's link kinds read in the platform's own metadata.
KIND_IN_METADATA: dict[str, str] = {
    "oneToMany": "hasMany",
    "manyToOne": "belongsTo",
    "manyToMany": "hasMany",
}

#: A one-to-one link reads as one or the other depending on which side holds
#: the key, and the design does not say which side it is written from.
ONE_TO_ONE_IN_METADATA = frozenset({"hasOne", "belongsTo"})


def strip_platform_prefix(name: str) -> str:
    """Remove one platform prefix from a link name.

    The prefix is a lowercase ``c`` immediately followed by a capital, so
    ``cEngagements`` becomes ``engagements`` while ``contacts`` — a name that
    merely begins with the letter — is untouched. Exactly one prefix is
    removed per call, so a doubly-prefixed name loses one layer.
    """
    if len(name) > 1 and name[0] == "c" and name[1].isupper():
        return name[1].lower() + name[2:]
    return name


@dataclass(frozen=True)
class LinkIntent:
    """One link between two object types, as the design declares it.

    :ivar entity: The design's name for the object type the link starts from.
    :ivar entity_foreign: The design's name for the object type it points to.
    :ivar link: The link's name on the starting side.
    :ivar link_foreign: The link's name on the other side.
    :ivar kind: ``oneToMany``, ``manyToOne``, ``manyToMany`` or ``oneToOne``.
    :ivar label: The link's name in the interface, on the starting side.
    :ivar label_foreign: The same, on the other side.
    :ivar relation_name: The name of the joining table, for a many-to-many
        link; the platform names one itself when this is absent.
    :ivar audited: Whether changes to the link are recorded, per side.
    """

    entity: str
    entity_foreign: str
    link: str
    link_foreign: str
    kind: str
    label: str | None = None
    label_foreign: str | None = None
    relation_name: str | None = None
    audited: bool = False
    audited_foreign: bool = False

    @property
    def description(self) -> str:
        """The link as a person would say it."""
        return f"{self.entity} → {self.entity_foreign} ({self.link})"

    def creation_payload(self) -> dict[str, Any]:
        """The create body, with the platform's prefix left to the platform."""
        link_foreign = self.link_foreign
        if self.entity_foreign in NATIVE_ENTITIES:
            link_foreign = strip_platform_prefix(link_foreign)
        return {
            "entity": wire_entity_name(self.entity),
            "entityForeign": wire_entity_name(self.entity_foreign),
            "link": self.link,
            "linkForeign": link_foreign,
            "label": self.label,
            "labelForeign": self.label_foreign,
            "linkType": self.kind,
            "relationName": self.relation_name,
            "linkMultipleField": False,
            "linkMultipleFieldForeign": False,
            "audited": self.audited,
            "auditedForeign": self.audited_foreign,
            "layout": None,
            "layoutForeign": None,
            "selectFilter": None,
            "selectFilterForeign": None,
        }


@dataclass
class LinkOutcome:
    """What happened to one link.

    :ivar link: The link as a person would say it.
    :ivar status: One of :data:`CREATED`, :data:`SKIPPED`, :data:`DIFFERS`,
        :data:`FAILED`, :data:`PREVIEWED`.
    :ivar detail: What a person needs to read about it.
    :ivar verified: Whether the link was read back and found after creating
        it. A creation the instance accepted but that left no link is the
        failure this catches.
    """

    link: str
    status: str
    detail: str = ""
    verified: bool = False

    @property
    def failed(self) -> bool:
        return self.status == FAILED


def _raise_if_unauthenticated(status: int) -> None:
    if status == 401:
        raise AuthenticationRejected(
            "the instance rejected the credential (401); nothing further "
            "can be applied"
        )


def platform_prefixed(name: str) -> str:
    """The name the platform gives a link added to an object type it ships.

    The inverse of :func:`strip_platform_prefix`, and applied for the same
    reason: on an object type the platform ships, it is the platform that
    names the link, not the design.
    """
    if not name:
        return name
    return "c" + name[0].upper() + name[1:]


def find_link(
    client: EspoWriteClient, entity_wire: str, link: str
) -> dict[str, Any] | None:
    """The link's metadata on the instance, or ``None`` if it is not there.

    On an object type the platform ships, a custom link is stored under a
    prefixed name (REQ-628): the design declares ``intakeSubmissions`` and the
    instance holds ``cIntakeSubmissions``. The prefixed name is tried first,
    because on such an object type it is the platform's own name and therefore
    the authoritative one; the declared name is tried after it, for a link the
    platform did not rename.

    Looking only for the declared name reported every such link as absent, so
    the publish asked the platform to create a link it already had and the
    create failed — on every run, for ever. Version 1 tried both names and the
    version 2 port dropped the fallback.
    """
    status, links = client.get_all_links(entity_wire)
    _raise_if_unauthenticated(status)
    if status != 200 or not isinstance(links, Mapping):
        return None
    candidates = [link]
    if entity_wire in NATIVE_ENTITIES:
        candidates.insert(0, platform_prefixed(link))
    for name in candidates:
        found = links.get(name)
        if isinstance(found, Mapping):
            return dict(found)
    return None


def link_matches(live: Mapping[str, Any], intent: LinkIntent) -> bool:
    """Whether the link on the instance is the one the design declares.

    :param live: The link as the instance reports it.
    :param intent: The link as declared.
    """
    live_kind = live.get("type")
    if intent.kind == "oneToOne":
        if live_kind not in ONE_TO_ONE_IN_METADATA:
            return False
    elif live_kind != KIND_IN_METADATA.get(intent.kind):
        return False

    if live.get("entity") != wire_entity_name(intent.entity_foreign):
        return False

    if "foreign" in live:
        # The platform may have applied its own prefix to the far side, so
        # compare both names with one prefix removed.
        if strip_platform_prefix(str(live["foreign"])) != strip_platform_prefix(
            intent.link_foreign
        ):
            return False
    return True


def apply_link(
    client: EspoWriteClient, intent: LinkIntent, *, preview: bool = False
) -> LinkOutcome:
    """Apply one declared link.

    :param client: A write-capable client for the target instance.
    :param intent: The link as declared.
    :param preview: When true, report what would happen and write nothing.
    :returns: What happened.
    :raises AuthenticationRejected: If the instance rejects the credential.
    """
    entity_wire = wire_entity_name(intent.entity)
    live = find_link(client, entity_wire, intent.link)

    if live is not None:
        if link_matches(live, intent):
            return LinkOutcome(
                intent.description, SKIPPED, "already as declared", verified=True
            )
        return LinkOutcome(
            intent.description,
            DIFFERS,
            "a link of this name already exists and does not match the "
            "design. The platform cannot change a link's shape without "
            "dropping it, and dropping it takes its data, so it is left as "
            "it is for a person to decide about.",
        )

    if preview:
        return LinkOutcome(intent.description, PREVIEWED, "would be created")

    status, body = client.create_link(intent.creation_payload())
    _raise_if_unauthenticated(status)
    if status != 200:
        return LinkOutcome(
            intent.description,
            FAILED,
            f"the instance refused the link ({status}): "
            f"{format_error_detail(body)}",
        )

    # The platform can accept the request and still not produce the link, and
    # everything built on top of a link assumes it is there.
    written = find_link(client, entity_wire, intent.link)
    if written is None:
        return LinkOutcome(
            intent.description,
            FAILED,
            "the instance accepted the link but does not report it; nothing "
            "should be built on top of it until that is understood",
        )
    return LinkOutcome(intent.description, CREATED, verified=True)


def apply_links(
    client: EspoWriteClient,
    intents: Iterable[LinkIntent],
    *,
    preview: bool = False,
) -> list[LinkOutcome]:
    """Apply every declared link, in the order given."""
    return [apply_link(client, intent, preview=preview) for intent in intents]
