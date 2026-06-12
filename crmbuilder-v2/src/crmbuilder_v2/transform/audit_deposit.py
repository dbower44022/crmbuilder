"""AuditReport-to-candidate deposit transform (WTK-090 design spec).

Carries a serialized V1 ``AuditReport`` manifest (``audit-report.json``,
spec §2.1) into the V2 requirements graph as **candidate** methodology
records with deposit-event provenance and utilization evidence:

* five candidate record types at ``candidate`` status — ``entity``,
  ``field`` (including relationship endpoints as ``reference`` fields),
  ``persona``, ``process``, ``manual_config`` (spec §3);
* one ``deposit_event`` of kind ``audit_deposit`` per source system per
  run, POSTed last, with ``deposit_event_wrote_record`` edges to every
  record the run created and an ``apply_context`` carrying source
  identity + snapshot timestamp (spec §4; required-key shape per the
  WTK-089 design spec §4.3, which supersedes this spec's lazy-payload
  sketch — the landed storage carries the ``deposit_event_kind``
  discriminator and an audit deposit has **no** close-out payload);
* one ``utilization_evidence`` row per candidate the run touched —
  created or matched (spec §5);
* one anomaly Planning Item per run summarizing everything unauditable
  or unmapped (spec §3.6) — created only when anomalies exist.

The plan/execute split keeps the mapping logic unit-testable without an
API: :func:`plan_deposit` is pure (manifest + optional profile +
:class:`ExistingState` in, deterministic :class:`DepositPlan` out);
:func:`execute_plan` drives the POSTs through a client object
implementing :class:`DepositClient`. The production client is
:class:`RestDepositClient` — a REST client of the live V2 API per the
TOP-013 record-creation principle, mirroring ``apply_close_out.py``
(envelope unwrapping, ``X-Engagement`` header, read-then-write
deposit-event identifier for the log-file path).

Idempotency (spec §7): matching is by the natural name keys the
repositories enforce uniqueness on. Matched records are never touched —
no create, no field update, no status transition; the run appends an
evidence row and moves on. The transform never issues a PATCH, PUT, or
DELETE through any client path.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import sys
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from pathlib import Path
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from crmbuilder_v2 import __version__ as _TRANSFORM_VERSION
from crmbuilder_v2.access.evidence_projection import (
    EVIDENCE_FLAG_KEYS,
    project_evidence_object,
)
from crmbuilder_v2.transform.normalize import (
    FALLBACK_FIELD_TYPE as _FALLBACK_FIELD_TYPE,
)
from crmbuilder_v2.transform.normalize import composed_type_map

MANIFEST_VERSION = 1
# Default when the manifest carries no `source_system` key (WTK-110
# §2.4 delta D1) — every pre-D1 manifest is an EspoCRM serialization.
SOURCE_SYSTEM = "espocrm"

# Version of the WTK-097 §4 evidence_detail key schema this transform
# emits; the discriminator consumers branch on when the detail shape
# evolves (§7.3).
EVIDENCE_SCHEMA_VERSION = 1

# EspoCRM metadata wire type -> FIELD_TYPES vocab (spec §3.2) — the
# WTK-102 espocrm stage-1 table composed with the fixed stage-2
# projection (normalize.py), pinned behavior-identical to the
# previously inline map by the N3 composition test. Lossy by design —
# the wire type always survives in notes and evidence detail.
# Module-level for the default system only; `plan_deposit` selects
# `composed_type_map(source_system)` per run (WTK-110 §2.4 delta D1).
WIRE_TYPE_MAP: dict[str, str] = composed_type_map(SOURCE_SYSTEM)
_LINK_WIRE_TYPES = frozenset({"link", "linkParent", "linkMultiple", "linkOne"})

# EspoCRM base entity type -> ENTITY_KINDS vocab (spec §3.1). Anything
# else stays unclassified (kind omitted per entity.md v1.1 §3.2.3).
ENTITY_KIND_MAP: dict[str, str] = {
    "Person": "person",
    "Company": "organization",
    "Event": "event",
}

_LOG_DIR = "PRDs/product/crmbuilder-v2/deposit-event-logs"


# ---------------------------------------------------------------------------
# Inputs — manifest, profile, source identity (spec §2)
# ---------------------------------------------------------------------------


def load_manifest(path: str | Path) -> dict:
    """Load and version-check an ``audit-report.json`` manifest (§2.1)."""
    with Path(path).open(encoding="utf-8") as fh:
        manifest = json.load(fh)
    version = manifest.get("manifest_version")
    if version != MANIFEST_VERSION:
        raise ValueError(
            f"unsupported manifest_version {version!r} "
            f"(expected {MANIFEST_VERSION})"
        )
    return manifest


def load_profile(path: str | Path | None) -> dict | None:
    """Load the optional ``utilization-profile.json`` (§2.2)."""
    if path is None:
        return None
    with Path(path).open(encoding="utf-8") as fh:
        profile = json.load(fh)
    version = profile.get("manifest_version")
    if version != MANIFEST_VERSION:
        raise ValueError(
            f"unsupported profile manifest_version {version!r} "
            f"(expected {MANIFEST_VERSION})"
        )
    return profile


def derive_source_label(manifest: dict) -> str:
    """``{product} @ {host}`` per §2.3, e.g. ``espocrm @ crm.cbmentors.org``.

    A ``file://`` URI has an empty netloc; the label uses the URL
    path's basename instead (WTK-110 §2.4 delta D2), e.g.
    ``spreadsheet @ cbm-mentor-tracking.xlsx``.
    """
    source_system = manifest.get("source_system") or SOURCE_SYSTEM
    split = urllib_parse.urlsplit(manifest.get("source_url") or "")
    host = split.netloc
    if not host:
        host = posixpath.basename(urllib_parse.unquote(split.path).rstrip("/"))
    return f"{source_system} @ {host or 'unknown'}"


# ---------------------------------------------------------------------------
# Existing state — the idempotency pre-read (spec §6/§7)
# ---------------------------------------------------------------------------


@dataclass
class ExistingRecord:
    """One pre-existing record relevant to natural-key matching."""

    identifier: str
    name: str
    deleted: bool


@dataclass
class ExistingState:
    """Name-keyed snapshot of the records the natural keys match against.

    Keys are lowercased names (the repositories' case-insensitive
    uniqueness rule); fields are keyed by ``(parent_entity_identifier,
    lowercased field name)``. Live rows win over soft-deleted rows when
    both carry a name (possible because uniqueness is live-scoped).
    """

    entities: dict[str, ExistingRecord] = dataclass_field(default_factory=dict)
    fields: dict[tuple[str, str], ExistingRecord] = dataclass_field(
        default_factory=dict
    )
    personas: dict[str, ExistingRecord] = dataclass_field(default_factory=dict)
    processes: dict[str, ExistingRecord] = dataclass_field(default_factory=dict)
    manual_configs: dict[str, ExistingRecord] = dataclass_field(
        default_factory=dict
    )
    domains: dict[str, ExistingRecord] = dataclass_field(default_factory=dict)


def _index_named(
    rows: list[dict], *, identifier_key: str, name_key: str, deleted_key: str
) -> dict[str, ExistingRecord]:
    index: dict[str, ExistingRecord] = {}
    for row in rows:
        record = ExistingRecord(
            identifier=row[identifier_key],
            name=row[name_key],
            deleted=row.get(deleted_key) is not None,
        )
        key = record.name.strip().lower()
        current = index.get(key)
        if current is None or (current.deleted and not record.deleted):
            index[key] = record
    return index


def fetch_existing_state(client: DepositClient) -> ExistingState:
    """Run the GET pre-reads and build the natural-key indexes."""
    state = ExistingState(
        entities=_index_named(
            client.list_entities(),
            identifier_key="entity_identifier",
            name_key="entity_name",
            deleted_key="entity_deleted_at",
        ),
        personas=_index_named(
            client.list_personas(),
            identifier_key="persona_identifier",
            name_key="persona_name",
            deleted_key="persona_deleted_at",
        ),
        processes=_index_named(
            client.list_processes(),
            identifier_key="process_identifier",
            name_key="process_name",
            deleted_key="process_deleted_at",
        ),
        manual_configs=_index_named(
            client.list_manual_configs(),
            identifier_key="manual_config_identifier",
            name_key="manual_config_name",
            deleted_key="manual_config_deleted_at",
        ),
        domains=_index_named(
            client.list_domains(),
            identifier_key="domain_identifier",
            name_key="domain_name",
            deleted_key="domain_deleted_at",
        ),
    )
    for row in client.list_fields_with_parents():
        parent = row.get("parent_entity_identifier")
        if parent is None:
            continue
        record = ExistingRecord(
            identifier=row["field_identifier"],
            name=row["field_name"],
            deleted=row.get("field_deleted_at") is not None,
        )
        key = (parent, record.name.strip().lower())
        current = state.fields.get(key)
        if current is None or (current.deleted and not record.deleted):
            state.fields[key] = record
    return state


# ---------------------------------------------------------------------------
# The plan (spec §3 mapping + §7 idempotency diff)
# ---------------------------------------------------------------------------


@dataclass
class PlannedCreate:
    """One record the run will create, with its evidence payload.

    ``key`` is the natural-key rendering used to resolve server-assigned
    identifiers at execute time (entity/persona/process/manual_config/
    domain: lowercased name; field: ``(parent entity key, lowercased
    name)`` flattened to ``"<entity key>/<name>"``).
    ``parent_entity_key`` (fields only) names the parent entity by its
    lowercased mapped name; execute resolves it against matched + newly
    created entities. ``evidence`` is the evidence-row payload minus the
    subject identifier and deposit-event identifier, both resolved at
    execute time. The anomaly Planning Item carries no evidence
    (governance, not methodology).
    """

    record_type: str
    key: str
    payload: dict
    parent_entity_key: str | None = None
    evidence: dict | None = None


@dataclass
class PlannedMatch:
    """One record matched by natural key — never touched, evidence only."""

    record_type: str
    identifier: str
    key: str
    evidence: dict


@dataclass
class DepositPlan:
    """Deterministic output of :func:`plan_deposit` (spec §6)."""

    source_label: str
    snapshot_at: str
    profiled_at: str
    apply_context: dict
    creates: list[PlannedCreate]
    matches: list[PlannedMatch]
    skipped_soft_deleted: list[dict]
    anomalies: list[str]

    def records_summary(self) -> dict:
        """Counts by capture type, non-zero keys only (T3: ``{}`` on a
        pure re-observation run)."""
        plural = {
            "entity": "entities",
            "field": "fields",
            "persona": "personas",
            "process": "processes",
            "manual_config": "manual_configs",
            "domain": "domains",
            "planning_item": "planning_items",
        }
        summary: dict[str, int] = {}
        for create in self.creates:
            key = plural[create.record_type]
            summary[key] = summary.get(key, 0) + 1
        return summary


def plan_evidence_object(
    evidence: dict,
    *,
    profiled_at: str,
    source_label: str,
    subject_identifier: str | None = None,
    deposit_event: str | None = None,
) -> dict:
    """Render one planned evidence payload as the §3 inline object.

    Builds the pseudo-row the evidence write will produce and runs it
    through the same assembler every read surface uses — WTK-097 §3.4
    determinism, acceptance criterion A8 (plan/read parity). The two
    execute-time-resolved envelope values default to ``None`` at plan
    time: a create's ``subject_identifier`` is server-assigned, and the
    ``deposit_event`` identifier is read just before the event POST.
    """
    row = {
        f"evidence_{key}": value
        for key, value in evidence.items()
        if key != "detail"
    }
    row["evidence_detail"] = evidence.get("detail")
    row["evidence_subject_identifier"] = subject_identifier
    row["evidence_profiled_at"] = profiled_at
    row["evidence_source_label"] = source_label
    row["evidence_deposit_event_identifier"] = deposit_event
    return project_evidence_object(row)


def _source_block(pairs: list[tuple[str, object]]) -> str:
    """Render the ``Source:`` notes block (spec §3 general rules)."""
    lines = ["Source:"]
    for key, value in pairs:
        rendered = json.dumps(value, sort_keys=True) if isinstance(
            value, (dict, list)
        ) else value
        lines.append(f"  {key}: {rendered}")
    return "\n".join(lines)


def _synth_description(source_label: str, source_text: str | None = None) -> str:
    """Deterministic description per the spec §3 general rule."""
    synthesized = f"Discovered by audit of {source_label}."
    if source_text and source_text.strip():
        return f"{source_text.strip()} {synthesized}"
    return synthesized


def _render_filter_oneline(filter_ast: object) -> str:
    if filter_ast is None:
        return "(unrecoverable)"
    return json.dumps(filter_ast, sort_keys=True)


def _entity_in_scope(entity: dict) -> bool:
    """Spec §3.1 scope: custom always; native only when the audit
    captured custom fields or filtered tabs on it; system never."""
    entity_class = entity.get("entity_class")
    if entity_class == "custom":
        return True
    if entity_class == "native":
        return bool(_fields_in_scope(entity)) or bool(
            entity.get("filtered_tabs") or []
        )
    return False


def _fields_in_scope(entity: dict) -> list[dict]:
    """Spec §3.2 scope: custom fields only. A per-field ``field_class``
    of anything but ``custom`` skips the field; absent class means the
    audit's own scope rules already filtered to custom."""
    return [
        f
        for f in entity.get("fields") or []
        if f.get("field_class") in (None, "custom")
    ]


