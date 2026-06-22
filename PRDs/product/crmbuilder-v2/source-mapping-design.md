# Source Instance Mapping — Design Model

**Status:** Design (SES-174)
**Last Updated:** 06-22-26 00:00
**Related projects:** PRJ-027 (Multi-Instance CRM Connection, Audit & Inventory)
**Supersedes:** PRJ-027 §6 reconcile algorithm (auto-promotion assumption eliminated)

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 06-22-26 | Doug Bower / Claude (SES-174) | Initial design. Establishes the source mapping model: candidate-gated mapping decisions, fractal decision structure, entity/field/value levels, join mapping, temporal change handling across four scenarios. |

---

## 1. Purpose

This document defines the **source mapping model** — the design layer that governs how objects discovered in a source CRM instance are related to objects in the canonical design held in V2.

It replaces the auto-promotion assumption in PRJ-027 §6 (step 3: "no canonical match → create a canonical design object"). Discovery now produces **candidates**; human mapping decisions gate every promotion.

---

## 2. Core principle: the source is a design input, not a design authority

A source instance is a CRM system that exists in the real world. Auditing it produces a structured inventory of what that system contains. That inventory is **design input** — evidence that informs the canonical design — but it is never automatically promoted to canonical design.

Multiple source instances can map to the same canonical design, and each may have a different mapping to it. Therefore **no source can drive the design**. The canonical design stands independently of any source.

This eliminates Option C from the relationship-ownership question: the mapping is strictly an interpretive record, not a mechanism that generates design objects.

---

## 3. Mapping decision types

Every discovered source object requires an explicit human mapping decision. There are four outcomes:

### 3.1 Direct map
Source object A maps to design object B in a 1:1 identity relationship. The value in the source is the value in the design. No translation needed.

### 3.2 Referential map (exact)
Source object A maps to design object B, but they are not the same thing by name or structure. `cPreferredContact` in production maps to `contact_channel` in the design. Same semantic intent, different surface. Value passes through unchanged.

### 3.3 Referential map (interpreted)
Source object A maps to design object B with a translation rule. `cContactType` in production has values `{E, P, T}`; the design's `contact_channel` has values `{email, phone, sms}`. The mapping carries translation logic `E→email, P→phone, T→sms`.

### 3.4 Explicit rejection
Source object A is seen, acknowledged, and deliberately excluded. No design object corresponds to it. The rejection is a decision with a lifecycle — it can be superseded later, but never silently undone.

---

## 4. Fractal decision structure

The mapping decision model applies at three levels. Each level inherits the structural frame established above it.

### 4.1 Entity level
The entity-level mapping establishes the structural frame. A source entity can map to:
- A single design entity (direct or referential)
- Multiple design entities (decomposition — e.g., source `Mentor` → design `Contact` + `MentorProfile`)
- Rejection

When a source entity decomposes into multiple design entities, the traversal path between those design entities is **implicit** — it is inherited from the relationship declared between them in the design layer. The mapping does not re-declare the hop for each field. The design relationship is the authority.

### 4.2 Field level
Field mappings are subordinate to and constrained by the entity-level mapping. A field mapping declares which design entity and field the source field maps to, within the structural frame the entity mapping established. When an entity decomposes into `Contact` + `MentorProfile`, field mappings explicitly declare which of those two entities they land on.

### 4.3 Value level
For enum-typed fields with interpreted mappings, value-level mapping decisions apply the same four-outcome structure to individual enum values. A field mapping with interpreted type translation is not fully resolved until every source enum value has an explicit value-level mapping decision.

A field mapping with outstanding unresolved value mappings is considered **partially resolved**, which is a distinct status from fully resolved or stale.

---

## 5. The join mapping

When an entity-level mapping declares a decomposition — source entity `Mentor` → design entities `Contact` + `MentorProfile` — field mappings on the resulting design entities need a way to locate the correct design record from a source record.

This is a **join condition**, following standard relational database principles. The join is declared once at the entity mapping level and shared by all field mappings beneath it.

The join mapping record carries:
- Source entity + source join field (e.g., `Mentor.email`)
- Design entity + design join field (e.g., `Contact.contact_email`)

Field names on either side may differ. The join mapping explicitly declares both sides. The traversal from the matched design entity to a further-related design entity (e.g., from `Contact` to its linked `MentorProfile`) is implicit from the design relationship between those entities — it is not re-declared per field.

**Completeness rule:** If the entity mapping declares a decomposition into multiple design entities, those design entities must have a declared relationship between them in the design layer. The mapping cannot declare a traversal the design does not support.

---

