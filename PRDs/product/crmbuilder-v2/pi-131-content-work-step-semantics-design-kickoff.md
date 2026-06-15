# PI-131 — Develop/Test Semantics for Content/Authoring Work (Design Pass Kickoff)

**Planning item:** PI-131 (Draft) — *"Define what Develop and Test mean for content/authoring work in the four-step Process"*
**Project:** PRJ-018 — *Agent Delivery Organization*
**Session type:** Design / methodology-definition pass. **No build.** Output is a *decision (refining DEC-392) + a reviewable requirement + a design doc*, not runtime code.
**Why this session exists:** DEC-392 set the four-step Process (Plan / Design / Develop / Test) and ruled that non-software work *"uses only the Design step active."* Running **PI-128** (authoring the agent-system PRD) and **PI-130** (migrating the governance recording rules into V2) showed that ruling is too crude: content/authoring work has a **real authoring step** (Develop = writing the records) and a **real verification step** (Test = confirming they are correct and complete). The ADO runtime needs to know how to phase content Planning Items, or it will keep mis-handling the methodology/dogfood work that is the repo's active direction. This session defines those semantics. ADO cannot consistently decompose/execute content PIs until it is decided.

---

## 1. Orientation — read these first

**Tier 1 (always):**
- `CLAUDE.md` — the **"Governance & delivery model redesign — PI-112"**, **"Agent Delivery Organization (ADO) substrate landed — PI-114"**, and **"ADO agent-layer evolution"** sections. Note the existing rule that **design/methodology areas get an Architect-tier profile only**, while build areas get Architect/Developer/Tester (DEC-368) — this design pass must say whether content/authoring work keeps Architect-only or now needs a Develop/Test tier presence.

**Tier 2 (v2 governance — read live, `X-Engagement: CRMBUILDER`, unwrap `{data,meta,errors}`):**
- `GET /planning-items/PI-131` — the framing.
- `GET /decisions/DEC-392` — **the decision being refined.** Four-step model; non-software work "uses only Design active"; old six step-names kept valid for historical records; one model for all work. PI-131 says the "only Design" part is wrong for content.
- `GET /decisions/DEC-393`, `/DEC-394` — governance recording rules moved into V2 under `TOP-013` (the PI-130 work that exposed the gap).
- `GET /planning-items/PI-128`, `/PI-130` — the two worked examples of content/authoring PIs that proved Develop+Test are real for content. Read how they were actually executed (their sessions/conversations) — the *empirical* authoring step and verification step are the raw material for the definition.
- The topic anchor `TOP-009` (PI-131 is `is_about` it) — read it for the methodology-process framing; attach/repair the topic anchor if needed.

**Tier 2 (design docs — read from disk):**
- `PRDs/product/crmbuilder-v2/agent-delivery-organization-design.md` (v0.3) and `agent-delivery-organization-evolution.md` (v0.3) — the matrix org (four passes × area-disciplines), the three tiers, the per-area discipline model. Content/authoring areas are `methodology-process`, `methodology-product`, `methodology-interviews`, `methodology-templates` (from `vocab.SYSTEM_AREA_RANKS`).

**Tier 2 (the verification connection — important):**
- The **requirements-provenance & review** surfaces (`access/readability.py`, `/review/*`, the Requirements Review panel). Content "Test" — *verifying a record is correct and complete* — overlaps the existing **blocking readability gate**, the **approval queue**, and the **review sign-off**. A central question below is whether content-Test *is* those gates or is distinct.

---

## 2. Questions this session must answer

1. **What is Develop for a content/authoring PI?** Presumably "author the records" (requirements, topics, rules, glossary entries, methodology definitions, PRD prose). Define it precisely: which record types, what "done" means for the authoring step, what artifact it produces.
2. **What is Test for a content/authoring PI?** Presumably "verify the authored records are correct and complete." Define the check: completeness against the PI's scope, internal consistency, and **how it relates to the existing review machinery** — is content-Test satisfied *by* the readability gate + Review-panel sign-off, or is it a separate verification step that precedes the human sign-off?
3. **Tiers for content areas.** DEC-368 gives design/methodology areas an Architect-tier profile only. If content now has a real Develop and Test, does a content area need a Developer-tier and/or Tester-tier profile, or does the Architect profile span all three steps for content? Decide and say why.
4. **How does the runtime classify a PI as content vs software**, and phase it accordingly? Is it the PI's area(s)? A flag? Does Design stay mandatory, and do Develop/Test become conditional-but-real rather than skipped?
5. **Decomposition impact.** Does the six-phase Workstream decomposition change shape for content PIs (e.g. Architecture→Development→Testing collapse or re-map), or stay the same with redefined *content* per phase?

---

## 3. Deliverables (triple-artifact close-out)

1. **A design doc** at `PRDs/product/crmbuilder-v2/pi-131-content-work-step-semantics-design.md`: the precise Develop/Test definitions for content work, the tier ruling (q3), the runtime classification rule (q4), the decomposition impact (q5), and the explicit relationship between content-Test and the requirements-provenance review gates (q2). Reference PI-128/PI-130 as the empirical basis.
2. **A governance decision** (`POST /decisions`) that **refines DEC-392** — keep DEC-392's "one model for all work" and the kept-valid history, but replace its "non-software work uses only Design" clause with the content Develop/Test semantics defined here.
3. **A traced, reviewable requirement** (`POST /requirements` — no `identifier` in the body) for the content-work step semantics, anchored to a topic + provenance conversation, surfaced in the **Requirements Review panel** for Doug's sign-off. This is the gate before any runtime change implementing it can be ADO-built.

**Explicitly out of scope:** changing `runtime/` code, the decomposition repository, or the agent profiles. Those follow once the definition + requirement are approved.

---

## 4. After this session

With the semantics decided and the requirement approved, the implementing work (runtime classification + any content-tier profiles + decomposition adjustment) becomes a normal ADO-buildable PI under PRJ-018: decompose → scope (areas `methodology-*`) → Ready → dispatch-approve. Until then PI-131 stays `Draft` in PRJ-018 and is correctly not dispatchable.