def _entity_name(entity: dict) -> str:
    return (entity.get("label_singular") or entity["yaml_name"]).strip()


def _field_name(field_result: dict) -> str:
    return (field_result.get("label") or field_result["yaml_name"]).strip()


def _profile_entity(profile: dict | None, espo_name: str) -> dict:
    if not profile:
        return {}
    return (profile.get("entities") or {}).get(espo_name) or {}


def _profile_field(profile_entity: dict, field_result: dict) -> dict:
    fields = profile_entity.get("fields") or {}
    return (
        fields.get(field_result.get("api_name"))
        or fields.get(field_result.get("yaml_name"))
        or {}
    )


def plan_deposit(
    manifest: dict, profile: dict | None, existing: ExistingState
) -> DepositPlan:
    """Map the manifest to the candidate set and diff it against
    ``existing`` (spec §3 + §7). Pure and deterministic: write order is
    dependency tiers, alphabetical within a tier."""
    source_label = derive_source_label(manifest)
    # WTK-110 §2.4 delta D1: optional manifest `source_system` selects
    # the composed type map per run; absent -> espocrm (every pre-D1
    # manifest is an EspoCRM serialization).
    source_system = manifest.get("source_system") or SOURCE_SYSTEM
    wire_type_map = composed_type_map(source_system)
    snapshot_at = manifest.get("timestamp") or ""
    profiled_at = (profile or {}).get("profiled_at") or snapshot_at
    profiler_version = (profile or {}).get("profiler_version")
    profile_options = (profile or {}).get("options") or {}
    # The profiler options the flags were derived under (WTK-096 §5) —
    # they travel with the flags so re-derivation is always possible
    # from the row alone (WTK-097 §4.1).
    thresholds = {
        key: profile_options[key]
        for key in ("dormancy_window_days", "low_population_threshold")
        if key in profile_options
    }

    def evidence_detail(wire_name: object, **keys: object) -> dict:
        """Assemble one §4-conformant ``evidence_detail`` block.

        Starts from the WTK-097 §4.1 common keys, adds the caller's
        subject-specific keys (omitted when ``None`` — the
        omitted-not-null convention; profile detail blocks are passed
        through verbatim, flags included, never recomputed), then
        finishes with ``thresholds`` when the block carries flags and
        ``schema_only: true`` on a profile-less run.
        """
        detail: dict = {
            "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
            "wire_name": wire_name,
            "transform_version": _TRANSFORM_VERSION,
        }
        if profiler_version is not None:
            detail["profiler_version"] = profiler_version
        if profile is None:
            detail["schema_only"] = True
        for key, value in keys.items():
            if value is not None:
                detail[key] = value
        if thresholds and any(key in detail for key in EVIDENCE_FLAG_KEYS):
            detail["thresholds"] = thresholds
        return detail

    anomalies: list[str] = []
    skipped: list[dict] = []
    creates: list[PlannedCreate] = []
    matches: list[PlannedMatch] = []

    for line in manifest.get("errors") or []:
        anomalies.append(f"audit error: {line}")
    for line in manifest.get("warnings") or []:
        anomalies.append(f"audit warning: {line}")

    def diff(
        record_type: str,
        index: dict[str, ExistingRecord],
        name: str,
        payload: dict,
        evidence: dict,
        *,
        parent_entity_key: str | None = None,
        field_parent_identifier: str | None = None,
    ) -> ExistingRecord | None:
        """Apply the §7 re-run rules to one mapped record. Returns the
        matched record (or None when a create was planned)."""
        # Negative numeric metrics are profiler count-probe sentinels
        # ("unknown"); evidence semantics for unknown is NULL, and the
        # API rejects negatives by design. Clamp once for every subject
        # type rather than per metric key.
        for key, value in list(evidence.items()):
            if key != "detail" and isinstance(value, (int, float)) and value < 0:
                evidence[key] = None
        if record_type == "field":
            key = (field_parent_identifier or "", name.lower())
            match = existing.fields.get(key) if field_parent_identifier else None
        else:
            match = index.get(name.lower())
        if match is not None and match.deleted:
            # Rule 3: soft-deleted match -> skip + anomaly, no evidence.
            skipped.append(
                {
                    "record_type": record_type,
                    "identifier": match.identifier,
                    "name": name,
                }
            )
            anomalies.append(
                f"soft-deleted match skipped: {record_type} {match.identifier} "
                f"({name!r}); restore it, or rename/delete it so the next "
                "run creates fresh"
            )
            return match
        if match is not None:
            # Rule 1: matched -> never touched; evidence only.
            matches.append(
                PlannedMatch(
                    record_type=record_type,
                    identifier=match.identifier,
                    key=name.lower(),
                    evidence=evidence,
                )
            )
            return match
        # Rule 2: missing -> created at candidate.
        key_render = (
            f"{parent_entity_key}/{name.lower()}"
            if record_type == "field"
            else name.lower()
        )
        creates.append(
            PlannedCreate(
                record_type=record_type,
                key=key_render,
                payload=payload,
                parent_entity_key=parent_entity_key,
                evidence=evidence,
            )
        )
        return None

    # ---- entities + their fields (tiers 2 and 3) --------------------------
    in_scope = [e for e in manifest.get("entities") or [] if _entity_in_scope(e)]
    in_scope.sort(key=lambda e: _entity_name(e).lower())

    # Wire-name lookup for relationship sides (§3.3): both yaml and espo
    # names of every in-scope entity resolve to its mapped name key.
    entity_key_by_wire: dict[str, str] = {}
    # Wire link names already consumed per entity, for the §3.3 dedup.
    consumed_links: dict[str, set[str]] = {}
    entity_class_by_key: dict[str, str] = {}

    field_plans: list[tuple[dict, dict]] = []  # (entity, field_result)
    for entity in in_scope:
        name = _entity_name(entity)
        key = name.lower()
        entity_key_by_wire[entity.get("yaml_name", "")] = key
        entity_key_by_wire[entity.get("espo_name", "")] = key
        entity_class_by_key[key] = entity.get("entity_class") or "custom"
        profile_entity = _profile_entity(profile, entity.get("espo_name", ""))

        kind = ENTITY_KIND_MAP.get(entity.get("entity_type") or "")
        description = _synth_description(source_label)
        label_plural = entity.get("label_plural")
        if label_plural:
            description = (
                f"{description} Plural label in the source: {label_plural}."
            )
        layouts_captured = sorted(
            layout.get("layout_type", "")
            for layout in entity.get("layouts") or []
        )
        payload = {
            "name": name,
            "description": description,
            "notes": _source_block(
                [
                    ("espo_name", entity.get("espo_name")),
                    ("yaml_name", entity.get("yaml_name")),
                    ("entity_type", entity.get("entity_type")),
                    ("entity_class", entity.get("entity_class")),
                    ("stream", entity.get("stream", False)),
                ]
            ),
            "status": "candidate",
        }
        if kind is not None:
            payload["kind"] = kind
        evidence = {
            "subject_type": "entity",
            "catalog_class": (
                "custom" if entity.get("entity_class") == "custom" else "standard"
            ),
            "record_count": profile_entity.get("record_count"),
            "last_record_created_at": profile_entity.get(
                "last_record_created_at"
            ),
            # §4.2 keys: the entity flags, sampling qualifiers, and
            # profiled_entity_at arrive verbatim in the profile's
            # entity detail block (§3.3 — flags copied, not computed).
            "detail": evidence_detail(
                entity.get("espo_name"),
                yaml_name=entity.get("yaml_name"),
                layouts_captured=layouts_captured,
                **(profile_entity.get("detail") or {}),
            ),
        }
        diff("entity", existing.entities, name, payload, evidence)

        for field_result in sorted(
            _fields_in_scope(entity), key=lambda f: _field_name(f).lower()
        ):
            field_plans.append((entity, field_result))

    # ---- relationship sides as reference fields (§3.3) --------------------
    relationship_fields: list[tuple[str, dict, dict]] = []
    for rel in manifest.get("relationships") or []:
        sides = (
            (
                rel.get("audited"),
                rel.get("entity"),
                rel.get("label"),
                rel.get("link"),
                rel.get("entity_foreign"),
                rel.get("link_foreign"),
            ),
            (
                rel.get("audited_foreign"),
                rel.get("entity_foreign"),
                rel.get("label_foreign"),
                rel.get("link_foreign"),
                rel.get("entity"),
                rel.get("link"),
            ),
        )
        for audited, wire_entity, label, link, other_entity, other_link in sides:
            if not audited or not link:
                continue
            entity_key = entity_key_by_wire.get(wire_entity or "")
            if entity_key is None:
                continue  # side's entity skipped (§3.1) -> side skipped
            consumed_links.setdefault(entity_key, set()).add(link)
            name = (label or link).strip()
            notes = _source_block(
                [
                    ("relationship", rel.get("name")),
                    ("link_type", rel.get("link_type")),
                    ("link", link),
                    ("entity_foreign", other_entity),
                    ("relation_name", rel.get("relation_name")),
                ]
            )
            payload = {
                "name": name,
                "description": _synth_description(source_label),
                "type": "reference",
                "required": False,
                "notes": notes,
                "status": "candidate",
            }
            evidence = {
                "subject_type": "field",
                "catalog_class": (
                    "custom"
                    if entity_class_by_key.get(entity_key) == "custom"
                    else "standard"
                ),
                # §4.3 relationship_pairing — the opposite side's wire
                # identity. No wire_type: a RelationshipAuditResult
                # carries the relationship's link_type, not the side's
                # metadata field type.
                "detail": evidence_detail(
                    link,
                    relationship_pairing={
                        "relationship": rel.get("name"),
                        "link_type": rel.get("link_type"),
                        "entity": other_entity,
                        "link": other_link,
                    },
                ),
            }
            relationship_fields.append((entity_key, payload, evidence))

    # ---- plain fields, deduped against consumed links (§3.3) --------------
    for entity, field_result in field_plans:
        entity_key = _entity_name(entity).lower()
        wire_type = field_result.get("field_type") or ""
        if (
            wire_type in _LINK_WIRE_TYPES
            and field_result.get("yaml_name")
            in consumed_links.get(entity_key, set())
        ):
            continue  # the relationship mapping wins
        name = _field_name(field_result)
        field_type = wire_type_map.get(wire_type)
        if field_type is None:
            field_type = _FALLBACK_FIELD_TYPE
            anomalies.append(
                f"unmapped wire type {wire_type!r} on "
                f"{entity.get('espo_name')}.{field_result.get('yaml_name')}; "
                f"mapped to {_FALLBACK_FIELD_TYPE!r}"
            )
        properties = field_result.get("properties") or {}
        options = properties.get("options")
        profile_field = _profile_field(
            _profile_entity(profile, entity.get("espo_name", "")), field_result
        )
        notes_pairs: list[tuple[str, object]] = [
            ("yaml_name", field_result.get("yaml_name")),
            ("api_name", field_result.get("api_name")),
            ("field_type", wire_type),
        ]
        for prop in ("options", "default"):
            if prop in properties:
                notes_pairs.append((prop, properties[prop]))
        payload = {
            "name": name,
            "description": _synth_description(source_label),
            "type": field_type,
            "required": bool(properties.get("required", False)),
            "notes": _source_block(notes_pairs),
            "status": "candidate",
        }
        evidence = {
            "subject_type": "field",
            "catalog_class": (
                "custom"
                if (field_result.get("field_class") or "custom") == "custom"
                else "standard"
            ),
            "populated_count": profile_field.get("populated_count"),
            "population_rate": profile_field.get("population_rate"),
            "last_populated_at": profile_field.get("last_populated_at"),
            "distinct_value_count": profile_field.get("distinct_value_count"),
            "declared_option_count": (
                len(options) if isinstance(options, list) else None
            ),
            "used_option_count": profile_field.get("used_option_count"),
            # §4.3 keys (value_distribution, undeclared_values,
            # top_values, last_populated_at_basis, empty_string_count,
            # distinct_overflow, and the field flags) arrive verbatim
            # in the profile's per-field detail block.
            "detail": evidence_detail(
                field_result.get("api_name"),
                yaml_name=field_result.get("yaml_name"),
                wire_type=wire_type,
                **(profile_field.get("detail") or {}),
            ),
        }
        relationship_fields.append((entity_key, payload, evidence))

    # Diff all field candidates in deterministic order (entity key, name).
    for entity_key, payload, evidence in sorted(
        relationship_fields, key=lambda item: (item[0], item[1]["name"].lower())
    ):
        parent = existing.entities.get(entity_key)
        parent_identifier = (
            parent.identifier if parent is not None and not parent.deleted else None
        )
        diff(
            "field",
            {},
            payload["name"],
            payload,
            evidence,
            parent_entity_key=entity_key,
            field_parent_identifier=parent_identifier,
        )

    # ---- personas (§3.4): roles + teams, merged by name --------------------
    persona_sources: dict[str, list[dict]] = {}
    for role in manifest.get("roles") or []:
        persona_sources.setdefault(role["name"].strip().lower(), []).append(
            {"kind": "role", **role}
        )
    for team in manifest.get("teams") or []:
        persona_sources.setdefault(team["name"].strip().lower(), []).append(
            {"kind": "team", **team}
        )
    for key in sorted(persona_sources):
        sources = persona_sources[key]
        primary = sources[0]
        name = primary["name"].strip()
        description = next(
            (s.get("description") for s in sources if s.get("description")), None
        )
        if description:
            role_summary = description
        elif primary["kind"] == "role":
            role_summary = f"Role discovered in {source_label}."
        else:
            role_summary = f"Team discovered in {source_label}."
        notes_pairs: list[tuple[str, object]] = [
            ("kinds", sorted({s["kind"] for s in sources}))
        ]
        for source in sources:
            if source["kind"] == "role":
                if source.get("scope_access"):
                    notes_pairs.append(("scope_access", source["scope_access"]))
                if source.get("system_permissions"):
                    notes_pairs.append(
                        ("system_permissions", source["system_permissions"])
                    )
        payload = {
            "name": name,
            "role_summary": role_summary,
            "notes": _source_block(notes_pairs),
            "status": "candidate",
        }
        kinds = sorted({s["kind"] for s in sources})
        evidence = {
            "subject_type": "persona",
            # §4.4 persona keys; ``kind`` is the primary source's
            # (role wins a role+team name merge), ``kinds`` the merged
            # set (a permitted additional key).
            "detail": evidence_detail(
                name,
                kind="role" if "role" in kinds else "team",
                kinds=kinds,
                scope_access=next(
                    (
                        s.get("scope_access")
                        for s in sources
                        if s.get("scope_access")
                    ),
                    None,
                ),
                system_permissions=next(
                    (
                        s.get("system_permissions")
                        for s in sources
                        if s.get("system_permissions")
                    ),
                    None,
                ),
            ),
        }
        diff("persona", existing.personas, name, payload, evidence)

    # ---- processes + null-filter manual_configs (§3.5) ---------------------
    placeholder_name = f"Baseline: {source_label}"
    process_plans: list[tuple[str, dict, dict]] = []
    manual_config_plans: list[tuple[str, dict, dict]] = []
    for entity in in_scope:
        entity_name = _entity_name(entity)
        for tab in entity.get("filtered_tabs") or []:
            tab_name = (tab.get("label") or tab.get("scope") or "").strip()
            filter_ast = tab.get("filter")
            purpose = (
                f"Filtered navigation tab over {entity_name} discovered in "
                f"{source_label}; filter: {_render_filter_oneline(filter_ast)}."
            )
            notes = _source_block(
                [
                    ("id", tab.get("id")),
                    ("scope", tab.get("scope")),
                    ("acl", tab.get("acl")),
                    ("nav_order", tab.get("nav_order")),
                    ("filter", filter_ast),
                ]
            )
            payload = {
                "name": tab_name,
                "purpose": purpose,
                "classification": "unclassified",
                "notes": notes,
            }
            # §4.4 process keys; ``filter`` is included even when null
            # (null IS the unrecoverable marker).
            process_detail = evidence_detail(
                tab.get("id"),
                scope=tab.get("scope"),
                acl=tab.get("acl"),
                nav_order=tab.get("nav_order"),
                entity=entity_name,
            )
            process_detail["filter"] = filter_ast
            evidence = {
                "subject_type": "process",
                "detail": process_detail,
            }
            process_plans.append((tab_name, payload, evidence))
            if filter_ast is None:
                mc_name = f"Recreate filter: {tab_name}"
                related_warnings = [
                    line
                    for line in manifest.get("warnings") or []
                    if (tab.get("scope") and tab["scope"] in line)
                    or (tab.get("id") and tab["id"] in line)
                ]
                instructions = (
                    f"The audit could not recover the filter for tab "
                    f"{tab_name!r} (scope {tab.get('scope')}, id "
                    f"{tab.get('id')}); recreate it manually on the target."
                )
                if related_warnings:
                    instructions = (
                        instructions
                        + " Audit warnings: "
                        + " | ".join(related_warnings)
                    )
                mc_payload = {
                    "name": mc_name,
                    "category": "saved_view",
                    "description": _synth_description(source_label),
                    "instructions": instructions,
                    "status": "candidate",
                }
                mc_evidence = {
                    "subject_type": "manual_config",
                    "detail": evidence_detail(
                        tab.get("id"),
                        origin="unrecoverable_filter",
                        tab_scope=tab.get("scope"),
                        tab_id=tab.get("id"),
                    ),
                }
                manual_config_plans.append((mc_name, mc_payload, mc_evidence))

    # The placeholder domain exists only when a process create needs it
    # (§4.4) — matched processes already live under their domain, and a
    # soft-deleted process match creates nothing (rule 3).
    needs_placeholder = any(
        existing.processes.get(key.strip().lower()) is None
        for key, _, _ in process_plans
    )
    if needs_placeholder:
        placeholder_match = existing.domains.get(placeholder_name.lower())
        if placeholder_match is None:
            creates.insert(
                0,
                PlannedCreate(
                    record_type="domain",
                    key=placeholder_name.lower(),
                    payload={
                        "name": placeholder_name,
                        "purpose": (
                            "Mechanical container for baseline process "
                            "candidates pending Phase 3 triage re-homing."
                        ),
                        "description": _synth_description(source_label),
                        "status": "candidate",
                    },
                ),
            )
        elif placeholder_match.deleted:
            anomalies.append(
                f"soft-deleted match skipped: domain "
                f"{placeholder_match.identifier} ({placeholder_name!r}); "
                "restore it or remove it so process candidates can be homed"
            )
            skipped.append(
                {
                    "record_type": "domain",
                    "identifier": placeholder_match.identifier,
                    "name": placeholder_name,
                }
            )

    for tab_name, payload, evidence in sorted(
        process_plans, key=lambda item: item[0].lower()
    ):
        payload = dict(payload)
        payload["domain_key"] = placeholder_name.lower()
        diff("process", existing.processes, tab_name, payload, evidence)
    for mc_name, payload, evidence in sorted(
        manual_config_plans, key=lambda item: item[0].lower()
    ):
        diff("manual_config", existing.manual_configs, mc_name, payload, evidence)

    # ---- anomaly Planning Item (§3.6) --------------------------------------
    if anomalies:
        description_lines = [
            f"Anomalies from the audit baseline deposit of {source_label} "
            f"(snapshot {snapshot_at}):",
            "",
        ]
        description_lines.extend(f"- {line}" for line in anomalies)
        creates.append(
            PlannedCreate(
                record_type="planning_item",
                key=f"anomalies/{source_label}",
                payload={
                    "title": f"Audit anomalies: {source_label}",
                    "item_type": "pending_work",
                    "status": "Draft",
                    "description": "\n".join(description_lines),
                    "executive_summary": (
                        f"The audit baseline deposit of {source_label} logged "
                        f"{len(anomalies)} anomaly item(s) needing operator "
                        "review: unauditable or unmapped source structures "
                        "recorded per Master CRMBuilder PRD section 7 — "
                        "nothing is silently dropped. Each entry names its "
                        "source object. Resolve by extending the transform's "
                        "wire-type map, restoring or renaming soft-deleted "
                        "twins, or hand-recreating unrecoverable filters, "
                        "then re-run the deposit to converge."
                    ),
                },
            )
        )

    apply_context = {
        # WTK-089 §4.3 required keys (validated by create_deposit_event).
        "source_system": source_system,
        "source_instance": manifest.get("source_url"),
        "snapshot_at": snapshot_at,
        # WTK-090 §4.3 diagnostic depth.
        "kind": "audit_baseline_deposit",
        "source_name": manifest.get("source_name"),
        "source_label": source_label,
        "profiled_at": (profile or {}).get("profiled_at"),
        "manifest_version": MANIFEST_VERSION,
        "transform_version": _TRANSFORM_VERSION,
    }
    return DepositPlan(
        source_label=source_label,
        snapshot_at=snapshot_at,
        profiled_at=profiled_at,
        apply_context=apply_context,
        creates=creates,
        matches=matches,
        skipped_soft_deleted=skipped,
        anomalies=anomalies,
    )


