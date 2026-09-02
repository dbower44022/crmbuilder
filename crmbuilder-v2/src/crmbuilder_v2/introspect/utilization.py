"""Utilization audit area — record profiling written as evidence (PI-426 / REQ-524).

The native V2 port of the V1 data profiler (``espo_impl/core/data_profiler.py``,
WTK-096). V1 profiled a source from a schema-discovery report and wrote a
``utilization-profile.json`` that a later transform folded into
``utilization_evidence`` rows; this area profiles the instance straight from the
design and writes the rows itself (DEC-950, REQ-339).

The work list is the design as it stands on the instance: every canonical entity
whose ``instance_membership`` is present or drifted here, and per entity its
present / drifted fields (custom and built-in). Neutral design names map to
EspoCRM wire names the way the reconcile reads them back — a custom entity is
``C<Name>``, a custom field on a native entity is ``c<Name>``, a custom entity's
fields and every built-in field keep their natural names — and neutral field
types map to wire types through the emitter's table, so the profiler asks the
CRM about exactly what the design describes.

The algorithm is V1's unchanged: a count-mode pass per field (populated where,
recency, per-option counts), a newest-first scan capped at ``scan_cap`` records
that refines the strict populated predicate and tracks distinct values, and the
WTK-096 §5 flags (``dormant`` / ``empty`` / ``low_population`` / ``stale``).
Reads are GET-only through :class:`EspoIntrospectionClient`; the §7 retry and
abort tiers (429/502/503/504 and transport failures retried five times with
1/2/4/8/16 s backoff, 401 aborts the run, three consecutive exhausted entities
abort the run) are kept as they were.

Provenance mirrors the retiring V1-file path: one ``audit_deposit`` deposit event
per run, its identifier stamped on every evidence row, and an ``observed_in``
edge from each profiled subject to the event (WTK-089 D1). The evidence detail
block uses the same WTK-097 §4 keys the old path wrote, so evidence produced here
is indistinguishable in shape from evidence produced from a profile file.

The pure predicate / where-clause / flag functions stay module-level and free of
HTTP so they unit-test without a client, as in V1.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from crmbuilder_v2 import __version__ as _V2_VERSION
from crmbuilder_v2.access.evidence_projection import EVIDENCE_FLAG_KEYS
from crmbuilder_v2.access.repositories import deposit_events as deposit_repo
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.access.repositories import instances as instances_repo
from crmbuilder_v2.access.repositories import references as references_repo
from crmbuilder_v2.access.repositories import utilization_evidence as evidence_repo
from crmbuilder_v2.adapters.espocrm.model import _derived_field_type, _map_field_type
from crmbuilder_v2.introspect.audit_utils import NATIVE_ENTITIES
from crmbuilder_v2.transform.audit_deposit import EVIDENCE_SCHEMA_VERSION

logger = logging.getLogger(__name__)

#: Progress sink — ``(message, level)`` as every reconcile area takes it.
ProgressFn = Callable[[str, str], None]

#: PI-448 — live counters sink: ``(entities_done, entities_total)``.
CountersFn = Callable[[int, int], None]


def _note(progress: ProgressFn | None, message: str, level: str = "info") -> None:
    if progress is not None:
        progress(message, level)


class _RecordsClient(Protocol):
    """The slice of the introspection client this area needs."""

    def count_records(
        self, entity: str, where: list[dict[str, Any]] | None = None
    ) -> tuple[int, int | None]: ...

    def list_records(self, entity: str, **kwargs: Any) -> tuple[int, Any]: ...


# --- Field-shape vocabularies (WTK-096 §3.1) -------------------------------

_SCALAR_STRING_TYPES = {
    "varchar", "text", "wysiwyg", "email", "phone", "url",
    "enum", "date", "datetime", "datetimeOptional",
}
_NUMERIC_TYPES = {"int", "float", "autoincrement"}
_CURRENCY_TYPES = {"currency", "currencyConverted"}
_ARRAY_TYPES = {"multiEnum", "checklist", "array"}
_LINK_TYPES = {"link", "linkOne", "foreign"}
_OPTIONED_TYPES = {"enum", "multiEnum", "checklist"}

_PERSON_NAME_COMPONENTS = ["firstName", "lastName", "middleName"]
_ADDRESS_COMPONENT_SUFFIXES = ["Street", "City", "State", "Country", "PostalCode"]

# --- Retry / failure-tier constants (WTK-096 §7) ----------------------------

_RETRYABLE_STATUSES = {-1, 429, 502, 503, 504}
_MAX_ATTEMPTS = 5
_BACKOFF_SECONDS = (1.0, 2.0, 4.0, 8.0, 16.0)
_CONSECUTIVE_ENTITY_FAILURE_LIMIT = 3

#: Membership states that put a design object on the instance's work list.
_ON_INSTANCE_STATES = ("present", "drifted")

#: Where the retiring file-fed deposit path names its per-event log; the native
#: area names the same location so the two kinds of event sit side by side.
_LOG_DIR = "PRDs/product/crmbuilder-v2/deposit-event-logs"


# ---------------------------------------------------------------------------
# Options and work-list containers
# ---------------------------------------------------------------------------


@dataclass
class ProfileOptions:
    """Options controlling the profiling pass (V1 ``ProfileOptions``, unchanged).

    :param dormancy_window_days: Window for the entity ``dormant`` and field
        ``stale`` flags (WTK-096 §5; anchored to WTK-088 Q2).
    :param low_population_threshold: Rate below which a field is flagged
        ``low_population`` (anchored to WTK-088 Q1).
    :param scan_cap: Maximum records scanned per entity; beyond it the scanned
        newest-first prefix becomes the sample (§4.5).
    :param throttle_seconds: Optional inter-request sleep against shared
        production instances.
    :param page_size: Scan page size (the ``maxSize=200`` convention).
    :param distinct_track_cap: Per-field cap on tracked distinct values.
    :param top_values_max_distinct: ``top_values`` is only emitted for non-enum
        fields at or under this many distinct values.
    :param top_values_count: How many top values to record.
    :param undeclared_values_cap: Cap on recorded undeclared enum values.
    """

    dormancy_window_days: int = 365
    low_population_threshold: float = 0.05
    scan_cap: int = 10000
    throttle_seconds: float = 0.0
    page_size: int = 200
    distinct_track_cap: int = 1000
    top_values_max_distinct: int = 100
    top_values_count: int = 10
    undeclared_values_cap: int = 50


@dataclass
class ProfileTarget:
    """One field-shaped profiling target on an entity.

    ``api_name`` / ``field_type`` are the EspoCRM wire name and type the reads
    use; ``field_identifier`` is the design record (FLD-) the evidence row is
    written against.
    """

    api_name: str
    field_type: str
    field_identifier: str
    declared_options: list[str] = field(default_factory=list)
    built_in: bool = False


@dataclass
class EntityWorkItem:
    """The profiling work-list entry for one entity."""

    espo_name: str
    entity_identifier: str
    native: bool
    targets: list[ProfileTarget] = field(default_factory=list)


class _RunAbort(Exception):
    """Internal: the §7.3 run tier fired (401 or sustained outage)."""

    def __init__(self, note: str) -> None:
        super().__init__(note)
        self.note = note


class _EntityFailure(Exception):
    """Internal: the §7.3 entity tier fired for one entity."""

    def __init__(self, status: int, note: str, exhausted: bool = False) -> None:
        super().__init__(note)
        self.status = status
        self.note = note
        self.exhausted = exhausted


# ---------------------------------------------------------------------------
# Pure predicate / derivation functions (no HTTP)
# ---------------------------------------------------------------------------


def select_attributes_for(api_name: str, field_type: str) -> list[str]:
    """Resolve the list-payload attributes a target needs scanned.

    ``linkMultiple`` returns an empty list — its ``{f}Ids`` collection is not
    reliably materialized on list reads (§4.4); ``bool`` also scans nothing
    because its distribution comes from count queries (§3.1).
    """
    if field_type in _LINK_TYPES or field_type == "linkParent":
        return [f"{api_name}Id"]
    if field_type in ("linkMultiple", "bool"):
        return []
    if field_type == "personName":
        return list(_PERSON_NAME_COMPONENTS)
    if field_type == "address":
        return [f"{api_name}{suffix}" for suffix in _ADDRESS_COMPONENT_SUFFIXES]
    return [api_name]


def populated_where_for(api_name: str, field_type: str) -> list[dict[str, Any]] | None:
    """Build the populated-where for a field per the §4.2 table.

    :returns: Where-item list, or ``None`` for ``bool`` (whose
        ``populated_count`` is definitionally the record count).
    """
    if field_type == "bool":
        return None
    if field_type in _ARRAY_TYPES:
        return [{"type": "arrayIsNotEmpty", "attribute": api_name}]
    if field_type in _LINK_TYPES or field_type == "linkParent":
        return [{"type": "isNotNull", "attribute": f"{api_name}Id"}]
    if field_type == "linkMultiple":
        return [{"type": "isLinked", "attribute": api_name}]
    if field_type == "personName":
        # Approximation; the scan refines under the any-component rule.
        return [{"type": "isNotNull", "attribute": "lastName"}]
    if field_type == "address":
        return [{"type": "isNotNull", "attribute": f"{api_name}City"}]
    # Scalar strings, numerics, currency, and unknown types alike: isNotNull on
    # the field's own attribute (currency's amount attribute carries the name).
    return [{"type": "isNotNull", "attribute": api_name}]


def option_where_for(api_name: str, field_type: str, option: str) -> list[dict[str, Any]]:
    """Build the option-where counting one declared option's usage (§4.2)."""
    if field_type in _ARRAY_TYPES:
        return [{"type": "arrayAnyOf", "attribute": api_name, "value": [option]}]
    return [{"type": "equals", "attribute": api_name, "value": option}]


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def is_populated(api_name: str, field_type: str, record: dict[str, Any]) -> bool:
    """The strict §3.1 populated predicate, evaluated on a scanned record."""
    if field_type == "bool":
        return True
    if field_type in _NUMERIC_TYPES or field_type in _CURRENCY_TYPES:
        return record.get(api_name) is not None
    if field_type in _ARRAY_TYPES:
        value = record.get(api_name)
        return isinstance(value, list) and len(value) > 0
    if field_type in _LINK_TYPES or field_type == "linkParent":
        return record.get(f"{api_name}Id") is not None
    if field_type == "personName":
        return any(_non_empty_string(record.get(c)) for c in _PERSON_NAME_COMPONENTS)
    if field_type == "address":
        return any(
            _non_empty_string(record.get(f"{api_name}{suffix}"))
            for suffix in _ADDRESS_COMPONENT_SUFFIXES
        )
    if field_type == "linkMultiple":
        # Not derivable from list payloads; the isLinked count query owns it.
        return False
    value = record.get(api_name)
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def scan_values(api_name: str, field_type: str, record: dict[str, Any]) -> list[str]:
    """Extract the distinct-tracking values a record contributes (§3.3).

    Arrays contribute their elements; links their foreign id; scalars their
    trimmed, case-preserved string form. Unpopulated fields contribute nothing.
    """
    if field_type in ("bool", "linkMultiple"):
        return []
    if not is_populated(api_name, field_type, record):
        return []
    if field_type in _ARRAY_TYPES:
        return [str(v) for v in record.get(api_name, [])]
    if field_type in _LINK_TYPES or field_type == "linkParent":
        return [str(record.get(f"{api_name}Id"))]
    if field_type == "personName":
        parts = [
            str(record.get(c)).strip()
            for c in _PERSON_NAME_COMPONENTS
            if _non_empty_string(record.get(c))
        ]
        return [" ".join(parts)]
    if field_type == "address":
        parts = [
            str(record.get(f"{api_name}{suffix}")).strip()
            for suffix in _ADDRESS_COMPONENT_SUFFIXES
            if _non_empty_string(record.get(f"{api_name}{suffix}"))
        ]
        return [", ".join(parts)]
    value = record.get(api_name)
    return [str(value).strip() if isinstance(value, str) else str(value)]


