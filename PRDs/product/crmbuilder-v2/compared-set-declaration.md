# Compared-set declaration — draft for PI-409 / REQ-490

Approved by Doug 2026-08-22 (SES-359 / CNV-320, DEC-928). One row per attribute of
every construct carrying an instance-membership member type. Each row states whether
conformance compares the attribute and, if so, by what rule two values are judged
equal.

Rows marked ⚑ were the seven that required a ruling rather than having one defensible
answer; all seven were approved as recommended. They are left marked so a later reader
can see which lines were decided rather than derived.

This document is the working proposal. The binding form is per-attribute declarations
carried on the design records themselves (REQ-490); PI-409 materializes them from this.

## Equality-rule vocabulary

| Rule | Meaning |
|---|---|
| `exact` | Python `==`, no normalization |
| `bool` | exact boolean |
| `int` | numeric equality; **absent ≠ 0** |
| `str-exact` | exact string, whitespace and case significant |
| `str-trim` | trim leading/trailing whitespace, then exact; case significant |
| `set` | order-insensitive collection equality |
| `seq` | order-**sensitive** sequence equality |
| `map` | key-wise comparison, key order irrelevant |
| `canonical` | normalize to a canonical form, then compare (semantic, not textual) |
| `join-key` | not an attribute comparison — this is the identity used to match design to instance |
| `—` | not compared |

**Null policy (global):** absent and empty are **different**. A field with no default
and a field defaulting to `""` behave differently in EspoCRM, so collapsing them
would hide a real divergence. Any attribute needing the opposite policy says so.

---

## Entity (15)

| Attribute | Compared | Rule | Note |
|---|---|---|---|
| `entity_identifier` | no | — | design's own ID; no counterpart on an instance |
| `entity_name` | identity | `join-key` | the match key, not a compared value |
| `entity_status` | no | — | design lifecycle (candidate/confirmed), not CRM state |
| `entity_kind` | no | — | design classification |
| `entity_description` | no | — | design-record prose; not deployed |
| `entity_notes` | no | — | authoring notes |
| `entity_label` ⚑ | **yes** | `str-trim` | user-visible; see contested set |
| `entity_label_plural` ⚑ | **yes** | `str-trim` | as above |
| `entity_default_sort_field` | yes | `exact` | determines what users see first |
| `entity_default_sort_direction` | yes | `exact` | as above |
| `entity_track_activity` | yes | `bool` | stream/feed flag |
| `entity_tracks_activities` | yes | `bool` | BasePlus activities/history panels (REQ-337) |
| `entity_text_filter_fields` ⚑ | **yes** | `set` | search behaviour; order contested |
| `entity_full_text_search` | yes | `bool` | |
| `entity_full_text_search_min_length` | yes | `int` | absent ≠ 0 |

## Field (24)

| Attribute | Compared | Rule | Note |
|---|---|---|---|
| `field_identifier` | no | — | design's own ID |
| `field_name` | identity | `join-key` | |
| `field_type` | yes | `exact` | already special-cased as a type conflict |
| `field_required` | yes | `bool` | |
| `field_read_only` | yes | `bool` | |
| `field_unique` | yes | `bool` | |
| `field_max_length` | yes | `int` | absent ≠ 0 |
| `field_min` | yes | `exact` | stored as string; absent ≠ `"0"` |
| `field_max` | yes | `exact` | as above |
| `field_numeric_scale` | yes | `exact` | absent ≠ `"0"` |
| `field_default_value` | yes | `exact` | absent ≠ `""` — they behave differently |
| `field_format` | yes | `exact` | |
| `field_formula` ⚑ | **yes** | `canonical` | semantic, not textual; see contested set |
| `field_foreign_link` | yes | `exact` | structural |
| `field_foreign_target` | yes | `exact` | structural |
| `field_label` ⚑ | **yes** | `str-trim` | see contested set |
| `field_tooltip` ⚑ | **no** | — | see contested set |
| `field_description` | no | — | design-record prose |
| `field_notes` | no | — | authoring notes |
| `field_status` | no | — | design lifecycle |
| `field_usage_summary` | no | — | design-record prose |
| `field_externally_populated` ⚑ | **no** | — | see contested set |
| `field_derived_result_type` | no | — | design-side derivation metadata |
| `field_previous_parent_entity_identifier` | no | — | design bookkeeping |