# ---------------------------------------------------------------------------
# Execution (spec §6 write path, §7 write order, §4.3 failure semantics)
# ---------------------------------------------------------------------------


class DepositClient:
    """Protocol the execute path drives. ``RestDepositClient`` is the
    production implementation; tests supply an access-layer-backed fake.

    Every ``create_*`` method returns the created record dict (the
    unwrapped ``data`` payload). The transform never calls a mutating
    method other than these creates.
    """

    def list_entities(self) -> list[dict]:
        raise NotImplementedError

    def list_fields_with_parents(self) -> list[dict]:
        """Field rows each carrying ``parent_entity_identifier`` (live
        ``field_belongs_to_entity`` edge, or the stash column for
        soft-deleted rows)."""
        raise NotImplementedError

    def list_personas(self) -> list[dict]:
        raise NotImplementedError

    def list_processes(self) -> list[dict]:
        raise NotImplementedError

    def list_manual_configs(self) -> list[dict]:
        raise NotImplementedError

    def list_domains(self) -> list[dict]:
        raise NotImplementedError

    def next_deposit_event_identifier(self) -> str:
        raise NotImplementedError

    def create_entity(self, **payload) -> dict:
        raise NotImplementedError

    def create_field(self, **payload) -> dict:
        raise NotImplementedError

    def create_persona(self, **payload) -> dict:
        raise NotImplementedError

    def create_process(self, **payload) -> dict:
        raise NotImplementedError

    def create_manual_config(self, **payload) -> dict:
        raise NotImplementedError

    def create_domain(self, **payload) -> dict:
        raise NotImplementedError

    def create_planning_item(self, **payload) -> dict:
        raise NotImplementedError

    def create_deposit_event(self, **payload) -> dict:
        raise NotImplementedError

    def create_utilization_evidence(self, **payload) -> dict:
        raise NotImplementedError


