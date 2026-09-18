"""Applying declared object types to a live CRM system (REQ-607 / PI-520).

Version 2 could say what object types a design declares; it could not make
them exist. This module does: it creates a missing object type, removes a
declared removal, refreshes the platform's definition cache afterwards, and
waits until the platform can actually use what was just created.

That last part is not defensive padding. The platform acknowledges a cache
rebuild before it has finished one, so the fields and layouts that follow a
new object type can fail with a server error against an object type the
platform does not yet know. Version 1 learned this the hard way; the wait is
ported with its backoff intact.

**Nothing here logs and nothing here decides what to do next.** Each call
returns what happened, and the caller — the publish path, later — records it
and chooses. The one exception is authentication: a rejected credential is
not a per-object outcome, it means the run cannot continue, so it raises.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from crmbuilder_v2.introspect.espo_client import format_error_detail
from crmbuilder_v2.introspect.utilization import wire_entity_name
from crmbuilder_v2.publish.espo_write_client import EspoWriteClient

#: What a declaration can ask for an object type.
CREATE = "create"
REMOVE = "remove"
REMOVE_AND_CREATE = "remove_and_create"
ACTIONS = frozenset({CREATE, REMOVE, REMOVE_AND_CREATE})

#: What happened.
CREATED = "created"
REMOVED = "removed"
SKIPPED = "skipped"
FAILED = "failed"
PREVIEWED = "previewed"

#: The wait's delays, in seconds, then two-second steps to the deadline.
_BACKOFF: tuple[float, ...] = (0.5, 0.5, 1.0, 1.0)
_STEADY_DELAY = 2.0
_DEFAULT_TIMEOUT = 30.0


class AuthenticationRejected(Exception):
    """The instance rejected the credential; the run cannot continue."""


@dataclass(frozen=True)
class EntityIntent:
    """What a design asks for one object type.

    Deliberately not the engine's own declaration model: this module is
    version 2's, and the caller maps whatever it holds onto this. ``name`` is
    the design's name for the object type — the platform's prefix is applied
    here, so a caller never has to know the rule.

    :ivar name: The design's name, e.g. ``Engagement``.
    :ivar action: One of :data:`ACTIONS`.
    :ivar kind: The platform's base kind, e.g. ``Base`` or ``Person``.
    :ivar label_singular: Its name in the interface; defaults to ``name``.
    :ivar label_plural: Its plural; defaults to ``name`` with an ``s``.
    :ivar stream: Whether the record stream is on.
    :ivar disabled: Whether the object type is hidden from the interface.
    """

    name: str
    action: str = CREATE
    kind: str = "Base"
    label_singular: str | None = None
    label_plural: str | None = None
    stream: bool = False
    disabled: bool = False

    @property
    def wire_name(self) -> str:
        """The platform's name for this object type."""
        return wire_entity_name(self.name)

    def creation_payload(self) -> dict[str, Any]:
        """The create body, with the labels defaulted.

        The design's own name is sent, not the prefixed one: the platform
        applies its prefix itself on create, and sending an already-prefixed
        name produces a doubly-prefixed object type.
        """
        return {
            "name": self.name,
            "type": self.kind or "Base",
            "labelSingular": self.label_singular or self.name,
            "labelPlural": self.label_plural or f"{self.name}s",
            "stream": bool(self.stream),
            "disabled": bool(self.disabled),
        }


@dataclass
class EntityOutcome:
    """What happened to one object type.

    :ivar name: The design's name.
    :ivar wire_name: The platform's name.
    :ivar action: What was asked for.
    :ivar status: One of :data:`CREATED`, :data:`REMOVED`, :data:`SKIPPED`,
        :data:`FAILED`, :data:`PREVIEWED`.
    :ivar detail: A sentence a person can read. Empty when there is nothing
        to say beyond the status.
    :ivar recovered: Whether a stranded half-created object type was cleared
        after a failure, freeing the name for another attempt.
    """

    name: str
    wire_name: str
    action: str
    status: str
    detail: str = ""
    recovered: bool = False

    @property
    def failed(self) -> bool:
        return self.status == FAILED


@dataclass
class WaitOutcome:
    """The result of waiting for new object types to become usable.

    :ivar ready: Design names the platform confirmed it can use.
    :ivar pending: Design names still not confirmed when the deadline passed.
    :ivar waited_seconds: How long the wait actually took.
    """

    ready: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    waited_seconds: float = 0.0

    @property
    def timed_out(self) -> bool:
        """Whether anything was still pending at the deadline.

        A timeout is a warning, not a failure: the platform is often merely
        slow, and the work that follows will say plainly if the object type
        really is missing.
        """
        return bool(self.pending)


def _raise_if_unauthenticated(status: int) -> None:
    if status == 401:
        raise AuthenticationRejected(
            "the instance rejected the credential (401); nothing further "
            "can be applied"
        )


def apply_entity(
    client: EspoWriteClient,
    intent: EntityIntent,
    *,
    preview: bool = False,
) -> list[EntityOutcome]:
    """Apply one object type's declaration.

    :param client: A write-capable client for the target instance.
    :param intent: What the design asks for.
    :param preview: When true, report what would happen and write nothing.
    :returns: One outcome per step taken — two for a removal followed by a
        creation, one otherwise.
    :raises AuthenticationRejected: If the instance rejects the credential.
    :raises ValueError: If the intent names an action this module does not
        know, which is a programming error rather than a target's answer.
    """
    if intent.action not in ACTIONS:
        raise ValueError(
            f"{intent.name}: unknown action {intent.action!r}; "
            f"expected one of {sorted(ACTIONS)}"
        )

    if intent.action == CREATE:
        return [_create(client, intent, preview=preview)]
    if intent.action == REMOVE:
        return [_remove(client, intent, preview=preview)]

    removal = _remove(client, intent, preview=preview)
    if removal.failed:
        # The object type is still there. Creating now would either collide
        # or, worse, succeed against a half-removed object type.
        return [removal]
    return [removal, _create(client, intent, preview=preview)]


