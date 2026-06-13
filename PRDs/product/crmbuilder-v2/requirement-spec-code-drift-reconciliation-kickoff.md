# Kickoff — Requirement Spec/Code Drift Reconciliation

**Last Updated:** 06-13-26 00:00
**Operating mode:** ARCHITECTURE
**Surface:** Claude.ai (planning / document authoring; commits AND pushes in the same turn)
**Target engagement:** CRMBUILDER (this is crmbuilder dogfood methodology work)

---

## Purpose

The live `requirement` access-layer code has drifted ahead of its methodology
schema spec on the **rejection model**, and the spec was never updated to match.
This session verifies the exact extent of the drift, decides which side is
canonical, and brings the affected spec(s) back into agreement with the code.

**Known drift (verify against actual files — do not trust this summary):**

- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/requirement.py` (live)
  implements a `rejected` status path: `update_requirement` and
  `patch_requirement` branch on `status == "rejected"`, accept a
  `rejected_by_decision` argument, and call
  `_rejection.enforce_rejected_status` / `_rejection.attach_decision`. The
  patch docstring attributes the atomic edge+flip to **PI-153 §3.4** — moving a
  requirement to `rejected` requires either a `rejected_by_decision` key or a
  pre-existing rejected-by-decision edge.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/requirement.md` v1.0
  (05-25-26) says the opposite: §3.4.1 lists the status enum as
  `candidate` / `confirmed` / `deferred` only; §3.4.5 states rejection is
  handled by **soft-delete, not a `rejected` status**; §3.4.6 states there is
  **no additional status** beyond the three.

So the code adds a decision-gated `rejected` terminal status that the v1.0 spec
explicitly disclaims.

---

## Tier reads (do these first, in order)

1. **Root `crmbuilder/CLAUDE.md`** — confirm this is the governing CLAUDE.md
   before any work; absorb the reference-vocab triad rules, the `{data, meta,
   errors}` envelope, the session lifecycle / close-out conventions, and the
   v2 governance recording rules (V2 topic Governance Recording Method,
   `TOP-013`).
2. **The drifted code** — read in full and characterize the *actual* current
   behavior, not the summary above:
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/requirement.py`
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/_rejection.py`
     (the shared rejection mechanism)
   - `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — the exact
     `REQUIREMENT_STATUSES` set and `REQUIREMENT_STATUS_TRANSITIONS` map (does
     `rejected` appear? what are its valid predecessors/successors?).
3. **The spec** — `PRDs/product/crmbuilder-v2/methodology-schema-specs/requirement.md`
   v1.0, §3.4 in particular.
4. **PI-153 rationale** — find the decision(s) that introduced the
   rejected-by-decision model. Query the live CRMBUILDER engagement (MCP
   `get_planning_item("PI-153")` and the decisions referencing it, or the REST
   API at `127.0.0.1:8765` with the `X-Engagement: CRMBUILDER` header,
   unwrapping `.data`). Capture the decision identifiers and their stated
   rationale — they are the evidence for which side is canonical.

## Scope discovery (do this before deciding)

The rejection-by-decision mechanism lives in shared `_rejection.py`, so the
same drift very likely exists across the **whole methodology-entity cohort**,
not just `requirement`. Before deciding anything, determine the full blast
radius: for each methodology entity whose repository imports `_rejection`
(candidates: `domain`, `entity`, `process`, `persona`, `field`,
`manual_config`, `test_spec`, `crm_candidate`), check whether its
`methodology-schema-specs/*.md` spec still describes rejection as soft-delete-only
with no `rejected` status. Produce a short table: entity → spec says → code
does → drifted? The reconciliation decision should then apply uniformly across
every drifted spec, not piecemeal.

---

## The decision to surface (eight-element template, one decision)

This is consequential: it has real downstream impact (every methodology spec is
the authoring source of truth under the V2 inversion) and there are two
genuinely different outcomes. Bring it to Doug using the consequential-decision
template, then execute on approval:

- **Option A — ratify code as canonical, update the spec(s).** The PI-153
  `rejected`-status + mandatory `rejected_by_decision` edge is the intended
  model; revise §3.4 of `requirement.md` (and every drifted sibling spec) to
  document the `rejected` status, its transition rules, and the decision-edge
  requirement, and rewrite the soft-delete-only-rejection language. Bump each
  spec to v1.1 with a revision-control row and change-log entry.
- **Option B — treat the v1.0 spec as canonical, reconsider the code.** Rejection
  should remain soft-delete-only; PI-153's `rejected` status is the thing to
  unwind. This implies a migration reversal and contradicts a shipped PI.

Likely recommendation is A (PI-153 was a deliberate, migrated, shipped decision,
and decision-gated rejection carries an audit rationale that soft-delete loses)
— but confirm A vs B against PI-153's actual rationale before recommending, and
let Doug make the call.

---

## Deliverables

1. **Drift-analysis finding** — the scope-discovery table plus a precise
   statement of the code-vs-spec delta on the rejection model (rendered in the
   conversation; no separate document needed unless the blast radius is large
   enough to warrant one).
2. **Updated spec(s)** — on approval of Option A, the affected
   `methodology-schema-specs/*.md` files revised to match the code, each bumped
   to v1.1 with a revision-control row and change-log entry, "Last Updated" in
   `MM-DD-YY HH:MM`. Committed AND pushed in the same turn.
3. **Close-out** against the **CRMBUILDER** engagement, per the CLAUDE.md
   session-lifecycle / close-out conventions (authoritative — follow them, do
   not re-derive):
   - close-out payload JSON at
     `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json`, `NNN` verified
     against live CRMBUILDER session heads at close (re-key if a parallel
     session has advanced the head);
   - apply prompt at
     `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md`,
     rendered inline so Doug can scan its net effect;
   - the reconciliation decision recorded as a `DEC` (decided_in → the session),
     `is_about` the spec file(s) it amends; status `Active`.
   - Both files committed AND pushed in the same turn; Doug runs the apply prompt
     via Claude Code.

`topics_covered` in the payload opens with the verbatim seed:
`Seed prompt: "Reconcile the requirement spec/code drift on the rejection model."`

---

## Guardrails

- Verify all behavior against the actual files and the live API — never from
  memory or from this kickoff's summary.
- Do not allocate any governance identifier against unstable heads; verify live
  heads immediately before authoring the payload.
- This session edits **specs and produces governance records only** — it does
  not change `requirement.py`, `_rejection.py`, or `vocab.py`. If the decision
  were ever Option B (reconsider the code), that is a separate
  implementation session with its own Claude Code prompt; this session would
  stop at surfacing it.
- One decision at a time; terse approval is sufficient; execute end-to-end after
  approval with a full review at the end rather than per-step check-ins.
