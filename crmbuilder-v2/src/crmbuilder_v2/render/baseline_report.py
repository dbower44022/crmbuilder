"""Baseline Report renderer (WTK-116 design spec).

Renders one Markdown Baseline Report per source system — Master
CRMBuilder PRD v0.2 §7 Activity 5: the machine-produced analog of the
Domain Discovery Report, grouping candidates by a render-time
best-guess domain, showing the standard/custom partition and the
utilization findings, and leading with the gaps-and-ghosts list.

The renderer is strictly a **consumer** of the landed supply side:

* the per-source candidate graph, read via the WTK-097
  ``include_evidence=latest`` projection and filtered client-side to
  records whose snapshots carry the source's label (spec §2.1);
* the manifest pair (``audit-report.json`` + ``utilization-profile
  .json``) for the stock-schema signal that is deliberately never
  deposited as candidates (spec §2.2);
* Phase 1 domain records as the grouping vocabulary (spec §2.3).

Read-only, both directions (spec §1): the module never constructs a
write-capable client — :class:`RenderClient` defines GET-backed list
methods only — and nothing it derives is written back. Deterministic
(spec §7.2): ``rendered_at`` is injected, every metric and flag is
taken verbatim from the inline evidence object, bands go through the
single landed implementation (``normalize.derive_priority_band``), and
all orderings are total. The plan-style split mirrors ``plan_deposit``:
:func:`fetch_render_inputs` does the reads, :func:`build_report_model`
is pure, :func:`render_markdown` is pure string assembly.

Run output discipline (spec §6.3): the *report* carries bounded
record-data excerpts by design; the CLI's stdout and any log carry
section names, counts, and paths only — never a cell value.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from crmbuilder_v2 import __version__ as _RENDERER_VERSION
from crmbuilder_v2.transform.audit_deposit import (
    _entity_in_scope,
    _entity_name,
    _field_name,
    _fields_in_scope,
    load_manifest,
    load_profile,
)
from crmbuilder_v2.transform.normalize import (
    BAND_T3,
    DORMANCY_WINDOW_DAYS,
    LOW_POPULATION_THRESHOLD,
    PRIORITY_BANDS,
    derive_priority_band,
    within_band_sort_key,
)

REPORT_FILENAME = "baseline-report.md"
UNASSIGNED_GROUP = "Unassigned"
GROUP_QUALIFIER = "(best guess — triage assigns)"

# §3 grouping: lexical, transparent, cheap to be wrong. Stop words are
# dropped before scoring; stemming is the trivial plural-strip only.
_STOP_WORDS = frozenset(
    {"a", "an", "and", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with"}
)
# Wire-name keys harvested from a candidate's `Source:` notes block for
# the grouping token set (§3 step 1).
_SOURCE_NAME_KEYS = ("espo_name", "yaml_name", "api_name")

_PLACEHOLDER_DOMAIN_PREFIX = "Baseline: "

_GAP_CATEGORIES = (
    ("G1", "Dormant / empty entities"),
    ("G2", "Low-population fields"),
    ("G3", "Stale fields"),
    ("G4", "Ghost options and undeclared values"),
    ("G5", "Automation referencing missing fields"),
    ("G6", "Empty roles"),
)

_BAND_RANK = {band: rank for rank, band in enumerate(PRIORITY_BANDS)}


# ---------------------------------------------------------------------------
# Client protocol + REST implementation (spec §2 reads, GET-only)
# ---------------------------------------------------------------------------


class RenderClient:
    """GET-only client protocol the fetch path drives (spec §7.1).

    Defines no mutating method — the read-only invariant is structural,
    not behavioral. :class:`RestRenderClient` is the production
    implementation; tests supply an access-layer-backed fake. The five
    candidate list methods return records carrying the WTK-097 §6.1
    ``utilization_evidence`` inline block (``include_evidence=latest``).
    """

    def list_entities(self) -> list[dict]:
        raise NotImplementedError

    def list_fields_with_parents(self) -> list[dict]:
        """Field rows each carrying ``parent_entity_identifier``."""
        raise NotImplementedError

    def list_personas(self) -> list[dict]:
        raise NotImplementedError

    def list_processes(self) -> list[dict]:
        raise NotImplementedError

    def list_manual_configs(self) -> list[dict]:
        raise NotImplementedError

    def list_domains(self) -> list[dict]:
        raise NotImplementedError

    def list_deposit_events(self) -> list[dict]:
        raise NotImplementedError

    def list_wrote_records(self, deposit_event_identifier: str) -> list[dict]:
        """``{target_type, target_id}`` rows of the event's
        ``deposit_event_wrote_record`` edges (the anomaly-PI discovery
        read for the §4.3 header)."""
        raise NotImplementedError


class RestRenderClient(RenderClient):
    """REST client of the live V2 API — GET requests only (spec §1).

    Every request sends the ``X-Engagement`` header (PI-β) and unwraps
    the ``{data, meta, errors}`` envelope, mirroring
    ``RestDepositClient``; non-2xx bodies may bypass the envelope
    (``api/errors.py``), so the raw body is surfaced in the raised
    error.
    """

    def __init__(
        self, base_url: str = "http://127.0.0.1:8765", engagement: str | None = None
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.engagement = engagement

    def _get(self, path: str):
        url = f"{self.base_url}{path}"
        req = urllib_request.Request(url, method="GET")
        if self.engagement:
            req.add_header("X-Engagement", self.engagement)
        try:
            with urllib_request.urlopen(req) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            raise RuntimeError(
                f"GET {path} -> HTTP {exc.code}: "
                f"{exc.read().decode('utf-8', errors='replace')}"
            ) from exc
        if payload.get("errors"):
            raise RuntimeError(f"GET {path} -> errors: {payload['errors']}")
        return payload["data"]

    def list_entities(self) -> list[dict]:
        return self._get("/entities?include_evidence=latest")

    def list_fields_with_parents(self) -> list[dict]:
        fields = self._get("/fields?include_evidence=latest")
        refs = self._get(
            "/references?source_type=field&relationship=field_belongs_to_entity"
        )
        parent_by_field = {r["source_id"]: r["target_id"] for r in refs}
        for row in fields:
            row["parent_entity_identifier"] = parent_by_field.get(
                row["field_identifier"]
            )
        return fields

    def list_personas(self) -> list[dict]:
        return self._get("/personas?include_evidence=latest")

    def list_processes(self) -> list[dict]:
        return self._get("/processes?include_evidence=latest")

    def list_manual_configs(self) -> list[dict]:
        return self._get("/manual-configs?include_evidence=latest")

    def list_domains(self) -> list[dict]:
        return self._get("/domains")

    def list_deposit_events(self) -> list[dict]:
        return self._get("/deposit-events")

    def list_wrote_records(self, deposit_event_identifier: str) -> list[dict]:
        return self._get(
            "/references?source_type=deposit_event"
            f"&source_id={urllib_parse.quote(deposit_event_identifier)}"
            "&relationship=deposit_event_wrote_record"
        )


# ---------------------------------------------------------------------------
# Inputs (spec §2)
# ---------------------------------------------------------------------------


@dataclass
class RenderInputs:
    """The §2 inputs for one source system, as read.

    Candidate lists are filtered to records whose evidence snapshots
    carry ``source_label`` (the §2.1 per-source candidate set);
    ``all_entities`` and ``all_processes`` are the unfiltered reads —
    parent-entity naming for fields and the §2.3 domain process
    vocabulary need records outside this source's candidate set.
    ``manifest``/``profile`` are the §2.2 pair, ``None`` in the §2.4
    DB-only degraded mode (``manifest_note`` then names the path that
    failed — loud, never silent).
    """

    source_label: str
    entities: list[dict]
    fields: list[dict]
    personas: list[dict]
    processes: list[dict]
    manual_configs: list[dict]
    all_entities: list[dict]
    all_processes: list[dict]
    domains: list[dict]
    deposit_events: list[dict]
    anomaly_planning_items: list[str]
    engagement: str | None = None
    manifest: dict | None = None
    profile: dict | None = None
    manifest_path: str | None = None
    profile_path: str | None = None
    manifest_note: str | None = None
    profile_note: str | None = None


def _source_snapshot(record: dict, source_label: str) -> dict | None:
    """The record's §3 inline object for this source, or None."""
    block = record.get("utilization_evidence") or {}
    for snap in block.get("snapshots") or []:
        if snap.get("source_label") == source_label:
            return snap
    return None


