# PI-215 — Reconciliation-Merge Engine: Architecture

**Wave 2 of the multi-agent release pipeline build** (build plan §19; `blocked_by`
PI-205 + PI-208, both merged). Architecture-phase deliverable for **PI-215** —
"Build the reconciliation-merge engine." Branched off `main` (Wave 0+1 merged).

Governing design: `multi-agent-release-pipeline-architecture.md` §5.4 / §16.5
(DEC-483…487, REQ-217…223). Implements RC-1…RC-7.

## 1. Scope

PI-215 builds the **merge engine + the typed conflict store + the reconciliation
gate**. It does **not** author the demanded changes (those are upstream input)
and does **not** write `vN+1` (RC-5 — that is architecture planning, PI-209, which
consumes the reconciled delta-set). Requirements are not versioned (RC-5).

## 2. Inputs & the merge shape (RC-2)

The engine reconciles, per touched artifact, a set of **demanded deltas** against
the artifact's **live base** (the latest *shipped* version from PI-208's
`artifact_versions.live()` — `{}` if none). A delta is the engine's input
contract (how a requirement authors a delta is upstream/out-of-scope):

```
{ requirement_identifier, artifact_type, artifact_identifier,
  field,            # "" for an entity/artifact-level attribute
  facet,            # e.g. "required", "type", "options"; "__field__" for add/remove
  op,               # "set" | "add" | "remove"
  value }           # demanded value (set/add); ignored for remove
```

Base/merged shape (a simple, generic convention so the engine stays artifact-
agnostic): `{"fields": {name: {facet: value}}, "attributes": {facet: value}}`.

It is an **N-way three-way merge**: one common base, N per-requirement deltas →
`merged = base + deltas`, order-independent (RC-2).

## 3. The facet taxonomy (RC-3) — the pure core

`access/reconciliation.py` `reconcile_artifact(base, deltas) -> {merged,
conflicts}` is a **pure, deterministic** function. Deltas group by field, then by
facet; classification:

| Class | Condition | Resolution |
|---|---|---|
| **NONE** | facet not touched | keep base |
| **IDENTICAL** | same facet, one distinct value | apply once |
| **COMPOSE** | different facets of one field | each facet resolves independently |
| **ADDITIVE-UNION** | `op=add` set-valued facet (e.g. `options`) | union the added values |
| **CONFLICT — facet_value** | `op=set`, >1 distinct value on one facet | escalate |
| **CONFLICT — remove_vs_modify** | a `remove` and any modify on one field | escalate |
| **CONFLICT — field_redefinition** | two `__field__` adds of one new field with differing facets | escalate (subsumed by facet_value per facet) |

The first four auto-merge with no judgment and are tagged with their demanding
requirement(s) (RC-7); only CONFLICT escalates (RC-4).

## 4. The conflict store (RC-4)

`reconciliation_conflicts` table — an engagement-scoped satellite (surrogate PK,
composite FK to `releases`), **outside** the refs/change_log discipline (no new
entity type, no vocab/CHECK churn). Keyed `UNIQUE(engagement_id,
release_identifier, artifact_type, artifact_identifier, facet)`:

| Column | Notes |
|---|---|
| `release_identifier`, `artifact_type`, `artifact_identifier`, `facet` | the conflict locus |
| `conflict_type` | `facet_value` / `remove_vs_modify` / `field_redefinition` |
| `competing` (JSON) | `[{requirement, op, value}]` — the contending demands |
| `status` | `open` / `resolved` |
| `resolved_value` (JSON) | the chosen value (on resolve) |
| `resolving_decision_identifier` | the governing decision (RC-4/RC-7; a soft `DEC-` reference, not a refs edge — keeps the satellite lean) |

The reconciler **never** resolves a conflict itself (RC-4); a same-facet
contradiction is settled by a governed decision via `resolve_conflict`.

## 5. Orchestration, single-writer & re-runnability (RC-6)

`reconcile_release(session, release, demands)`:
1. gate the release is in `reconciliation`;
2. group demands by artifact; process artifacts in **intra-model dependency
   order — entities & personas before associations** (an association binds
   entities);
3. per artifact: base ← `artifact_versions.live`, run `reconcile_artifact`;
4. **upsert** conflicts keyed on `(release, artifact, facet)` — a still-`open`
   conflict is refreshed, a new one created `open`, an existing **`resolved`** one
   is left intact (resolutions stick across re-runs); conflicts no longer present
   are cleared;
5. return the per-artifact reconciled **delta-set** (auto-merged + resolved
   values), each change carrying its requirement provenance (RC-5/RC-7).

One reconciler per release (the release's `reconciliation` stage) over the static
frozen demand set → deterministic and re-runnable (RC-6).

## 6. The gate (RC-1)

`releases.transition` `reconciliation → architecture_planning` is gated: it
rejects while any `open` `reconciliation_conflict` exists for the release. A
release cannot leave reconciliation with an unresolved model conflict.

## 7. Resolution (RC-4 / RC-7)

`resolve_conflict(session, conflict_id, *, decision_identifier, resolved_value)` —
records the governing decision + the chosen value, flips `open → resolved`. The
decision is the human/governed choice (pick A / pick B / synthesize); a follow-on
requirement amend uses the existing `requirement_changed_by_decision` path.

## 8. API

- `POST /releases/{id}/reconcile` `{demands:[…]}` → run; returns `{delta_sets,
  conflicts}`.
- `GET /releases/{id}/reconciliation-conflicts?status=` → list.
- `POST /reconciliation-conflicts/{id}/resolve` `{decision_identifier,
  resolved_value}` → resolve.

## 9. Schema / migration

`reconciliation_conflicts` table; SQLite `0067` + PG `0024` (`create_table`, no
CHECK rebuilds). Added to the 0038 scoped-tables allowlist.

## 10. Tests

- pure `reconcile_artifact`: NONE/IDENTICAL/COMPOSE/ADDITIVE-UNION auto-merge;
  facet_value, remove_vs_modify conflicts; N-way order-independence; base merge.
- `reconcile_release`: dependency order; base from `artifact_versions.live`;
  conflict upsert + resolved-sticks-on-rerun; determinism.
- the gate: `reconciliation → architecture_planning` rejected with an open
  conflict, allowed once resolved.
- `resolve_conflict` flips status + records the decision.
- SQLite + PG.

## 11. Requirement traceability

| REQ | Where |
|---|---|
| RC-1 no open conflict leaves reconciliation | §6 gate |
| RC-2 three-way merge vs live base | §2 + `artifact_versions.live` |
| RC-3 facet-grain taxonomy, auto-merge | §3 |
| RC-4 contradiction → governed decision | §4, §7 (reconciler never self-resolves) |
| RC-5 conflict-free delta-set; vN+1 downstream | §5 return; no version write |
| RC-6 single-writer, dependency-ordered, deterministic | §5 |
| RC-7 provenance: change→requirement, conflict→decision | §3 tags, §4 resolving_decision |
