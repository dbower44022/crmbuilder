"""Catalog normalizer (WTK-102 design spec).

The normalization layer between audit discovery and the V2 candidate
deposit — Master CRMBuilder PRD v0.2 §7 Activity step 3, specified in
``PRDs/product/crmbuilder-v2/methodology-schema-specs/
catalog-normalizer-type-mapping-and-partition.md``. Three concerns,
all pure functions with no I/O (unit-testable offline like
``plan_deposit``):

* **Type mapping** (spec §3) — a two-stage deterministic mapping from
  each of the seven catalog-surveyed systems' native field types to
  the engine-agnostic ``FIELD_TYPES`` vocabulary. Stage 1 is the
  per-system table ``SYSTEM_TYPE_MAPS[system]`` (native type or keyed
  pair → ``CATALOG_ATTRIBUTE_TYPES``); stage 2 is the single fixed
  total projection ``CATALOG_TO_FIELD_TYPE``. Stage 2 is the **only**
  place the lossy collapse happens — when ``FIELD_TYPES`` grows
  (PI-054), only that table changes and all seven systems inherit the
  refinement at once. Fallbacks per spec §3.10: unknown native type →
  ``string`` → ``text`` + anomaly; unknown pair → bare-type row when
  one exists (anomaly-free), else the unknown-type chain. The map is
  never extended at runtime — new native types enter only through a
  versioned spec amendment.

* **Standard-vs-custom partition** (spec §4) — the three-tier oracle
  classifying every discovered item: source marker (authoritative) →
  catalog presence (reference oracle, injected as a callable) →
  conservative ``custom`` + anomaly. The class is evidence
  (``evidence_catalog_class``), never record state.

* **Triage priority** (spec §5) — the T1–T4 band projection from
  partition class × utilization evidence, derived at read/render time
  and never stored; thresholds shared with the WTK-096 profiling pass.

The six non-EspoCRM stage-1 tables are **adapter contracts** (spec
§2.3): pinned now from each product's public schema documentation so
the vocabulary cannot drift per-adapter, validated against a
live-discovery fixture before each adapter's first production use
(criterion N4), and corrected only by versioned spec amendment.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from crmbuilder_v2.access.vocab import CATALOG_SYSTEMS

# ---------------------------------------------------------------------------
# Stage 2 — the fixed projection CATALOG_ATTRIBUTE_TYPES -> FIELD_TYPES
# (spec §3.2). Total over all 21 catalog attribute types; no fallback
# exists at this stage — a stage-1 output outside this table is a
# programming error, not an input condition (criterion N2).
# ---------------------------------------------------------------------------

CATALOG_TO_FIELD_TYPE: dict[str, str] = {
    "string": "text",
    "text": "long_text",
    "richtext": "long_text",  # formatting is presentation, not shape
    "integer": "number",
    "decimal": "number",
    "currency": "money",
    "boolean": "boolean",
    "date": "date",
    "datetime": "datetime",
    # Lossy: FIELD_TYPES has no time-of-day; `datetime` would assert a
    # date that does not exist. Finer type recoverable from evidence.
    "time": "text",
    "enum": "enum",
    "multienum": "multi_enum",
    "reference": "reference",
    "multireference": "reference",  # cardinality survives in evidence detail
    "email": "text",  # PI-054 refinement candidates: email/phone/url/address
    "phone": "text",
    "url": "text",
    "address": "text",
    "attachment": "text",  # no file shape in FIELD_TYPES; survives in notes
    "autonumber": "number",
    "formula": "derived",
}

# §3.10 rule 1: an unknown native type maps to `string` (hence `text`)
# and raises an anomaly — same end-behavior as the landed
# `_FALLBACK_FIELD_TYPE` path, restated at the stage-1 level.
FALLBACK_CATALOG_TYPE = "string"
FALLBACK_FIELD_TYPE = CATALOG_TO_FIELD_TYPE[FALLBACK_CATALOG_TYPE]

# ---------------------------------------------------------------------------
# Stage 1 — per-system native type -> CATALOG_ATTRIBUTE_TYPES (spec
# §3.3–§3.9). Keys are either a bare native type (str) or an exact
# (type, subtype) pair; lookup precedence is computed-value flag, exact
# pair, bare type, fallback (§3.1). Single-valued kinds promote to
# multi-valued via the `multivalued` flag (Attio `is_multiselect`,
# CiviCRM `serialize`) rather than per-system pair rows.
# ---------------------------------------------------------------------------

StageOneKey = str | tuple[str, str]

# §3.3 — grounded in the landed WIRE_TYPE_MAP; the composition of this
# table with stage 2 reproduces it value-for-value (criterion N3). The
# §3.3 named extensions (file/image/attachmentMultiple/barcode) are
# deliberately NOT adopted here — today they take the fallback chain,
# preserving landed behavior exactly.
_ESPOCRM_TYPES: dict[StageOneKey, str] = {
    "varchar": "string",
    "personName": "string",
    "email": "email",
    "phone": "phone",
    "url": "url",
    "address": "address",
    "text": "text",
    "wysiwyg": "richtext",
    "enum": "enum",
    "multiEnum": "multienum",
    "checklist": "multienum",
    "array": "multienum",
    "date": "date",
    "datetime": "datetime",
    "datetimeOptional": "datetime",
    "currency": "currency",
    "currencyConverted": "currency",
    "bool": "boolean",
    "int": "integer",
    "float": "decimal",
    "autoincrement": "autonumber",
    "link": "reference",
    "linkParent": "reference",
    "linkOne": "reference",
    "linkMultiple": "multireference",
    "foreign": "formula",
}

# §3.4 — keyed on the Metadata/Describe field type. Fields the source
# marks `calculated: true` (formula and roll-up summary) map `formula`
# regardless of declared result type via the `calculated` flag (§3.1).
# §3.5: salesforce_npsp is identical by construction — NPSP is a
# managed package and introduces no new field types; only the
# partition differs (§4.3).
_SALESFORCE_TYPES: dict[StageOneKey, str] = {
    "Text": "string",
    "EncryptedText": "string",
    "Name": "string",  # compound; maps as one candidate field (§3.1)
    "TextArea": "text",
    "LongTextArea": "text",
    "Html": "richtext",
    "Number": "decimal",
    "Percent": "decimal",
    "Currency": "currency",
    "AutoNumber": "autonumber",
    "Checkbox": "boolean",
    "Date": "date",
    "DateTime": "datetime",
    "Time": "time",
    "Email": "email",
    "Phone": "phone",
    "Url": "url",
    "Address": "address",  # compound
    "Geolocation": "string",  # lat/long pair as text; no geo shape
    "Location": "string",
    "Picklist": "enum",
    "MultiselectPicklist": "multienum",
    "Lookup": "reference",
    "MasterDetail": "reference",
    "ExternalLookup": "reference",
    "IndirectLookup": "reference",
    "Hierarchy": "reference",
    "MetadataRelationship": "reference",
    "Formula": "formula",
    "Summary": "formula",
}

# §3.6 — keyed on the property pair (type, fieldType); calculated
# properties map `formula` first per §3.1. Bare-type rows back the
# §3.10 rule-2 pair fallback. (`json`, any) is deliberately absent —
# it takes the rule-1 fallback chain. Cross-object links are
# associations, not properties; they map per WTK-090 §3.3, not here.
_HUBSPOT_TYPES: dict[StageOneKey, str] = {
    ("string", "text"): "string",
    ("string", "textarea"): "text",
    ("string", "html"): "richtext",
    ("string", "file"): "attachment",
    ("string", "phonenumber"): "phone",
    "string": "string",
    "phone_number": "phone",
    "number": "decimal",
    "date": "date",
    "datetime": "datetime",
    "bool": "boolean",
    ("enumeration", "booleancheckbox"): "boolean",
    ("enumeration", "select"): "enum",
    ("enumeration", "radio"): "enum",
    ("enumeration", "checkbox"): "multienum",
    "enumeration": "enum",
}

# §3.7 — keyed on the attribute type; `is_multiselect` arrives as the
# `multivalued` flag (select -> multienum, record-reference ->
# multireference).
_ATTIO_TYPES: dict[StageOneKey, str] = {
    "text": "string",
    "personal-name": "string",
    "number": "decimal",
    "rating": "integer",
    "currency": "currency",
    "checkbox": "boolean",
    "date": "date",
    "timestamp": "datetime",
    "status": "enum",
    "select": "enum",
    "record-reference": "reference",
    "actor-reference": "reference",  # persona-adjacent signal for triage
    "location": "address",
    "domain": "url",
    "email-address": "email",
    "phone-number": "phone",
    # Read-only system aggregate — usually excluded pre-mapping by the
    # adapter's system set; mapped defensively if it leaks through.
    "interaction": "datetime",
}

# §3.8 — keyed on the custom-field pair (data_type, html_type), with
# the `serialize` flag arriving as `multivalued`. The Date row's
# discriminator is the time_format flag, not html_type: the adapter
# passes subtype="time_format" when the field carries a time
# component, else the bare "Date" row applies. Core (non-custom-group)
# fields map by the same data-shape rows.
_CIVICRM_TYPES: dict[StageOneKey, str] = {
    ("String", "Text"): "string",
    ("String", "Select"): "enum",
    ("String", "Radio"): "enum",
    ("String", "Autocomplete-Select"): "enum",
    ("String", "CheckBox"): "multienum",
    ("String", "Multi-Select"): "multienum",
    "String": "string",
    "Int": "integer",
    "Float": "decimal",
    "Money": "currency",
    ("Memo", "TextArea"): "text",
    ("Memo", "RichTextEditor"): "richtext",
    "Memo": "text",
    "Date": "date",
    ("Date", "time_format"): "datetime",
    "Boolean": "boolean",
    "StateProvince": "enum",
    "Country": "enum",
    "File": "attachment",
    "Link": "url",
    "ContactReference": "reference",
    "EntityReference": "reference",
}

# §3.9 — Bloomerang custom fields carry a data type and a pick
# structure (subtype "pick_one"/"pick_many"); the stock schema's typed
# channels map by shape under the adapter-contract slugs below. The
# least-settled table of the seven (§2.3) — the N4 fixture gate is its
# enforcement.
_BLOOMERANG_TYPES: dict[StageOneKey, str] = {
    "text": "string",
    ("text", "pick_one"): "enum",
    ("text", "pick_many"): "multienum",
    "date": "date",
    "currency": "currency",
    "number": "decimal",
    "decimal": "decimal",
    "boolean": "boolean",
    "email": "email",  # stock email channel
    "phone": "phone",  # stock phone channel
    "address": "address",  # stock address block
    "note": "text",  # stock note / narrative fields
    "reference": "reference",  # stock links (household, soft-credit, tribute)
}

# WTK-110 §6.3 (delta D3) — the spreadsheet adapter's closed
# inferred-type vocabulary, the eighth stage-1 table. All bare-string
# keys (the adapter owns its own vocabulary, so it never needs a
# subtype discriminator) and no calculated/multivalued flags (formulas
# are invisible in CSV exports; multi-valuedness is its own native
# type). `CATALOG_SYSTEMS` deliberately does NOT grow — that frozenset
# is the catalog-survey vocabulary, and a spreadsheet is not a surveyed
# product; only this registry and the partition rule know the slug.
_SPREADSHEET_TYPES: dict[StageOneKey, str] = {
    "text": "string",
    "long_text": "text",
    "integer": "integer",
    "decimal": "decimal",
    "currency": "currency",
    "percent": "decimal",
    "boolean": "boolean",
    "date": "date",
    "datetime": "datetime",
    # Stage-2 lossy rule, shared: no time-of-day in FIELD_TYPES.
    "time": "time",
    # PI-054 refinement candidates, shared: email/phone/url -> text.
    "email": "email",
    "phone": "phone",
    "url": "url",
    "enum": "enum",
    "multi_enum": "multienum",
    "reference": "reference",
    "auto_number": "autonumber",
    # An empty column is signal (gaps-and-ghosts evidence), not the
    # anomaly fallback; inference confidence is `none` in evidence.
    "empty": "string",
}

SPREADSHEET_SYSTEM = "spreadsheet"

SYSTEM_TYPE_MAPS: dict[str, dict[StageOneKey, str]] = {
    "espocrm": _ESPOCRM_TYPES,
    "salesforce": _SALESFORCE_TYPES,
    "salesforce_npsp": _SALESFORCE_TYPES,
    "hubspot": _HUBSPOT_TYPES,
    "attio": _ATTIO_TYPES,
    "civicrm": _CIVICRM_TYPES,
    "bloomerang": _BLOOMERANG_TYPES,
    SPREADSHEET_SYSTEM: _SPREADSHEET_TYPES,
}

# Single-valued -> multi-valued promotion for the `multivalued` flag
# (Attio `is_multiselect`, CiviCRM `serialize`); identity elsewhere.
_MULTIVALUED_PROMOTION = {"enum": "multienum", "reference": "multireference"}


@dataclass(frozen=True)
class Anomaly:
    """One line destined for the run's anomaly Planning Item (WTK-090 §3.6).

    ``kind`` is ``unmapped_type`` (§3.10 rule 1) or ``unpartitioned``
    (§4.2 tier 3); callers prepend their own subject context (entity,
    field) when rendering the PI entry.
    """

    kind: str
    system: str
    message: str


def _require_system(system: str) -> dict[StageOneKey, str]:
    table = SYSTEM_TYPE_MAPS.get(system)
    if table is None:
        raise ValueError(f"unknown catalog system {system!r}")
    return table


def resolve_type(
    system: str,
    native: str,
    *,
    subtype: str | None = None,
    calculated: bool = False,
    multivalued: bool = False,
) -> tuple[str, str, Anomaly | None]:
    """Resolve one native type through both stages.

    Returns ``(catalog_type, field_type, anomaly)`` — the stage-1
    catalog attribute type is additionally recorded in evidence detail
    (key ``catalog_attribute_type``, §2.2) so triage and the eventual
    migration mapping can recover the finer shape. Lookup precedence
    per §3.1: ``calculated`` flag first, then the exact
    ``(native, subtype)`` pair, then the bare type, then the §3.10
    fallback chain.
    """
    table = _require_system(system)
    anomaly = None
    if calculated:
        catalog_type = "formula"
    elif subtype is not None and (native, subtype) in table:
        catalog_type = table[(native, subtype)]
    elif native in table:
        catalog_type = table[native]
    else:
        catalog_type = None
    if catalog_type is None:
        catalog_type = FALLBACK_CATALOG_TYPE
        rendered = f"({native!r}, {subtype!r})" if subtype is not None else repr(native)
        anomaly = Anomaly(
            kind="unmapped_type",
            system=system,
            message=(
                f"unmapped native type {rendered} in {system}; "
                f"mapped to {FALLBACK_FIELD_TYPE!r}"
            ),
        )
    elif multivalued:
        catalog_type = _MULTIVALUED_PROMOTION.get(catalog_type, catalog_type)
    return catalog_type, CATALOG_TO_FIELD_TYPE[catalog_type], anomaly


def normalize_type(
    system: str,
    native: str,
    *,
    subtype: str | None = None,
    calculated: bool = False,
    multivalued: bool = False,
) -> tuple[str, Anomaly | None]:
    """Map one native type to its ``FIELD_TYPES`` value (spec §3).

    Pure: the same input always yields the same output, fixture-stable.
    The fallback (§3.10) keeps unattended runs safe; the anomaly keeps
    them honest. Fallback-mapped items are otherwise full citizens.
    """
    _, field_type, anomaly = resolve_type(
        system,
        native,
        subtype=subtype,
        calculated=calculated,
        multivalued=multivalued,
    )
    return field_type, anomaly


def composed_type_map(system: str) -> dict[StageOneKey, str]:
    """The stage-1 table composed with stage 2: native type ->
    ``FIELD_TYPES`` value. For ``espocrm`` this reproduces the landed
    ``WIRE_TYPE_MAP`` entry-for-entry (criterion N3), and
    ``audit_deposit`` consumes it in place of its previous inline map.
    """
    return {
        key: CATALOG_TO_FIELD_TYPE[catalog_type]
        for key, catalog_type in _require_system(system).items()
    }


# ---------------------------------------------------------------------------
# The standard-vs-custom partition (spec §4)
# ---------------------------------------------------------------------------

# The NPSP managed-package namespaces — the stock schema of the product
# the `salesforce_npsp` slug names (§4.3).
NPSP_NAMESPACES: frozenset[str] = frozenset(
    {"npsp", "npe01", "npe03", "npe4", "npe5", "npo02"}
)

# The output vocabulary: CATALOG_PRESENCE_STATUSES minus `absent`
# (meaningless for an item just discovered *in* the system, §4.1).
PARTITION_CLASSES: frozenset[str] = frozenset({"standard", "custom"})

# Tier-2 oracle contract: ``(system, api_name, *, kind, label=None)``
# -> the catalog's class for the item, or None when the catalog has no
# usable row (no row, or presence `absent`). Entity rows may return
# `partial` (§4.4); attribute rows return `standard`/`custom`. The
# concrete implementation reads the catalog tables
# (`access/repositories/catalog/read.py`) with synonym-extended
# matching — exact-api_name match outranks a synonym match. The
# normalizer stays pure by taking it as a callable; on an unseeded
# catalog DB, tier 2 degrades to tier 3 with anomalies, which
# criterion N9 makes safe.
CatalogLookup = Callable[..., str | None]


@dataclass(frozen=True)
class DiscoveredItem:
    """One discovered entity or attribute, as the normalizer sees it.

    ``marker`` carries the source system's own custom-vs-stock signal,
    read at discovery time by the adapter (tier 1's input). Keys per
    system (§4.3): espocrm ``class`` (``custom``/``native``, from the
    manifest's entity_class/field_class); hubspot ``object_type_id``
    (entities) / ``hubspot_defined`` (attributes); attio
    ``default_object`` (entities) / ``default_attribute`` (attributes,
    the adapter-pinned default-slug sets); civicrm ``custom_group``;
    bloomerang ``custom_field``. Salesforce needs no marker — its
    signal is structural in the api_name. ``None`` means the source
    exposed no marker, falling to tier 2.
    """

    kind: str  # "entity" | "attribute"
    api_name: str
    label: str | None = None
    marker: Mapping[str, object] | None = None


@dataclass(frozen=True)
class PartitionResult:
    """One item's partition outcome, with derivation provenance.

    ``tier`` records which oracle tier decided (1 source marker, 2
    catalog presence, 3 conservative default). ``disagreement`` is the
    §4.2 marker-vs-catalog mismatch payload destined for the evidence
    row's ``catalog_disagreement`` detail key — catalog-correction
    input, not a runtime decision.
    """

    catalog_class: str
    tier: int
    disagreement: dict | None = None


def salesforce_namespace(api_name: str) -> str | None:
    """The package namespace of a ``ns__Name__c`` api name, else None."""
    if not api_name.endswith("__c"):
        return None
    parts = api_name[: -len("__c")].split("__")
    return parts[0] if len(parts) > 1 else None


def _tier1_salesforce(item: DiscoveredItem, *, npsp_is_standard: bool) -> str:
    """The structural api-name suffix rule, entities and attributes alike.

    NPSP-namespaced items follow N6/§3.5: the raw platform marks them
    custom, so under plain ``salesforce`` they partition ``custom``;
    under ``salesforce_npsp`` they are the product's stock schema ->
    ``standard``. Other namespaces are some vendor's stock schema,
    installed deliberately -> ``standard`` (+ namespace note, §4.5).
    """
    if not item.api_name.endswith("__c"):
        return "standard"
    namespace = salesforce_namespace(item.api_name)
    if namespace is None:
        return "custom"
    if namespace.lower() in NPSP_NAMESPACES:
        return "standard" if npsp_is_standard else "custom"
    return "standard"


def _tier1(system: str, item: DiscoveredItem) -> str | None:
    """The §4.3 per-system source-marker rules; None falls to tier 2."""
    marker = item.marker
    if system == "espocrm":
        item_class = (marker or {}).get("class")
        if item_class == "custom":
            return "custom"
        if item_class == "native":
            return "standard"
        return None
    if system in ("salesforce", "salesforce_npsp"):
        return _tier1_salesforce(
            item, npsp_is_standard=system == "salesforce_npsp"
        )
    if system == "hubspot":
        if item.kind == "entity":
            object_type_id = str((marker or {}).get("object_type_id") or "")
            if object_type_id.startswith("0-"):
                return "standard"
            if object_type_id.startswith("2-"):
                return "custom"
            return None
        # `hubspotDefined: true` -> standard; false/absent -> custom —
        # authoritative whenever the adapter saw property metadata.
        if marker is None:
            return None
        return "standard" if marker.get("hubspot_defined") else "custom"
    if system == "attio":
        if item.kind == "entity":
            default_object = (marker or {}).get("default_object")
            if default_object is None:
                return None
            return "standard" if default_object else "custom"
        # No per-attribute API flag is relied on (§4.3): the adapter's
        # pinned default-slug sets say standard; everything else falls
        # to tier 2.
        return "standard" if (marker or {}).get("default_attribute") else None
    if system == "civicrm":
        if item.kind == "entity":
            # Structural: no client mechanism for new top-level
            # entities (custom *groups* attach fields to existing
            # entities); extension-provided entities also standard.
            return "standard"
        if marker is None:
            return None
        return "custom" if marker.get("custom_group") else "standard"
    if system == "bloomerang":
        if item.kind == "entity":
            # Structural: the fixed product schema; no client-defined
            # entities exist.
            return "standard"
        if marker is None:
            return None
        return "custom" if marker.get("custom_field") else "standard"
    raise ValueError(f"unknown catalog system {system!r}")


def _normalize_catalog_status(raw: str | None, *, kind: str) -> str | None:
    """Collapse a tier-2 oracle return onto the partition vocabulary.

    Entity ``partial`` partitions ``standard`` — some stock footing
    exists; the per-attribute scrutiny tiers 1–3 do anyway (§4.4).
    ``is_standard`` true/false values are admitted for entity rows;
    ``absent`` (a catalog concept missing from this system) is a miss.
    """
    if raw in PARTITION_CLASSES:
        return raw
    if kind == "entity":
        if raw in ("partial", "true"):
            return "standard"
        if raw == "false":
            return "custom"
    return None


def partition_detailed(
    system: str,
    item: DiscoveredItem,
    catalog_lookup: CatalogLookup | None = None,
) -> tuple[PartitionResult, Anomaly | None]:
    """Run the §4.2 three-tier oracle for one discovered item.

    The first tier that yields a class wins. When tier 1 decides and
    the catalog disagrees, the marker wins and the disagreement is
    recorded on the result (the live system is the witness). The tier-3
    default is deliberately conservative in the direction that protects
    signal: misclassifying standard as custom costs one triage glance;
    the reverse buries paid-for requirements signal.
    """
    if system == SPREADSHEET_SYSTEM:
        # WTK-110 §2.4 delta D4: a spreadsheet has no stock schema and
        # no catalog presence — every item, entity and attribute, is
        # `custom`; tiers 2 and 3 are never consulted.
        return PartitionResult("custom", 1), None
    if system not in CATALOG_SYSTEMS:
        raise ValueError(f"unknown catalog system {system!r}")
    marker_class = _tier1(system, item)
    catalog_class = None
    if catalog_lookup is not None:
        catalog_class = _normalize_catalog_status(
            catalog_lookup(system, item.api_name, kind=item.kind, label=item.label),
            kind=item.kind,
        )
    if marker_class is not None:
        disagreement = None
        if catalog_class is not None and catalog_class != marker_class:
            disagreement = {"marker": marker_class, "catalog": catalog_class}
        return PartitionResult(marker_class, 1, disagreement), None
    if catalog_class is not None:
        return PartitionResult(catalog_class, 2), None
    anomaly = Anomaly(
        kind="unpartitioned",
        system=system,
        message=(
            f"no source marker or catalog row for {item.kind} "
            f"{item.api_name!r} in {system}; classified 'custom' "
            "(conservative default)"
        ),
    )
    return PartitionResult("custom", 3), anomaly


def partition(
    system: str,
    item: DiscoveredItem,
    catalog_lookup: CatalogLookup | None = None,
) -> tuple[str, Anomaly | None]:
    """The spec §7 surface: one item's class from ``{standard, custom}``."""
    result, anomaly = partition_detailed(system, item, catalog_lookup)
    return result.catalog_class, anomaly


# ---------------------------------------------------------------------------
# Triage priority derivation (spec §5) — derived at read/render time
# from the partition class and the latest evidence snapshot, never
# stored (criterion N8: same inputs -> same band, deterministically).
# ---------------------------------------------------------------------------

# Use thresholds reused unchanged from WTK-096 (which aligned them to
# the WTK-088 triage queries) so every consumer agrees on what "real
# use" means; an evidence row's recorded `detail.thresholds` override
# these defaults so bands re-derive from the row alone.
DORMANCY_WINDOW_DAYS = 365
LOW_POPULATION_THRESHOLD = 0.05

BAND_T1 = "T1"  # custom + real use: concentrated requirements signal
BAND_T2 = "T2"  # custom + dormant: the gaps-and-ghosts list
BAND_T3 = "T3"  # standard + real use: stock schema the org leans on
BAND_T4 = "T4"  # standard + dormant: product noise floor
# Schema-only runs (WTK-090 §2.2 degraded mode): the use prong is
# unknown, so bands collapse to the partition axis — the report states
# that profiling is pending rather than presenting structure-only
# priority as use-verified priority.
BAND_UNPROFILED_CUSTOM = "T1/T2 (use unprofiled)"
BAND_UNPROFILED_STANDARD = "T3/T4 (use unprofiled)"

PRIORITY_BANDS: tuple[str, ...] = (
    BAND_T1,
    BAND_T2,
    BAND_T3,
    BAND_T4,
    BAND_UNPROFILED_CUSTOM,
    BAND_UNPROFILED_STANDARD,
)


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def derive_priority_band(evidence_object: dict) -> str:
    """Project one item's T1–T4 band from its projected evidence object.

    ``evidence_object`` is the §3 inline shape every surface presents
    (:func:`crmbuilder_v2.access.evidence_projection.project_evidence_object`)
    for the item's **latest** snapshot per ``(subject, source)``. The
    use prongs (§5.2): a field is in real use at ``population_rate`` ≥
    the low-population threshold with ``last_populated_at`` inside the
    dormancy window of ``profiled_at``; an entity at ``record_count`` >
    0 with ``last_record_created_at`` inside the window. Enum
    option-shrinkage does not change the band.
    """
    catalog_class = evidence_object.get("catalog_class")
    if catalog_class not in PARTITION_CLASSES:
        raise ValueError(
            f"evidence object carries no partition class: {catalog_class!r}"
        )
    detail = evidence_object.get("detail") or {}
    metrics = evidence_object.get("metrics") or {}
    thresholds = detail.get("thresholds") or {}
    window_days = thresholds.get("dormancy_window_days", DORMANCY_WINDOW_DAYS)
    low_threshold = thresholds.get(
        "low_population_threshold", LOW_POPULATION_THRESHOLD
    )
    is_entity = evidence_object.get("subject_type") == "entity"
    profiled_at = _parse_dt(evidence_object.get("profiled_at"))
    use_prong_key = "record_count" if is_entity else "population_rate"
    if (
        detail.get("schema_only")
        or use_prong_key not in metrics
        or profiled_at is None
    ):
        return (
            BAND_UNPROFILED_CUSTOM
            if catalog_class == "custom"
            else BAND_UNPROFILED_STANDARD
        )
    cutoff = profiled_at - timedelta(days=window_days)
    if is_entity:
        last = _parse_dt(metrics.get("last_record_created_at"))
        in_use = (metrics.get("record_count") or 0) > 0 and (
            last is not None and last >= cutoff
        )
    else:
        rate = metrics.get("population_rate")
        last = _parse_dt(metrics.get("last_populated_at"))
        in_use = (
            rate is not None
            and rate >= low_threshold
            and last is not None
            and last >= cutoff
        )
    if catalog_class == "custom":
        return BAND_T1 if in_use else BAND_T2
    return BAND_T3 if in_use else BAND_T4


def within_band_sort_key(
    band: str, evidence_object: dict, name: str
) -> tuple[float, str]:
    """The §5.4 deterministic in-band ordering key (ascending sort).

    Entities order by ``record_count`` descending then name; T1/T3
    fields by ``population_rate`` descending; T2 fields by
    ``last_populated_at`` descending (most-recently-abandoned first,
    the freshest ghost trail); ties and the remaining bands by name
    ascending. Grouping T1/T2 fields under their parent entity is the
    renderer's composition — it needs the parents' evidence too.
    """
    metrics = evidence_object.get("metrics") or {}
    lowered = name.strip().lower()
    if evidence_object.get("subject_type") == "entity":
        return (-(metrics.get("record_count") or 0), lowered)
    if band == BAND_T2:
        last = _parse_dt(metrics.get("last_populated_at"))
        return (-last.timestamp() if last else float("inf"), lowered)
    if band in (BAND_T1, BAND_T3):
        return (-(metrics.get("population_rate") or 0.0), lowered)
    return (0.0, lowered)
