"""EspoCRM data-profiling pass — pass 2 of the Phase 1.5 audit.

Consumes the schema-discovery pass's :class:`AuditReport` as its
work-list, queries the source's record search/count endpoints
(read-only — GET exclusively), and produces the
``utilization-profile.json`` contract: per-entity record counts and
creation recency, per-field population rates, actual enum value
distribution versus declared options, and dormant-entity detection.

Design spec: ``PRDs/product/crmbuilder-v2/methodology-schema-specs/
espocrm-data-profiling-pass.md`` (WTK-096). Consumer contract:
``audit-report-to-candidate-deposit-transform.md`` (WTK-090) §2.2.

The module keeps the manager/pure-function split used across
``espo_impl/core``: the populated predicate, where-clause derivation,
and flag derivations are module-level functions free of HTTP so they
unit-test without a client; :class:`DataProfiler` orchestrates the
REST strategy on top of them.
"""

import json
import logging
import os
import tempfile
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.audit_manager import (
    AuditReport,
    EntityAuditResult,
)
from espo_impl.core.audit_utils import EntityClass

logger = logging.getLogger(__name__)

# Callback signature matches the audit manager's: (message, color).
ProgressCallback = Callable[[str, str], None]

PROFILE_FILENAME = "utilization-profile.json"

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


# ---------------------------------------------------------------------------
# Options and result containers
# ---------------------------------------------------------------------------

@dataclass
class ProfileOptions:
    """Options controlling the data-profiling pass.

    :param dormancy_window_days: Window for the entity ``dormant`` and
        field ``stale`` flags (WTK-096 §5; anchored to WTK-088 Q2).
    :param low_population_threshold: Rate below which a field is
        flagged ``low_population`` (anchored to WTK-088 Q1).
    :param scan_cap: Maximum records scanned per entity; beyond it the
        scanned newest-first prefix becomes the sample (§4.5).
    :param throttle_seconds: Optional inter-request sleep for operator-
        imposed politeness against shared production instances.
    :param page_size: Scan page size (the codebase's ``maxSize=200``
        convention; the server may clamp lower).
    :param distinct_track_cap: Per-field cap on tracked distinct values.
    :param top_values_max_distinct: ``top_values`` is only emitted for
        non-enum fields at or under this many distinct values.
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

    Targets come from the entity's audited fields and from relationship
    sides (deduplicated by wire name, WTK-090 §3.3). ``api_name`` is the
    EspoCRM wire name — the key the profile output and the WTK-090
    transform join on.
    """

    api_name: str
    field_type: str
    declared_options: list[str] = field(default_factory=list)


@dataclass
class EntityWorkItem:
    """The profiling work-list entry for one entity."""

    espo_name: str
    targets: list[ProfileTarget] = field(default_factory=list)


@dataclass
class UtilizationProfile:
    """Result of a data-profiling run.

    :param data: The ``utilization-profile.json`` payload, or ``None``
        when the run aborted before any entity completed (in which case
        no file is written, §7.3 run tier).
    :param aborted: True when the run hit the §7.3 run tier.
    """

    data: dict[str, Any] | None
    aborted: bool = False

    @property
    def anomalies(self) -> list[dict[str, Any]]:
        """The anomaly rows carried in the profile (empty when no data)."""
        if self.data is None:
            return []
        return self.data.get("anomalies", [])

    def warning_lines(self) -> list[str]:
        """Render anomalies as audit-warning strings for ``AuditReport.warnings``."""
        lines = []
        for a in self.anomalies:
            where = a.get("entity") or "run"
            if a.get("field"):
                where = f"{where}.{a['field']}"
            lines.append(f"profiler [{a.get('scope', '?')}] {where}: {a.get('note', '')}")
        return lines

    def write(self, output_dir: Path, filename: str = PROFILE_FILENAME) -> Path | None:
        """Atomically write the profile JSON beside ``audit-report.json``.

        Temp-file + rename so a crash mid-write never leaves a torn
        profile (§6). No-op returning ``None`` when there is no data.

        :param output_dir: The audit output directory.
        :param filename: Output filename (default per the contract).
        :returns: The written path, or ``None`` when nothing was written.
        """
        if self.data is None:
            return None
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / filename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(output_dir), prefix=f".{filename}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2, sort_keys=False)
                fh.write("\n")
            os.replace(tmp_path, target)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return target


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

    ``linkMultiple`` returns an empty list — its ``{f}Ids`` collection
    is not reliably materialized on list reads, so it is excluded from
    the scan select (§4.4); ``bool`` also scans nothing because its
    distribution comes from count queries (§3.1).

    :param api_name: Wire field name.
    :param field_type: Wire field type.
    :returns: Attribute names for the scan select-list.
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

    :param api_name: Wire field name.
    :param field_type: Wire field type.
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
    # Scalar strings, numerics, currency, and unknown types alike:
    # isNotNull on the field's own attribute. (Currency's amount
    # attribute carries the field name.)
    return [{"type": "isNotNull", "attribute": api_name}]


