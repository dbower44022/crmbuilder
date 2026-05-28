# Methodology-Records Ingestion Mechanism — Kickoff

**Document type:** Kickoff prompt (session seed for designing the V2 methodology-records ingestion mechanism)
**Repository:** `crmbuilder`
**Path:** `PRDs/product/crmbuilder-v2/methodology-records-ingestion-kickoff.md`
**Last Updated:** 05-27-26 (re-keyed to main identifiers — see notice below)
**Operating mode:** ARCHITECTURE
**Estimated duration:** One substantive session — design decision plus possibly a follow-on Claude Code prompt for implementation
**Engagement:** CRMBUILDER
**Predecessor session:** SES-100 (Phase 2 Domain Discovery for CRMBUILDER dogfood — 14 candidate domains, 9 personas, ~40 entities captured in MD inventory; methodology-records promotion deferred to PI-095)
**Parent workstream:** Candidate WS-009 (Code Change Lifecycle — covers payload-section extensions, schema work) or a new dogfood-methodology-authoring workstream (provisionally WS-013). Resolve at session start; default WS-009 pragmatically.

---

> **⚠ RE-KEY NOTICE (added during PI-073 merge reconciliation).** This
> kickoff was authored in a Claude.ai sandbox under sandbox-local
> identifiers that collided with main when the Phase 2 Domain Discovery
> close-out was merged. The close-out was re-keyed on apply to main
> (see commit `b2f248e`, SES-100). Every identifier in this document has
> been updated to its **main** value. The mapping was:
>
> | Sandbox (original) | Main (current) | What it is |
> |---|---|---|
> | SES-098 | **SES-100** | Phase 2 Domain Discovery session |
> | CONV-068 | **CNV-002** | the conversation within it |
> | PI-091 | **PI-094** | user/role entity model PI |
> | PI-092 | **PI-095** | methodology-records promotion PI (the work this kickoff designs) |
> | DEC-319 … DEC-324 | *unchanged* | the six Phase 2 decisions (no collision on main) |
>
> A future session opening against this kickoff should capture fresh
> identifier heads at session start per DEC-300 — the heads section near
> the bottom has been updated to reflect post-merge reality.

---

## What landed in SES-100 (the prior session)

CRMBuilder dogfood Phase 2 Domain Discovery conducted per `interview-domain-discovery.md` v1.1 with Variant A administrator-as-proxy adapted for dogfood (Doug as both administrator and sole stakeholder).

**Direction established (six decisions):**