def fetch_render_inputs(client: RenderClient, source_label: str) -> RenderInputs:
    """Run the §2.1/§2.3 reads and filter to the named source.

    Refuses (§2.4) when no candidate carries evidence for
    ``source_label`` — a typo'd label must not produce an
    empty-but-plausible report — and when no ``audit_deposit`` event
    names the source (the provenance header would be unrenderable).
    """
    known_labels: set[str] = set()

    def keep(rows: list[dict]) -> list[dict]:
        kept = []
        for row in rows:
            block = row.get("utilization_evidence") or {}
            known_labels.update(block.get("sources") or [])
            if _source_snapshot(row, source_label) is not None:
                kept.append(row)
        return kept

    all_entities = client.list_entities()
    all_processes = client.list_processes()
    entities = keep(all_entities)
    fields = keep(client.list_fields_with_parents())
    personas = keep(client.list_personas())
    processes = keep(all_processes)
    manual_configs = keep(client.list_manual_configs())

    if not (entities or fields or personas or processes or manual_configs):
        known = ", ".join(sorted(known_labels)) or "(none)"
        raise ValueError(
            f"no candidates carry evidence for source {source_label!r}; "
            f"known source labels: {known}"
        )

    events = [
        e
        for e in client.list_deposit_events()
        if e.get("deposit_event_kind") == "audit_deposit"
        and (e.get("deposit_event_apply_context") or {}).get("source_label")
        == source_label
    ]
    events.sort(
        key=lambda e: (
            str(e.get("deposit_event_created_at") or ""),
            e["deposit_event_identifier"],
        ),
        reverse=True,
    )
    if not events:
        raise ValueError(
            f"no audit_deposit event names source {source_label!r}; "
            "the provenance header cannot be rendered"
        )
    anomaly_pis = sorted(
        ref["target_id"]
        for ref in client.list_wrote_records(events[0]["deposit_event_identifier"])
        if ref.get("target_type") == "planning_item"
    )
    return RenderInputs(
        source_label=source_label,
        entities=entities,
        fields=fields,
        personas=personas,
        processes=processes,
        manual_configs=manual_configs,
        all_entities=all_entities,
        all_processes=all_processes,
        domains=client.list_domains(),
        deposit_events=events,
        anomaly_planning_items=anomaly_pis,
        engagement=getattr(client, "engagement", None),
    )


def locate_manifest_pair(event: dict) -> tuple[str | None, str | None]:
    """Resolve the §2.2 manifest pair paths from a deposit event.

    Precedence: the additive ``audit_manifest_path`` apply_context key
    (written by the deposit run since this build); else a ``file://``
    ``source_instance`` (a spreadsheet snapshot — the pair lives in the
    snapshot directory, WTK-111 §4.1). Historical EspoCRM events
    predate the key and resolve to ``(None, None)`` — the explicit
    ``--manifest``/``--profile`` overrides are then required.
    """
    context = event.get("deposit_event_apply_context") or {}
    manifest_path = context.get("audit_manifest_path")
    if not manifest_path:
        uri = context.get("source_instance") or ""
        if uri.startswith("file://"):
            split = urllib_parse.urlsplit(uri)
            snapshot = Path(urllib_parse.unquote(split.path))
            directory = snapshot if snapshot.is_dir() else snapshot.parent
            manifest_path = str(directory / "audit-report.json")
    if not manifest_path:
        return None, None
    return manifest_path, str(Path(manifest_path).parent / "utilization-profile.json")


def attach_manifest_pair(
    inputs: RenderInputs,
    *,
    manifest_path: str | None,
    profile_path: str | None,
) -> RenderInputs:
    """Load the manifest pair onto ``inputs``, degrading loudly (§2.4).

    An unlocatable or unreadable manifest sets ``manifest_note`` (the
    DB-only render); a missing profile beside a present manifest sets
    ``profile_note`` (stock-usage metrics unavailable). Never raises on
    a missing file — degraded modes are render postures, not errors.
    """
    if manifest_path is None:
        inputs.manifest_note = (
            "manifest pair unlocatable: the deposit event carries no "
            "audit_manifest_path and no file:// snapshot URI; pass --manifest"
        )
        return inputs
    inputs.manifest_path = manifest_path
    inputs.profile_path = profile_path
    try:
        inputs.manifest = load_manifest(manifest_path)
    except (OSError, ValueError) as exc:
        inputs.manifest_note = f"manifest unavailable at `{manifest_path}`: {exc}"
        return inputs
    if profile_path is not None:
        try:
            inputs.profile = load_profile(profile_path)
        except (OSError, ValueError) as exc:
            inputs.profile_note = f"profile unavailable at `{profile_path}`: {exc}"
    return inputs


# ---------------------------------------------------------------------------
# The report model (spec §7.1) — pure assembly from RenderInputs
# ---------------------------------------------------------------------------


@dataclass
class ReportModel:
    """Everything :func:`render_markdown` prints, fully ordered.

    Two builds from the same inputs are equal (spec §7.2 / R8); the
    summary is derived from the same members as the body, so the two
    cannot disagree (§4.3).
    """

    source_label: str
    rendered_at: str
    header: dict
    summary: dict
    gaps: list[dict]
    domain_groups: list[dict]
    personas: list[dict]
    stock: dict
    coverage: dict
    handoff: dict


def _stem(token: str) -> str:
    """Trivial plural-strip (§3 step 1) — `s`/`es` only."""
    if re.search(r"(ss|ch|sh|x|z)es$", token):
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss") and len(token) > 3:
        return token[:-1]
    return token


def _tokenize(*texts: object) -> frozenset[str]:
    tokens: set[str] = set()
    for text in texts:
        if not text:
            continue
        for raw in re.split(r"[^a-z0-9]+", str(text).lower()):
            if raw and raw not in _STOP_WORDS:
                tokens.add(_stem(raw))
    return frozenset(tokens)


def _source_block_names(notes: str | None) -> list[str]:
    """Wire names from a candidate's ``Source:`` notes block (§3)."""
    values = []
    for line in (notes or "").splitlines():
        match = re.match(r"\s+(\w+): (.+)$", line)
        if match and match.group(1) in _SOURCE_NAME_KEYS:
            values.append(match.group(2))
    return values


@dataclass
class _DomainVocab:
    identifier: str
    name: str
    name_tokens: frozenset[str]
    text_tokens: frozenset[str]


def _domain_vocabulary(
    domains: list[dict], all_processes: list[dict]
) -> list[_DomainVocab]:
    """The §2.3 grouping vocabulary, identifier ascending.

    The per-source placeholder (``Baseline: …``) is a mechanical
    container, never a domain group (§2.1) — excluded here and noted in
    the coverage appendix instead.
    """
    process_names: dict[str, list[str]] = {}
    for proc in all_processes:
        key = proc.get("process_domain_identifier")
        if key:
            process_names.setdefault(key, []).append(proc["process_name"])
    vocab = []
    for dom in sorted(domains, key=lambda d: d["domain_identifier"]):
        if dom["domain_name"].startswith(_PLACEHOLDER_DOMAIN_PREFIX):
            continue
        vocab.append(
            _DomainVocab(
                identifier=dom["domain_identifier"],
                name=dom["domain_name"],
                name_tokens=_tokenize(dom["domain_name"]),
                text_tokens=_tokenize(
                    dom.get("domain_purpose"),
                    *process_names.get(dom["domain_identifier"], []),
                ),
            )
        )
    return vocab