**Enum options** are carried by the `FieldOption` child collection, not a column.
Compared as `set` over `(value, effective-label)` — order-insensitive, per REQ-442,
which exists because ordering produced false drift. For a field with a per-chapter
active subset (REQ-486), the **complete list** is compared identically on every
instance; the active subset is a setting and is not part of this comparison.

## Association (10)

| Attribute | Compared | Rule | Note |
|---|---|---|---|
| `association_identifier` | no | — | |
| `association_name` | identity | `join-key` | |
| `association_source_entity` | yes | `exact` | structural |
| `association_target_entity` | yes | `exact` | structural |
| `association_cardinality` | yes | `exact` | structural |
| `association_source_role` | yes | `exact` | link name on the instance |
| `association_target_role` | yes | `exact` | as above |
| `association_description` | no | — | design-record prose |
| `association_notes` | no | — | |
| `association_status` | no | — | design lifecycle |

## Layout (6)

| Attribute | Compared | Rule | Note |
|---|---|---|---|
| `layout_identifier` | no | — | |
| `layout_entity_identifier` | identity | `join-key` | with `layout_type` |
| `layout_type` | identity | `join-key` | |
| `layout_content` ⚑ | **yes** | `seq` | order IS the visible arrangement; see contested set |
| `layout_status` | no | — | design lifecycle |
| `layout_notes` | no | — | |

Layouts stay fully compared even under zero-direct-CRM-operations, because consuming
applications read `layout/list` and `layout/detail` live as metadata. Portal variants
and `forRoles` per-role variants remain `NOT_SUPPORTED` (DEC-6) and are therefore
**captured but not compared**.

## Role (7)

| Attribute | Compared | Rule | Note |
|---|---|---|---|
| `role_identifier` | no | — | |
| `role_name` | identity | `join-key` | |
| `role_scope_access` | yes | `map` | the security boundary |
| `role_system_permissions` | yes | `map` | |
| `role_description` | no | — | design-record prose |
| `role_status` | no | — | design lifecycle |
| `role_notes` | no | — | |

Roles matter **more** under zero-direct-CRM-operations, not less: they are the access
boundary the consuming applications authenticate through. The API role granting read
on the per-instance settings record (DEC-927) is part of this compared set.

## Team (5)

| Attribute | Compared | Rule | Note |
|---|---|---|---|
| `team_identifier` | no | — | |
| `team_name` | identity | `join-key` | |
| `team_description` | no | — | design-record prose |
| `team_status` | no | — | design lifecycle |
| `team_notes` | no | — | |

Team **definitions** are compared; team **membership** is user data and is not a
design object.

## FilteredTab (6)

| Attribute | Compared | Rule | Note |
|---|---|---|---|
| `filtered_tab_identifier` | no | — | |
| `filtered_tab_entity_identifier` | identity | `join-key` | |
| `filtered_tab_label` ⚑ | **yes** | `str-trim` | user-visible; see contested set |
| `filtered_tab_filter` | yes | `canonical` | condition AST — semantic, not textual |
| `filtered_tab_status` | no | — | design lifecycle |
| `filtered_tab_notes` | no | — | |

---

## Tally

| | Count |
|---|---|
| Compared | 30 |
| Identity / join-key | 9 |
| Not compared | 34 |
| **Total** | **73** |

Plus the `FieldOption` child collection (compared as a set) and, once PI-406 lands,
the settings construct with its per-instance value dimension.

## Still to add after other planning items land

- **Settings** construct (PI-406) — per-instance valued; compared against the
  instance's own declared value, not a shared one.
- **Workflow** member type (PI-413) — presence compared; the instance already carries
  one undeclared workflow.
- **Duplicate-check** configuration — detectable via read-only metadata (DEC-927), so
  it enters the compared set ahead of any write path.
