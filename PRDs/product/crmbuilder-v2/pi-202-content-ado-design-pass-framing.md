# PI-202 — Content-work ADO integration: Design-pass framing

**Planning item:** PI-202 (`Ready`) — *"Content-work ADO integration — review-gate verification, tiers, classification, decomposition (PI-131 follow-on)"* · PRJ-018 (Agent Delivery Organization) · REL-010.
**This phase:** the **Design phase (WSK-163)**. **No build.** Output is **two governance decisions** (rulings on REQ-183 and REQ-184) + a short design note. The build (REQ-185/186/187) follows once these are ruled.
**Why it exists:** DEC-444 / PI-131 settled what Plan/Design/Develop/Test *mean* for content work (REQ-166–170, confirmed + built). It left two questions open that **size the build**, plus three build items. This pass closes the two open questions so the build can be scoped accurately.

---

## Background (already settled)

- **The four-step content model is decided and built** (REQ-166–170 → PI-131, Resolved): Plan = split; Design = decide what-to-author + acceptance criteria; Develop = author the records; Test = verify correct + complete against those criteria; content PIs run all three by default.
- **The direction is decided** (REQ-187, confirmed; REQ-171 rejected/superseded): content PIs run **through** the ADO via review-gate verification, **not** outside it.
- **What exists in code:** the decomposer already produces Design→Develop→Test for every PI; the scheduler already has review agents (a Design reconciliation reviewer, a PI-closure reviewer, a develop-gate enforcing blocking findings); 4 `methodology-*` system areas exist (`process / product / interviews / templates`); there are **no** methodology-area agent profiles yet.

---

## Ruling 1 (REQ-183) — Is content-Test the existing review gates, or a distinct step? **[the pivotal one]**

**Question.** Content-Test = *"verify the authored records are correct and complete against the Design's acceptance criteria"* (completeness, correctness, conformance — REQ-169). The requirements-provenance system already has gates: the **readability blocking gate** (statement quality at approval), the **approval queue + provenance/topic gates**, and the **Review-panel human sign-off**. Is content-Test **satisfied by** those gates, or a **distinct verification step that precedes** the human sign-off?

**Why it's genuinely open — and why it sizes the build.** The existing gates check *format* (readability), *provenance/topic*, and *human approval*. **None of them checks whether the records the Design called for were actually authored, are internally consistent, and are complete against the PI's acceptance criteria.** A record can pass readability + provenance + sign-off and still be incomplete or wrong relative to what the Design asked for. So the gates are **necessary but not sufficient** for REQ-169's definition of Test.

**Options:**

| | Option | What it means | Build impact |
|---|---|---|---|
| **A** | content-Test **==** the existing gates | No new verification; Develop's records just go through readability + approval + sign-off | **Smallest** — but **under-verifies**: nothing checks completeness/correctness vs the Design's acceptance criteria. The author's own records reach sign-off unchecked. |
| **B** | content-Test is a **distinct review step** before sign-off | A reviewer checks the authored records against the Design's acceptance criteria (completeness/correctness/conformance) → pass-or-findings → *then* the existing human sign-off | **Medium** — reuses the existing closure-reviewer machinery with a content-specific check; the human sign-off remains the final gate |
| **C** | **Hybrid** (explicit layering) | = B, stated as two layers: (i) an agent review against acceptance criteria is content-Test; (ii) the existing readability/approval/sign-off are the unchanged *human* gate that content-Test feeds | Same as B, just names the seam clearly |

**Recommendation: B / C.** Content-Test is a **real, distinct step** — an agent (or human) verifying the authored records against the Design's acceptance criteria — that **feeds, not replaces,** the existing human sign-off. The existing gates stay as the final human gate. This honors REQ-169 (it actually checks completeness/correctness) while **reusing** the scheduler's existing reviewer machinery, which keeps REQ-187 at "Medium," not "Large." Option A is cheapest but quietly drops the verification REQ-169 requires.