def _parse_espo_datetime(value: Any) -> datetime | None:
    """Parse an EspoCRM datetime (``YYYY-MM-DD HH:MM:SS`` or ISO); naive = UTC."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().replace(" ", "T")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _format_utc(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Flag derivations (WTK-096 §5)
# ---------------------------------------------------------------------------


def derive_entity_flags(
    record_count: int,
    last_record_created_at: datetime | None,
    profiled_at: datetime,
    dormancy_window_days: int,
) -> dict[str, bool]:
    """Derive the advisory ``dormant`` / ``empty`` entity flags."""
    empty = record_count == 0
    cutoff = profiled_at - timedelta(days=dormancy_window_days)
    dormant = empty or (
        last_record_created_at is not None and last_record_created_at < cutoff
    )
    return {"dormant": dormant, "empty": empty}


def is_low_population(rate: float | None, threshold: float) -> bool:
    """Q1 flag: rate strictly below threshold (the threshold itself is not flagged)."""
    return rate is not None and rate < threshold


def is_stale(
    populated_count: int,
    last_populated_at: datetime | None,
    profiled_at: datetime,
    dormancy_window_days: int,
) -> bool:
    """Field ``stale`` flag: populated, but not on any recent record."""
    if populated_count <= 0 or last_populated_at is None:
        return False
    return last_populated_at < profiled_at - timedelta(days=dormancy_window_days)


# ---------------------------------------------------------------------------
# Work-list derivation from the design + membership
# ---------------------------------------------------------------------------


def wire_entity_name(entity_name: str) -> str:
    """The EspoCRM scope name for a design entity — the reverse of
    ``strip_entity_c_prefix``: native names stay, everything else is ``C``-prefixed."""
    if entity_name in NATIVE_ENTITIES:
        return entity_name
    return f"C{entity_name}"


def wire_field_name(field_name: str, *, entity_native: bool, built_in: bool) -> str:
    """The EspoCRM attribute name for a design field — the reverse of
    ``strip_field_c_prefix``: only a custom field on a native entity carries the
    platform ``c`` prefix (REQ-342); built-in fields are their own wire name."""
    if entity_native and not built_in and field_name:
        return "c" + field_name[0].upper() + field_name[1:]
    return field_name


def wire_field_type(field_row: dict) -> str | None:
    """The EspoCRM field type a design field profiles as, via the emitter's table.

    A ``reference`` field is link-shaped (the V1 relationship-side target); a
    ``derived`` field profiles as its result type; ``foreign`` as itself. ``None``
    means EspoCRM has no type for what the design describes (REQ-502) and the
    field is reported rather than guessed at.
    """
    kind = field_row.get("field_type")
    if kind == "reference":
        return "link"
    if kind == "foreign":
        return "foreign"
    if kind == "derived":
        return _derived_field_type(field_row)
    return _map_field_type(field_row)


def _declared_options(field_row: dict) -> list[str]:
    opts = list(field_row.get("field_options") or [])
    opts.sort(
        key=lambda o: (
            o.get("option_order") if o.get("option_order") is not None else 0,
            str(o.get("option_value") or ""),
        )
    )
    return [str(o["option_value"]) for o in opts if o.get("option_value")]


def build_work_list(
    session: Session,
    *,
    instance_identifier: str,
    anomalies: list[dict[str, Any]] | None = None,
) -> list[EntityWorkItem]:
    """Derive the work list from the design as it stands on this instance.

    Every canonical entity with a present / drifted membership here is profiled;
    its targets are its present / drifted fields, custom and built-in alike.
    Relationship sides are not targets: a relationship is not an evidence subject
    (``EVIDENCE_SUBJECT_TYPES``), so only a design field that describes a link
    (``reference`` / ``foreign``) is profiled link-shaped.

    :param anomalies: Collects a ``{"scope": "field", ...}`` row for each field
        the design describes but EspoCRM cannot type (not profiled).
    :returns: One :class:`EntityWorkItem` per entity, in identifier order.
    """
    entity_states = {
        m["member_identifier"]: m["state"]
        for m in membership_repo.list_memberships(
            session, instance_identifier=instance_identifier, member_type="entity"
        )
        if m["state"] in _ON_INSTANCE_STATES
    }
    field_states = {
        m["member_identifier"]: m["state"]
        for m in membership_repo.list_memberships(
            session, instance_identifier=instance_identifier, member_type="field"
        )
        if m["state"] in _ON_INSTANCE_STATES
    }
    items: list[EntityWorkItem] = []
    for entity_identifier in sorted(entity_states):
        entity = entity_repo.get_entity(session, entity_identifier)
        if entity is None:
            continue
        native = entity["entity_name"] in NATIVE_ENTITIES
        item = EntityWorkItem(
            espo_name=wire_entity_name(entity["entity_name"]),
            entity_identifier=entity_identifier,
            native=native,
        )
        for row in field_repo.list_fields(session, entity_identifier=entity_identifier):
            if row["field_identifier"] not in field_states:
                continue
            built_in = bool(row.get("field_built_in"))
            api_name = wire_field_name(
                row["field_name"], entity_native=native, built_in=built_in
            )
            wire_type = wire_field_type(row)
            if wire_type is None:
                if anomalies is not None:
                    anomalies.append({
                        "scope": "field",
                        "entity": item.espo_name,
                        "field": api_name,
                        "status": None,
                        "note": (
                            f"design kind {row.get('field_type')!r} has no EspoCRM "
                            f"type; not profiled"
                        ),
                    })
                continue
            item.targets.append(ProfileTarget(
                api_name=api_name,
                field_type=wire_type,
                field_identifier=row["field_identifier"],
                declared_options=(
                    _declared_options(row) if wire_type in _OPTIONED_TYPES else []
                ),
                built_in=built_in,
            ))
        items.append(item)
    return items


# ---------------------------------------------------------------------------
# Per-field scan accumulator
# ---------------------------------------------------------------------------


class _ScanStats:
    """Accumulates one target's scan-derived metrics across pages."""

    def __init__(self, target: ProfileTarget, options: ProfileOptions) -> None:
        self.target = target
        self._options = options
        self.value_counts: Counter[str] = Counter()
        self.distinct_overflow = False
        self.strict_populated = 0
        self.count_mode_populated = 0  # non-NULL approximation, for delta
        self.empty_strings = 0
        self.last_populated: datetime | None = None

    def observe(self, record: dict[str, Any]) -> None:
        t = self.target
        strict = is_populated(t.api_name, t.field_type, record)
        if strict:
            self.strict_populated += 1
            created = _parse_espo_datetime(record.get("createdAt"))
            if created and (self.last_populated is None or created > self.last_populated):
                self.last_populated = created
        # Empty-string delta: non-NULL under the count-query approximation but
        # unpopulated under the strict predicate.
        if t.field_type in _SCALAR_STRING_TYPES:
            value = record.get(t.api_name)
            if value is not None:
                self.count_mode_populated += 1
                if not strict:
                    self.empty_strings += 1
        for value in scan_values(t.api_name, t.field_type, record):
            if value in self.value_counts:
                self.value_counts[value] += 1
            elif len(self.value_counts) < self._options.distinct_track_cap:
                self.value_counts[value] = 1
            else:
                self.distinct_overflow = True

    @property
    def distinct_value_count(self) -> int:
        return len(self.value_counts)