def _best_guess(tokens: frozenset[str], vocab: list[_DomainVocab]) -> str | None:
    """§3 step 3: shared-token score, domain-name tokens ×2; ties break
    by domain identifier ascending (strict ``>`` over an
    identifier-ascending iteration); score 0 -> None (Unassigned)."""
    best_score = 0
    best_identifier = None
    for dom in vocab:
        score = sum(
            2 if token in dom.name_tokens else 1
            for token in tokens
            if token in dom.name_tokens or token in dom.text_tokens
        )
        if score > best_score:
            best_score = score
            best_identifier = dom.identifier
    return best_identifier


def _metric_absent(evidence: dict | None) -> str:
    """The §4.4 A3-distinguishable empty cell."""
    detail = (evidence or {}).get("detail") or {}
    return "— (schema-only)" if detail.get("schema_only") else "— (no records)"


def _rate(value: object) -> str:
    return f"{float(value) * 100:.1f}%" if value is not None else ""


def _flags_cell(evidence: dict | None) -> str:
    flags = (evidence or {}).get("flags") or {}
    parts = []
    for key in sorted(flags):
        value = flags[key]
        if value is True:
            parts.append(key)
        elif value:
            parts.append(f"{key}: {value}")
    return ", ".join(parts)


def _filter_leaf_attributes(node: object) -> list[str]:
    """Every leaf attribute name in a recovered filter AST (G5)."""
    leaves: set[str] = set()

    def walk(value: object) -> None:
        if isinstance(value, dict):
            attr = value.get("field") or value.get("attribute")
            if isinstance(attr, str):
                leaves.add(attr)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(node)
    return sorted(leaves)


def _manifest_entity(manifest: dict, entity_name: str) -> dict | None:
    for entity in manifest.get("entities") or []:
        names = {
            _entity_name(entity),
            entity.get("yaml_name") or "",
            entity.get("espo_name") or "",
        }
        if entity_name in names:
            return entity
    return None


def _manifest_attribute_names(manifest: dict, entity: dict) -> set[str]:
    """Audited attribute wire names for one manifest entity: every
    field's yaml/api name plus this entity's relationship link names."""
    names: set[str] = set()
    for field_result in entity.get("fields") or []:
        for key in ("yaml_name", "api_name"):
            if field_result.get(key):
                names.add(field_result[key])
    wire_names = {entity.get("yaml_name"), entity.get("espo_name")}
    for rel in manifest.get("relationships") or []:
        if rel.get("entity") in wire_names and rel.get("link"):
            names.add(rel["link"])
        if rel.get("entity_foreign") in wire_names and rel.get("link_foreign"):
            names.add(rel["link_foreign"])
    return names


def _stock_evidence(
    subject_type: str, metrics: dict, profiled_at: str | None, thresholds: dict
) -> dict:
    """A pseudo evidence object for a bare standard item, so its band
    comes from the one landed implementation (§4.6 / §7.2)."""
    return {
        "subject_type": subject_type,
        "catalog_class": "standard",
        "profiled_at": profiled_at,
        "metrics": {k: v for k, v in metrics.items() if v is not None},
        "detail": {"thresholds": thresholds} if thresholds else {},
    }