- **DEC-319** — Adopt Option C.1 for SES-100 close-out: durable Markdown candidate inventory at `PRDs/product/crmbuilder-v2/CRMBuilder-Phase-2-Candidate-Inventory.md`; standard governance close-out only (no methodology records written by the apply); methodology-records promotion deferred to **PI-095** pending the V2 close-out pipeline's methodology-ingestion support. Doug's explicit additional requirement at confirmation: "convert MD document to database record when the closeout allows." This session is that work.
- **DEC-320** — Mission revision to application-framework framing with three-mode platform-or-build option (recommend existing platform / extend existing with custom / build from scratch).
- **DEC-321** — CRMBUILDER engagement domain set: 14 candidate domains (Methodology Authoring, Engagement Governance, Requirements Capture, CRM Platform Decision, CRM Deployment, CRM Configuration, CRM Verification, Custom CRM Build, AI-Assisted Interview Surface, CRM Inventory & Functional Analysis, CRM Deployment Pattern Inventory, Configuration Artifact Generation, Document Rendering, Engagement Setup), all passing Rule 2.1.
- **DEC-322** — Symmetric pattern-inventory parallels rejected for #6 (CRM Configuration) and #8 (Custom CRM Build) — patterns intrinsic to those operational domains rather than separate knowing-domains.
- **DEC-323** — Methodology Authoring (#1) is CRMBuilder-internal-only — present in CRMBUILDER engagement; absent from external client engagements' domain sets (which default to 13 domains).
- **DEC-324** — Entity naming disambiguation: Pattern qualifiers locked in (Deployment Pattern, Pattern Library Entry, Configuration Pattern); Render Run standardized across #12 and #13 distinguished by render_target_kind; Generated Artifact and Generated Document stay distinct.

**Two planning items filed:**

- **PI-094** — Design and implement user/role entity model in V2 for tracking per-engagement participants. 7 of 9 candidate personas have TBD Rule 2.2 backing pending this. Not blocking this session.
- **PI-095** — Promote Phase 2 candidate methodology records from the MD inventory into V2 records once the close-out pipeline supports methodology ingestion. **This is the work this session designs.**

**Open at session end:**

- 14 candidate Domains, 9 candidate Personas, and ~40 candidate Entities exist only in the MD inventory file — not yet in V2 records.
- Workstream parentage for SES-100's conversation was pragmatic (WS-011 V2 storage API refinements); a dedicated dogfood-methodology-authoring workstream is recommended but not yet authored.
- The new Master CRMBuilder PRD's Phase 2 placeholder can now be drafted from SES-100's execution per §III iterative-drafting framework.
- Phase 3 Inventory Reconciliation under the old methodology has limited applicability with a sole stakeholder — open question for a separate session.

---

## The task

Decide the V2 methodology-records ingestion mechanism — the precondition for resolving PI-095 and any future Phase 2 session for external clients (CBM and beyond) that surfaces candidate Domains, Personas, and Entities.

This is a **consequential design decision** under the userPreferences eight-element template — real downstream impact (the chosen mechanism locks in tooling shape for every engagement's Phase 2 records promotion) and at least four viable options producing meaningfully different outcomes.

The mechanism must handle two distinct write situations:

1. **Backfill** — SES-100's already-captured MD inventory has 14 + 9 + ~40 candidate records waiting to be written. Any new mechanism must handle batch ingestion of a captured inventory.
2. **Forward use** — Future Phase 2 sessions for external clients (CBM next) will surface candidates that should land in V2. The mechanism should accommodate live-session capture (during the conduct of Phase 2 itself) and/or post-session promotion (the SES-100 pattern).

The decision should also produce a high-level implementation plan and the Claude Code prompt(s) needed to implement it, or at minimum the Planning Item(s) that hold the implementation work.

---

## Candidate options (initial surface — expect the conversation to refine and possibly extend)

PI-095's description named four options. Expect the conversation to surface more or to merge/split these.

**Option A — v0.9 payload schema extension.** Add three new sections to the close-out payload schema (e.g., `domains`, `personas`, `entities`) plus their associated reference relationships. Extend `apply_close_out.py` with the new section handlers in `_SECTIONS`. Most aligned with the existing close-out discipline; preserves the transactional shape and identifier-head capture protocol. Costs: schema version bump, validator updates, the existing payload-shape rules document needs amendment, and a v0.7-style consolidating migration may be needed depending on how the schema is captured. Live-session writes still require a separate path (this option only solves batch close-out ingestion).

**Option B — Separate methodology-write apply path.** Own script (e.g., `scripts/apply_methodology_inventory.py`), own validation, own ordering rules; less invasive to the existing close-out infrastructure. Costs: a second parallel apply pipeline to maintain; risk of drift in transactional discipline between the two pipelines; live-session writes still separate.

**Option C — MCP tool surface for methodology batch ingestion.** Expose `mcp__crmbuilder__write_candidate_domains`, `_personas`, `_entities` tools that Claude.ai can call directly. Most useful for live-session capture during Phase 2 conduct; less natural for batch backfill of MD-captured inventories (would require Claude.ai reading the MD and emitting tool calls). Costs: MCP server work; introduces a second control plane alongside REST.

**Option D — Inline curl POSTs in apply prompts.** Each candidate record becomes a `curl -X POST` in the SES-NNN apply prompt. Mechanically simplest; mentioned in PI-095's description for completeness. Costs: least disciplined; no transactional rollback; large apply prompts; precedent risk if used widely.

**Option E (likely to surface) — Live-session direct API POST during Phase 2 conduct.** Per the stop-and-log discipline in `governance-recording-rules.md` §4, conversations are authored at the boundary moment via direct API POST. The same pattern could apply to candidate methodology records — Claude.ai writes each candidate at the moment of capture during Phase 2 conduct. Avoids the batch-vs-live split entirely. Costs: requires API access from the conducting sandbox; less helpful for the SES-100 backfill case (which is already captured as MD).

**Option F (likely to surface) — Hybrid.** Some combination, e.g., live-session POSTs during conduct (Option E) plus a batch import script for retroactive cases like SES-100 (Option B narrowed in scope). Multiple sub-shapes possible.

---

## Pre-flight (per governance-recording-rules.md §1.6, every new session)

Before authoring any governance content (decisions, planning items, references, sessions, conversations), the new conversation MUST execute these steps:

### 1. Read the engagement CLAUDE.md

```bash
cat crmbuilder/CLAUDE.md
```

Engagement is CRMBUILDER. Particular attention to: "Current direction" section, methodology-layer entity status, the v2 governance recording rules pointer, and the dogfood-engagement notes.

### 2. Read the governance recording rules

```bash
cat specifications/governance-recording-rules.md
```

Authoritative for every record this session authors. Particular attention to: §1 Identifier Discipline (heads-capture protocol), §5 Decision Authoring (eight-element template at the moment of decision, not batched), §6 Planning Item Authoring (cross-session work item rule), §9 Close-Out Payload Authoring (v0.8 ten-element shape).

### 3. Capture identifier heads via curl block

```bash
curl -sf http://127.0.0.1:8765/sessions       | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(s['identifier'] for s in d); print('SES head:', ids[-1])"
curl -sf http://127.0.0.1:8765/conversations  | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(c['conversation_identifier'] for c in d); print('CONV head:', ids[-1])"
curl -sf http://127.0.0.1:8765/decisions      | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(dc['identifier'] for dc in d); print('DEC head:', ids[-1])"
curl -sf http://127.0.0.1:8765/planning-items | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(p['identifier'] for p in d); print('PI head:', ids[-1])"
curl -sf http://127.0.0.1:8765/work-tickets   | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(w['work_ticket_identifier'] for w in d); print('WT head:', ids[-1])"
curl -sf http://127.0.0.1:8765/workstreams    | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; ids=sorted(w['workstream_identifier'] for w in d); print('WS head:', ids[-1])"
```

Post-merge reality (as of the re-key, 05-27-26): the Phase 2 Domain
Discovery work is already on main as SES-100 / CNV-002 / DEC-319..324 /
PI-094 / PI-095 — those identifiers are *consumed*, not future heads.
A session opening against this kickoff captures its own fresh heads at
start (next available were roughly SES-109, CNV-011, DEC-325, PI-097
at re-key time, but **always re-query live** per DEC-300 — the
orchestrator and parallel sessions advance these frequently). The
records to read for orientation are the fixed ones above (SES-100,
PI-095, DEC-319); the heads to claim for this session's own DEC/PI/SES
are whatever the live next-identifier helpers return at session start.

### 4. Identify the parent workstream

Candidate parents (named in §"Parent workstream" header above): WS-009 (Code Change Lifecycle) is the closest existing fit because the dominant option (A — v0.9 payload schema extension) is exactly that workstream's scope. Alternative: create WS-013 "CRMBuilder Dogfood Methodology Authoring" via direct API POST at session start; the SES-100 in_flight_at_end flagged this as substantively better. Decide at session start.

### 5. API health check

```bash
curl -sf http://127.0.0.1:8765/health || curl -sf http://127.0.0.1:8765/sessions | head -c 200
```

### 6. git pull --ff-only origin main

```bash
git pull --ff-only origin main
```

### 7. Session-specific reading (required before authoring decisions)

```bash
# The SES-100 work this session continues
cat PRDs/product/crmbuilder-v2/CRMBuilder-Phase-2-Candidate-Inventory.md
cat PRDs/product/crmbuilder-v2/close-out-payloads/ses_098.json | python3 -m json.tool

# The existing close-out apply mechanism (the baseline this design extends or parallels)
cat crmbuilder-v2/scripts/apply_close_out.py

# Existing methodology records' shape — the target schema
ls crmbuilder-v2/src/crmbuilder_v2/access/
# Particular attention to domain.py, persona.py, entity.py if they exist
cat crmbuilder-v2/src/crmbuilder_v2/access/vocab.py  # relationship vocabulary

# Current snapshot of methodology tables (empty or sparse for CRMBUILDER engagement,
# but populated for CBM if those records exist)
cat PRDs/product/crmbuilder-v2/db-export/domains.json | python3 -c "import sys,json; d=json.load(sys.stdin); print('domain count:', len(d))"
cat PRDs/product/crmbuilder-v2/db-export/personas.json | python3 -c "import sys,json; d=json.load(sys.stdin); print('persona count:', len(d))"
cat PRDs/product/crmbuilder-v2/db-export/entities.json | python3 -c "import sys,json; d=json.load(sys.stdin); print('entity count:', len(d))"

# The PI being designed for
curl -sf http://127.0.0.1:8765/planning-items/PI-095 | python3 -m json.tool

# The decision that surfaced PI-095
curl -sf http://127.0.0.1:8765/decisions/DEC-319 | python3 -m json.tool

# Master CRMBuilder PRD §III iterative-drafting framework (this work informs Phase 2 PRD content)
cat specifications/master-crmbuilder-PRD.md
```

If any of the SES-100 records are not present in the live API, the SES-100 close-out has not yet been applied — surface that to Doug and pause before authoring this session. The apply prompt is at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-098.md`.

---

## Session topics (decision-driven structure)

This session is built around one core consequential decision plus its immediate follow-ons. Topics:

### Topic 1 — Confirm pre-session state

Confirm SES-100 close-out has been applied (live heads at SES-100, CNV-002, DEC-324, PI-095). Confirm inventory MD is in place. Confirm parent workstream choice. Frame the core decision.

### Topic 2 — Survey and refine the option set

Walk through Options A through F (above) plus any new options the conversation surfaces. For each, name the concrete behavior — what a Phase 2 session conducting a methodology capture looks like under that option, and what a backfill of an already-captured MD inventory looks like under that option.

Sub-questions to surface for each option:
- **Transactional discipline.** What happens if 7 of 14 domains POST successfully and the 8th 422s? Rollback or partial-state?
- **Identifier discipline.** How are DOM-NNN, PER-NNN, ENT-NNN identifiers reserved and protected against concurrent-sandbox collision (governance-recording-rules.md §1)?
- **Reference resolution.** Candidate Personas reference candidate Entities for Rule 2.2 backing. References across freshly-created records require post-create resolution. How does the chosen mechanism sequence creates and reference writes?
- **Schema versioning.** Does this require a v0.9 payload schema bump, an out-of-band extension, or no schema impact?
- **MCP affordance.** Should the same mechanism work over MCP for live-session capture from Claude.ai during external client Phase 2 conduct?
- **Backfill applicability.** Can this mechanism handle SES-100's already-MD-captured inventory, or does backfill need a separate path?

### Topic 3 — Apply the consequential-decision template

Per userPreferences, this decision passes the two-part test and must be presented with the eight-element template:

1. Plain-language question
2. Concrete example from real project content (use SES-100's 14+9+~40 candidates as the example)
3. Each option named with concrete behavior
4. Why this matters (the principle / constraint that makes this consequential)
5. Cost of the recommended option, honestly named
6. Recommendation with one-line rationale
7. Follow-on detail (naming, mechanism specifics, validation rules)
8. Decision request with named options to approve or push back on

### Topic 4 — Decide and capture

Capture the decision as DEC-NNN in the close-out payload's `decisions` section (moment-of-decision authoring per §5 of the governance rules — author the DEC in the working payload before moving on).

### Topic 5 — Implementation plan

Sketch the implementation plan at high level. Outputs to produce:

- If the chosen mechanism is implementable in a single bounded code change, a Claude Code prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-{descriptor}.md`.
- If the work spans multiple phases, a series of Planning Items (one per phase) plus a top-level coordinating planning item, with the Claude Code prompts authored as each phase's preconditions clear.
- Either way: a planning item update on PI-095 noting the chosen mechanism and any sub-PIs that hold the implementation work.

### Topic 6 — Backfill plan for SES-100 inventory

The chosen mechanism may handle SES-100's MD inventory differently from forward-use live-session capture. Decide:
- Is SES-100's MD inventory ingested via the chosen mechanism, or via a one-time backfill script (precedent: `scripts/backfill_pi_024_*.py`, `scripts/backfill_pi_025_*.py`, `scripts/backfill_pi_026_*.py`)?
- When is PI-095 marked Resolved — when the mechanism ships, when SES-100's records land in V2, or both?

### Topic 7 — Close-out

Standard close-out per governance-recording-rules.md §9. Author SES-NNN payload at `PRDs/product/crmbuilder-v2/close-out-payloads/ses_NNN.json`. Author apply prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md`. Commit and push from sandbox.

---

## Expected outputs

At session end the conversation produces:

- **One Decision** (DEC-NNN) capturing the chosen ingestion mechanism with the eight-element rationale.
- **Possibly additional decisions** for sub-choices (parent workstream creation, backfill path, MCP-tool-vs-API choice within a hybrid option).
- **One or more Planning Items** holding the implementation work, plus an addresses-or-resolves reference on PI-095.
- **One or more Claude Code prompts** at `PRDs/product/crmbuilder-v2/prompts/` for the code changes — schema migration, `apply_close_out.py` extension, MCP-tool surfaces, backfill script, or whatever the chosen mechanism requires.
- **Standard close-out triple** — SES record, payload, apply prompt — per Option C.1 / governance-recording-rules.md §9.
- **Possibly a workstream creation** — direct API POST for WS-013 "CRMBuilder Dogfood Methodology Authoring" or equivalent if Topic 1's workstream-parentage discussion lands there.

---

## Adjacent open work the session may or may not touch

These are tracked in SES-100's `in_flight_at_end` and may surface in the conversation; not in primary scope but worth flagging:

- **PI-094** (user/role entity model). Candidate Personas' backings depend on PI-094; if this session decides to write Personas with TBD backings now and resolve backings later, PI-094 remains unresolved but unblocked. If this session decides Personas can't be written without backings, PI-094 becomes a hard precondition.
- **Phase 3 Inventory Reconciliation applicability.** Single-stakeholder dogfood doesn't reconcile across stakeholders. Whether reconciliation gets absorbed into Phase 1 or becomes optional is a separate Master CRMBuilder PRD §III iterative-drafting decision.
- **Master CRMBuilder PRD Phase 2 drafting.** SES-100's execution effectively drafts Phase 2 by doing; capturing that into the PRD's Phase 2 section is a separate session candidate.

---

## Operating mode note

Default ARCHITECTURE per project setting. The two-part test for what stops the flow: real downstream impact AND at least two viable options producing meaningfully different outcomes. The core mechanism decision passes both. Sub-choices that are determined by the core decision (e.g., specific filenames, exact validation rules) are decided and announced in-line rather than surfaced as separate consequential decisions.

If the session arrives at a point where authoring a Claude Code prompt is the next concrete action, switch to DETAIL mode for that authoring per the project default.

---

## How to start

The new session's first turn is typically:

> Read `PRDs/product/crmbuilder-v2/methodology-records-ingestion-kickoff.md` and execute the pre-flight. Confirm SES-100 close-out has been applied before authoring anything.

Doug confirms which parent workstream to use (WS-009 pragmatic vs. WS-013 new), and the session proceeds through the topics above.
