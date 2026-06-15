"""Entity PRD document emitter (PRJ-025 PI-196 / design §10).

The **second render sink** on the engine-neutral design model. PI-D (the
EspoCRM adapter) is the engine-specific sink: it maps the same design
records to deployable, product-shaped YAML. This module is the *other*
emitter — a **product-neutral, human-readable Entity PRD** generated from
the identical design records. Implements REQ-147: "the design model also
renders human-readable design documents; the generated field table
matches the source records."

It consumes the **raw neutral records** (entities, fields with embedded
options, associations, rules, views, dedup-rules, automations,
message-templates), *not* the EspoCRM-shaped ``build_program_model``
output. Nothing engine-specific leaks in: no internal/wire names, no
platform type enums, no formula/condition syntax — only the neutral
``field_type`` vocabulary, neutral cardinalities, and prose rendered from
the neutral condition AST.

The plan-style split mirrors ``render/baseline_report.py`` and the EspoCRM
adapter: :func:`fetch_prd_inputs` does the reads (impure), filtered to
``confirmed`` records; :func:`build_prd_model` is pure and deterministic
(every ordering total, ``rendered_at`` injected); :func:`render_prd_markdown`
is pure string assembly via the ``tools/docgen`` document model. One
Entity PRD document is produced per confirmed entity.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from pathlib import Path

from crmbuilder_v2 import __version__ as _RENDERER_VERSION
from crmbuilder_v2.adapters.espocrm.client import DesignClient, RestDesignClient
from tools.docgen.models import DocDocument, DocParagraph, DocSection, DocTable

DOC_FILENAME_SUFFIX = "-PRD.md"

# Neutral leaf operator → readable prose fragment. ``is_empty`` /
# ``is_not_empty`` are value-less; the rest take a value rendered after.
_OP_PROSE: dict[str, str] = {
    "eq": "equals",
    "ne": "does not equal",
    "gt": "is greater than",
    "lt": "is less than",
    "gte": "is greater than or equal to",
    "lte": "is less than or equal to",
    "in": "is one of",
    "contains": "contains",
    "is_empty": "is empty",
    "is_not_empty": "is not empty",
}
_OP_NO_VALUE = frozenset({"is_empty", "is_not_empty"})

# Neutral ``association_cardinality`` → readable phrase.
_CARDINALITY_PROSE: dict[str, str] = {
    "one_to_one": "one-to-one",
    "one_to_many": "one-to-many",
    "many_to_many": "many-to-many",
}

# Neutral ``rule_effect`` → the human label for the rule's section row.
_EFFECT_PROSE: dict[str, str] = {
    "required_when": "Required when",
    "visible_when": "Visible when",
    "valid_when": "Valid when",
}


# ---------------------------------------------------------------------------
# Inputs (the §10 reads, GET-only, confirmed-only)
# ---------------------------------------------------------------------------


@dataclass
class PrdInputs:
    """The confirmed neutral design records the emitter renders.

    Every list is filtered to ``confirmed`` records (design noise must not
    reach a design deliverable any more than a deploy artifact). ``fields``
    each carry ``field_options`` (embedded) and ``parent_entity_identifier``
    (the parent edge).
    """

    entities: list[dict]
    fields: list[dict]
    associations: list[dict]
    rules: list[dict]
    views: list[dict]
    dedup_rules: list[dict]
    automations: list[dict]
    message_templates: list[dict]
    engagement: str | None = None


def _confirmed(rows: list[dict], status_key: str) -> list[dict]:
    return [r for r in rows if r.get(status_key) == "confirmed"]


def fetch_prd_inputs(client: DesignClient, *, entity: str | None = None) -> PrdInputs:
    """Run the GET reads and filter to ``confirmed`` records.

    ``entity`` is accepted for API symmetry but does not restrict the reads
    (cross-entity associations and field-reference resolution need the full
    confirmed corpus); the per-entity restriction happens in
    :func:`build_prd_model`.
    """
    return PrdInputs(
        entities=_confirmed(client.list_entities(), "entity_status"),
        fields=_confirmed(client.list_fields(), "field_status"),
        associations=_confirmed(client.list_associations(), "association_status"),
        rules=_confirmed(client.list_rules(), "rule_status"),
        views=_confirmed(client.list_views(), "view_status"),
        dedup_rules=_confirmed(client.list_dedup_rules(), "dedup_rule_status"),
        automations=_confirmed(client.list_automations(), "automation_status"),
        message_templates=_confirmed(
            client.list_message_templates(), "message_template_status"
        ),
        engagement=getattr(client, "engagement", None),
    )


# ---------------------------------------------------------------------------
# The PRD model (pure assembly from PrdInputs)
# ---------------------------------------------------------------------------


@dataclass
class EntityPrd:
    """One entity's fully-ordered, product-neutral PRD model.

    Two builds from the same inputs are equal (determinism): every list is
    deterministically ordered and ``rendered_at`` is injected, not read
    from a clock.
    """

    identifier: str
    name: str
    overview: dict
    fields: list[dict] = dataclass_field(default_factory=list)
    relationships: list[str] = dataclass_field(default_factory=list)
    rules: list[str] = dataclass_field(default_factory=list)
    views: list[dict] = dataclass_field(default_factory=list)
    dedup_rules: list[dict] = dataclass_field(default_factory=list)
    automations: list[dict] = dataclass_field(default_factory=list)
    templates: list[dict] = dataclass_field(default_factory=list)


@dataclass
class PrdModel:
    """The pure result of :func:`build_prd_model` — one document per entity."""

    rendered_at: str
    engagement: str | None
    renderer_version: str
    entities: list[EntityPrd] = dataclass_field(default_factory=list)


def _option_labels(field_row: dict) -> list[str]:
    """Ordered, human option labels for an enum/multi_enum field.

    Mirrors the adapter's option ordering (``option_order`` then value), but
    prefers a human ``option_label`` over the raw ``option_value`` so the
    PRD reads in business terms while still faithfully covering every option.
    """
    opts = list(field_row.get("field_options") or [])
    opts.sort(
        key=lambda o: (
            o.get("option_order") if o.get("option_order") is not None else 0,
            str(o.get("option_value") or ""),
        )
    )
    labels: list[str] = []
    for o in opts:
        label = o.get("option_label")
        value = o.get("option_value")
        if label and value and str(label) != str(value):
            labels.append(f"{label} ({value})")
        elif label:
            labels.append(str(label))
        elif value is not None:
            labels.append(str(value))
    return labels


def _bound_text(field_row: dict) -> str:
    """Min/max bound prose for a number field, or empty."""
    low = field_row.get("field_min")
    high = field_row.get("field_max")
    if low is not None and high is not None:
        return f"{low}–{high}"
    if low is not None:
        return f"≥ {low}"
    if high is not None:
        return f"≤ {high}"
    return ""


def _format_text(field_row: dict) -> str:
    """The Format column: the neutral ``field_format``, refined with scale
    and length detail where the neutral record carries it — all neutral,
    no platform mechanics."""
    parts: list[str] = []
    fmt = field_row.get("field_format")
    if fmt:
        parts.append(str(fmt))
    if field_row.get("field_type") == "number":
        scale = field_row.get("field_numeric_scale")
        if scale:
            parts.append(str(scale))
    bounds = _bound_text(field_row)
    if bounds:
        parts.append(bounds)
    max_length = field_row.get("field_max_length")
    if isinstance(max_length, int):
        parts.append(f"max length {max_length}")
    return "; ".join(parts)


def _field_row(field_row: dict) -> dict:
    """One field's render dict — faithfully derived from the source record.

    The Name/Type/Required/Default cells are read verbatim from the neutral
    field record (REQ-147 acceptance: the rendered table matches source).
    """
    options = _option_labels(field_row)
    default = field_row.get("field_default_value")
    notes: list[str] = []
    if field_row.get("field_read_only"):
        notes.append("read-only")
    if field_row.get("field_unique"):
        notes.append("unique")
    if field_row.get("field_externally_populated"):
        notes.append("externally populated")
    if field_row.get("field_tooltip"):
        notes.append(f"tooltip: {field_row['field_tooltip']}")
    if field_row.get("field_usage_summary"):
        notes.append(f"usage: {field_row['field_usage_summary']}")
    description = field_row.get("field_description") or ""
    if notes:
        description = (
            f"{description} ({'; '.join(notes)})" if description
            else "; ".join(notes)
        )
    return {
        "identifier": field_row["field_identifier"],
        "name": field_row.get("field_name") or "",
        "type": field_row.get("field_type") or "",
        "required": "Yes" if field_row.get("field_required") else "No",
        "default": "" if default is None else str(default),
        "format": _format_text(field_row),
        "options": options,
        "description": description,
    }


def _value_prose(value: object) -> str:
    """Render a leaf condition value as plain text (lists comma-joined)."""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value)


def _condition_prose(node: object, name_of: dict[str, str]) -> str:
    """Render a neutral condition AST to readable prose.

    ``name_of`` maps a field reference (a ``FLD-NNN`` identifier or a field
    name) to its business field name, so the prose reads in business terms.
    Groups render as parenthesized ``and`` / ``or`` joins; a malformed node
    degrades to a compact JSON fragment rather than raising (a PRD is a
    best-effort human render, never a deploy gate).
    """
    if not isinstance(node, dict):
        return json.dumps(node, sort_keys=True)
    if "all" in node or "any" in node:
        key = "all" if "all" in node else "any"
        joiner = " and " if key == "all" else " or "
        children = node.get(key)
        if not isinstance(children, list) or not children:
            return json.dumps(node, sort_keys=True)
        parts = [_condition_prose(child, name_of) for child in children]
        if len(parts) == 1:
            return parts[0]
        return "(" + joiner.join(parts) + ")"
    raw_field = node.get("field")
    op = node.get("op")
    if not isinstance(raw_field, str) or op not in _OP_PROSE:
        return json.dumps(node, sort_keys=True)
    field_name = name_of.get(raw_field, raw_field)
    op_text = _OP_PROSE[op]
    if op in _OP_NO_VALUE:
        return f"{field_name} {op_text}"
    return f"{field_name} {op_text} {_value_prose(node.get('value'))}"


def _rule_prose(
    rule: dict, name_of_field: dict[str, str], entity_name_by_id: dict[str, str]
) -> str:
    """One rule as a readable sentence.

    e.g. "**Approver name** — Required when Application status equals approved."
    """
    effect = _EFFECT_PROSE.get(rule.get("rule_effect"), rule.get("rule_effect") or "")
    subject_id = rule.get("rule_subject_identifier")
    if rule.get("rule_subject_type") == "entity":
        subject = entity_name_by_id.get(subject_id, subject_id or "")
    else:
        subject = name_of_field.get(subject_id, subject_id or "")
    cond = _condition_prose(rule.get("rule_condition"), name_of_field)
    if cond:
        sentence = f"**{subject}** — {effect} {cond}".rstrip()
    else:
        # valid_when with no condition, or a rule carrying only a message.
        sentence = f"**{subject}** — {effect}".rstrip()
    message = rule.get("rule_message")
    if message:
        sentence += f" (message: {message})"
    return sentence


def build_prd_model(
    inputs: PrdInputs, *, rendered_at: str, entity: str | None = None
) -> PrdModel:
    """Assemble the full per-entity PRD model — pure, deterministic.

    Only confirmed records are present in ``inputs`` already; this function
    groups fields under their parent entity, resolves field references on
    associations/rules/views/etc. to business names, and renders the neutral
    conditions to prose. Every ordering is total so two builds compare equal.
    ``entity`` (optional) restricts the produced documents to a single
    entity identifier.
    """
    entities = sorted(inputs.entities, key=lambda e: e["entity_identifier"])
    if entity is not None:
        entities = [e for e in entities if e["entity_identifier"] == entity]
    confirmed_ids = {e["entity_identifier"] for e in inputs.entities}
    entity_name_by_id = {
        e["entity_identifier"]: e.get("entity_name") or "" for e in inputs.entities
    }

    # Fields grouped by parent (confirmed parent only), ordered by identifier.
    fields_by_parent: dict[str, list[dict]] = {}
    # field reference → business name, resolvable by FLD-NNN *and* by name.
    name_of_field: dict[str, str] = {}
    for field_row in inputs.fields:
        parent = field_row.get("parent_entity_identifier")
        if parent not in confirmed_ids:
            continue
        fields_by_parent.setdefault(parent, []).append(field_row)
        fname = field_row.get("field_name") or ""
        name_of_field[field_row["field_identifier"]] = fname
        if fname:
            name_of_field[fname] = fname
    for rows in fields_by_parent.values():
        rows.sort(key=lambda f: f["field_identifier"])

    # Associations touching each entity (as source or target).
    assoc_by_entity: dict[str, list[str]] = {}
    for assoc in sorted(
        inputs.associations, key=lambda a: a["association_identifier"]
    ):
        source_id = assoc.get("association_source_entity")
        target_id = assoc.get("association_target_entity")
        if source_id not in confirmed_ids or target_id not in confirmed_ids:
            continue
        source = entity_name_by_id.get(source_id, source_id or "")
        target = entity_name_by_id.get(target_id, target_id or "")
        cardinality = _CARDINALITY_PROSE.get(
            assoc.get("association_cardinality"),
            assoc.get("association_cardinality") or "related to",
        )
        source_role = assoc.get("association_source_role")
        verb = source_role or "relates to"
        line = f"**{source}** {verb} **{target}** ({cardinality})"
        target_role = assoc.get("association_target_role")
        if target_role:
            line += f"; the {target} side is the *{target_role}*"
        description = assoc.get("association_description")
        if description:
            line += f" — {description}"
        assoc_by_entity.setdefault(source_id, []).append(line)
        if target_id != source_id:
            assoc_by_entity.setdefault(target_id, []).append(line)

    # Rules grouped by their subject's owning entity.
    field_entity: dict[str, str] = {}
    for parent, rows in fields_by_parent.items():
        for row in rows:
            field_entity[row["field_identifier"]] = parent
    rules_by_entity: dict[str, list[str]] = {}
    for rule in sorted(inputs.rules, key=lambda r: r["rule_identifier"]):
        subject_id = rule.get("rule_subject_identifier")
        if rule.get("rule_subject_type") == "entity":
            owning = subject_id
        else:
            owning = field_entity.get(subject_id)
        if owning not in confirmed_ids:
            continue
        rules_by_entity.setdefault(owning, []).append(
            _rule_prose(rule, name_of_field, entity_name_by_id)
        )

    views_by_entity = _group_views(inputs.views, confirmed_ids, name_of_field)
    dedup_by_entity = _group_dedup(inputs.dedup_rules, confirmed_ids, name_of_field)
    autos_by_entity = _group_automations(
        inputs.automations, confirmed_ids, name_of_field
    )
    templates_by_entity = _group_templates(inputs.message_templates, confirmed_ids)

    docs: list[EntityPrd] = []
    for ent in entities:
        eid = ent["entity_identifier"]
        overview = {
            "name": ent.get("entity_name") or "",
            "kind": ent.get("entity_kind") or "—",
            "description": ent.get("entity_description") or "",
            "default_sort": _default_sort_prose(ent, fields_by_parent.get(eid, [])),
            "track_activity": bool(ent.get("entity_track_activity")),
        }
        docs.append(
            EntityPrd(
                identifier=eid,
                name=ent.get("entity_name") or "",
                overview=overview,
                fields=[_field_row(f) for f in fields_by_parent.get(eid, [])],
                relationships=assoc_by_entity.get(eid, []),
                rules=rules_by_entity.get(eid, []),
                views=views_by_entity.get(eid, []),
                dedup_rules=dedup_by_entity.get(eid, []),
                automations=autos_by_entity.get(eid, []),
                templates=templates_by_entity.get(eid, []),
            )
        )

    return PrdModel(
        rendered_at=rendered_at,
        engagement=inputs.engagement,
        renderer_version=_RENDERER_VERSION,
        entities=docs,
    )


def _default_sort_prose(entity_row: dict, field_rows: list[dict]) -> str:
    raw = entity_row.get("entity_default_sort_field")
    if not raw:
        return ""
    name_by_id = {
        f["field_identifier"]: (f.get("field_name") or "") for f in field_rows
    }
    field_name = name_by_id.get(raw, raw)
    direction = entity_row.get("entity_default_sort_direction") or "asc"
    arrow = "descending" if direction == "desc" else "ascending"
    return f"{field_name} ({arrow})"


def _group_views(
    views: list[dict], confirmed_ids: set[str], name_of_field: dict[str, str]
) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for view in sorted(views, key=lambda v: v["view_identifier"]):
        eid = view.get("view_entity")
        if eid not in confirmed_ids:
            continue
        columns = [
            name_of_field.get(c, c) for c in (view.get("view_columns") or [])
        ]
        sort_field = view.get("view_sort_field")
        sort = ""
        if sort_field:
            direction = view.get("view_sort_direction") or "asc"
            arrow = "descending" if direction == "desc" else "ascending"
            sort = f"{name_of_field.get(sort_field, sort_field)} ({arrow})"
        out.setdefault(eid, []).append(
            {
                "name": view.get("view_name") or "",
                "description": view.get("view_description") or "",
                "columns": columns,
                "filter": _condition_prose(view.get("view_filter"), name_of_field)
                if view.get("view_filter") is not None
                else "",
                "sort": sort,
            }
        )
    return out


def _group_dedup(
    dedup_rules: list[dict], confirmed_ids: set[str], name_of_field: dict[str, str]
) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for dr in sorted(dedup_rules, key=lambda d: d["dedup_rule_identifier"]):
        eid = dr.get("dedup_rule_entity")
        if eid not in confirmed_ids:
            continue
        match_fields = [
            name_of_field.get(f, f) for f in (dr.get("dedup_rule_match_fields") or [])
        ]
        normalize = dr.get("dedup_rule_normalize") or {}
        norm_prose = "; ".join(
            f"{name_of_field.get(fref, fref)}: {token}"
            for fref, token in sorted(normalize.items())
        )
        out.setdefault(eid, []).append(
            {
                "name": dr.get("dedup_rule_name") or "",
                "match_fields": match_fields,
                "normalize": norm_prose,
                "on_match": dr.get("dedup_rule_on_match") or "",
                "message": dr.get("dedup_rule_message") or "",
            }
        )
    return out


def _group_automations(
    automations: list[dict], confirmed_ids: set[str], name_of_field: dict[str, str]
) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for auto in sorted(automations, key=lambda a: a["automation_identifier"]):
        eid = auto.get("automation_entity")
        if eid not in confirmed_ids:
            continue
        actions: list[str] = []
        for action in auto.get("automation_actions") or []:
            atype = action.get("type") or "action"
            field_ref = action.get("field")
            value = action.get("value")
            if field_ref is not None and value is not None:
                actions.append(
                    f"{atype}: set {name_of_field.get(field_ref, field_ref)} "
                    f"to {value}"
                )
            elif field_ref is not None:
                actions.append(f"{atype}: {name_of_field.get(field_ref, field_ref)}")
            else:
                actions.append(atype)
        out.setdefault(eid, []).append(
            {
                "name": auto.get("automation_name") or "",
                "description": auto.get("automation_description") or "",
                "trigger": auto.get("automation_trigger") or "",
                "condition": _condition_prose(
                    auto.get("automation_condition"), name_of_field
                )
                if auto.get("automation_condition") is not None
                else "",
                "actions": actions,
            }
        )
    return out


def _group_templates(
    message_templates: list[dict], confirmed_ids: set[str]
) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for mt in sorted(
        message_templates, key=lambda m: m["message_template_identifier"]
    ):
        eid = mt.get("message_template_entity")
        if eid not in confirmed_ids:
            continue
        out.setdefault(eid, []).append(
            {
                "name": mt.get("message_template_name") or "",
                "channel": mt.get("message_template_channel") or "",
                "subject": mt.get("message_template_subject") or "",
                "audience": mt.get("message_template_audience") or "",
            }
        )
    return out


# ---------------------------------------------------------------------------
# Document assembly (via tools/docgen models) + Markdown render
# ---------------------------------------------------------------------------


def build_document(doc: EntityPrd, model: PrdModel) -> DocDocument:
    """Assemble one entity's :class:`DocDocument` — pure, product-neutral.

    Empty sections are omitted cleanly. The document carries only neutral
    design intent; nothing engine-specific appears.
    """
    sections: list[DocSection] = []

    # 1. Entity Overview
    overview = doc.overview
    ov_lines = [
        f"**Name:** {overview['name']}",
        f"**Kind:** {overview['kind']}",
    ]
    if overview["description"]:
        ov_lines.append(f"**Description:** {overview['description']}")
    if overview["default_sort"]:
        ov_lines.append(f"**Default sort:** {overview['default_sort']}")
    ov_lines.append(
        "**Activity tracking:** "
        + ("enabled" if overview["track_activity"] else "not tracked")
    )
    sections.append(
        DocSection(
            title="Entity Overview",
            level=2,
            content=[DocParagraph(line) for line in ov_lines],
        )
    )

    # 2. Fields
    if doc.fields:
        headers = [
            "Name", "Type", "Required", "Default", "Format", "Allowed values",
            "Description",
        ]
        rows = [
            [
                f["name"],
                f["type"],
                f["required"],
                f["default"],
                f["format"],
                "; ".join(f["options"]),
                f["description"],
            ]
            for f in doc.fields
        ]
        sections.append(
            DocSection(
                title="Fields",
                level=2,
                content=[DocTable(headers=headers, rows=rows)],
            )
        )

    # 3. Relationships (Associations)
    if doc.relationships:
        sections.append(
            DocSection(
                title="Relationships",
                level=2,
                content=[DocParagraph(f"- {line}") for line in doc.relationships],
            )
        )

    # 4. Rules
    if doc.rules:
        sections.append(
            DocSection(
                title="Rules",
                level=2,
                content=[DocParagraph(f"- {line}") for line in doc.rules],
            )
        )

    # 5. Views
    if doc.views:
        content: list = []
        for v in doc.views:
            content.append(DocParagraph(f"**{v['name']}**"))
            if v["description"]:
                content.append(DocParagraph(v["description"]))
            if v["columns"]:
                content.append(DocParagraph(f"- Columns: {', '.join(v['columns'])}"))
            if v["filter"]:
                content.append(DocParagraph(f"- Filter: {v['filter']}"))
            if v["sort"]:
                content.append(DocParagraph(f"- Sort: {v['sort']}"))
        sections.append(DocSection(title="Views", level=2, content=content))

    # 6. Duplicate Detection
    if doc.dedup_rules:
        content = []
        for d in doc.dedup_rules:
            content.append(DocParagraph(f"**{d['name']}**"))
            if d["match_fields"]:
                content.append(
                    DocParagraph(f"- Match fields: {', '.join(d['match_fields'])}")
                )
            if d["normalize"]:
                content.append(DocParagraph(f"- Normalization: {d['normalize']}"))
            if d["on_match"]:
                content.append(DocParagraph(f"- On match: {d['on_match']}"))
            if d["message"]:
                content.append(DocParagraph(f"- Message: {d['message']}"))
        sections.append(
            DocSection(title="Duplicate Detection", level=2, content=content)
        )

    # 7. Automation
    if doc.automations:
        content = []
        for a in doc.automations:
            content.append(DocParagraph(f"**{a['name']}**"))
            if a["description"]:
                content.append(DocParagraph(a["description"]))
            content.append(DocParagraph(f"- Trigger: {a['trigger']}"))
            if a["condition"]:
                content.append(DocParagraph(f"- Condition: {a['condition']}"))
            for act in a["actions"]:
                content.append(DocParagraph(f"- Action: {act}"))
        sections.append(DocSection(title="Automation", level=2, content=content))

    # 8. Notification Templates
    if doc.templates:
        headers = ["Name", "Channel", "Subject", "Audience"]
        rows = [
            [t["name"], t["channel"], t["subject"], t["audience"]]
            for t in doc.templates
        ]
        sections.append(
            DocSection(
                title="Notification Templates",
                level=2,
                content=[DocTable(headers=headers, rows=rows)],
            )
        )

    return DocDocument(
        title=f"Entity PRD — {doc.name}",
        subtitle=doc.identifier,
        version=model.renderer_version,
        timestamp=model.rendered_at,
        sections=sections,
    )


def render_prd_markdown(doc: EntityPrd, model: PrdModel) -> str:
    """Render one entity's PRD to a product-neutral Markdown string.

    A self-contained renderer (not the docgen ``md_renderer``, whose title
    page hard-codes EspoCRM wording that would violate neutrality) over the
    docgen document model, so the section/table structure stays consistent.
    """
    document = build_document(doc, model)
    out: list[str] = []
    out.append(f"# {document.title}")
    out.append("")
    out.append(f"**Design record:** {document.subtitle}")
    if model.engagement:
        out.append(f"**Engagement:** {model.engagement}")
    out.append(f"**Generated:** {document.timestamp}")
    out.append(f"**Renderer version:** {document.version}")
    out.append("")
    out.append(
        "Generated from the engine-neutral design records. This document "
        "describes *what the entity must do*, independent of any CRM product."
    )
    out.append("")
    out.append("---")
    out.append("")
    for section in document.sections:
        out.extend(_render_section(section))
    return "\n".join(out).rstrip() + "\n"


def _render_section(section: DocSection) -> list[str]:
    lines: list[str] = []
    prefix = "#" * min(section.level, 4)
    lines.append(f"{prefix} {section.title}")
    lines.append("")
    for item in section.content:
        if isinstance(item, DocSection):
            lines.extend(_render_section(item))
        elif isinstance(item, DocTable):
            lines.extend(_render_table(item))
        elif isinstance(item, DocParagraph):
            lines.append(item.text)
            lines.append("")
    return lines


def _render_table(table: DocTable) -> list[str]:
    lines: list[str] = []
    if table.caption:
        lines.append(f"*{table.caption}*")
        lines.append("")
    lines.append("| " + " | ".join(table.headers) + " |")
    lines.append("| " + " | ".join("---" for _ in table.headers) + " |")
    for row in table.rows:
        padded = list(row) + [""] * (len(table.headers) - len(row))
        cells = [str(c).replace("|", "\\|") for c in padded]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def _doc_filename(doc: EntityPrd) -> str:
    """A deterministic, filesystem-safe per-entity document file name
    (mirrors the adapter's slug convention, with ``-PRD.md``)."""
    slug = "-".join(w for w in re.split(r"[^A-Za-z0-9]+", doc.name) if w)
    base = slug or doc.identifier
    return f"{base}{DOC_FILENAME_SUFFIX}"


# ---------------------------------------------------------------------------
# Atomic write + CLI
# ---------------------------------------------------------------------------


def _atomic_write(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` via a same-directory temp + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def write_documents(model: PrdModel, output_dir: Path) -> list[str]:
    """Render and write one Entity PRD document per entity in ``model``.

    Returns the filenames written (sorted), so the CLI can report paths and
    counts without echoing record values.
    """
    written: list[str] = []
    for doc in model.entities:
        filename = _doc_filename(doc)
        _atomic_write(output_dir / filename, render_prd_markdown(doc, model))
        written.append(filename)
    return sorted(written)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-render-entity-prd",
        description=(
            "Render product-neutral, human-readable Entity PRD documents from "
            "the engine-neutral V2 design records (PRJ-025 PI-196 / REQ-147)."
        ),
    )
    parser.add_argument(
        "--engagement",
        required=True,
        help="engagement identifier or code (sent as the X-Engagement header)",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8765",
        help="V2 REST API base URL (default: http://127.0.0.1:8765)",
    )
    parser.add_argument(
        "--entity",
        default=None,
        help="restrict output to a single entity identifier (ENT-NNN)",
    )
    parser.add_argument(
        "--output",
        default=".",
        help="output directory for the generated Entity PRD documents",
    )
    parser.add_argument(
        "--rendered-at",
        default=None,
        help="ISO timestamp for the document header (default: now, UTC)",
    )
    args = parser.parse_args(argv)

    rendered_at = args.rendered_at or datetime.now(UTC).isoformat()
    client = RestDesignClient(base_url=args.base_url, engagement=args.engagement)
    inputs = fetch_prd_inputs(client, entity=args.entity)
    model = build_prd_model(inputs, rendered_at=rendered_at, entity=args.entity)
    output_dir = Path(args.output)
    written = write_documents(model, output_dir)

    # Section names, counts, and paths only — never a record value.
    print(f"engagement: {args.engagement}")
    print(f"entities rendered: {len(written)}")
    for name in written:
        print(f"  {output_dir / name}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