def build_report_model(
    inputs: RenderInputs,
    *,
    rendered_at: str,
    catalog_attributes=None,
) -> ReportModel:
    """Assemble the full §4 report model — pure, deterministic.

    ``catalog_attributes`` is the optional G5 tier-2 oracle:
    ``(source_system, entity_wire_name) -> set of standard attribute
    names``. ``None`` (an unseeded catalog — the live default) degrades
    the G5 check to manifest-only with a per-item "unverified" note,
    never silently passing or failing (§5.1).
    """
    source_label = inputs.source_label
    newest = inputs.deposit_events[0]
    context = newest.get("deposit_event_apply_context") or {}
    source_system = context.get("source_system") or "espocrm"
    profiled_at = context.get("profiled_at")
    schema_only = profiled_at is None

    # Thresholds in force (§4.3): profile options, else recorded
    # evidence thresholds, else the normalize.py defaults.
    thresholds: dict = {}
    thresholds_origin = "normalize.py defaults"
    profile_options = (inputs.profile or {}).get("options") or {}
    recorded = {
        key: profile_options[key]
        for key in ("dormancy_window_days", "low_population_threshold")
        if key in profile_options
    }
    if recorded:
        thresholds = recorded
        thresholds_origin = "utilization profile options"
    else:
        for row in inputs.entities + inputs.fields:
            snap = _source_snapshot(row, source_label)
            detail = (snap or {}).get("detail") or {}
            if detail.get("thresholds"):
                thresholds = detail["thresholds"]
                thresholds_origin = "recorded evidence detail.thresholds"
                break
    effective_thresholds = {
        "dormancy_window_days": thresholds.get(
            "dormancy_window_days", DORMANCY_WINDOW_DAYS
        ),
        "low_population_threshold": thresholds.get(
            "low_population_threshold", LOW_POPULATION_THRESHOLD
        ),
    }

    # ---- candidate views, each with its source evidence object -------------
    entity_views = []
    for row in inputs.entities:
        evidence = _source_snapshot(row, source_label)
        entity_views.append(
            {
                "identifier": row["entity_identifier"],
                "name": row["entity_name"],
                "status": row.get("entity_status"),
                "kind": row.get("entity_kind"),
                "notes": row.get("entity_notes"),
                "evidence": evidence,
                "band": derive_priority_band(evidence),
            }
        )
    entity_name_by_identifier = {
        row["entity_identifier"]: row["entity_name"] for row in inputs.all_entities
    }
    entity_notes_by_identifier = {
        row["entity_identifier"]: row.get("entity_notes")
        for row in inputs.all_entities
    }
    field_views = []
    for row in inputs.fields:
        evidence = _source_snapshot(row, source_label)
        field_views.append(
            {
                "identifier": row["field_identifier"],
                "name": row["field_name"],
                "status": row.get("field_status"),
                "type": row.get("field_type"),
                "parent": row.get("parent_entity_identifier"),
                "evidence": evidence,
                "band": derive_priority_band(evidence),
            }
        )
    persona_views = []
    for row in inputs.personas:
        evidence = _source_snapshot(row, source_label)
        persona_views.append(
            {
                "identifier": row["persona_identifier"],
                "name": row["persona_name"],
                "status": row.get("persona_status"),
                "evidence": evidence,
            }
        )
    process_views = []
    for row in inputs.processes:
        evidence = _source_snapshot(row, source_label)
        process_views.append(
            {
                "identifier": row["process_identifier"],
                "name": row["process_name"],
                "purpose": row.get("process_purpose"),
                "classification": row.get("process_classification"),
                "status": row.get("process_status"),
                "evidence": evidence,
            }
        )
    manual_config_views = []
    for row in inputs.manual_configs:
        evidence = _source_snapshot(row, source_label)
        manual_config_views.append(
            {
                "identifier": row["manual_config_identifier"],
                "name": row["manual_config_name"],
                "category": row.get("manual_config_category"),
                "instructions": row.get("manual_config_instructions"),
                "status": row.get("manual_config_status"),
                "evidence": evidence,
            }
        )

    # ---- best-guess grouping (§3) ------------------------------------------
    vocab = _domain_vocabulary(inputs.domains, inputs.all_processes)
    domain_name_by_identifier = {v.identifier: v.name for v in vocab}

    def entity_group(name: str, notes: str | None, detail: dict):
        tokens = _tokenize(
            name,
            *_source_block_names(notes),
            detail.get("wire_name"),
            detail.get("yaml_name"),
        )
        return _best_guess(tokens, vocab)

    group_of_entity: dict[str, str | None] = {}
    for view in entity_views:
        detail = (view["evidence"] or {}).get("detail") or {}
        group_of_entity[view["identifier"]] = entity_group(
            view["name"], view["notes"], detail
        )
    # Fields inherit their parent entity's group unconditionally (§3).
    # A parent outside this source's candidate set still anchors its
    # fields: its group is computed from the record alone.
    for view in field_views:
        parent = view["parent"]
        if parent and parent not in group_of_entity:
            group_of_entity[parent] = entity_group(
                entity_name_by_identifier.get(parent, ""),
                entity_notes_by_identifier.get(parent),
                {},
            )

    def scored_group(*texts: object) -> str | None:
        return _best_guess(_tokenize(*texts), vocab)

    # ---- domain groups (D, §4.4) -------------------------------------------
    groups: dict[str, dict] = {}

    def group_bucket(domain_identifier: str | None) -> dict:
        key = domain_identifier or UNASSIGNED_GROUP
        if key not in groups:
            groups[key] = {
                "identifier": domain_identifier,
                "name": domain_name_by_identifier.get(
                    domain_identifier, UNASSIGNED_GROUP
                ),
                "entities": [],
                "processes": [],
                "manual_configs": [],
            }
        return groups[key]

    fields_by_parent: dict[str, list[dict]] = {}
    for view in field_views:
        fields_by_parent.setdefault(view["parent"] or "", []).append(view)
    for parent_fields in fields_by_parent.values():
        parent_fields.sort(
            key=lambda v: (
                _BAND_RANK[v["band"]],
                *within_band_sort_key(v["band"], v["evidence"], v["name"]),
            )
        )

    rendered_entity_parents: set[str] = set()
    entity_entries = []
    for view in entity_views:
        entity_entries.append(view)
        rendered_entity_parents.add(view["identifier"])
    # Parents evidenced only in another source still anchor their
    # fields' table — rendered without this-source evidence, honestly.
    for parent in sorted(fields_by_parent):
        if parent and parent not in rendered_entity_parents:
            entity_entries.append(
                {
                    "identifier": parent,
                    "name": entity_name_by_identifier.get(parent, parent),
                    "status": None,
                    "kind": None,
                    "notes": None,
                    "evidence": None,
                    "band": None,
                }
            )
    for view in sorted(
        entity_entries,
        key=lambda v: within_band_sort_key(
            v["band"] or "", v["evidence"] or {"subject_type": "entity"}, v["name"]
        ),
    ):
        bucket = group_bucket(group_of_entity.get(view["identifier"]))
        bucket["entities"].append(
            {**view, "fields": fields_by_parent.get(view["identifier"], [])}
        )
    for view in sorted(process_views, key=lambda v: v["name"].lower()):
        detail = (view["evidence"] or {}).get("detail") or {}
        bucket = group_bucket(
            scored_group(view["name"], view["purpose"], detail.get("entity"))
        )
        bucket["processes"].append(view)
    for view in sorted(manual_config_views, key=lambda v: v["name"].lower()):
        detail = (view["evidence"] or {}).get("detail") or {}
        bucket = group_bucket(
            scored_group(
                view["name"],
                view["instructions"],
                detail.get("entity") or detail.get("tab_scope"),
            )
        )
        bucket["manual_configs"].append(view)

    domain_groups = [
        groups[key]
        for key in sorted(groups, key=lambda k: (k == UNASSIGNED_GROUP, k))
    ]

    # ---- gaps and ghosts (G, §5) -------------------------------------------
    gaps: list[dict] = []

    def category(code: str, title: str) -> dict:
        block = {"category": code, "title": title, "note": None, "items": []}
        gaps.append(block)
        return block

    def flag_sorted(views: list[dict], metric: str) -> list[dict]:
        def key(view: dict):
            metrics = (view["evidence"] or {}).get("metrics") or {}
            last = metrics.get(metric)
            # Descending timestamp; absent timestamps last; name breaks ties.
            return (
                0 if last is not None else 1,
                "" if last is None else _invert_iso(last),
                view["name"].lower(),
            )

        return sorted(views, key=key)

    not_evaluable_data = (
        "schema-only deposit — data flags unavailable" if schema_only else None
    )

    g1 = category(*_GAP_CATEGORIES[0])
    g1["note"] = not_evaluable_data
    for view in flag_sorted(entity_views, "last_record_created_at"):
        flags = (view["evidence"] or {}).get("flags") or {}
        metrics = (view["evidence"] or {}).get("metrics") or {}
        if flags.get("empty"):
            g1["items"].append(
                {
                    "identifier": view["identifier"],
                    "name": view["name"],
                    "line": "empty — never used (0 records)",
                    "probe": (
                        f"Your current system has {view['name']}, but it has "
                        "never been used — tell me about that."
                    ),
                }
            )
        elif flags.get("dormant"):
            newest_record = metrics.get("last_record_created_at", "unknown")
            g1["items"].append(
                {
                    "identifier": view["identifier"],
                    "name": view["name"],
                    "line": (
                        f"dormant — no longer used (newest record "
                        f"{newest_record})"
                    ),
                    "probe": (
                        f"Your current system tracks {view['name']}, but "
                        f"nothing new has been added since {newest_record} — "
                        "tell me about that."
                    ),
                }
            )

    g2 = category(*_GAP_CATEGORIES[1])
    g2["note"] = not_evaluable_data
    g3 = category(*_GAP_CATEGORIES[2])
    g3["note"] = not_evaluable_data
    g4 = category(*_GAP_CATEGORIES[3])
    g4["note"] = not_evaluable_data
    for view in flag_sorted(field_views, "last_populated_at"):
        evidence = view["evidence"] or {}
        flags = evidence.get("flags") or {}
        metrics = evidence.get("metrics") or {}
        detail = evidence.get("detail") or {}
        parent_name = entity_name_by_identifier.get(view["parent"], "")
        label = f"{parent_name}.{view['name']}" if parent_name else view["name"]
        if flags.get("low_population"):
            g2["items"].append(
                {
                    "identifier": view["identifier"],
                    "name": label,
                    "line": (
                        f"low population ({_rate(metrics.get('population_rate'))}"
                        " of records)"
                    ),
                    "probe": (
                        f"Your current system tracks {label}, but it is filled "
                        f"in on only {_rate(metrics.get('population_rate'))} of "
                        "records — tell me about that."
                    ),
                }
            )
        if flags.get("stale"):
            last = metrics.get("last_populated_at", "unknown")
            g3["items"].append(
                {
                    "identifier": view["identifier"],
                    "name": label,
                    "line": f"stale — last populated {last}",
                    "probe": (
                        f"Your current system tracks {label}, but it hasn't "
                        f"been filled in since {last} — tell me about that."
                    ),
                }
            )
        if flags.get("ghost_options"):
            distribution = detail.get("value_distribution") or {}
            ghosts = sorted(k for k, v in distribution.items() if not v)
            rendered = ", ".join(ghosts) if ghosts else "see value distribution"
            g4["items"].append(
                {
                    "identifier": view["identifier"],
                    "name": label,
                    "line": (
                        f"{flags['ghost_options']} declared option(s) unused "
                        f"({rendered})"
                    ),
                    "probe": (
                        f"{label} offers options no record uses ({rendered}) — "
                        "are those still needed?"
                    ),
                }
            )
        if detail.get("undeclared_values"):
            undeclared = ", ".join(str(v) for v in detail["undeclared_values"])
            g4["items"].append(
                {
                    "identifier": view["identifier"],
                    "name": label,
                    "line": f"undeclared value(s) in data ({undeclared})",
                    "probe": (
                        f"{label} holds values that are not on its declared "
                        f"list ({undeclared}) — tell me about that."
                    ),
                }
            )

    g5 = category(*_GAP_CATEGORIES[4])
    if inputs.manifest is None:
        g5["note"] = (
            "manifest pair unavailable — filter attributes cannot be "
            "resolved against the audited schema"
        )
    else:
        for view in sorted(process_views, key=lambda v: v["name"].lower()):
            detail = (view["evidence"] or {}).get("detail") or {}
            filter_ast = detail.get("filter")
            if filter_ast is None:
                continue
            entity_name = detail.get("entity") or ""
            manifest_entity = _manifest_entity(inputs.manifest, entity_name)
            known = (
                _manifest_attribute_names(inputs.manifest, manifest_entity)
                if manifest_entity
                else set()
            )
            for leaf in _filter_leaf_attributes(filter_ast):
                if leaf in known:
                    continue
                if catalog_attributes is not None and leaf in catalog_attributes(
                    source_system, entity_name
                ):
                    continue
                qualifier = (
                    ""
                    if catalog_attributes is not None
                    else " (unverified — stock fields not in catalog)"
                )
                g5["items"].append(
                    {
                        "identifier": view["identifier"],
                        "name": view["name"],
                        "line": (
                            f"filters on `{leaf}`, which is not in the audited "
                            f"schema of {entity_name}{qualifier}"
                        ),
                        "probe": (
                            f"The view {view['name']} filters on {leaf}, which "
                            "does not appear to exist any more — tell me about "
                            "that."
                        ),
                    }
                )

    if source_system != "spreadsheet":
        g6 = category(*_GAP_CATEGORIES[5])
        member_counts = [
            (view, (view["evidence"] or {}).get("detail") or {})
            for view in sorted(persona_views, key=lambda v: v["name"].lower())
        ]
        evaluable = [
            (view, detail)
            for view, detail in member_counts
            if "member_count" in detail
        ]
        if not evaluable:
            g6["note"] = (
                "role membership is not captured by the v1 audit; review "
                "role assignment in the source admin UI during triage"
            )
        else:
            for view, detail in evaluable:
                if detail["member_count"] == 0:
                    g6["items"].append(
                        {
                            "identifier": view["identifier"],
                            "name": view["name"],
                            "line": "0 members",
                            "probe": (
                                f"The role {view['name']} has no members — is "
                                "it still needed?"
                            ),
                        }
                    )

    # ---- personas (P, §4.5) -------------------------------------------------
    def persona_sort_key(view: dict):
        detail = (view["evidence"] or {}).get("detail") or {}
        return (0 if detail.get("kind") == "role" else 1, view["name"].lower())

    personas_section = []
    for view in sorted(persona_views, key=persona_sort_key):
        detail = (view["evidence"] or {}).get("detail") or {}
        scope_access = detail.get("scope_access")
        personas_section.append(
            {
                "identifier": view["identifier"],
                "name": view["name"],
                "kind": detail.get("kind") or "—",
                "scope_access": (
                    json.dumps(scope_access, sort_keys=True) if scope_access else ""
                ),
                "status": view["status"],
            }
        )

    # ---- stock usage (U, §4.6) ----------------------------------------------
    profile_entities = (inputs.profile or {}).get("entities") or {}
    profile_profiled_at = (inputs.profile or {}).get("profiled_at")
    stock: dict = {
        "state": "ok",
        "note": None,
        "partition": None,
        "t3_entities": [],
        "t3_fields": [],
        "stock_fields_note": None,
    }
    # Bare standard items by manifest entity wire name, shared with the
    # coverage accounting below so the two sections cannot disagree.
    bare_standard: dict[str, dict] = {}
    if source_system == "spreadsheet":
        stock["state"] = "all_custom"
        stock["note"] = (
            "No standard items in scope — a spreadsheet source is all-custom "
            "by construction"
        )
    elif inputs.manifest is None:
        stock["state"] = "manifest_unavailable"
        stock["note"] = inputs.manifest_note or "manifest pair unavailable"
    else:
        partition = {
            "custom_entities": 0,
            "standard_entities": 0,
            "custom_fields": 0,
            "standard_fields": 0,
        }
        native_fields_captured = False
        for entity in inputs.manifest.get("entities") or []:
            entity_class = entity.get("entity_class")
            if entity_class == "custom":
                partition["custom_entities"] += 1
            elif entity_class == "native":
                partition["standard_entities"] += 1
                if not _entity_in_scope(entity):
                    bare_standard[entity.get("espo_name") or ""] = entity
            else:
                # System class never maps (WTK-090 §3.1) — its fields
                # are not part of the partition either; the coverage
                # accounting below still explains them by name.
                continue
            for field_result in entity.get("fields") or []:
                if field_result.get("field_class") == "native":
                    partition["standard_fields"] += 1
                    native_fields_captured = True
                else:
                    partition["custom_fields"] += 1
        stock["partition"] = partition
        if schema_only or inputs.profile is None:
            stock["state"] = "profiling_pending"
            stock["note"] = (
                "Profiling pending — stock usage cannot be assessed"
                if schema_only
                else stock["note"]
                or (
                    inputs.profile_note
                    or "utilization profile unavailable — stock usage cannot "
                    "be assessed"
                )
            )
        else:
            t3_rows = []
            for wire_name, entity in sorted(bare_standard.items()):
                profile_entity = profile_entities.get(wire_name) or {}
                if not profile_entity:
                    continue
                band = derive_priority_band(
                    _stock_evidence(
                        "entity",
                        {
                            "record_count": profile_entity.get("record_count"),
                            "last_record_created_at": profile_entity.get(
                                "last_record_created_at"
                            ),
                        },
                        profile_profiled_at,
                        effective_thresholds,
                    )
                )
                row = {
                    "name": _entity_name(entity),
                    "record_count": profile_entity.get("record_count"),
                    "last_record_created_at": profile_entity.get(
                        "last_record_created_at"
                    ),
                    "band": band,
                }
                if band == BAND_T3:
                    t3_rows.append(row)
            t3_rows.sort(
                key=lambda r: (-(r["record_count"] or 0), r["name"].lower())
            )
            stock["t3_entities"] = t3_rows
            if not native_fields_captured:
                stock["stock_fields_note"] = (
                    "Stock fields were not audited (include_native_fields "
                    "unset); entity-level stock usage only"
                )
            else:
                t3_fields = []
                for entity in inputs.manifest.get("entities") or []:
                    profile_entity = (
                        profile_entities.get(entity.get("espo_name") or "") or {}
                    )
                    profile_fields = profile_entity.get("fields") or {}
                    for field_result in entity.get("fields") or []:
                        if field_result.get("field_class") != "native":
                            continue
                        profile_field = (
                            profile_fields.get(field_result.get("api_name"))
                            or profile_fields.get(field_result.get("yaml_name"))
                            or {}
                        )
                        if not profile_field:
                            continue
                        band = derive_priority_band(
                            _stock_evidence(
                                "field",
                                {
                                    "population_rate": profile_field.get(
                                        "population_rate"
                                    ),
                                    "last_populated_at": profile_field.get(
                                        "last_populated_at"
                                    ),
                                },
                                profile_profiled_at,
                                effective_thresholds,
                            )
                        )
                        if band == BAND_T3:
                            t3_fields.append(
                                {
                                    "name": (
                                        f"{_entity_name(entity)}."
                                        f"{_field_name(field_result)}"
                                    ),
                                    "population_rate": profile_field.get(
                                        "population_rate"
                                    ),
                                    "last_populated_at": profile_field.get(
                                        "last_populated_at"
                                    ),
                                }
                            )
                t3_fields.sort(
                    key=lambda r: (
                        -(r["population_rate"] or 0.0),
                        r["name"].lower(),
                    )
                )
                stock["t3_fields"] = t3_fields

    # ---- coverage appendix (C, §4.7) ----------------------------------------
    coverage: dict = {
        "partial": inputs.manifest is None,
        "buckets": [],
        "manifest_total": None,
        "unexplained": [],
        "t4": [],
        "anomalies": list((inputs.profile or {}).get("anomalies") or []),
        "anomaly_planning_items": list(inputs.anomaly_planning_items),
        "placeholder_note": (
            f"The placeholder domain `Baseline: {source_label}` is a "
            "mechanical container pending Phase 3 triage re-homing, not a "
            "domain group"
        ),
        "snapshot_note": (
            f"Spreadsheet snapshot: `{inputs.manifest_path}` — record-data "
            "excerpts never leave the snapshot's content class (WTK-111 §3.5)"
            if source_system == "spreadsheet" and inputs.manifest_path
            else None
        ),
        "manifest_note": inputs.manifest_note,
    }
    if inputs.manifest is not None:
        buckets: dict[str, int] = {}
        unexplained: list[dict] = []
        t4: list[dict] = []

        def tally(rule: str) -> None:
            buckets[rule] = buckets.get(rule, 0) + 1

        total = 0
        for entity in inputs.manifest.get("entities") or []:
            total += 1
            entity_class = entity.get("entity_class")
            name = _entity_name(entity)
            if _entity_in_scope(entity):
                tally("candidate entities (section D)")
            elif entity_class == "system":
                tally("system class — never maps (WTK-090 §3.1)")
            elif entity_class == "native":
                profile_entity = (
                    profile_entities.get(entity.get("espo_name") or "") or {}
                )
                if inputs.profile is None or not profile_entity:
                    tally("bare standard, unprofiled (WTK-090 §3.1 skip)")
                else:
                    band = derive_priority_band(
                        _stock_evidence(
                            "entity",
                            {
                                "record_count": profile_entity.get("record_count"),
                                "last_record_created_at": profile_entity.get(
                                    "last_record_created_at"
                                ),
                            },
                            profile_profiled_at,
                            effective_thresholds,
                        )
                    )
                    if band == BAND_T3:
                        tally("bare standard in use (section U)")
                    else:
                        tally("bare standard dormant (T4 noise floor)")
                        record_count = profile_entity.get("record_count")
                        t4.append(
                            {
                                "name": name,
                                "kind": "entity",
                                "fact": (
                                    "0 records"
                                    if not record_count
                                    else "newest record "
                                    + str(
                                        profile_entity.get(
                                            "last_record_created_at"
                                        )
                                    )
                                ),
                            }
                        )
            else:
                unexplained.append(
                    {
                        "name": name,
                        "kind": "entity",
                        "reason": f"unrecognized entity_class {entity_class!r}",
                    }
                )
            in_scope = _entity_in_scope(entity)
            custom_field_names = {
                f.get("yaml_name") for f in _fields_in_scope(entity)
            }
            profile_entity = (
                profile_entities.get(entity.get("espo_name") or "") or {}
            )
            profile_fields = profile_entity.get("fields") or {}
            for field_result in entity.get("fields") or []:
                total += 1
                field_class = field_result.get("field_class")
                field_label = f"{name}.{_field_name(field_result)}"
                if field_class in (None, "custom"):
                    if in_scope and field_result.get("yaml_name") in (
                        custom_field_names
                    ):
                        tally("custom fields (section D)")
                    elif not in_scope:
                        tally("fields of excluded entities — never map")
                    else:
                        unexplained.append(
                            {
                                "name": field_label,
                                "kind": "field",
                                "reason": "custom field outside the audit scope",
                            }
                        )
                elif field_class == "native":
                    profile_field = (
                        profile_fields.get(field_result.get("api_name"))
                        or profile_fields.get(field_result.get("yaml_name"))
                        or {}
                    )
                    if inputs.profile is None or not profile_field:
                        tally("stock fields undeposited (WTK-090 §3.2)")
                    else:
                        band = derive_priority_band(
                            _stock_evidence(
                                "field",
                                {
                                    "population_rate": profile_field.get(
                                        "population_rate"
                                    ),
                                    "last_populated_at": profile_field.get(
                                        "last_populated_at"
                                    ),
                                },
                                profile_profiled_at,
                                effective_thresholds,
                            )
                        )
                        if band == BAND_T3:
                            tally("stock fields in use (section U)")
                        else:
                            tally("stock fields dormant (T4 noise floor)")
                            t4.append(
                                {
                                    "name": field_label,
                                    "kind": "field",
                                    "fact": "last populated "
                                    + str(
                                        profile_field.get("last_populated_at")
                                        or "never"
                                    ),
                                }
                            )
                else:
                    unexplained.append(
                        {
                            "name": field_label,
                            "kind": "field",
                            "reason": f"unrecognized field_class {field_class!r}",
                        }
                    )
        coverage["manifest_total"] = total
        coverage["buckets"] = [
            {"rule": rule, "count": buckets[rule]} for rule in sorted(buckets)
        ]
        coverage["unexplained"] = unexplained
        coverage["t4"] = t4

    # ---- summary (S, §4.3) — derived from the assembled model ---------------
    band_totals: dict[str, int] = {}
    for view in entity_views + field_views:
        band_totals[view["band"]] = band_totals.get(view["band"], 0) + 1
    status_counts: dict[str, dict[str, int]] = {}
    for record_type, views in (
        ("entity", entity_views),
        ("field", field_views),
        ("persona", persona_views),
        ("process", process_views),
        ("manual_config", manual_config_views),
    ):
        counts: dict[str, int] = {}
        for view in views:
            status = view.get("status") or "—"
            counts[status] = counts.get(status, 0) + 1
        status_counts[record_type] = counts
    summary = {
        "candidates": status_counts,
        "bands": {band: band_totals[band] for band in sorted(band_totals)},
        "gaps": {
            block["category"]: len(block["items"]) for block in gaps
        },
        "sources_of_record": {
            "manifest": inputs.manifest_path,
            "profile": inputs.profile_path,
        },
    }

    # ---- provenance header (H, §4.3) ----------------------------------------
    header = {
        "source_label": source_label,
        "source_system": source_system,
        "source_instance": context.get("source_instance"),
        "snapshot_at": context.get("snapshot_at"),
        "profiled_at": profiled_at,
        "schema_only": schema_only,
        "deposit_events": [
            {
                "identifier": e["deposit_event_identifier"],
                "outcome": e.get("deposit_event_outcome"),
            }
            for e in inputs.deposit_events
        ],
        "thresholds": effective_thresholds,
        "thresholds_origin": thresholds_origin,
        "engagement": inputs.engagement,
        "anomaly_planning_items": list(inputs.anomaly_planning_items),
        "transform_version": context.get("transform_version"),
        "profiler_version": (inputs.profile or {}).get("profiler_version"),
        "renderer_version": _RENDERER_VERSION,
    }

    handoff = {
        "gap_count": sum(len(block["items"]) for block in gaps),
        "group_count": len(domain_groups),
    }

    return ReportModel(
        source_label=source_label,
        rendered_at=rendered_at,
        header=header,
        summary=summary,
        gaps=gaps,
        domain_groups=domain_groups,
        personas=personas_section,
        stock=stock,
        coverage=coverage,
        handoff=handoff,
    )