---

## Ruling 2 (REQ-184) — Tiers for methodology areas

**Question.** DEC-368 gave methodology/design areas an **Architect-tier profile only** (because content was Design-only). Now content has a real Develop (author records) and Test (verify them). Do methodology-* areas need a **Developer** and/or **Tester** profile, or does the Architect span all three content steps?

**Options:**

| | Option | Profiles per methodology area | Trade-off |
|---|---|---|---|
| **A** | Architect spans all three | Architect only (unchanged) | Simplest, no new profiles — but the author **verifies its own work** (no independent Test). Weakens REQ-169. |
| **B** | **Architect + Tester** | Architect (Design+Develop) + Tester | Independent verification (the verifier isn't the author); Design and Develop stay one coherent authoring act. **One** new profile kind. |
| **C** | Full Architect/Developer/Tester | Three, mirroring build areas | Maximal separation — but splitting "decide what to author" from "author it" adds handoff friction for prose/records with little gain. |

**Recommendation: B (Architect + Tester).** The whole value of a separate Test step is **independent** verification — catching incomplete/wrong records — which requires the verifier *not be the author*. So a distinct **Tester** profile is worth it. But splitting Design from Develop (Architect vs Developer) for content is over-decomposition: deciding-what-to-author and authoring records/prose are one cognitive act. So: **Architect does Design+Develop, a separate Tester does Test.**

---

## How the two rulings connect

They're one coherent answer. **If content-Test is a distinct verification (Ruling 1 = B/C), it should be performed by an independent verifier (Ruling 2 = B Tester).** Together: *content-Test is an independent review of the authored records against the Design's acceptance criteria, performed by a methodology-area Tester profile, producing pass-or-findings, which then feeds the unchanged human sign-off in the Review panel.* That single sentence is what the build implements.

---

## What the build (REQ-185/186/187) becomes once these are ruled

- **REQ-185 (classify + phase)** — *Small.* Classify a PI as content iff its area(s) are all `methodology-*`; Design mandatory, Develop/Test conditional-but-real.
- **REQ-186 (decomposition shape)** — *XS.* Same Design→Develop→Test phases, content meaning — the decomposer already produces them; document that no shape change is needed (or the narrow exception, if any).
- **REQ-187 (review-gate execution)** — *Medium.* In the scheduler, branch content phases off the git/commit + pytest verify path onto the review path: content Develop "complete" = records authored per acceptance criteria (DB writes, no branch); content Test = the Tester-profile review (Ruling 1B) → findings gate → existing human sign-off (Ruling 2B). **Reuses** the existing reviewer/closure machinery; the new work is the *content branch* in the verify logic + the Tester contract. **Sensitive code (the scheduler's core verification) — well-tested.**

---

## Deliverables for this Design phase (triple-artifact close-out)

1. **Two governance decisions** (`POST /decisions`) — one ruling REQ-183 (recommend B/C), one ruling REQ-184 (recommend B) — each with rationale, referenced from REQ-183/REQ-184.
2. **A short design note** at `PRDs/product/crmbuilder-v2/pi-202-content-ado-integration-design.md` capturing the two rulings, the connecting sentence, and the resulting build shape for REQ-185/186/187.
3. The Develop/Test phases (WSK-164/165) then get **scoped** (Work Tasks) against that build shape and the PI proceeds.

**Out of scope here:** any `scheduler/` / `decomposition` / agent-profile code — that's the build pass, gated on these two rulings.

---

## Open risk to keep in view

The scheduler's verification is **git-deep** (`ado/<wtk-id>` branches, unmerged-residue detection, the develop-gate, the commit-producing pool-run). Content needs a **clean parallel verify lane**, not a hack into the git path, or content PIs will trip commit-based checks. And since the methodology/dogfood work *is* content work, this is the ADO learning to drive its own governance authoring — **prove it on one small real content PI before trusting it broadly.**
