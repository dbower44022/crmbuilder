# PI-202 — Content-work ADO integration: Design

**Planning item:** PI-202 (PRJ-018 / REL-010) — *"Content-work ADO integration — review-gate verification, tiers, classification, decomposition (PI-131 follow-on)."*
**Status of this doc:** the decided design for PI-202's build, produced by its Design phase. Rulings recorded as **DEC-763** (REQ-183) and **DEC-764** (REQ-184). Framing/options: `pi-202-content-ado-design-pass-framing.md`.
**Implements:** REQ-183, REQ-184 (decided here) + REQ-185, REQ-186, REQ-187 (built per this design).

---

## 1. The decided model (one sentence)

> **Content-Test is an independent review of the authored records against the Design's acceptance criteria — performed by a methodology-area Tester profile, producing pass-or-findings — which feeds the unchanged human sign-off in the Requirements Review panel.**

That sentence is what the build (REQ-185/186/187) makes real.

## 2. The two rulings

**DEC-763 (REQ-183) — content-Test is a *distinct* step, not merely the existing gates.** The readability/approval/sign-off gates check statement format, provenance/topic, and human approval; **none** checks whether the records the Design called for were authored and are complete and internally consistent against the PI's acceptance criteria. So content-Test is a distinct verification (completeness, correctness, conformance) that **precedes and feeds** the existing human sign-off. The existing gates remain the final human gate — necessary but not sufficient.

**DEC-764 (REQ-184) — methodology areas get Architect (Design+Develop) + Tester.** The Architect performs Design (decide what to author + acceptance criteria) and Develop (author the records); a **separate Tester** independently performs content-Test. No Developer tier — deciding-what-to-author and authoring are one coherent act. Amends DEC-368's Architect-only ruling for methodology areas now that content has a real Develop and Test. The Tester is the independent verifier DEC-763 requires.

## 3. Resulting build shape

### 3.1 REQ-185 — classify and phase content PIs  *(area: access · size: S)*
- **Classification signal:** a PI is **content** iff every area it carries is a `methodology-*` area (`methodology-process | -product | -interviews | -templates`); otherwise **software**. (Mixed content+software areas → treat as software; out of scope to split, flag as a future case.)
- **Phasing:** content PIs run **Design mandatory, Develop and Test conditional-but-real** (never auto-skipped). Default is all three active (REQ-170).
- **Where:** a `classify_planning_item(pi) -> {"content" | "software"}` helper in the access layer, consumed by the scheduler and decomposition. Keep it a pure function of the PI's areas so it's testable without the runtime.

### 3.2 REQ-186 — decomposition shape  *(area: access · size: XS)*
- **No shape change.** `decompose_planning_item` already produces `Design → Develop → Test` for every PI (`PHASE_SEQUENCE`). Content uses the **same phases with content meaning**; document that explicitly and add a test asserting a content PI decomposes to the three active phases (not Design-only).

### 3.3 REQ-187 — review-gate execution  *(area: access/scheduler · size: M — the substantive piece)*
The scheduler today verifies build work **through git** (`ado/<wtk-id>` branches, `task_branch_unmerged`, the develop-gate, the commit-producing pool-run) + the pytest gate. Content has **no commits** — Develop authors DB records. So:
- **Branch the verify path by classification.** For a **content** PI's Develop/Test phases, do **not** take the git/commit + pytest lane.
- **Content Develop "complete"** = the records the Design called for were authored (DB writes per the Work Task's acceptance criteria), verified by result — **not** a merged branch.
- **Content Test** = the **Tester profile** (DEC-764) reviews the authored records against the Design's acceptance criteria → **pass-or-findings**. A finding blocks (mirrors the existing develop-gate's blocking-finding behavior); a pass advances the PI to In Review → the **existing human sign-off** in the Review panel (DEC-763) closes it.
- **Reuse, don't reinvent:** the scheduler already has a reconciliation reviewer and a closure reviewer (`build_review_prompt` / `review_close_pi`) and a blocking-finding gate. The new work is (a) the content branch in the verify logic and (b) the **content-Test reviewer contract** (a Tester operating-protocol prompt that checks records vs acceptance criteria, not code vs tests).
- **Keep it a clean parallel lane** — do not thread content through the git-residue/branch checks, or content PIs will trip commit-based assertions.

## 4. Agent profiles (from DEC-764)

Per (area × tier) the registry needs, for each methodology-* area that runs content PIs:
- an **Architect** profile (Design + Develop) — author-the-records contract, and
- a **Tester** profile — the content-Test reviewer contract (review records vs acceptance criteria → findings).

These are registry rows + operating-protocol prompts; no Developer-tier profile.

## 5. Build sequence & test posture

1. **REQ-185 classifier** (pure function) + tests — foundation everything keys off.
2. **REQ-186 decomposition** — confirm + test the content phase shape (mostly a test + a doc line).
3. **REQ-187 verify branch** — the content Develop/Test lane in the scheduler + the Tester contract, reusing the existing reviewer/closure machinery.
4. **Profiles (§4)** — Architect + Tester contracts for the methodology areas.

**Test posture:** the scheduler's verification is sensitive core code. Unit-test the classifier and decomposition shape; for the verify branch, test the content lane in isolation (a content PI reaching In Review via review-pass, and blocking on a finding) without touching the git path. **Prove on one small real content PI** before trusting it broadly — the methodology/dogfood work *is* content work, so this is the ADO learning to drive its own governance authoring.

## 6. Out of scope / deferred

- Mixed content+software PIs (areas spanning both) — treat as software for now; revisit if a real case appears.
- Migrating existing content PIs onto the new lane retroactively — go-forward only.