def _invert_iso(value: str) -> str:
    """A descending sort key for an ISO timestamp under an ascending
    sort: invert each character's ordinal. Total and deterministic."""
    return "".join(chr(0x10FFFF - ord(ch)) for ch in value)


# ---------------------------------------------------------------------------
# Markdown rendering (spec §4 structure) — pure string assembly
# ---------------------------------------------------------------------------


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(cell or "" for cell in row) + " |")
    return lines


def render_markdown(model: ReportModel) -> str:
    """Render the §4.2 section map. No logic beyond formatting: every
    section renders (absence of findings is itself a finding), every
    number comes from the model verbatim."""
    out: list[str] = []
    header = model.header

    out.append(f"# Baseline Report — {model.source_label}")
    out.append("")
    out.append(
        "Machine-produced working input to Phase 2 discovery and Phase 3 "
        "triage — analogous to the Domain Discovery Report. Nothing in it "
        "is authoritative until reconciled."
    )
    out.append("")

    # H — provenance header
    out.append("## Provenance")
    out.append("")
    dep_list = ", ".join(
        f"{e['identifier']} ({e['outcome']})" for e in header["deposit_events"]
    )
    facts = [
        ("Source label", header["source_label"]),
        ("Source system", header["source_system"]),
        ("Source instance", header["source_instance"]),
        ("Snapshot at", header["snapshot_at"]),
        (
            "Profiled at",
            "schema-only: true" if header["schema_only"] else header["profiled_at"],
        ),
        ("Deposit events (newest first)", dep_list),
        (
            "Thresholds",
            f"{json.dumps(header['thresholds'], sort_keys=True)} "
            f"({header['thresholds_origin']})",
        ),
        ("Engagement", header["engagement"]),
        (
            "Anomaly planning items",
            ", ".join(header["anomaly_planning_items"]) or "none",
        ),
        ("Transform version", header["transform_version"]),
        ("Profiler version", header["profiler_version"]),
        ("Renderer version", header["renderer_version"]),
        ("Rendered at", model.rendered_at),
    ]
    for label, value in facts:
        out.append(f"- **{label}:** {value if value is not None else '—'}")
    out.append("")

    # S — summary
    out.append("## Summary")
    out.append("")
    rows = []
    for record_type in ("entity", "field", "persona", "process", "manual_config"):
        counts = model.summary["candidates"].get(record_type, {})
        rendered = (
            ", ".join(f"{status}: {n}" for status, n in sorted(counts.items()))
            or "0"
        )
        rows.append([record_type, str(sum(counts.values())), rendered])
    out.extend(_table(["Type", "Count", "By status"], rows))
    out.append("")
    bands = model.summary["bands"]
    out.append(
        "- **Bands (entities + fields):** "
        + (", ".join(f"{band}: {n}" for band, n in bands.items()) or "none")
    )
    out.append(
        "- **Gaps and ghosts:** "
        + ", ".join(f"{cat}: {n}" for cat, n in model.summary["gaps"].items())
    )
    sources = model.summary["sources_of_record"]
    out.append(f"- **Manifest:** {sources['manifest'] or '— (unavailable)'}")
    out.append(f"- **Profile:** {sources['profile'] or '— (unavailable)'}")
    out.append("")

    # G — gaps and ghosts (headline, before the candidate body)
    out.append("## Gaps and Ghosts")
    out.append("")
    out.append(
        "Review each item and flag the ones to raise as Phase 2 probes "
        "(phase completion criterion). Probe seeds are advisory wording — "
        "adapt, and never open with them (anchoring discipline, see the "
        "handoff notes)."
    )
    out.append("")
    if not any(block["items"] for block in model.gaps):
        out.append("**No gaps or ghosts detected.**")
        out.append("")
    for block in model.gaps:
        out.append(f"### {block['category']} — {block['title']}")
        out.append("")
        if block["note"] is not None:
            out.append(f"*Not evaluated: {block['note']}.*")
            out.append("")
            continue
        if not block["items"]:
            out.append("none found")
            out.append("")
            continue
        for item in block["items"]:
            out.append(
                f"- **{item['identifier']} {item['name']}** — {item['line']}"
            )
            out.append(f"  - Probe seed: *{item['probe']}*")
        out.append("")

    # D — candidates by best-guess domain
    out.append("## Candidates by Best-Guess Domain")
    out.append("")
    if not model.domain_groups:
        out.append("No candidates to group.")
        out.append("")
    for group in model.domain_groups:
        identifier = f"{group['identifier']} " if group["identifier"] else ""
        out.append(f"### {identifier}{group['name']} {GROUP_QUALIFIER}")
        out.append("")
        for entity in group["entities"]:
            evidence = entity["evidence"]
            metrics = (evidence or {}).get("metrics") or {}
            if evidence is None:
                metrics_line = "(no evidence for this source)"
            elif "record_count" in metrics:
                newest = metrics.get("last_record_created_at")
                metrics_line = f"{metrics['record_count']} records" + (
                    f", newest {newest}" if newest else ""
                )
            else:
                metrics_line = _metric_absent(evidence)
            band = f" — band {entity['band']}" if entity["band"] else ""
            kind = entity["kind"] or "—"
            out.append(
                f"#### {entity['identifier']} {entity['name']} "
                f"({entity['status'] or '—'}){band}"
            )
            out.append("")
            out.append(f"- Kind: {kind}; {metrics_line}")
            flags = _flags_cell(evidence)
            if flags:
                out.append(f"- Flags: {flags}")
            layouts = ((evidence or {}).get("detail") or {}).get("layouts_captured")
            if layouts:
                out.append(f"- Curated UI: layouts captured ({', '.join(layouts)})")
            out.append("")
            if entity["fields"]:
                rows = []
                for view in entity["fields"]:
                    field_evidence = view["evidence"] or {}
                    field_metrics = field_evidence.get("metrics") or {}
                    if "populated_count" in field_metrics:
                        population = (
                            f"{field_metrics['populated_count']} / "
                            f"{_rate(field_metrics.get('population_rate'))}"
                        )
                    else:
                        population = _metric_absent(field_evidence)
                    declared = field_metrics.get("declared_option_count")
                    used = field_metrics.get("used_option_count")
                    options = (
                        f"{used} of {declared} used"
                        if declared is not None and used is not None
                        else ""
                    )
                    rows.append(
                        [
                            view["identifier"],
                            view["name"],
                            view["type"] or "",
                            view["band"],
                            population,
                            str(field_metrics.get("last_populated_at") or ""),
                            options,
                            _flags_cell(field_evidence),
                        ]
                    )
                out.extend(
                    _table(
                        [
                            "Field",
                            "Name",
                            "Type",
                            "Band",
                            "Population",
                            "Last populated",
                            "Options",
                            "Flags",
                        ],
                        rows,
                    )
                )
                out.append("")
        if group["processes"]:
            out.append("**Processes**")
            out.append("")
            for view in group["processes"]:
                detail = (view["evidence"] or {}).get("detail") or {}
                filter_line = json.dumps(detail.get("filter"), sort_keys=True)
                out.append(
                    f"- **{view['identifier']} {view['name']}** "
                    f"({view['classification'] or '—'}) — filter: "
                    f"`{filter_line}`"
                )
            out.append("")
        if group["manual_configs"]:
            out.append("**Manual configuration items**")
            out.append("")
            for view in group["manual_configs"]:
                out.append(
                    f"- **{view['identifier']} {view['name']}** "
                    f"({view['category'] or '—'}, {view['status'] or '—'})"
                )
            out.append("")

    # P — personas
    out.append("## Personas")
    out.append("")
    out.append(
        "Source roles and teams are persona *evidence*, not personas; "
        "triage confirms or merges them against the Phase 1 interview "
        "personas. Empty-role findings are cross-referenced in G6, not "
        "duplicated here."
    )
    out.append("")
    if not model.personas:
        out.append("No roles or teams were discovered in this source.")
        out.append("")
    else:
        rows = [
            [
                view["identifier"],
                view["name"],
                view["kind"],
                f"`{view['scope_access']}`" if view["scope_access"] else "",
                view["status"] or "",
            ]
            for view in model.personas
        ]
        out.extend(
            _table(["Persona", "Name", "Kind", "Scope access", "Status"], rows)
        )
        out.append("")

    # U — standard/custom partition and stock usage
    out.append("## Standard/Custom Partition and Stock Usage")
    out.append("")
    stock = model.stock
    if stock["note"]:
        out.append(f"*{stock['note']}.*")
        out.append("")
    if stock["partition"] is not None:
        partition = stock["partition"]
        out.append(
            f"- Entities discovered: {partition['custom_entities']} custom, "
            f"{partition['standard_entities']} standard"
        )
        out.append(
            f"- Fields discovered: {partition['custom_fields']} custom, "
            f"{partition['standard_fields']} standard"
        )
        out.append(
            "- Custom items are the candidate sections above; bare standard "
            "items deposit nothing by design (WTK-090 §3.2)"
        )
        out.append("")
    if stock["state"] == "ok":
        out.append("### Standard entities in real use (T3)")
        out.append("")
        if stock["t3_entities"]:
            rows = [
                [
                    row["name"],
                    str(row["record_count"]),
                    str(row["last_record_created_at"] or ""),
                    "confirmable into a candidate at triage",
                ]
                for row in stock["t3_entities"]
            ]
            out.extend(_table(["Entity", "Records", "Newest", "Note"], rows))
        else:
            out.append("none found")
        out.append("")
        out.append("### Standard fields in real use (T3)")
        out.append("")
        if stock["stock_fields_note"]:
            out.append(f"*{stock['stock_fields_note']}.*")
        elif stock["t3_fields"]:
            rows = [
                [
                    row["name"],
                    _rate(row["population_rate"]),
                    str(row["last_populated_at"] or ""),
                ]
                for row in stock["t3_fields"]
            ]
            out.extend(_table(["Field", "Population", "Last populated"], rows))
        else:
            out.append("none found")
        out.append("")

    # C — coverage appendix
    out.append("## Coverage Appendix")
    out.append("")
    coverage = model.coverage
    if coverage["partial"]:
        out.append(
            "**PARTIAL COVERAGE** — the manifest pair was unavailable "
            f"({coverage['manifest_note'] or 'no path resolved'}); the "
            "reconciliation accounting below could not run."
        )
        out.append("")
    else:
        explained = sum(b["count"] for b in coverage["buckets"])
        unexplained_count = len(coverage["unexplained"])
        out.append("Reconciliation (manifest items = rendered + named exclusions):")
        out.append("")
        for bucket in coverage["buckets"]:
            out.append(f"- {bucket['rule']}: {bucket['count']}")
        out.append(
            f"- **Total:** {coverage['manifest_total']} manifest items = "
            f"{explained} explained + {unexplained_count} unexplained"
        )
        out.append("")
        if coverage["unexplained"]:
            out.append(
                f"**RECONCILIATION FAILURE — {unexplained_count} unexplained "
                "item(s):**"
            )
            out.append("")
            for item in coverage["unexplained"]:
                out.append(
                    f"- {item['kind']} {item['name']}: {item['reason']}"
                )
            out.append("")
        out.append("### T4 — standard + dormant (noise floor)")
        out.append("")
        if coverage["t4"]:
            for item in coverage["t4"]:
                out.append(f"- {item['kind']} {item['name']} — {item['fact']}")
        else:
            out.append("none")
        out.append("")
    out.append("### Anomalies")
    out.append("")
    if coverage["anomalies"] or coverage["anomaly_planning_items"]:
        for anomaly in coverage["anomalies"]:
            rendered = (
                json.dumps(anomaly, sort_keys=True)
                if isinstance(anomaly, dict)
                else str(anomaly)
            )
            out.append(f"- {rendered}")
        for pi in coverage["anomaly_planning_items"]:
            out.append(f"- Anomaly planning item: {pi}")
    else:
        out.append("none recorded")
    out.append("")
    out.append(f"- {coverage['placeholder_note']}")
    if coverage["snapshot_note"]:
        out.append(f"- {coverage['snapshot_note']}")
    out.append("")

    # N — Phase 2/3 handoff notes
    out.append("## Phase 2/3 Handoff Notes")
    out.append("")
    out.append(
        "- **Anchoring discipline:** this report is withheld from the "
        "stakeholder during Phase 2 until their unprompted account is "
        "captured; ghosts are introduced as probes, never as the opening "
        "frame (Master CRMBuilder PRD §7)."
    )
    out.append(
        f"- The consultant reviews the gaps-and-ghosts list "
        f"({model.handoff['gap_count']} item(s)) and flags the ones to "
        "raise as probes — a Phase 1.5 completion criterion."
    )
    out.append(
        f"- Phase 3 triage sessions batch by the {model.handoff['group_count']} "
        "domain group(s) above (Master CRMBuilder PRD §8); group headings "
        "are best guesses — triage assigns."
    )
    out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Output (spec §6) — atomic write, deposit-run integration, CLI