## 6. The discovery candidate

Audit output is **candidates**, not mapping decisions. The reconciler writes to the `mapping_candidate` table; it never writes directly to mapping tables. Candidates become mapping records only when a human resolves them.

The reconciler suggests resolutions where it can infer confidently — name similarity, type match, precedent from a prior source instance — but always requires human confirmation.

---

## 7. Temporal change model

Mapping records have a lifecycle. Changes on either side of the mapping (source or design) produce **staleness signals**, not automatic updates. The mapping is never silently updated and never silently invalidated. It persists in its last-known-good state with a staleness flag until a human resolves it.

### 7.1 Design changes after mapping is established

When a design object changes, affected mapping records transition to `stale`. Staleness is graduated by severity:

**Rename only** — low severity. The system suggests "this mapping probably still holds, update the pointer." Human confirms.

**Type change** — high severity. Translation logic may now produce wrong values. Human must actively review.

- If all source enum values translate to the new target type: update mapping with translation function, confirm. Staleness clears.
- If some source enum values have no valid translation: those values become new value-level mapping decisions (map, reject, or interpret).

**Structural change to the design entity** (merge, decomposition) — high severity. The traversal path itself may be broken. All field mappings under the affected entity mapping go stale.

### 7.2 Source instance changes after mapping is established

When the next audit discovers changes in the source:

**Source field renamed** — the existing mapping for the old name goes stale with signal "source field no longer found." The new name appears as a new discovery candidate. The system suggests the mapping if field name similarity plus same type plus same enum values provides strong evidence. Human confirms.

**New enum value added** — the field mapping goes stale at low severity. A new value-level mapping decision is queued.

**New field added** — appears as a new discovery candidate on the source entity. Standard mapping decision from scratch. No existing mapping affected.

**Field deleted** — the existing mapping goes stale with signal "source field no longer found." Human confirms whether to retire the mapping or treat as temporary absence.

### 7.3 New source instance added

Mapping decisions are scoped to a `(source instance, canonical design)` pair. When a second source is audited, all its objects start as unresolved candidates — even if identical objects exist in the first source with resolved mappings.

Discovery is bucketed by confidence:

**Bucket 1 — Confident suggestions:** objects that exist in the new source and have an identical resolved mapping in a prior source (same entity name, field name, type, enum values). System suggests the same mapping decision; human confirms or bulk-confirms.

**Bucket 2 — Partial suggestions:** objects with a related prior mapping but differences (different field name, enum values, or type). System suggests a starting point flagged with the differences. Human reviews each one.

**Bucket 3 — Net-new discoveries:** objects with no analog in any prior source mapping. Standard mapping decision from scratch.

Objects in the design with no match in the new source get `absent` membership for that instance. No mapping decision required — absent is a valid state.

The suggestion engine compounds over time: each additional source makes subsequent onboarding faster.

### 7.4 Explicit rejection reversed

A rejection is a decision with a lifecycle. When a rejected source object needs to be promoted:

1. The rejection record is closed (timestamped, reversal reason recorded).
2. A new unresolved candidate is created for the **current** state of the source field.
3. Standard mapping decision process applies against the current state of both the source and the design.

The rejection record is never deleted. It is superseded. The full chain (rejected → reinstated → mapped as X) is preserved and navigable in both directions via `superseded_by` references.

---

## 8. Data model

### 8.1 `source_mapping` — entity-level mapping decision

```
source_mapping
  id
  instance_identifier          FK → instances (the source instance)
  source_entity_name           what the auditor found
  decision_type                direct | decomposition | referential | rejected
  status                       unresolved | resolved | stale | superseded
  stale_reason                 source_changed | design_changed | null
  stale_severity               low | high | null
  resolved_at                  DATETIME
  superseded_by                FK → source_mapping (self-referential chain, nullable)
  notes                        human rationale for the decision
  created_at / updated_at
```

### 8.2 `source_mapping_target` — design entity targets of a source mapping

Separate from `source_mapping` because decomposition produces multiple targets.

```
source_mapping_target
  id
  source_mapping_id            FK → source_mapping
  entity_identifier            FK → entities (ENT-NNN)
```

### 8.3 `source_mapping_join` — join key for locating the correct design record

One record per source_mapping. Structured as a table to support future multi-column joins.

```
source_mapping_join
  id
  source_mapping_id            FK → source_mapping
  source_field_name            e.g. "email"
  design_entity_identifier     FK → entities (ENT-NNN)
  design_field_identifier      FK → fields (FLD-NNN)
```

### 8.4 `field_mapping` — field-level mapping decision