def option_where_for(api_name: str, field_type: str, option: str) -> list[dict[str, Any]]:
    """Build the option-where counting one declared option's usage (§4.2).

    :param api_name: Wire field name.
    :param field_type: Wire field type (``enum`` or an array shape).
    :param option: The declared option value.
    :returns: Where-item list.
    """
    if field_type in _ARRAY_TYPES:
        return [{"type": "arrayAnyOf", "attribute": api_name, "value": [option]}]
    return [{"type": "equals", "attribute": api_name, "value": option}]


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def is_populated(api_name: str, field_type: str, record: dict[str, Any]) -> bool:
    """The strict §3.1 populated predicate, evaluated on a scanned record.

    :param api_name: Wire field name.
    :param field_type: Wire field type.
    :param record: One record dict from the list payload.
    :returns: True when the field is populated on the record.
    """
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
        # Not derivable from list payloads; the isLinked count query
        # owns this metric (§4.4).
        return False
    value = record.get(api_name)
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def scan_values(api_name: str, field_type: str, record: dict[str, Any]) -> list[str]:
    """Extract the distinct-tracking values a record contributes (§3.3).

    Arrays contribute their elements; links their foreign id; scalars
    their trimmed, case-preserved string form. Unpopulated fields
    contribute nothing.

    :param api_name: Wire field name.
    :param field_type: Wire field type.
    :param record: One record dict from the list payload.
    :returns: Zero or more normalized scalar values.
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
    """Parse an EspoCRM datetime string (``YYYY-MM-DD HH:MM:SS`` or ISO).

    EspoCRM list payloads carry space-separated UTC datetimes; metadata
    occasionally carries ISO forms. Naive values are assumed UTC.

    :param value: The raw attribute value.
    :returns: An aware UTC datetime, or ``None`` when unparseable.
    """
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
# Work-list derivation (WTK-096 §2.1)
# ---------------------------------------------------------------------------

def _c_prefixed(name: str) -> str:
    """Forward-map a YAML natural field name to its c-prefixed wire form."""
    if not name:
        return name
    return "c" + name[0].upper() + name[1:]


def _relationship_side_type(link_type: str, primary: bool) -> str:
    """Map a YAML linkType to the wire field shape of one side.

    The primary side of ``manyToOne`` is the belongsTo (single) side;
    the primary side of ``oneToMany`` is the hasMany side (matching
    ``_resolve_link_type`` in the audit manager).

    :param link_type: YAML linkType (manyToOne, oneToMany, manyToMany,
        oneToOne).
    :param primary: True for the ``entity``/``link`` side of the
        :class:`RelationshipAuditResult`, False for the foreign side.
    :returns: Wire field type for the side's profiling target.
    """
    if link_type == "manyToOne":
        return "link" if primary else "linkMultiple"
    if link_type == "oneToMany":
        return "linkMultiple" if primary else "link"
    if link_type == "manyToMany":
        return "linkMultiple"
    return "link"


def build_work_list(report: AuditReport) -> list[EntityWorkItem]:
    """Derive the profiling work-list from a schema-discovery report.

    Every audited entity is profiled, custom and native alike (the
    WTK-090 skipped-native rule is a transform rule, not a profiler
    rule). Per entity: every audited field, plus one link-shaped target
    per relationship side, deduplicated against field targets by wire
    name (§2.1).

    :param report: The pass-1 :class:`AuditReport` aggregate.
    :returns: One :class:`EntityWorkItem` per entity, in report order.
    """
    items: list[EntityWorkItem] = []
    by_yaml_name: dict[str, EntityAuditResult] = {
        e.yaml_name: e for e in report.entities
    }
    item_by_espo: dict[str, EntityWorkItem] = {}

    for entity in report.entities:
        item = EntityWorkItem(espo_name=entity.espo_name)
        for f in entity.fields:
            options = f.properties.get("options") or []
            item.targets.append(ProfileTarget(
                api_name=f.api_name,
                field_type=f.field_type,
                declared_options=[str(o) for o in options]
                if f.field_type in _OPTIONED_TYPES else [],
            ))
        items.append(item)
        item_by_espo[entity.espo_name] = item

    for rel in report.relationships:
        sides = (
            (rel.entity, rel.link, True),
            (rel.entity_foreign, rel.link_foreign, False),
        )
        for yaml_entity, yaml_link, primary in sides:
            entity = by_yaml_name.get(yaml_entity)
            if entity is None or not yaml_link:
                continue
            item = item_by_espo[entity.espo_name]
            existing = {t.api_name for t in item.targets}
            # The relationship stores YAML names; recover the wire name.
            # A custom link on a native entity is c-prefixed on the wire
            # and (when captured as a link field) already a field target
            # — either candidate matching an existing target dedups the
            # side away (WTK-090 §3.3). Otherwise the natural name is
            # the wire name (custom entities store fields under natural
            # names; remaining native-entity links are native links).
            if yaml_link in existing or _c_prefixed(yaml_link) in existing:
                continue
            wire_name = yaml_link
            if (
                entity.entity_class == EntityClass.NATIVE
                and yaml_link != _c_prefixed(yaml_link)
                and rel.relation_name
            ):
                # manyToMany middle-table links on native entities are
                # custom-created and carry the c-prefix on the wire.
                wire_name = _c_prefixed(yaml_link)
            item.targets.append(ProfileTarget(
                api_name=wire_name,
                field_type=_relationship_side_type(rel.link_type, primary),
            ))

    return items


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
    """Q1 flag: rate strictly below threshold (0.05 exactly is not flagged)."""
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
        # Empty-string delta: non-NULL under the count-query
        # approximation but unpopulated under the strict predicate.
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
# The profiler
# ---------------------------------------------------------------------------

class DataProfiler:
    """Pass-2 data profiler over an EspoCRM source (WTK-096).

    Read-only by construction: every request goes through
    :meth:`EspoAdminClient.count_records` / :meth:`~EspoAdminClient.
    list_records`, both GET-only surfaces.

    :param client: Client connected to the source instance (the same
        connection pass 1 used).
    :param report: The pass-1 :class:`AuditReport` work-list source.
    :param options: Profiling options (thresholds, caps, throttle).
    :param callback: Progress callback for UI log lines.
    """

    def __init__(
        self,
        client: EspoAdminClient,
        report: AuditReport,
        options: ProfileOptions | None = None,
        callback: ProgressCallback | None = None,
    ) -> None:
        self._client = client
        self._report = report
        self._options = options or ProfileOptions()
        self._cb = callback or (lambda msg, color: None)
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

        Retries transport sentinels and 429/502/503/504 with 1/2/4/8 s
        backoff (5 attempts total); a larger ``Retry-After`` wins over
        the computed delay. A 401 anywhere raises the run tier.

        :param fn: Zero-arg callable issuing the request.
        :returns: The final (status, body); a status still in the
            retryable set means retries were exhausted.
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

    def run(self) -> UtilizationProfile:
        """Execute the profiling pass over the report's work-list.

        :returns: The :class:`UtilizationProfile`; ``data`` is ``None``
            only when the run aborted before any entity completed.
        """
        profiled_at = datetime.now(tz=UTC)
        work_list = build_work_list(self._report)
        entities_out: dict[str, dict[str, Any]] = {}
        consecutive_failures = 0
        aborted = False

        for index, item in enumerate(work_list):
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
                self._cb(
                    f"[AUDIT]    WARNING: profiling {item.espo_name} failed — {exc.note}",
                    "yellow",
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
                self._cb(f"[AUDIT]    ERROR: profiling aborted — {exc.note}", "red")
                aborted = True
                break

        if aborted and not entities_out:
            return UtilizationProfile(data=None, aborted=True)

        completed_at = datetime.now(tz=UTC)
        data = {
            "manifest_version": 1,
            "profiled_at": _format_utc(profiled_at),
            "completed_at": _format_utc(completed_at),
            "source_url": self._report.source_url,
            "source_label": self._source_label(),
            "profiler_version": _profiler_version(),
            "options": {
                "dormancy_window_days": self._options.dormancy_window_days,
                "low_population_threshold": self._options.low_population_threshold,
                "scan_cap": self._options.scan_cap,
            },
            "anomalies": self._anomalies,
            "entities": entities_out,
        }
        return UtilizationProfile(data=data, aborted=aborted)

    def _source_label(self) -> str:
        host = urlparse(self._report.source_url or "").netloc
        return f"espocrm @ {host or self._report.source_name}"

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

        # 1. record_count — also the entity-tier gate (and, on the first
        # entity of the run, the §7.2 precondition probe).
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
        record_count = total

        # 2. last_record_created_at — recency query, skipped when empty.
        last_record_created: datetime | None = None
        if record_count > 0:
            created = self._recency_query(espo, None)
            if created is not None:
                last_record_created = created

        field_metrics: dict[str, dict[str, Any]] = {}
        scan_fallback: dict[str, set[str]] = {}

        # 3–5. Count mode per field.
        for target in item.targets:
            field_metrics[target.api_name] = self._count_mode_field(
                espo, target, record_count, scan_fallback,
            )

        # 6. Scan pass — value inspection plus count→scan fallback (§4.4).
        scan_info = self._scan_entity(item, record_count, field_metrics, scan_fallback)

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
            detail["sample_fraction"] = scan_info["sample_fraction"]
            detail["sample_basis"] = "most_recent_by_created_at"

        entity_out: dict[str, Any] = {"record_count": record_count}
        if last_record_created is not None:
            entity_out["last_record_created_at"] = _format_utc(last_record_created)
        entity_out["detail"] = detail
        entity_out["fields"] = fields_out

        self._cb(
            f"[AUDIT]    Profiling {espo}: {record_count} records, "
            f"{len(item.targets)} fields",
            "white",
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
            # No records means no evidence about the field either way
            # (§3.3) — no queries; the entity-level empty flag carries
            # the finding.
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
            if record_count > 0:
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
            if distribution or not target.declared_options:
                metrics["value_distribution"] = distribution
        return metrics

    # -- scan pass ------------------------------------------------------

    def _scan_entity(
        self,
        item: EntityWorkItem,
        record_count: int,
        field_metrics: dict[str, dict[str, Any]],
        scan_fallback: dict[str, set[str]],
    ) -> dict[str, Any]:
        """Run the §4.4 paged scan and fold results into field metrics."""
        opts = self._options
        espo = item.espo_name
        scannable = [t for t in item.targets if select_attributes_for(t.api_name, t.field_type)]
        if not scannable or record_count == 0:
            return {"sampled": False}

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

        sampled = scanned < record_count
        complete_scan = not sampled and not truncated_by_error

        for target in scannable:
            stat = stats[target.api_name]
            metrics = field_metrics[target.api_name]
            fallbacks = scan_fallback.get(target.api_name, set())
            self._fold_scan_stats(target, stat, metrics, fallbacks, complete_scan, scanned)

        info: dict[str, Any] = {"sampled": sampled}
        if sampled:
            info["scan_count"] = scanned
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

        # §3.1 strict-predicate refinements — only a complete scan may
        # override exact count-mode numbers (a sample is a floor).
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
        """Shape one field's entry per the §6 contract rules."""
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
            out["last_populated_at"] = _format_utc(last_populated)
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

        if detail:
            out["detail"] = detail
        return out


def _profiler_version() -> str:
    """The espo_impl distribution version, for the profile header."""
    try:
        return importlib_metadata.version("crmbuilder")
    except importlib_metadata.PackageNotFoundError:
        return "unknown"