# ---------------------------------------------------------------------------
# The profiler (V1 ``DataProfiler`` over the V2 client and work list)
# ---------------------------------------------------------------------------


@dataclass
class ProfileRun:
    """What one profiling pass produced.

    :param entities: ``{espo_name: entity_out}`` for every entity that completed.
    :param anomalies: The §7 anomaly rows (metric / entity / run scopes).
    :param aborted: True when the run hit the §7.3 run tier.
    """

    profiled_at: datetime
    entities: dict[str, dict[str, Any]]
    anomalies: list[dict[str, Any]]
    aborted: bool = False


class Profiler:
    """Read-only record profiler over a work list (WTK-096, V1 algorithm).

    :param client: Introspection client connected to the instance.
    :param options: Profiling options (thresholds, caps, throttle).
    :param progress: Progress sink for the operator's running audit log.
    """

    def __init__(
        self,
        client: _RecordsClient,
        options: ProfileOptions | None = None,
        progress: ProgressFn | None = None,
        counters: CountersFn | None = None,
    ) -> None:
        self._client = client
        self._options = options or ProfileOptions()
        self._progress = progress
        self._counters = counters
        self._anomalies: list[dict[str, Any]] = []
        self._entity_request_count = 0

    # -- transport ----------------------------------------------------

    def _retry_after_seconds(self) -> float | None:
        headers = getattr(self._client, "last_response_headers", None) or {}
        raw = headers.get("Retry-After")
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def _call_with_retry(self, fn: Callable[[], tuple[int, Any]]) -> tuple[int, Any]:
        """Issue one logical request under the §7.1 retry policy.

        Retries transport sentinels and 429/502/503/504 with 1/2/4/8 s backoff
        (5 attempts total); a larger ``Retry-After`` wins over the computed
        delay. A 401 anywhere raises the run tier.
        """
        status, body = -1, None
        for attempt in range(_MAX_ATTEMPTS):
            if self._options.throttle_seconds > 0:
                time.sleep(self._options.throttle_seconds)
            self._entity_request_count += 1
            status, body = fn()
            if status == 401:
                raise _RunAbort("HTTP 401 — credentials rejected mid-run")
            if status not in _RETRYABLE_STATUSES:
                return status, body
            if attempt == _MAX_ATTEMPTS - 1:
                break
            delay = _BACKOFF_SECONDS[attempt]
            retry_after = self._retry_after_seconds()
            if status == 429 and retry_after is not None and retry_after > delay:
                delay = retry_after
            time.sleep(delay)
        return status, body

    # -- run ------------------------------------------------------------

    def run(self, work_list: list[EntityWorkItem]) -> ProfileRun:
        """Execute the profiling pass over ``work_list``."""
        profiled_at = datetime.now(tz=UTC)
        entities_out: dict[str, dict[str, Any]] = {}
        consecutive_failures = 0
        aborted = False

        for index, item in enumerate(work_list):
            if self._counters is not None:
                self._counters(index, len(work_list))
            try:
                entities_out[item.espo_name] = self._profile_entity(item, profiled_at)
                consecutive_failures = 0
            except _EntityFailure as exc:
                self._anomalies.append({
                    "scope": "entity",
                    "entity": item.espo_name,
                    "status": exc.status,
                    "note": exc.note,
                })
                _note(
                    self._progress,
                    f"{item.espo_name}: profiling failed — {exc.note}",
                    "warning",
                )
                if exc.exhausted:
                    consecutive_failures += 1
                    if consecutive_failures >= _CONSECUTIVE_ENTITY_FAILURE_LIMIT:
                        remainder = [w.espo_name for w in work_list[index + 1:]]
                        self._anomalies.append({
                            "scope": "run",
                            "entity": None,
                            "status": exc.status,
                            "note": (
                                f"retries exhausted on {consecutive_failures} "
                                f"consecutive entities — aborting; "
                                f"unprofiled: {remainder}"
                            ),
                        })
                        _note(
                            self._progress,
                            f"profiling aborted after {consecutive_failures} "
                            f"consecutive entity failures; unprofiled: {remainder}",
                            "error",
                        )
                        aborted = True
                        break
                else:
                    consecutive_failures = 0
            except _RunAbort as exc:
                remainder = [w.espo_name for w in work_list[index:]]
                self._anomalies.append({
                    "scope": "run",
                    "entity": item.espo_name,
                    "status": 401,
                    "note": f"{exc.note}; unprofiled: {remainder}",
                })
                _note(self._progress, f"profiling aborted — {exc.note}", "error")
                aborted = True
                break

        if self._counters is not None:
            self._counters(len(entities_out), len(work_list))
        return ProfileRun(
            profiled_at=profiled_at,
            entities=entities_out,
            anomalies=self._anomalies,
            aborted=aborted,
        )

    # -- per-entity -----------------------------------------------------

    def _profile_entity(
        self, item: EntityWorkItem, profiled_at: datetime
    ) -> dict[str, Any]:
        """Profile one entity: count mode, then the scan pass (§4.2–§4.5).

        :raises _EntityFailure: On the §7.3 entity tier.
        :raises _RunAbort: On 401 (propagated from the retry wrapper).
        """
        opts = self._options
        espo = item.espo_name
        self._entity_request_count = 0
        entity_started = datetime.now(tz=UTC)

        # 1. record_count — also the entity-tier gate.
        status, total = self._call_with_retry(
            lambda: self._client.count_records(espo)
        )
        if status in (403, 404):
            raise _EntityFailure(status, f"HTTP {status} on record count")
        if status in _RETRYABLE_STATUSES:
            raise _EntityFailure(
                status, f"retries exhausted on record count (HTTP {status})",
                exhausted=True,
            )
        if status != 200 or total is None:
            raise _EntityFailure(status, f"record count failed (HTTP {status})")
        # An entity with counting disabled (the ``countDisabled`` collection
        # setting the audit captures) answers ``total: -1`` — the platform will
        # not count, and every count-mode query would answer the same. V1 wrote
        # the -1 through unchecked (PI-428 live parity finding); here the record
        # count comes from the scan instead — exact when the scan completes,
        # otherwise a flagged lower bound — and every field metric is scan-derived.
        count_disabled = total < 0
        record_count = total if not count_disabled else 0
        if count_disabled:
            self._anomalies.append({
                "scope": "entity", "entity": espo, "field": None,
                "metric": "record_count", "status": status,
                "note": (
                    "counting is disabled on this entity; record count taken "
                    "from the scan (exact if the scan completed, else a lower bound)"
                ),
            })

        # 2. last_record_created_at — recency query, skipped when empty.
        last_record_created: datetime | None = None
        if record_count > 0 or count_disabled:
            last_record_created = self._recency_query(espo, None)

        field_metrics: dict[str, dict[str, Any]] = {}
        scan_fallback: dict[str, set[str]] = {}

        # 3–5. Count mode per field (none when the platform will not count).
        for target in item.targets:
            if count_disabled:
                field_metrics[target.api_name] = {}
                scan_fallback[target.api_name] = {
                    "populated_count", "last_populated_at", "value_distribution",
                }
            else:
                field_metrics[target.api_name] = self._count_mode_field(
                    espo, target, record_count, scan_fallback,
                )

        # 6. Scan pass — value inspection plus count→scan fallback (§4.4).
        scan_info = self._scan_entity(
            item, record_count, field_metrics, scan_fallback,
            count_known=not count_disabled,
        )
        if count_disabled:
            record_count = scan_info.get("scanned", 0)

        # 7. Assemble, deriving flags (§5) and the §6 shape rules.
        fields_out: dict[str, dict[str, Any]] = {}
        for target in item.targets:
            fields_out[target.api_name] = self._assemble_field(
                target, field_metrics[target.api_name], record_count, profiled_at,
            )

        flags = derive_entity_flags(
            record_count, last_record_created, profiled_at, opts.dormancy_window_days,
        )
        detail: dict[str, Any] = {
            "profiled_entity_at": _format_utc(entity_started),
            "dormant": flags["dormant"],
            "empty": flags["empty"],
            "sampled": scan_info.get("sampled", False),
            "request_count": self._entity_request_count,
        }
        if scan_info.get("sampled"):
            detail["scan_count"] = scan_info["scan_count"]
            if "sample_fraction" in scan_info:
                detail["sample_fraction"] = scan_info["sample_fraction"]
            detail["sample_basis"] = "most_recent_by_created_at"
        if count_disabled:
            detail["count_disabled"] = True
            if scan_info.get("sampled"):
                detail["count_lower_bound"] = True

        entity_out: dict[str, Any] = {
            "record_count": record_count,
            "last_record_created_at": last_record_created,
            "detail": detail,
            "fields": fields_out,
        }
        _note(
            self._progress,
            f"{espo}: {record_count} records, {len(item.targets)} fields profiled",
        )
        return entity_out

    def _recency_query(
        self, espo: str, where: list[dict[str, Any]] | None
    ) -> datetime | None:
        """Newest matching record's createdAt, or None (metric tier)."""
        status, body = self._call_with_retry(
            lambda: self._client.list_records(
                espo, select=["id", "createdAt"], where=where,
                order_by="createdAt", order="desc", max_size=1,
            )
        )
        if status == 200 and isinstance(body, dict):
            rows = body.get("list") or []
            if rows:
                return _parse_espo_datetime(rows[0].get("createdAt"))
        return None

    def _count_mode_field(
        self,
        espo: str,
        target: ProfileTarget,
        record_count: int,
        scan_fallback: dict[str, set[str]],
    ) -> dict[str, Any]:
        """Run a field's count-mode queries; mark fallbacks on 400 (§4.2)."""
        metrics: dict[str, Any] = {}
        f = target.api_name

        if record_count == 0:
            # No records means no evidence about the field either way (§3.3) —
            # no queries; the entity-level empty flag carries the finding.
            metrics["populated_count"] = 0
            if target.declared_options:
                metrics["value_distribution"] = dict.fromkeys(target.declared_options, 0)
            return metrics

        def _mark_fallback(metric: str, status: int, note: str) -> None:
            scan_fallback.setdefault(f, set()).add(metric)
            self._anomalies.append({
                "scope": "metric", "entity": espo, "field": f,
                "metric": metric, "status": status, "note": note,
            })

        if target.field_type == "bool":
            # §3.1 — populated definitionally; the useful signal is the
            # true-count distribution from an isTrue count query.
            metrics["populated_count"] = record_count
            status, true_count = self._call_with_retry(
                lambda: self._client.count_records(
                    espo, where=[{"type": "isTrue", "attribute": f}],
                )
            )
            if status == 200 and true_count is not None:
                metrics["value_distribution"] = {
                    "true": true_count,
                    "false": record_count - true_count,
                }
            else:
                _mark_fallback(
                    "value_distribution", status,
                    f"isTrue count failed (HTTP {status})",
                )
            return metrics

        where = populated_where_for(f, target.field_type)
        status, populated = self._call_with_retry(
            lambda: self._client.count_records(espo, where=where)
        )
        if status == 200 and populated is not None:
            metrics["populated_count"] = populated
        else:
            note = (
                f"{where[0]['type']} rejected for attribute; metric scan-derived"
                if status == 400
                else f"populated count failed (HTTP {status}); metric scan-derived"
            )
            _mark_fallback("populated_count", status, note)

        if metrics.get("populated_count", 0) > 0:
            created = self._recency_query(espo, where)
            if created is not None:
                metrics["last_populated_at"] = created
            else:
                _mark_fallback(
                    "last_populated_at", 0,
                    "recency query failed; metric scan-derived",
                )

        if target.declared_options:
            distribution: dict[str, int] = {}
            for option in target.declared_options:
                o_where = option_where_for(f, target.field_type, option)
                status, count = self._call_with_retry(
                    lambda w=o_where: self._client.count_records(espo, where=w)
                )
                if status == 200 and count is not None:
                    distribution[option] = count
                else:
                    _mark_fallback(
                        "value_distribution", status,
                        f"option count for {option!r} failed (HTTP {status}); "
                        f"distribution scan-derived",
                    )
                    distribution = {}
                    break
            if distribution:
                metrics["value_distribution"] = distribution
        return metrics

    # -- scan pass ------------------------------------------------------

    def _scan_entity(
        self,
        item: EntityWorkItem,
        record_count: int,
        field_metrics: dict[str, dict[str, Any]],
        scan_fallback: dict[str, set[str]],
        *,
        count_known: bool = True,
    ) -> dict[str, Any]:
        """Run the §4.4 paged scan and fold results into field metrics.

        With ``count_known`` False (counting disabled on the entity) the scan
        runs to the cap or the end of the data, and ``scanned`` is the record
        count the caller adopts; ``sampled`` then means the cap was hit.
        """
        opts = self._options
        espo = item.espo_name
        scannable = [t for t in item.targets if select_attributes_for(t.api_name, t.field_type)]
        if not count_known:
            # Even with nothing to inspect, the scan is the only way to count
            # (ids only) when the platform will not.
            record_count = opts.scan_cap
        elif not scannable or record_count == 0:
            return {"sampled": False, "scanned": 0}

        select = ["id", "createdAt"]
        for target in scannable:
            for attr in select_attributes_for(target.api_name, target.field_type):
                if attr not in select:
                    select.append(attr)

        stats = {t.api_name: _ScanStats(t, opts) for t in scannable}
        scanned = 0
        offset = 0
        truncated_by_error = False
        while scanned < min(record_count, opts.scan_cap):
            page_size = min(opts.page_size, opts.scan_cap - scanned)
            status, body = self._call_with_retry(
                lambda o=offset, m=page_size: self._client.list_records(
                    espo, select=select, order_by="createdAt", order="desc",
                    offset=o, max_size=m,
                )
            )
            if status != 200 or not isinstance(body, dict):
                self._anomalies.append({
                    "scope": "metric", "entity": espo, "field": None,
                    "metric": "scan", "status": status,
                    "note": (
                        f"scan page at offset {offset} failed (HTTP {status}); "
                        f"scan-derived metrics computed from {scanned} records"
                    ),
                })
                truncated_by_error = True
                break
            rows = body.get("list") or []
            if not rows:
                break
            for record in rows:
                for stat in stats.values():
                    stat.observe(record)
            scanned += len(rows)
            offset += len(rows)
            if offset >= record_count:
                break
            if not count_known and len(rows) < page_size:
                break  # end of the data — the scan is complete

        sampled = (scanned >= opts.scan_cap) if not count_known else (scanned < record_count)
        complete_scan = not sampled and not truncated_by_error

        for target in scannable:
            stat = stats[target.api_name]
            metrics = field_metrics[target.api_name]
            fallbacks = scan_fallback.get(target.api_name, set())
            self._fold_scan_stats(target, stat, metrics, fallbacks, complete_scan, scanned)

        info: dict[str, Any] = {"sampled": sampled, "scanned": scanned}
        if sampled:
            info["scan_count"] = scanned
            if count_known:
                info["sample_fraction"] = (
                    round(scanned / record_count, 3) if record_count else 0.0
                )
        return info

    def _fold_scan_stats(
        self,
        target: ProfileTarget,
        stat: _ScanStats,
        metrics: dict[str, Any],
        fallbacks: set[str],
        complete_scan: bool,
        scanned: int,
    ) -> None:
        """Fold one target's scan stats into its metric dict (§3, §4.5)."""
        opts = self._options
        if scanned == 0:
            return

        metrics["distinct_value_count"] = stat.distinct_value_count
        if stat.distinct_overflow:
            metrics["distinct_overflow"] = True

        if target.declared_options:
            declared = set(target.declared_options)
            undeclared = {
                value: count
                for value, count in stat.value_counts.most_common()
                if value not in declared
            }
            metrics["undeclared_values"] = dict(
                list(undeclared.items())[: opts.undeclared_values_cap]
            )
            if "value_distribution" in fallbacks or "value_distribution" not in metrics:
                metrics["value_distribution"] = {
                    option: stat.value_counts.get(option, 0)
                    for option in target.declared_options
                }
        elif target.field_type != "bool":
            if stat.distinct_value_count <= opts.top_values_max_distinct:
                metrics["top_values"] = dict(
                    stat.value_counts.most_common(opts.top_values_count)
                )

        # Count→scan fallback: supply metrics count mode couldn't (§4.2).
        if "populated_count" in fallbacks and "populated_count" not in metrics:
            metrics["populated_count"] = stat.strict_populated
            if stat.last_populated is not None and "last_populated_at" not in metrics:
                metrics["last_populated_at"] = stat.last_populated
        if (
            "last_populated_at" in fallbacks
            and "last_populated_at" not in metrics
            and stat.last_populated is not None
        ):
            metrics["last_populated_at"] = stat.last_populated

        # §3.1 strict-predicate refinements — only a complete scan may override
        # exact count-mode numbers (a sample is a floor).
        if complete_scan:
            if (
                target.field_type in _SCALAR_STRING_TYPES
                and stat.empty_strings > 0
                and "populated_count" in metrics
            ):
                metrics["empty_string_count"] = stat.empty_strings
                if stat.strict_populated < metrics["populated_count"]:
                    metrics["populated_count"] = stat.strict_populated
                    if stat.last_populated is not None:
                        metrics["last_populated_at"] = stat.last_populated
                    elif "last_populated_at" in metrics:
                        del metrics["last_populated_at"]
            if target.field_type in ("personName", "address"):
                # Any-component rule supersedes the single-component
                # count-query approximation.
                metrics["populated_count"] = stat.strict_populated
                if stat.last_populated is not None:
                    metrics["last_populated_at"] = stat.last_populated
                elif "last_populated_at" in metrics:
                    del metrics["last_populated_at"]

    # -- assembly ---------------------------------------------------------

    def _assemble_field(
        self,
        target: ProfileTarget,
        metrics: dict[str, Any],
        record_count: int,
        profiled_at: datetime,
    ) -> dict[str, Any]:
        """Shape one field's entry per the §6 contract rules.

        ``last_populated_at`` stays a datetime here (the evidence row takes it
        typed); every other value is as the profile contract carries it.
        """
        opts = self._options
        out: dict[str, Any] = {}
        detail: dict[str, Any] = {}

        populated_count = metrics.get("populated_count")
        if populated_count is not None:
            out["populated_count"] = populated_count
            if record_count > 0:
                if target.field_type == "bool":
                    out["population_rate"] = 1.0
                else:
                    out["population_rate"] = round(
                        populated_count / record_count, 3
                    )

        last_populated: datetime | None = metrics.get("last_populated_at")
        if last_populated is not None and (populated_count or 0) > 0:
            out["last_populated_at"] = last_populated
            detail["last_populated_at_basis"] = "created_at"

        if target.field_type == "bool":
            distribution = metrics.get("value_distribution")
            if distribution is not None:
                detail["value_distribution"] = distribution
                out["distinct_value_count"] = sum(
                    1 for count in distribution.values() if count > 0
                )
        elif "distinct_value_count" in metrics:
            out["distinct_value_count"] = metrics["distinct_value_count"]

        if target.declared_options:
            out["declared_option_count"] = len(target.declared_options)
            distribution = metrics.get("value_distribution")
            if distribution is not None:
                out["used_option_count"] = sum(
                    1 for option in target.declared_options
                    if distribution.get(option, 0) > 0
                )
                detail["value_distribution"] = distribution
                ghost = out["declared_option_count"] - out["used_option_count"]
                if ghost > 0:
                    detail["ghost_options"] = ghost
            if "undeclared_values" in metrics:
                detail["undeclared_values"] = metrics["undeclared_values"]
        elif "top_values" in metrics:
            detail["top_values"] = metrics["top_values"]

        if metrics.get("distinct_overflow"):
            detail["distinct_overflow"] = True
        if metrics.get("empty_string_count"):
            detail["empty_string_count"] = metrics["empty_string_count"]

        if is_low_population(
            out.get("population_rate") if target.field_type != "bool" else None,
            opts.low_population_threshold,
        ):
            detail["low_population"] = True
        if is_stale(
            populated_count or 0, last_populated, profiled_at,
            opts.dormancy_window_days,
        ):
            detail["stale"] = True

        out["detail"] = detail
        return out