_IDENTIFIER_KEYS = {
    "entity": "entity_identifier",
    "field": "field_identifier",
    "persona": "persona_identifier",
    "process": "process_identifier",
    "manual_config": "manual_config_identifier",
    "domain": "domain_identifier",
    "planning_item": "identifier",
}


def execute_plan(plan: DepositPlan, client: DepositClient) -> dict:
    """Run the plan's POSTs in the §7 write order.

    Each POST is its own transaction; the run is resumable, not atomic.
    On a mid-run failure the deposit event is still POSTed with outcome
    ``failure``, ``error_info``, and ``wrote_record`` edges covering
    exactly the records that landed (truthful provenance, §4.3); the
    original error then re-raises. Evidence rows are POSTed after the
    event (they reference it) and only on a success run.

    Returns a summary dict: ``deposit_event_identifier``, ``created``
    (list of ``{record_type, identifier, key}``), ``matched`` count,
    ``evidence_rows``, ``records_summary``.
    """
    created: list[dict] = []
    resolved_entities: dict[str, str] = {
        record.key: record.identifier
        for record in plan.matches
        if record.record_type == "entity"
    }
    resolved_domains: dict[str, str] = {}
    error_info: dict | None = None

    creators = {
        "entity": client.create_entity,
        "field": client.create_field,
        "persona": client.create_persona,
        "process": client.create_process,
        "manual_config": client.create_manual_config,
        "domain": client.create_domain,
        "planning_item": client.create_planning_item,
    }

    pending = list(plan.creates)
    try:
        for item in pending:
            payload = dict(item.payload)
            if item.record_type == "field":
                parent_identifier = resolved_entities.get(
                    item.parent_entity_key or ""
                )
                if parent_identifier is None:
                    raise RuntimeError(
                        "unresolved parent entity for field "
                        f"{item.key!r} (key {item.parent_entity_key!r})"
                    )
                payload["field_belongs_to_entity_identifier"] = parent_identifier
            if item.record_type == "process":
                domain_key = payload.pop("domain_key")
                domain_identifier = resolved_domains.get(domain_key)
                if domain_identifier is None:
                    match = None
                    # A matched placeholder from a prior run is in the
                    # existing domains the planner saw; the plan carries
                    # no create for it, so resolve through the client.
                    for row in client.list_domains():
                        if (
                            row.get("domain_deleted_at") is None
                            and row["domain_name"].strip().lower() == domain_key
                        ):
                            match = row["domain_identifier"]
                            break
                    if match is None:
                        raise RuntimeError(
                            f"unresolved baseline domain {domain_key!r}"
                        )
                    domain_identifier = match
                    resolved_domains[domain_key] = domain_identifier
                payload["domain_identifier"] = domain_identifier
            record = creators[item.record_type](**payload)
            identifier = record[_IDENTIFIER_KEYS[item.record_type]]
            created.append(
                {
                    "record_type": item.record_type,
                    "identifier": identifier,
                    "key": item.key,
                }
            )
            if item.record_type == "entity":
                resolved_entities[item.key] = identifier
            if item.record_type == "domain":
                resolved_domains[item.key] = identifier
    except Exception as exc:  # noqa: BLE001 — captured into error_info, re-raised after the failure event
        error_info = {
            "error": str(exc),
            "failed_after_records": len(created),
            "planned_records": len(pending),
        }

    # The deposit event is POSTed regardless of outcome — wrote_record
    # edges cover exactly the records that landed (§4.3).
    dep_identifier = client.next_deposit_event_identifier()
    log_file_path = f"{_LOG_DIR}/{dep_identifier.lower().replace('-', '_')}.log"
    records_summary: dict[str, int] = {}
    plural = {
        "entity": "entities",
        "field": "fields",
        "persona": "personas",
        "process": "processes",
        "manual_config": "manual_configs",
        "domain": "domains",
        "planning_item": "planning_items",
    }
    for row in created:
        key = plural[row["record_type"]]
        records_summary[key] = records_summary.get(key, 0) + 1
    references = [
        {
            "relationship": "deposit_event_wrote_record",
            "target_type": row["record_type"],
            "target_id": row["identifier"],
        }
        for row in created
    ]
    event = client.create_deposit_event(
        identifier=dep_identifier,
        title=f"Audit deposit: {plan.source_label}",
        description=(
            f"Phase 1.5 audit baseline deposit of {plan.source_label}, "
            f"source snapshot {plan.snapshot_at}."
        ),
        kind="audit_deposit",
        outcome="failure" if error_info is not None else "success",
        records_summary=records_summary,
        apply_context=plan.apply_context,
        log_file_path=log_file_path,
        error_info=error_info,
        references=references,
    )
    dep_identifier = event["deposit_event_identifier"]

    if error_info is not None:
        raise RuntimeError(
            f"audit deposit failed after {len(created)} record(s); recorded "
            f"as {dep_identifier} (outcome failure): {error_info['error']}"
        )

    # Evidence rows — created + matched subjects, in run order (§5).
    created_by_key = {
        (row["record_type"], row["key"]): row["identifier"] for row in created
    }
    evidence_rows = 0
    for item in plan.creates:
        if item.evidence is None:
            continue
        identifier = created_by_key[(item.record_type, item.key)]
        client.create_utilization_evidence(
            subject_identifier=identifier,
            profiled_at=plan.profiled_at,
            source_label=plan.source_label,
            deposit_event_identifier=dep_identifier,
            **item.evidence,
        )
        evidence_rows += 1
    for match in plan.matches:
        client.create_utilization_evidence(
            subject_identifier=match.identifier,
            profiled_at=plan.profiled_at,
            source_label=plan.source_label,
            deposit_event_identifier=dep_identifier,
            **match.evidence,
        )
        evidence_rows += 1

    return {
        "deposit_event_identifier": dep_identifier,
        "created": created,
        "matched": len(plan.matches),
        "evidence_rows": evidence_rows,
        "records_summary": records_summary,
        "log_file_path": log_file_path,
    }


