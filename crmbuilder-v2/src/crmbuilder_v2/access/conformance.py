"""Conformance evaluation — one instance against the declared design (PI-410).

Answers REQ-492/493's question mechanically: for every construct the design
defines and every attribute the compared set declares (REQ-490 / DEC-928,
materialized in :mod:`crmbuilder_v2.access.compared_set`), what does this
instance hold? The evaluation exercises no judgement of its own — it walks the
declaration, reads the audit's stored observations, and reports one entry per
compared attribute with its outcome and reason.

**Honesty over cheer (REQ-491 / DEC-923).** A compared attribute the audit
cannot yet read is ``unknown`` naming why — never omitted, never treated as
matching — and an instance with any unknown compared attribute is never
conformant. Today that includes real gaps (labels, formulas and foreign
coordinates have no reader yet, SES-360's finding), so a strict check reports
``unable_to_be_checked`` until audit coverage grows. That is the requirement
working, not the check failing.

**Statuses (DEC-923's five, minus apply-failed which belongs to the deploy):**
``conformant`` — every compared attribute answered and matching;
``drifted`` — any writable difference;
``named_but_unwritable`` — the ONLY differences are on constructs the applier
has no write path for (fires narrowly, per DEC-923's refinement);
``unable_to_be_checked`` — no differences, but a compared attribute is unknown.
Drift outranks unknown (a gate blocks either way and drift is actionable);
unknown outranks unwritable-only difference (an unverifiable instance cannot
claim its only problems are unwritable ones).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from crmbuilder_v2.access import compared_set
from crmbuilder_v2.access.reconcile_compare import option_sets_equal
from crmbuilder_v2.access.repositories import association as association_repo
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import filtered_tabs as filtered_tab_repo
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.access.repositories import layouts as layout_repo
from crmbuilder_v2.access.repositories import message_template as message_template_repo
from crmbuilder_v2.access.repositories import releases as releases_repo
from crmbuilder_v2.access.repositories import roles as role_repo
from crmbuilder_v2.access.repositories import rule as rule_repo
from crmbuilder_v2.access.repositories import system_settings as system_settings_repo
from crmbuilder_v2.access.repositories import teams as team_repo
from crmbuilder_v2.access.vocab import FIELD_VOCABULARY_VERSION

#: Outcomes of one compared attribute (the reconcile vocabulary, reused).
MATCH = "match"
DRIFT = "drift"
UNKNOWN = "unknown"

#: Overall statuses — DEC-923 / REQ-493.
CONFORMANT = "conformant"
DRIFTED = "drifted"
UNABLE_TO_BE_CHECKED = "unable_to_be_checked"
NAMED_BUT_UNWRITABLE = "named_but_unwritable"

#: Member types the applier has NO write path for today: publish stays closed
#: for roles, teams and filtered tabs until the emitter renders them (REQ-519 /
#: PI-417). A difference on one is real drift but nothing a deploy can fix, so
#: it is named-but-unwritable rather than drifted (DEC-923's narrow refinement).
_UNWRITABLE_MEMBER_TYPES = frozenset({"role", "team", "filtered_tab"})

#: Attributes the applier cannot write even though their member type deploys:
#: the engine cannot alter an existing link's cardinality in place (REQ-443).
_UNWRITABLE_ATTRIBUTES = frozenset({("association", "association_cardinality")})

#: The compared attributes the audit can actually answer today, per member
#: type. A compared attribute outside this set is ``unknown`` naming the gap
#: (REQ-491): the audit simply has no reader for it yet. This inventory is the
#: audit's, not the declaration's — extending the audit shrinks it naturally.
_AUDIT_READS: dict[str, frozenset[str]] = {
    "entity": frozenset({
        "entity_track_activity", "entity_tracks_activities",
        "entity_default_sort_field", "entity_default_sort_direction",
        "entity_text_filter_fields", "entity_full_text_search",
        "entity_full_text_search_min_length", "entity_base_type",
        "entity_icon", "entity_color", "entity_status_field",
        "entity_kanban_view", "entity_count_disabled",
        "entity_optimistic_concurrency", "entity_multiple_assigned_users",
        "entity_formula_scripts",
        # Labels are read and captured into the design on audit, so a present
        # membership implies they were answered.
        "entity_label", "entity_label_plural",
    }),
    "field": frozenset({
        "field_type", "field_required", "field_read_only", "field_unique",
        "field_max_length", "field_default_value", "field_min", "field_max",
        "field_format", "field_numeric_scale", "field_display",
        "field_values", "field_holds", "field_supplied_by", "field_options",
        "field_built_in",
        # Answered by capture-sync: the audit reads these from the instance
        # and writes them INTO the design (REL-025 / PI-374), so a present
        # membership implies they were read and now agree by construction.
        "field_label", "field_foreign_link", "field_foreign_target",
        # Answered structurally for an ordinary field: EspoCRM carries no
        # per-field formula construct, so a design that declares none
        # matches by construction. A DECLARED formula is the special case
        # below — its deployed reality lives in the entity's formula
        # scripts, which have no per-field reader yet.
        "field_formula",
    }),
    "association": frozenset({"association_cardinality"}),
    "layout": frozenset({"layout_content"}),
    "role": frozenset({"role_scope_access", "role_system_permissions"}),
    "team": frozenset(),  # definitions are the name; nothing else is read
    "filtered_tab": frozenset({"filtered_tab_label", "filtered_tab_filter"}),
    "message_template": frozenset({
        "message_template_subject", "message_template_body",
        "message_template_merge_fields",
    }),
    "rule": frozenset({"rule_condition"}),
    "system_setting": frozenset({"value"}),
}

#: (member_type, canonical-list callable, identifier key, display-name key) —
#: mirrors ``reconcile_compare._MEMBER_SOURCES`` plus governed settings.
_SOURCES = (
    ("entity", entity_repo.list_entities, "entity_identifier", "entity_name"),
    ("field", field_repo.list_fields, "field_identifier", "field_name"),
    (
        "association", association_repo.list_associations,
        "association_identifier", "association_name",
    ),
    ("layout", layout_repo.list_layouts, "layout_identifier", "layout_type"),
    ("role", role_repo.list_roles, "role_identifier", "role_name"),
    ("team", team_repo.list_teams, "team_identifier", "team_name"),
    (
        "filtered_tab", filtered_tab_repo.list_filtered_tabs,
        "filtered_tab_identifier", "filtered_tab_label",
    ),
    (
        "message_template", message_template_repo.list_message_templates,
        "message_template_identifier", "message_template_name",
    ),
    ("rule", rule_repo.list_rules, "rule_identifier", "rule_name"),
)

_PRESENT_STATES = frozenset({"present", "drifted"})


def _writable(member_type: str, attribute: str | None) -> bool:
    if member_type in _UNWRITABLE_MEMBER_TYPES:
        return False
    if attribute is not None and (member_type, attribute) in _UNWRITABLE_ATTRIBUTES:
        return False
    return True


def _entry(
    member_type: str,
    member_identifier: str,
    member_name: str | None,
    attribute: str,
    outcome: str,
    reason: str | None,
    read_at: str | None,
) -> dict[str, Any]:
    return {
        "construct": f"{member_type} {member_name or member_identifier}",
        "member_type": member_type,
        "member_identifier": member_identifier,
        "attribute": attribute,
        "outcome": outcome,
        "reason": reason,
        "writable": _writable(member_type, attribute),
        "read_at": read_at,
    }


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value else None


def _member_entries(
    member_type: str,
    obj: dict[str, Any],
    membership: dict[str, Any] | None,
    identifier_key: str,
    name_key: str,
) -> list[dict[str, Any]]:
    member_id = obj[identifier_key]
    name = obj.get(name_key)
    attributes = compared_set.compared_attributes(member_type)
    reads = _AUDIT_READS.get(member_type, frozenset())
    read_at = _iso((membership or {}).get("last_audited_at"))
    entries: list[dict[str, Any]] = []

    if membership is None:
        entries.append(_entry(
            member_type, member_id, name, "presence", UNKNOWN,
            "this construct was never audited on this instance", None,
        ))
        for attribute in attributes:
            entries.append(_entry(
                member_type, member_id, name, attribute, UNKNOWN,
                "this construct was never audited on this instance", None,
            ))
        return entries

    if membership.get("state") not in _PRESENT_STATES:
        entries.append(_entry(
            member_type, member_id, name, "presence", DRIFT,
            "the design defines this construct and the instance does not "
            "carry it", read_at,
        ))
        return entries

    entries.append(_entry(
        member_type, member_id, name, "presence", MATCH, None, read_at
    ))
    override = membership.get("override") or {}
    for attribute in attributes:
        if (
            member_type == "field"
            and attribute == "field_formula"
            and obj.get("field_formula") is not None
        ):
            entries.append(_entry(
                member_type, member_id, name, attribute, UNKNOWN,
                "a declared formula is verified through the entity's "
                "formula scripts, which have no per-field reader yet",
                read_at,
            ))
            continue
        if attribute not in reads:
            entries.append(_entry(
                member_type, member_id, name, attribute, UNKNOWN,
                "the audit has no reader for this attribute yet", read_at,
            ))
            continue
        design_value = obj.get(attribute)
        if attribute in override:
            observed = override[attribute]
            if attribute == "field_options":
                equal = option_sets_equal(design_value, observed)
            else:
                equal = compared_set.attr_equal(
                    member_type, attribute, design_value, observed
                )
            if equal:
                entries.append(_entry(
                    member_type, member_id, name, attribute, MATCH, None,
                    read_at,
                ))
            else:
                entries.append(_entry(
                    member_type, member_id, name, attribute, DRIFT,
                    "the instance holds a different value than the design "
                    "declares", read_at,
                ))
        else:
            # No stored deviation on an attribute the audit reads: the last
            # audit answered it and found it equal to the design.
            entries.append(_entry(
                member_type, member_id, name, attribute, MATCH, None, read_at
            ))
    return entries


def _setting_entries(
    session: Session,
    instance_identifier: str,
    membership_index: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Governed settings: each compares against the instance's OWN declared
    value (REQ-485); a setting with no declared value is not captured —
    reported unknown, never conformant."""
    entries: list[dict[str, Any]] = []
    for setting in system_settings_repo.list_system_settings(
        session, status="confirmed"
    ):
        member_id = setting["system_setting_identifier"]
        name = setting.get("system_setting_name")
        membership = membership_index.get(("system_setting", member_id))
        read_at = _iso((membership or {}).get("last_audited_at"))
        declared_row = system_settings_repo.get_value(
            session,
            system_setting_identifier=member_id,
            instance_identifier=instance_identifier,
        )
        if membership is None:
            entries.append(_entry(
                "system_setting", member_id, name, "value", UNKNOWN,
                "this setting was never audited on this instance", None,
            ))
            continue
        if declared_row is None:
            entries.append(_entry(
                "system_setting", member_id, name, "value", UNKNOWN,
                "the design declares no value for this instance — not "
                "captured (REQ-485)", read_at,
            ))
            continue
        declared = declared_row["value"]
        if membership.get("state") not in _PRESENT_STATES:
            entries.append(_entry(
                "system_setting", member_id, name, "value", DRIFT,
                "the design declares a value and the instance holds none",
                read_at,
            ))
            continue
        override = membership.get("override") or {}
        observed = override.get("value", declared)
        if compared_set.attr_equal("system_setting", "value", declared, observed):
            entries.append(_entry(
                "system_setting", member_id, name, "value", MATCH, None,
                read_at,
            ))
        else:
            entries.append(_entry(
                "system_setting", member_id, name, "value", DRIFT,
                "the instance holds a different value than declared for it",
                read_at,
            ))
    return entries