# ---------------------------------------------------------------------------
# The audit area: profile, then write evidence + provenance
# ---------------------------------------------------------------------------


def source_label_for(instance_url: str | None, fallback: str) -> str:
    """``espocrm @ <host>`` as V1 derived it (the evidence ``source_label``)."""
    host = urlparse(instance_url or "").netloc
    return f"espocrm @ {host or fallback}"


def _evidence_detail(
    wire_name: str,
    thresholds: dict[str, Any],
    **keys: Any,
) -> dict[str, Any]:
    """Assemble one WTK-097 §4-conformant ``evidence_detail`` block.

    The same key discipline as the file-fed deposit path: the common keys first
    (``evidence_schema_version``, ``wire_name``, ``profiler_version``), then the
    subject-specific keys (omitted when ``None``), then ``thresholds`` whenever
    the block carries a flag so the flags can always be re-derived from the row.
    """
    detail: dict[str, Any] = {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "wire_name": wire_name,
        "profiler_version": _V2_VERSION,
    }
    for key, value in keys.items():
        if value is not None:
            detail[key] = value
    if thresholds and any(key in detail for key in EVIDENCE_FLAG_KEYS):
        detail["thresholds"] = thresholds
    return detail


def reconcile_utilization(
    session: Session,
    *,
    instance_identifier: str,
    client: _RecordsClient,
    progress: ProgressFn | None = None,
    options: ProfileOptions | None = None,
    counters: CountersFn | None = None,
) -> dict:
    """Profile how the instance's records use the design, as evidence (REQ-524).

    Builds the work list from the design's membership on this instance, runs
    the profiler, then records the run: one ``audit_deposit`` deposit event
    (outcome ``failure`` only when the run aborted before any entity completed),
    one ``utilization_evidence`` row per profiled entity and field carrying the
    event's identifier, and an ``observed_in`` edge from each subject to the
    event. An instance with nothing present writes nothing at all.

    Opt-in by design: this area reads every record of every entity on the
    instance, so the structural audit does not run it; the per-area endpoint does.

    :returns: ``{entities, fields, evidence_rows, anomalies, aborted,
        deposit_event_identifier}``.
    """
    opts = options or ProfileOptions()
    instance = instances_repo.get_instance(session, instance_identifier) or {}
    source_label = source_label_for(
        instance.get("instance_url"), instance.get("instance_name") or instance_identifier
    )
    anomalies: list[dict[str, Any]] = []
    work_list = build_work_list(
        session, instance_identifier=instance_identifier, anomalies=anomalies
    )
    for row in anomalies:
        _note(progress, f"{row['entity']}.{row['field']}: {row['note']}", "warning")
    if not work_list:
        _note(progress, "nothing present on this instance to profile")
        return {
            "entities": 0, "fields": 0, "evidence_rows": 0,
            "anomalies": anomalies, "aborted": False,
            "deposit_event_identifier": None,
        }

    # PI-448: the work-list phase only read; commit here to release this
    # connection's transaction before the long record scan, so the job's live
    # progress and log writes (their own short sessions) are not blocked by an
    # idle-in-transaction connection — SQLite escalates that to
    # "database is locked". The completion writes below begin a fresh
    # transaction, so failure atomicity of the written records is unchanged.
    session.commit()
    run = Profiler(client, opts, progress, counters).run(work_list)
    anomalies.extend(run.anomalies)
    thresholds = {
        "dormancy_window_days": opts.dormancy_window_days,
        "low_population_threshold": opts.low_population_threshold,
    }
    profiled_at = _format_utc(run.profiled_at)

    dep_identifier = deposit_repo.next_deposit_event_identifier(session)
    log_file_path = f"{_LOG_DIR}/{dep_identifier.lower().replace('-', '_')}.log"
    failed = run.aborted and not run.entities
    apply_context = {
        "source_system": "espocrm",
        "source_instance": instance.get("instance_url") or instance_identifier,
        "snapshot_at": profiled_at,
        "kind": "audit_utilization",
        "instance_identifier": instance_identifier,
        "source_label": source_label,
        "profiled_at": profiled_at,
        "options": {**thresholds, "scan_cap": opts.scan_cap},
        "aborted": run.aborted,
    }
    event = deposit_repo.create_deposit_event(
        session,
        identifier=dep_identifier,
        title=f"Utilization audit: {source_label}",
        description=(
            f"Record utilization of {source_label} profiled natively by the "
            f"audit of instance {instance_identifier} at {profiled_at}."
        ),
        kind="audit_deposit",
        outcome="failure" if failed else "success",
        records_summary={},
        apply_context=apply_context,
        log_file_path=log_file_path,
        error_info=(
            {
                "error": "profiling aborted before any entity completed",
                "anomalies": anomalies,
            }
            if failed
            else None
        ),
    )
    dep_identifier = event["deposit_event_identifier"]

    evidence_rows = 0
    field_rows = 0
    for item in work_list:
        entity_out = run.entities.get(item.espo_name)
        if entity_out is None:
            continue
        evidence_repo.create_utilization_evidence(
            session,
            subject_type="entity",
            subject_identifier=item.entity_identifier,
            profiled_at=run.profiled_at,
            source_label=source_label,
            deposit_event_identifier=dep_identifier,
            catalog_class="standard" if item.native else "custom",
            record_count=entity_out["record_count"],
            last_record_created_at=entity_out["last_record_created_at"],
            detail=_evidence_detail(
                item.espo_name, thresholds, **entity_out["detail"]
            ),
        )
        references_repo.upsert(
            session,
            source_type="entity", source_id=item.entity_identifier,
            target_type="deposit_event", target_id=dep_identifier,
            relationship="observed_in",
        )
        evidence_rows += 1
        for target in item.targets:
            out = entity_out["fields"][target.api_name]
            evidence_repo.create_utilization_evidence(
                session,
                subject_type="field",
                subject_identifier=target.field_identifier,
                profiled_at=run.profiled_at,
                source_label=source_label,
                deposit_event_identifier=dep_identifier,
                catalog_class="standard" if target.built_in else "custom",
                populated_count=out.get("populated_count"),
                population_rate=out.get("population_rate"),
                last_populated_at=out.get("last_populated_at"),
                distinct_value_count=out.get("distinct_value_count"),
                declared_option_count=out.get("declared_option_count"),
                used_option_count=out.get("used_option_count"),
                detail=_evidence_detail(
                    target.api_name, thresholds,
                    wire_type=target.field_type,
                    **out["detail"],
                ),
            )
            references_repo.upsert(
                session,
                source_type="field", source_id=target.field_identifier,
                target_type="deposit_event", target_id=dep_identifier,
                relationship="observed_in",
            )
            evidence_rows += 1
            field_rows += 1

    return {
        "entities": len(run.entities),
        "fields": field_rows,
        "evidence_rows": evidence_rows,
        "anomalies": anomalies,
        "aborted": run.aborted,
        "deposit_event_identifier": dep_identifier,
    }
