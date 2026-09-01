"""Reading an instance's governed setting values — PI-406 (REQ-488 / DEC-927).

REQ-488 constrains *where* CRMBuilder may put a per-instance setting value: it
must be readable by a consuming application holding only the ordinary
organization-wide API credential, with no administrative account, no second
credential, and no call to any service but the instance itself. DEC-927 settled
the home on that evidence — the Settings endpoint splits its payload by
privilege, leaving outbound email administrator-only while organization name is
world-readable, so it fails the requirement in both directions at once. A
single-record custom entity governed by ordinary ACL does not.

**Why the outcome set is the shape it is.** The trap this module exists to avoid
is the one the consumer's own preflight fell into: collapsing *absent*,
*forbidden* and *unreachable* into one answer, which turns "your key lost its
role" into "your CRM is missing everything". REQ-488 requires specifically that a
credential failure stay distinguishable from a successful read that found
nothing configured.

That distinction is available here and is not available everywhere. EspoCRM's
**record** API returns 403 for a scope the caller has no grant on, so an empty
result really does mean "nothing configured". Its **Metadata** endpoint instead
returns an empty 200 for a scope the caller cannot see, which is why a
metadata-based read could not satisfy REQ-488 no matter how it were written.
Reading through the record API is therefore load-bearing, not incidental.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

#: The single-record custom entity that carries an instance's governed values
#: (DEC-927; reusing the entity the CBM engagement already built).
SETTINGS_ENTITY = "CNetworkStandard"

#: The field on that record carrying the governed values, as a mapping of
#: governed setting key to value.
#:
#: One carrier field rather than one field per setting is deliberate: a field
#: per setting would make every newly governed setting a schema change on every
#: chapter's CRM, which is a migration the network has to run in lockstep for
#: something the design already knows. A single mapping lets the governed set
#: grow without touching any instance's schema.
SETTINGS_FIELD = "settings"

#: The design-version stamp fields on the same record (REQ-495 / DEC-974,
#: DEC-980): the frozen release the design was published under, and the
#: identity of the exact plan applied. Read here with the same ordinary
#: credential — the stamp lives in the instance, not in any consuming
#: application's environment.
STANDARD_VERSION_FIELD = "standardVersion"
PLAN_FINGERPRINT_FIELD = "planFingerprint"

#: The read succeeded. ``values`` may still be empty — that is a real answer.
OK = "ok"
#: The scope exists but this credential has no grant on it. Not "no values".
FORBIDDEN = "forbidden"
#: The credential is not valid at all.
UNAUTHENTICATED = "unauthenticated"
#: The instance could not be reached, so its values are unknown — not absent.
UNREACHABLE = "unreachable"
#: The carrier entity is not present on this instance.
ABSENT = "absent"


class _RecordClient(Protocol):
    """The one call this read needs — deliberately narrow.

    REQ-488 forbids the read path from requiring elevated rights or a second
    credential, and the surest way to keep that true is for the reader to be
    unable to ask for anything else.
    """

    def get_records(
        self, entity: str, **kwargs: Any
    ) -> tuple[int, dict | None]: ...


@dataclass(frozen=True)
class SettingsRead:
    """The outcome of one attempt to read an instance's governed values.

    ``values`` is meaningful only when ``outcome`` is :data:`OK`. Every other
    outcome leaves it empty and carries a ``reason``, so a caller that ignores
    the outcome and reads ``values`` gets an empty mapping rather than a
    confident wrong answer about what the instance holds.
    """

    outcome: str
    values: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None
    status_code: int | None = None
    #: The design-version stamp the instance carries (REQ-495), meaningful only
    #: when ``outcome`` is :data:`OK`; ``None`` when the instance was never
    #: stamped (an apply that fails partway leaves the previous values).
    standard_version: str | None = None
    plan_fingerprint: str | None = None

    @property
    def configured(self) -> bool:
        """Whether the instance holds any governed value at all.

        Only ever true for a successful read; an unreadable instance is never
        reported as unconfigured.
        """
        return self.outcome == OK and bool(self.values)


def read_setting_values(
    client: _RecordClient, *, entity: str = SETTINGS_ENTITY
) -> SettingsRead:
    """Read one instance's governed setting values with the ordinary credential.

    :param client: anything offering ``get_records`` — the ordinary org-wide
        credential is sufficient and no administrative account is used.
    :returns: a :class:`SettingsRead` whose ``outcome`` separates a successful
        read from a credential failure, an absent carrier and an unreachable
        instance (REQ-488 / REQ-491).
    """
    status, body = client.get_records(entity)

    if status == -1:
        return SettingsRead(
            UNREACHABLE,
            reason=f"{entity} could not be read: the instance was unreachable",
            status_code=status,
        )
    if status == 401:
        return SettingsRead(
            UNAUTHENTICATED,
            reason=f"{entity} could not be read: the credential was rejected",
            status_code=status,
        )
    if status == 403:
        # Not "no values" — the grant that DEC-927 chose this home for is
        # missing, and the CBM build found this exact state on first attempt.
        return SettingsRead(
            FORBIDDEN,
            reason=(
                f"{entity} exists but this credential has no read grant on it; "
                "the API role needs the scope granted"
            ),
            status_code=status,
        )
    if status == 404:
        return SettingsRead(
            ABSENT,
            reason=f"{entity} is not present on this instance",
            status_code=status,
        )
    if status != 200 or not isinstance(body, dict):
        return SettingsRead(
            UNREACHABLE,
            reason=f"{entity} returned an unusable response (HTTP {status})",
            status_code=status,
        )

    records = body.get("list")
    if not isinstance(records, list) or not records:
        # A genuine, grant-backed "nothing configured here yet" — the honest
        # state of an instance built to report but never applied to.
        return SettingsRead(OK, values={}, status_code=status)

    record = records[0]
    stamp = {
        "standard_version": record.get(STANDARD_VERSION_FIELD) or None,
        "plan_fingerprint": record.get(PLAN_FINGERPRINT_FIELD) or None,
    }
    carried = record.get(SETTINGS_FIELD)
    if carried is None:
        return SettingsRead(OK, values={}, status_code=status, **stamp)
    if not isinstance(carried, dict):
        return SettingsRead(
            UNREACHABLE,
            reason=(
                f"{entity}.{SETTINGS_FIELD} is not a mapping of setting key to "
                "value; the carrier field holds something this reader cannot "
                "interpret"
            ),
            status_code=status,
        )
    return SettingsRead(OK, values=dict(carried), status_code=status, **stamp)
