"""The governed per-instance values, and the stamp that says what was applied
(REQ-615 / PI-529).

Some values belong to the instance rather than to the design: the ones a
network sets centrally and each member instance holds its own copy of. They
live on a carrier record, and two things about writing them are easy to get
wrong.

**A write the instance accepts is not a write the instance made.** The
platform answers success and then discards an attribute it will not store —
an unknown one, or one somebody marked read-only. Version 1 learned this
from a field whose every write was silently ignored for weeks. So a write is
proved against the record that comes back, never trusted from the status.

**Undeclared values are not this system's business.** The declared values are
merged over what the carrier already holds, so a value somebody set by hand
and the design says nothing about survives.

The stamp is separate and deliberately narrow: it records which design
version and which exact plan an instance was last brought to, so an instance
can be identified later. It is written only after a run that fully succeeded
under a frozen release — the caller holds that gate, because only the caller
knows how the run went.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from crmbuilder_v2.introspect.espo_client import format_error_detail
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.espo_write_client import EspoWriteClient

#: What happened.
UPDATED = "updated"
SKIPPED = "skipped"
UNAVAILABLE = "unavailable"
FAILED = "failed"
PREVIEWED = "previewed"

#: The record the governed values are kept on, and the field that holds them.
CARRIER_RECORD = "CNetworkStandard"
VALUES_FIELD = "settings"
CARRIER_NAME = "Network standard"

#: Where the stamp is written.
DESIGN_VERSION_FIELD = "standardVersion"
PLAN_FIELD = "planFingerprint"

_NO_CARRIER = (
    "this instance has no record to hold the governed values. Create it, and "
    "grant the account this system uses permission to read it, before the "
    "values can be applied."
)


@dataclass
class SettingsOutcome:
    """What happened to the governed values or the stamp.

    :ivar what: ``values`` or ``stamp``.
    :ivar status: One of :data:`UPDATED`, :data:`SKIPPED`,
        :data:`UNAVAILABLE`, :data:`FAILED`, :data:`PREVIEWED`.
    :ivar changed: The value names that differed.
    :ivar detail: What a person needs to read about it.
    :ivar manual_config: What somebody must do by hand.
    """

    what: str
    status: str
    changed: list[str] = dataclass_field(default_factory=list)
    detail: str = ""
    manual_config: list[str] = dataclass_field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.status == FAILED


def silently_dropped(
    sent: Mapping[str, Any], written: Any
) -> list[str]:
    """The values the instance accepted the write of but did not keep.

    :param sent: What was written.
    :param written: The record the instance answered with.
    :returns: The names it did not keep, sorted. Empty when the instance
        answered with nothing to check against — the status has already
        ruled on that case.
    """
    if not isinstance(written, Mapping):
        return []
    return sorted(
        name for name, value in sent.items() if written.get(name) != value
    )


def _carrier(client: EspoWriteClient) -> tuple[int, Mapping[str, Any] | None]:
    status, body = client.list_records(CARRIER_RECORD, max_size=1)
    if status == 401:
        raise AuthenticationRejected(
            "the instance rejected the credential (401); nothing further "
            "can be applied"
        )
    if status != 200 or not isinstance(body, Mapping):
        return status, None
    records = body.get("list") or []
    first = records[0] if records else None
    return status, first if isinstance(first, Mapping) else None


def apply_values(
    client: EspoWriteClient,
    declared: Mapping[str, Any],
    *,
    preview: bool = False,
) -> SettingsOutcome:
    """Write this instance's governed values.

    :param client: A write-capable client for the target instance.
    :param declared: The values this instance is declared to hold. A value
        the design says nothing about is never invented.
    :param preview: When true, report what would change and write nothing.
    :returns: What happened.
    :raises AuthenticationRejected: If the instance rejects the credential.
    """
    if not declared:
        return SettingsOutcome(
            "values", SKIPPED, detail="the design declares no values for this instance"
        )

    status, record = _carrier(client)
    if status == 404:
        return SettingsOutcome(
            "values",
            UNAVAILABLE,
            detail=_NO_CARRIER,
            manual_config=[_NO_CARRIER],
        )
    if status != 200:
        return SettingsOutcome(
            "values",
            FAILED,
            detail=f"the instance did not report the carrier record ({status})",
        )

    held_raw = record.get(VALUES_FIELD) if record else None
    held = held_raw if isinstance(held_raw, Mapping) else {}
    changed = sorted(
        name for name, value in declared.items() if held.get(name) != value
    )
    if not changed:
        return SettingsOutcome(
            "values", SKIPPED, detail="every declared value is already held"
        )
    if preview:
        return SettingsOutcome(
            "values",
            PREVIEWED,
            changed=changed,
            detail=f"would change: {', '.join(changed)}",
        )

    # Merged, not replaced: a value somebody set that the design says nothing
    # about is not this system's to remove.
    payload = {VALUES_FIELD: {**held, **declared}}
    if record is None:
        write_status, written = client.create_record(
            CARRIER_RECORD, {"name": CARRIER_NAME, **payload}
        )
    else:
        write_status, written = client.patch_record(
            CARRIER_RECORD, str(record.get("id")), payload
        )
    if write_status == 401:
        raise AuthenticationRejected(
            "the instance rejected the credential (401); nothing further "
            "can be applied"
        )
    if write_status != 200:
        return SettingsOutcome(
            "values",
            FAILED,
            changed=changed,
            detail=f"the instance refused the values ({write_status}): "
            f"{format_error_detail(written)}",
        )

    dropped = silently_dropped(payload, written)
    if dropped:
        return SettingsOutcome(
            "values",
            FAILED,
            changed=changed,
            detail=(
                f"the instance accepted the write but did not keep "
                f"{', '.join(dropped)} — the field is missing from the "
                f"carrier record, or somebody has made it read-only"
            ),
        )
    return SettingsOutcome(
        "values", UPDATED, changed=changed, detail=f"changed: {', '.join(changed)}"
    )


def write_stamp(
    client: EspoWriteClient,
    *,
    design_version: str,
    plan: str,
    preview: bool = False,
) -> SettingsOutcome:
    """Record which design version and which plan this instance was brought to.

    The caller decides whether to call this at all: it belongs after a run
    that fully succeeded under a frozen release, and only the caller knows
    how the run went. Calling it after a partial run would overwrite a true
    statement with a false one.

    :param client: A write-capable client for the target instance.
    :param design_version: The frozen release the design was published under.
    :param plan: The identity of the exact plan applied.
    :param preview: When true, report what would change and write nothing.
    :raises AuthenticationRejected: If the instance rejects the credential.
    """
    stamp = {DESIGN_VERSION_FIELD: design_version, PLAN_FIELD: plan}

    status, record = _carrier(client)
    if status == 404:
        return SettingsOutcome(
            "stamp",
            UNAVAILABLE,
            detail=_NO_CARRIER,
            manual_config=[_NO_CARRIER],
        )
    if status != 200:
        return SettingsOutcome(
            "stamp",
            FAILED,
            detail=f"the instance did not report the carrier record ({status})",
        )

    if record is not None and all(
        record.get(name) == value for name, value in stamp.items()
    ):
        return SettingsOutcome(
            "stamp", SKIPPED, detail=f"already stamped {design_version}"
        )
    if preview:
        return SettingsOutcome(
            "stamp",
            PREVIEWED,
            changed=sorted(stamp),
            detail=f"would stamp {design_version}",
        )

    if record is None:
        write_status, written = client.create_record(
            CARRIER_RECORD, {"name": CARRIER_NAME, **stamp}
        )
    else:
        write_status, written = client.patch_record(
            CARRIER_RECORD, str(record.get("id")), stamp
        )
    if write_status == 401:
        raise AuthenticationRejected(
            "the instance rejected the credential (401); nothing further "
            "can be applied"
        )
    if write_status != 200:
        return SettingsOutcome(
            "stamp",
            FAILED,
            detail=f"the instance refused the stamp ({write_status}): "
            f"{format_error_detail(written)}",
        )

    dropped = silently_dropped(stamp, written)
    if dropped:
        return SettingsOutcome(
            "stamp",
            FAILED,
            detail=(
                f"the instance accepted the stamp but did not keep "
                f"{', '.join(dropped)}, so this instance cannot be identified "
                f"by what it is running. The field is missing from the "
                f"carrier record, or somebody has made it read-only."
            ),
        )
    return SettingsOutcome(
        "stamp", UPDATED, changed=sorted(stamp), detail=f"stamped {design_version}"
    )