def _design_version(session: Session) -> str | None:
    """The design version checked against: the latest shipped release.

    The artifact-version spine defines "current" as the highest version whose
    release has shipped (REQ-215), and the stamp writes the frozen release a
    publish ran under (DEC-980) — this is the same axis read from the design
    side. ``None`` when nothing has shipped yet, which the result states
    rather than hides.
    """
    shipped = releases_repo.list_releases(session, status="shipped")
    if not shipped:
        return None
    return sorted(
        (r["release_identifier"] for r in shipped),
        key=lambda i: int(i.split("-")[1]),
    )[-1]


def evaluate_instance(
    session: Session, instance_identifier: str
) -> dict[str, Any]:
    """Evaluate one instance against the declared design (REQ-492/493).

    Pure store read: walks the design records, the compared-set declaration
    and the audit's stored observations. Deterministic — the same store state
    yields an identical result, which is what makes the check's repeatability
    a testable property.
    """
    memberships = membership_repo.list_memberships(
        session, instance_identifier=instance_identifier
    )
    index = {
        (m["member_type"], m["member_identifier"]): m for m in memberships
    }
    entries: list[dict[str, Any]] = []
    for member_type, list_fn, identifier_key, name_key in _SOURCES:
        for obj in list_fn(session):
            status = obj.get(f"{member_type}_status")
            if status is not None and status != "confirmed":
                continue  # candidate/draft design records are not conformance
            entries.extend(_member_entries(
                member_type, obj, index.get((member_type, obj[identifier_key])),
                identifier_key, name_key,
            ))
    entries.extend(_setting_entries(session, instance_identifier, index))

    counts = {MATCH: 0, DRIFT: 0, UNKNOWN: 0, "unwritable_drift": 0}
    for entry in entries:
        if entry["outcome"] == DRIFT and not entry["writable"]:
            counts["unwritable_drift"] += 1
        else:
            counts[entry["outcome"]] += 1

    if counts[DRIFT]:
        status = DRIFTED
    elif counts[UNKNOWN]:
        status = UNABLE_TO_BE_CHECKED
    elif counts["unwritable_drift"]:
        status = NAMED_BUT_UNWRITABLE
    else:
        status = CONFORMANT

    readings = [e["read_at"] for e in entries if e["read_at"]]
    return {
        "instance": instance_identifier,
        "design_version": _design_version(session),
        "vocabulary_version": FIELD_VOCABULARY_VERSION,
        "status": status,
        "counts": counts,
        "entries": entries,
        "oldest_reading_at": min(readings) if readings else None,
        "newest_reading_at": max(readings) if readings else None,
    }