# ---------------------------------------------------------------------------


def write_report(text: str, output_path: str | Path) -> Path:
    """Atomic write — temp file + rename, the family idiom (§6.2)."""
    path = Path(output_path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return path


def render_baseline_report(
    client: RenderClient,
    source_label: str,
    *,
    output_path: str | Path,
    rendered_at: str,
    manifest: dict | None = None,
    profile: dict | None = None,
    manifest_path: str | None = None,
    profile_path: str | None = None,
) -> Path:
    """Fetch, build, render, and write one report — the §6.3 deposit-run
    step (``audit_deposit.main`` calls this with the pair it was invoked
    with) and the programmatic surface of the standalone CLI."""
    inputs = fetch_render_inputs(client, source_label)
    if manifest is not None:
        inputs.manifest = manifest
        inputs.profile = profile
        inputs.manifest_path = manifest_path
        inputs.profile_path = profile_path
    else:
        if manifest_path is None:
            manifest_path, profile_path = locate_manifest_pair(
                inputs.deposit_events[0]
            )
        attach_manifest_pair(
            inputs, manifest_path=manifest_path, profile_path=profile_path
        )
    model = build_report_model(inputs, rendered_at=rendered_at)
    return write_report(render_markdown(model), output_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-render-baseline",
        description=(
            "Render the Baseline Report for one source system from the V2 "
            "candidate graph (WTK-116). Standalone re-render: reads the "
            "current DB state, writes no governance record."
        ),
    )
    parser.add_argument(
        "--source-label", required=True, help="evidence source label to render"
    )
    parser.add_argument(
        "--engagement", required=True, help="X-Engagement header value"
    )
    parser.add_argument(
        "--base-url", default="http://127.0.0.1:8765", help="V2 API base URL"
    )
    parser.add_argument(
        "--manifest", default=None, help="path to audit-report.json (override)"
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="path to utilization-profile.json (override)",
    )
    parser.add_argument(
        "--output", default=None, help="report output path (override)"
    )
    parser.add_argument(
        "--rendered-at",
        default=None,
        help="ISO timestamp stamped into the report (defaults to now)",
    )
    args = parser.parse_args(argv)

    client = RestRenderClient(args.base_url, engagement=args.engagement)
    inputs = fetch_render_inputs(client, args.source_label)
    manifest_path = args.manifest
    profile_path = args.profile
    if manifest_path is None:
        manifest_path, located_profile = locate_manifest_pair(
            inputs.deposit_events[0]
        )
        profile_path = profile_path or located_profile
    elif profile_path is None:
        profile_path = str(
            Path(manifest_path).parent / "utilization-profile.json"
        )
    attach_manifest_pair(
        inputs, manifest_path=manifest_path, profile_path=profile_path
    )
    if inputs.manifest_note:
        print(f"NOTE: DB-only render — {inputs.manifest_note}")
    rendered_at = args.rendered_at or datetime.now(UTC).isoformat()
    model = build_report_model(inputs, rendered_at=rendered_at)
    if args.output:
        output_path = Path(args.output)
    elif inputs.manifest_path:
        output_path = Path(inputs.manifest_path).parent / REPORT_FILENAME
    else:
        output_path = Path(REPORT_FILENAME)
        print(f"NOTE: no manifest home resolved; writing to ./{output_path}")
    written = write_report(render_markdown(model), output_path)
    # Counts and paths only — never a cell value (§6.3).
    gap_count = sum(len(block["items"]) for block in model.gaps)
    print(
        f"Baseline report: {len(model.domain_groups)} domain group(s), "
        f"{gap_count} gaps-and-ghosts item(s), "
        f"{len(model.personas)} persona(s). Written: {written}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
