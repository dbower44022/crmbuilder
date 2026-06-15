# CBM End-to-End Pipeline Proof Plan

> **Status: Draft proposal.** A plan for proving CRMBuilder's full
> requirements→generated-CRM pipeline on one real CBM slice. Not yet executed;
> Stage 1 (generation) is gated on PRJ-025. Drafted 2026-06-15.

## Why

Every stage of the CRMBuilder pipeline has been built and tested in isolation —
audit/baseline capture (Phase 1.5), requirement confirmation and provenance
(Phases 2–3 + the requirements-provenance engine), generation (PRJ-025, in
progress), the V1 Configure deploy engine, and the audit re-read. **No single
real example has gone through all of them in sequence.** This plan takes one
small, real CBM feature from *captured requirement* to *deployed and verified in
the live CRM* — the proof that the framework delivers its core promise, and the
integration test that surfaces the seams between stages.

The data makes a full loop: an existing CRM is read **in** (audit → requirements),
and a generated CRM is written back **out** (design → YAML → deploy), with the
audit then re-reading the result to confirm it matches.

## The slice

Keep the first pass deliberately minimal to isolate pipeline seams from feature
complexity:

- **One custom entity**, already present in CBM's baseline candidates (ENG-002,
  from the 2026-06-15 Phase 1.5 run). Recommended: a small, self-contained one
  (e.g. a profile or resource entity) — *not* the most relational (Engagement,
  Session) on the first pass.
- **~5–8 fields** spanning the common types (text, enum, date, boolean) so
  generation exercises real type mapping, including one `enum` with options.
- **No relationships and no record data** in pass 1. Relationships are pass 2;
  data migration (the keep/transform mappings) is pass 3. Pass 1 proves the
  schema path end to end.

Pick the exact entity at execution time from the Baseline Report's confirmed
candidates; the plan is entity-agnostic.

## Stages

| # | Stage | Pipeline phase | Capability | Status |
|---|-------|----------------|------------|--------|
| 0 | Confirm the slice | Phase 3 triage | confirm candidates + provenance | **exists** |
| 1 | Generate EspoCRM YAML | (generation) | PRJ-025 adapter | **gated — needs PRJ-025** |
| 2 | Deploy to a CRM instance | Phase 12 | V1 Configure engine | **exists** |
| 3 | Verify the deployment | Phase 13 | audit re-read / metadata check | **exists** |

### Stage 0 — Confirm the slice (Phase 3 triage)

From ENG-002's baseline candidates, select the slice entity and fields and move
them `candidate → confirmed` (keep disposition). Wire each to a confirmed
requirement so the provenance/coverage chain holds (the coverage report must show
no orphan for the slice). Defer migration-mapping records (no data this pass).

**Output:** a confirmed entity + fields in ENG-002, each traced to a requirement.
**Verify:** `/coverage/capabilities` shows the slice's planning item(s) non-orphan.

### Stage 1 — Generate EspoCRM YAML (PRJ-025) — the gate

Run the PRJ-025 engine-neutral adapter over the confirmed design records to emit
an EspoCRM YAML program file in the `app-yaml-schema.md` shape.

**Output:** one YAML file ready for the Configure engine.
**Verify:** the YAML passes `validate_program()` (the V1 hard-reject pre-flight)
with zero errors. This is the seam where the engine-neutral design meets the
EspoCRM-specific deploy format; if generation and the schema disagree, it shows
here, before any deploy.
**Dependency:** PRJ-025 must be landed. Until then Stages 2–3 can be rehearsed
with a hand-written YAML for the same slice, to de-risk the deploy/verify path
independently.

### Stage 2 — Deploy to a CRM instance (V1 Configure engine)

Apply the generated YAML through the existing Configure flow.

- **Dry run first** against the CBM **test** instance
  (`crm-test.clevelandbusinessmentors.org`) — non-destructive rehearsal.
- **Then** the CBM **production** instance (`crm.clevelandbusinessmentors.org`,
  live since 2026-06-13). Pass 1 is purely **additive** (a new custom entity +
  its fields); it touches no existing data, which is what makes deploying to
  production acceptable for the proof.

**Output:** the entity + fields created in the live EspoCRM instance.
**Verify:** the Configure run's STEP SUMMARY reports OK (no FAILED steps);
`NOT_SUPPORTED` items, if any, are expected platform constraints, not failures.

### Stage 3 — Verify the deployment (audit re-read)

Run the audit (Phase 1.5 / PRJ-027 introspection) against the deployed instance
for the slice entity and compare to the confirmed design records.

**Output:** a confirmation that the deployed schema matches the spec.
**Verify (the loop closes):** re-auditing the *generated* CRM reproduces the
*confirmed design* — same entity, same fields, same types. Any drift is a
generation or deploy defect, surfaced concretely.

## Success criteria

1. The slice entity and its fields exist in the live CBM EspoCRM instance exactly
   as specified.
2. The deployment is verified by re-audit (or a targeted metadata check), not by
   eyeballing.
3. The full provenance trail is recorded in governance: requirement → confirmed
   design records → generated YAML → deploy event → verification.
4. Coverage stays clean (no orphan capability introduced).

## Decisions to settle before running

- **Which entity** is the slice (pick from confirmed candidates; smallest viable).
- **Production vs test-only** for the first proof — recommend test dry-run always,
  then production for the real proof (additive schema only).
- **How Stage 3 verifies** — full audit re-read vs. a targeted metadata assertion.
- **Governance shape** — which session/conversation records the proof run and how
  the deploy/verify events are captured.

## What this de-risks for the broader goal

Pass 1 (single entity, schema only) proves the spine: design → YAML → deploy →
verify. Pass 2 adds relationships; pass 3 adds record-data migration via the
keep/transform mappings. Each pass extends the same proven chain rather than
integrating everything at once — and the first pass is runnable the moment
PRJ-025 lands, with Stages 2–3 rehearsable on a hand-written YAML before then.