```
field_mapping
  id
  source_mapping_id            FK → source_mapping
  source_field_name            what the auditor found
  decision_type                direct | referential_exact | referential_interpreted | rejected
  status                       unresolved | resolved | stale | superseded
  stale_reason                 source_changed | design_changed | null
  stale_severity               low | high | null
  target_entity_identifier     FK → entities (ENT-NNN)
  target_field_identifier      FK → fields (FLD-NNN)
  resolved_at                  DATETIME
  superseded_by                FK → field_mapping (self-referential chain, nullable)
  notes
  created_at / updated_at
```

### 8.5 `field_mapping_translation` — translation function for interpreted field mappings

Only present when `field_mapping.decision_type = referential_interpreted`.

```
field_mapping_translation
  id
  field_mapping_id             FK → field_mapping
  translation_type             value_map | expression
  expression                   TEXT (nullable; for expression-based translations)
```

### 8.6 `value_mapping` — value-level mapping decision for enum fields

```
value_mapping
  id
  field_mapping_id             FK → field_mapping
  source_value                 e.g. "A"
  decision_type                direct | interpreted | rejected
  target_value                 TEXT (nullable if rejected)
  status                       unresolved | resolved | stale | superseded
  superseded_by                FK → value_mapping (self-referential chain, nullable)
  notes
  created_at / updated_at
```

### 8.7 `mapping_candidate` — pre-decision discovery output

The reconciler writes here. Human resolution writes to the mapping tables above.

```
mapping_candidate
  id
  instance_identifier          FK → instances
  audit_event_id               which audit surfaced this
  candidate_type               entity | field | value
  source_entity_name
  source_field_name            null for entity-level candidates
  source_value                 null for entity/field candidates
  suggested_mapping_id         FK → source_mapping | field_mapping | value_mapping (nullable)
  suggestion_confidence        high | medium | low | null
  suggestion_basis             identical_to_inst_NNN | name_similarity | type_match | null
  resolved                     BOOLEAN
  resolved_at                  DATETIME (nullable)
  resolved_to                  FK → source_mapping | field_mapping | value_mapping (nullable)
  created_at
```

---

## 9. Key invariants

These invariants hold across the entire mapping model:

1. **Candidates gate promotion.** The reconciler never writes to mapping tables directly. Candidates become mapping records only through human resolution.

2. **Mappings never update automatically.** Changes on either side (source or design) produce staleness signals. The human resolves staleness.

3. **Rejections are lifecycle records.** A rejection can be superseded but never deleted. The full decision chain is permanent.

4. **The design is the authority.** No source can drive design objects. The mapping is an interpretive record.

5. **Mappings are per-(source instance, design) pair.** Two source instances can have different mappings to the same design object.

6. **The join belongs to the entity mapping.** Field mappings inherit the traversal path; they do not re-declare it.

7. **A field mapping is not fully resolved until all value mappings beneath it are resolved** (for interpreted enum fields).

---

## 10. Relationship to PRJ-027

This design extends and partially supersedes PRJ-027's reconcile algorithm (§6). The changes are:

- Step 3 ("no canonical match → create a canonical design object; mark membership present") is replaced by: "no canonical match → create a `mapping_candidate`; mark as unresolved; membership state is `candidate_pending` until resolved."
- The `instance_membership` join gains two new states beyond `present/drifted/absent`: `candidate_pending` (discovered, awaiting mapping decision) and `mapping_stale` (mapping existed but has become stale).
- The `mapping_candidate` table is new; all other PRJ-027 structures remain valid.

The PRJ-027 open question on canonical object identity (§12) is partially answered by this model: identity matching is the reconciler's suggestion function (name similarity + type + enum values), but it is always human-confirmed, so a miss in the matching heuristic is recoverable through the candidate resolution workflow.

---

## 11. Open questions

- **Multi-column join keys.** The `source_mapping_join` table supports one join column per side per source mapping. If a join condition requires multiple columns, the table needs a cardinality extension. Deferred pending a real case.

- **Expression-based translation functions.** The `field_mapping_translation.expression` field is a placeholder. The neutral expression AST from PRJ-025 (the `rule`/formula model) is the likely home for this. Deferred to the PRJ-025 integration pass.

- **Candidate UI surface.** The desktop panel for reviewing and resolving candidates is not designed here. It is a follow-on PI under PRJ-027.

- **Membership state extensions.** The two new `instance_membership` states (`candidate_pending`, `mapping_stale`) need to be formally added to the PRJ-027 §5 membership join spec. Deferred to the PI-185 design pass.

---

*End of document.*