def apply_entities(
    client: EspoWriteClient,
    intents: Iterable[EntityIntent],
    *,
    preview: bool = False,
) -> list[EntityOutcome]:
    """Apply several object types, in the order given.

    One object type's failure does not stop the others: a declaration
    describes many things and the operator is better served by one run that
    reports every outcome than by one that stops at the first.
    """
    outcomes: list[EntityOutcome] = []
    for intent in intents:
        outcomes.extend(apply_entity(client, intent, preview=preview))
    return outcomes


def _remove(
    client: EspoWriteClient, intent: EntityIntent, *, preview: bool
) -> EntityOutcome:
    wire = intent.wire_name
    status, exists = client.check_entity_exists(wire)
    _raise_if_unauthenticated(status)

    if not exists:
        return EntityOutcome(
            intent.name, wire, REMOVE, SKIPPED, "not present on the instance"
        )
    if preview:
        return EntityOutcome(
            intent.name, wire, REMOVE, PREVIEWED, "would be removed"
        )

    status, body = client.remove_entity(wire)
    _raise_if_unauthenticated(status)
    if status == 200:
        return EntityOutcome(intent.name, wire, REMOVE, REMOVED)
    return EntityOutcome(
        intent.name,
        wire,
        REMOVE,
        FAILED,
        f"the instance refused the removal ({status}): "
        f"{format_error_detail(body)}",
    )


def _create(
    client: EspoWriteClient, intent: EntityIntent, *, preview: bool
) -> EntityOutcome:
    wire = intent.wire_name
    status, exists = client.check_entity_exists(wire)
    _raise_if_unauthenticated(status)

    if exists:
        return EntityOutcome(
            intent.name, wire, CREATE, SKIPPED, "already present on the instance"
        )
    if preview:
        return EntityOutcome(
            intent.name, wire, CREATE, PREVIEWED, "would be created"
        )

    status, body = client.create_entity(intent.creation_payload())
    _raise_if_unauthenticated(status)
    if status == 200:
        return EntityOutcome(intent.name, wire, CREATE, CREATED)

    detail = (
        f"the instance refused the creation ({status}): "
        f"{format_error_detail(body)}"
    )
    # A refusal the instance decided (4xx) created nothing. A server error
    # may have left the name reserved with no usable definition behind it,
    # which strands the name until someone clears it.
    if status >= 500:
        recovered, note = _clear_stranded_name(client, wire)
        return EntityOutcome(
            intent.name, wire, CREATE, FAILED, f"{detail} {note}", recovered
        )
    return EntityOutcome(intent.name, wire, CREATE, FAILED, detail)


def _clear_stranded_name(
    client: EspoWriteClient, wire_name: str
) -> tuple[bool, str]:
    """Try to free a name a failed creation may have stranded.

    :returns: ``(recovered, note)`` — whether the name is free again, and a
        sentence for the outcome's detail. When the platform will not clear
        it, the note says what to do on the server, because the alternative
        is an operator who cannot reuse the name and is not told why.
    """
    status, _ = client.remove_entity(wire_name)
    if status == 200:
        client.rebuild()
        return True, (
            "The half-created object type was removed, so the name is free "
            "to try again."
        )
    return False, (
        f"The name may be reserved with no definition behind it and could "
        f"not be cleared ({status}). On the server: make sure the custom "
        f"resources directory is writable by the web user, remove the "
        f"leftover controller for {wire_name}, then rebuild."
    )


def rebuild_cache(client: EspoWriteClient) -> EntityOutcome:
    """Ask the platform to rebuild its definition cache.

    :returns: An outcome naming the cache rather than an object type, so a
        caller can report it in the same list as the rest.
    :raises AuthenticationRejected: If the instance rejects the credential.
    """
    status, body = client.rebuild()
    _raise_if_unauthenticated(status)
    if status == 200:
        return EntityOutcome("definition cache", "", "rebuild", CREATED)
    return EntityOutcome(
        "definition cache",
        "",
        "rebuild",
        FAILED,
        f"the instance refused the rebuild ({status}): "
        f"{format_error_detail(body)}",
    )


def wait_until_usable(
    client: EspoWriteClient,
    names: Sequence[str],
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> WaitOutcome:
    """Wait until the platform can use each named object type.

    The platform answers a rebuild request before the rebuild has finished,
    so a definition asked for too early comes back empty and the work that
    follows fails against an object type that does exist. Polling for the
    definition is the only reliable signal that it is safe to continue.

    :param client: A client for the target instance.
    :param names: Design names, not the platform's.
    :param timeout_seconds: The whole wait's budget, not per object type.
    :param sleep: Injected for tests, so they need not really wait.
    :param now: Injected for tests, as a monotonic clock.
    :returns: What became ready and what did not.
    """
    if not names:
        return WaitOutcome()

    started = now()
    deadline = started + timeout_seconds
    pending = list(names)
    ready: list[str] = []
    attempt = 0

    while pending and now() < deadline:
        delay = _BACKOFF[attempt] if attempt < len(_BACKOFF) else _STEADY_DELAY
        sleep(delay)
        attempt += 1

        still_pending: list[str] = []
        for name in pending:
            status, defs = client.get_entity_defs(wire_entity_name(name))
            if status == 200 and isinstance(defs, dict) and defs:
                ready.append(name)
            else:
                still_pending.append(name)
        pending = still_pending

    return WaitOutcome(ready=ready, pending=pending, waited_seconds=now() - started)