# ---------------------------------------------------------------------------
# REST client + CLI (spec §6)
# ---------------------------------------------------------------------------


def _prefix_payload(
    prefix: str, payload: dict, passthrough: frozenset[str] = frozenset()
) -> dict:
    """Map repository-kwarg keys to a REST body's parent-prefixed names.

    The plan's payloads use the repositories' unprefixed kwargs (the
    shape the access-layer test client consumes directly); the REST
    schemas carry parent-prefixed field names with ``extra="forbid"``.
    Keys already prefixed (``field_belongs_to_entity_identifier``) and
    keys named in ``passthrough`` (``references``) pass unchanged.
    """
    return {
        (
            key
            if key in passthrough or key.startswith(prefix)
            else f"{prefix}{key}"
        ): value
        for key, value in payload.items()
    }


class RestDepositClient(DepositClient):
    """REST client of the live V2 API (TOP-013; mirrors apply_close_out).

    Every request sends the ``X-Engagement`` header (PI-β) and unwraps
    the ``{data, meta, errors}`` envelope; non-2xx bodies may bypass the
    envelope (``api/errors.py``), so the raw body is surfaced in the
    raised error. Issues GET and POST only — never PATCH, PUT, or
    DELETE (spec §6). Create payloads are re-keyed to the REST schemas'
    parent-prefixed names via :func:`_prefix_payload`; planning-item
    and utilization-evidence bodies are unprefixed on the wire already.
    """

    def __init__(
        self, base_url: str = "http://127.0.0.1:8765", engagement: str | None = None
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.engagement = engagement

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib_request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.engagement:
            req.add_header("X-Engagement", self.engagement)
        try:
            with urllib_request.urlopen(req) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            raise RuntimeError(
                f"{method} {path} -> HTTP {exc.code}: "
                f"{exc.read().decode('utf-8', errors='replace')}"
            ) from exc
        if payload.get("errors"):
            raise RuntimeError(f"{method} {path} -> errors: {payload['errors']}")
        return payload["data"]

    def list_entities(self) -> list[dict]:
        return self._request("GET", "/entities?include_deleted=true")

    def list_fields_with_parents(self) -> list[dict]:
        fields = self._request("GET", "/fields?include_deleted=true")
        refs = self._request(
            "GET",
            "/references?source_type=field"
            "&relationship=field_belongs_to_entity",
        )
        parent_by_field = {r["source_id"]: r["target_id"] for r in refs}
        for row in fields:
            row["parent_entity_identifier"] = parent_by_field.get(
                row["field_identifier"]
            ) or row.get("field_previous_parent_entity_identifier")
        return fields

    def list_personas(self) -> list[dict]:
        return self._request("GET", "/personas?include_deleted=true")

    def list_processes(self) -> list[dict]:
        return self._request("GET", "/processes?include_deleted=true")

    def list_manual_configs(self) -> list[dict]:
        return self._request("GET", "/manual-configs?include_deleted=true")

    def list_domains(self) -> list[dict]:
        return self._request("GET", "/domains?include_deleted=true")

    def next_deposit_event_identifier(self) -> str:
        # The DEC-043 next-identifier helpers return {"next": "<PREFIX>-NNN"}.
        data = self._request("GET", "/deposit-events/next-identifier")
        if isinstance(data, dict):
            return data.get("next") or data["identifier"]
        return data

    def create_entity(self, **payload) -> dict:
        return self._request(
            "POST", "/entities", _prefix_payload("entity_", payload)
        )

    def create_field(self, **payload) -> dict:
        return self._request(
            "POST", "/fields", _prefix_payload("field_", payload)
        )

    def create_persona(self, **payload) -> dict:
        return self._request(
            "POST", "/personas", _prefix_payload("persona_", payload)
        )

    def create_process(self, **payload) -> dict:
        return self._request(
            "POST", "/processes", _prefix_payload("process_", payload)
        )

    def create_manual_config(self, **payload) -> dict:
        return self._request(
            "POST",
            "/manual-configs",
            _prefix_payload("manual_config_", payload),
        )

    def create_domain(self, **payload) -> dict:
        return self._request(
            "POST", "/domains", _prefix_payload("domain_", payload)
        )

    def create_planning_item(self, **payload) -> dict:
        return self._request("POST", "/planning-items", payload)

    def create_deposit_event(self, **payload) -> dict:
        return self._request(
            "POST",
            "/deposit-events",
            _prefix_payload(
                "deposit_event_", payload, passthrough=frozenset({"references"})
            ),
        )

    def create_utilization_evidence(self, **payload) -> dict:
        return self._request("POST", "/utilization-evidence", payload)


def _print_plan(plan: DepositPlan) -> None:
    """Print the plan, each candidate's evidence as its §3 inline
    object (WTK-097 §5 obligation 3) — the operator previews at deposit
    time exactly what triage reads later."""

    def _render(evidence: dict, identifier: str | None = None) -> str:
        obj = plan_evidence_object(
            evidence,
            profiled_at=plan.profiled_at,
            source_label=plan.source_label,
            subject_identifier=identifier,
        )
        return json.dumps(obj, sort_keys=True)

    print(f"Source: {plan.source_label} (snapshot {plan.snapshot_at})")
    print(f"Creates ({len(plan.creates)}):")
    for item in plan.creates:
        print(f"  + {item.record_type}: {item.key}")
        if item.evidence is not None:
            print(f"    evidence: {_render(item.evidence)}")
    print(f"Matches ({len(plan.matches)}):")
    for match in plan.matches:
        print(f"  = {match.record_type}: {match.identifier} ({match.key})")
        print(f"    evidence: {_render(match.evidence, match.identifier)}")
    for row in plan.skipped_soft_deleted:
        print(
            f"  ! skipped soft-deleted {row['record_type']} "
            f"{row['identifier']} ({row['name']!r})"
        )
    print(f"Anomalies: {len(plan.anomalies)}")
    evidence_count = sum(
        1 for item in plan.creates if item.evidence is not None
    ) + len(plan.matches)
    print(f"Evidence rows to write: {evidence_count}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-deposit-audit",
        description=(
            "Deposit a V1 audit-report.json into the V2 engagement DB as "
            "candidate methodology records (WTK-090)."
        ),
    )
    parser.add_argument("manifest", help="path to audit-report.json")
    parser.add_argument(
        "--profile", default=None, help="path to utilization-profile.json"
    )
    parser.add_argument(
        "--engagement", required=True, help="X-Engagement header value"
    )
    parser.add_argument(
        "--base-url", default="http://127.0.0.1:8765", help="V2 API base URL"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the plan (creates, matches, evidence count) and exit",
    )
    parser.add_argument(
        "--no-render-report",
        dest="render_report",
        action="store_false",
        help=(
            "skip the Baseline Report render step (rendering is default-on "
            "per WTK-116 §6.3; the deposit itself is unaffected either way)"
        ),
    )
    parser.add_argument(
        "--report-output",
        default=None,
        help=(
            "Baseline Report output path (default: baseline-report.md "
            "beside the manifest)"
        ),
    )
    args = parser.parse_args(argv)

    # Imported here, not at module level — the renderer imports this
    # module's manifest helpers (WTK-116 §9 reuses, not duplicates).
    from crmbuilder_v2.render import baseline_report

    manifest = load_manifest(args.manifest)
    profile = load_profile(args.profile)
    client = RestDepositClient(args.base_url, engagement=args.engagement)
    plan = plan_deposit(manifest, profile, fetch_existing_state(client))
    # Additive apply_context diagnostics (WTK-089 §4.3 free growth):
    # where the manifest pair lives (WTK-116 §2.2 — the standalone
    # re-render's discovery route) and, when rendering, where the
    # report will land (§6.3). The event is POSTed before rendering
    # begins, so the report path is the *planned* home — a later render
    # failure never taints the deposit.
    manifest_path = Path(args.manifest).resolve()
    plan.apply_context["audit_manifest_path"] = str(manifest_path)
    report_path = (
        Path(args.report_output)
        if args.report_output
        else manifest_path.parent / baseline_report.REPORT_FILENAME
    )
    if args.render_report:
        plan.apply_context["baseline_report_path"] = str(report_path)
    _print_plan(plan)
    if args.dry_run:
        return 0
    summary = execute_plan(plan, client)
    print(
        f"Deposit event: {summary['deposit_event_identifier']} — "
        f"{len(summary['created'])} created, {summary['matched']} matched, "
        f"{summary['evidence_rows']} evidence row(s)."
    )
    log_path = Path(summary["log_file_path"])
    if log_path.parent.is_dir():
        log_path.write_text(
            json.dumps(
                {
                    "deposit_event_identifier": summary[
                        "deposit_event_identifier"
                    ],
                    "records_summary": summary["records_summary"],
                    "created": summary["created"],
                    "matched": summary["matched"],
                    "evidence_rows": summary["evidence_rows"],
                    "apply_context": plan.apply_context,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Deposit log written: {log_path}")
    else:
        print(
            f"NOTE: log directory {log_path.parent} not found from the "
            "current working directory; deposit log not written (run from "
            "the repo root to capture it)."
        )

    if args.render_report:
        # Render failure never taints a successful deposit (WTK-116
        # §6.3): the event is already posted; report the failure loudly
        # with its own exit status and leave the standalone re-render
        # (crmbuilder-v2-render-baseline) as the repair path.
        try:
            render_client = baseline_report.RestRenderClient(
                args.base_url, engagement=args.engagement
            )
            written = baseline_report.render_baseline_report(
                render_client,
                plan.source_label,
                output_path=report_path,
                rendered_at=datetime.now(UTC).isoformat(),
                manifest=manifest,
                profile=profile,
                manifest_path=str(manifest_path),
                profile_path=args.profile,
            )
            print(f"Baseline report written: {written}")
        except Exception as exc:  # noqa: BLE001 — the deposit stands; the render fails on its own exit status
            print(
                "ERROR: Baseline Report render failed (deposit "
                f"{summary['deposit_event_identifier']} stands): {exc}"
            )
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
