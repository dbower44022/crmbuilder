# CBM Redo — Step 8: Internal Validation Pass

**Document type:** Captured execution of the evolved methodology test (validation pass)
**Repository:** `crmbuilder`
**Path:** `PRDs/process/research/evolved-methodology/cbm-redo/cbm-redo-step-8-validation-pass.md`
**Last Updated:** 04-30-26 21:10
**Version:** 1.0

---

## Status

This document captures Step 8 of the CBM redo execution plan, per `cbm-redo-ground-rules.md` §9. Step 8 is the validation pass — the experiment's one external check on the simulator's interpretations.

The validation pass was conducted as an **internal validation pass**: Doug, in his role as the operational owner of CBM (rather than as the methodology researcher), answered the four questions derived from the open gap log entries plus the general approach gut-check. Per ground rules §6.2 (mitigations baked into the experiment design) and §6.4 (mitigations after the redo), an internal validation pass is less rigorous than a separate-CBM-stakeholder validation pass would be — but it is materially better than no validation pass at all, and the limitation is named honestly here.

The findings in this document substantially correct or qualify the preliminary findings in `cbm-redo-step-7-pre-validation-findings.md`. **Three of the four validation-pass answers went against the experiment's preliminary findings rather than for them.** This is recorded straightforwardly because honest signal is more valuable than a clean narrative.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 04-30-26 21:10 | Doug Bower / Claude | Initial captured execution of Step 8. Internal validation pass with four questions answered. Three answers correct or qualify the experiment's preliminary findings. |

---

## Change Log

**Version 1.0 (04-30-26 21:10):** Captured execution of Step 8 — internal validation pass. Records four questions and Doug's answers as the CBM operational stakeholder. Q1 (reactivation): the simulator fabricated a fit/no-fit distinction that doesn't exist at CBM; G-001 dissolves; "Reactivation" should be removed from the methodology output. Q2 (donor work scope): the simulator fabricated an operational-strategic split that doesn't exist at CBM; G-003 and G-006 dissolve; the Funding Coordinator owns all donor relations and the Donors and Funding domain's classification needs reconsideration. Q3 (general approach): both efficiency and substantive comparison are inconclusive because (a) simulated sessions don't measure real-engagement effort and (b) Phase-1-only redo doesn't produce comparable artifacts to the original engagement's full specification work. Q4 (anything else): nothing additional. The validation pass surfaces a fundamental limit of the experiment that was underweighted in the §5.5 acknowledgments.

---

## 1. Method

The validation pass was conducted as four sequential questions asked of Doug in his capacity as the CBM operational owner. Doug was explicitly asked to answer as CBM operations rather than as the methodology researcher, to surface the operational reality of CBM rather than methodology-aware analysis.

Per ground rules §7, the questions were derived from the open gap log entries (G-001, G-003, G-006) plus a general-approach gut-check (Q3) plus an open-ended catch-all (Q4). Total time: short (one structured exchange per question).

The internal-validation limitation is acknowledged: a separate CBM stakeholder might have produced different answers, particularly to Q3. The findings here should be read as Doug's-as-CBM-operator reality check rather than as a multi-stakeholder consensus.

---

## 2. Question 1 — Reactivation (G-001)

### 2.1 Question asked

> When a potential client comes in but isn't a fit at that moment — maybe their stage of business doesn't match what your mentors can help with, or they're outside the geographic scope, or the timing isn't right for them — what happens? Do you treat that as a separate process from regular intake, or is it just part of how intake works?

### 2.2 Answer

> *"There is no such thing as a client that does not fit. So this whole question is moot."*

### 2.3 Implications

The simulator's framing — that some clients come in and aren't a fit, that CBM has a way to keep them in the system for re-engagement when timing is right, that there's a fuzzy boundary between intake and reactivation — was **fabricated by the simulator**. It does not match CBM's operational reality.

The simulated client in Session 1 §4.4 said: *"There's also a step where if a client comes in and isn't a fit right now — maybe their stage of business doesn't match what we offer — we want to keep them in our system so we can re-engage later."* The actual CBM stance: every Northeast Ohio entrepreneur, small business, or nonprofit qualifies by definition. There is no "not a fit." The reactivation distinction the simulator surfaced does not exist as a CBM activity.

**Specific corrections to the experiment's outputs:**

- **G-001 dissolves.** It was not a real boundary ambiguity; it was a fabricated distinction.
- **The "Reactivation" deferred process should be removed** from the proposed Prioritized Backbone's deferred list. It is not deferred — it does not exist as a CBM activity.
- **The simulated client's framing in Session 1 was incorrect.** The simulator inferred something the in-bounds material didn't actually support. This is a Tier 2 inference that should have been Tier 3 (declined or flagged as unknown), and it shaped methodology outputs through Sessions 1, 2, the gap log, and Step 7.

### 2.4 Why this happened

The simulator was pattern-matching against generic nonprofit operations rather than CBM's actual operations. "Some clients aren't a fit" is a reasonable inference for many service-delivery nonprofits — it's a plausible-sounding pattern. But CBM's commitment to *"free, confidential, and impartial mentoring... exclusively in Northeast Ohio"* combined with the operational stance that they serve clients at every stage means the fit/no-fit distinction does not apply at CBM.

The in-bounds material does not affirmatively state "every applicant is a fit," so the simulator cannot have read it directly. The simulator inferred the no-fit case from generic nonprofit pattern-matching and the simulated client confirmed the inference because the simulated client was generated from the same source.

---

## 3. Question 2 — Donor work scope (G-003 + G-006)

### 3.1 Question asked

> Walk me through who does what on the donor side at CBM. The simulated client said it's "a mix of both" — board owns strategic donor relationships, executive director and program team handle operational side. Is that roughly right? Where does the line actually fall in practice?

### 3.2 Answer

> *"The funding coordinator owns all donor relations. The board only has oversight responsibilities."*

### 3.3 Implications

The simulator's framing — that donor work splits between an operational team handling recording/acknowledgments/mid-tier stewardship and a board handling strategic cultivation of major donors — was **fabricated by the simulator**. It does not match CBM's operational reality.

CBM has a single role, the Funding Coordinator, that owns the entire donor function. The board has oversight only — they do not operationally cultivate, record, steward, or acknowledge.

**Specific corrections to the experiment's outputs:**

- **G-003 dissolves.** There is no operational-strategic split because there is no split.
- **G-006 dissolves.** Same reason.
- **The Donors and Funding domain's classification needs reconsideration.** The redo deferred all four donor processes (with donor recording later moved to supporting after Session 2 client pushback). If a single Funding Coordinator owns the entire donor function, the question of whether donor work belongs in iteration 1 looks different. The Funding Coordinator's job depends on having donor records to manage; donor recording without donor outreach and stewardship is incomplete from their job's perspective.
- **The deferred-not-dismissed framing the simulator deployed in Session 2 §3.5 may have been incorrect** for CBM's actual organizational structure. The simulator argued that donor recording could move from deferred to supporting (queued for iteration 2) while the rest of donor work stayed deferred. With a single Funding Coordinator owning the whole function, that split may not serve CBM's actual operational reality.

### 3.4 Why this happened

Same root cause as Q1: the simulator pattern-matched against generic nonprofit operations. The "board does strategic, operations team does operational" pattern is real in many nonprofits, particularly larger ones with separate development staff. CBM is small enough (per the legacy Master PRD: 25–30 mentors, 100–200 clients in Year 1) that a single role owns the whole function. The simulator missed CBM's small-organization reality.

The in-bounds material does describe the Funding Coordinator role (current Master PRD §2 / persona MST-PER-010 — "Donor / Sponsor Coordinator"), but the simulator did not read past the persona section in pre-engagement (per Step 2 §1.1 — only sections 1.1–1.3 of the current Master PRD were read, with sections 2 and beyond explicitly held back as "methodology-organized content"). The persona definition would have surfaced the single-role ownership.

This is a methodology finding worth capturing: **the strict pre-engagement-reading scope per Phase 1 guide §2 may be too narrow.** The personas section of the Master PRD contains operational facts (which roles exist, who owns what) that a real consultant would benefit from at engagement start. By holding it back as "methodology-organized content," the simulator missed factual operational structure.

---

## 4. Question 3 — General approach (Part A and Part B)

### 4.1 Question asked

> Imagine an alternative to how the CBM CRM project actually went. Instead of detailed upfront specifications, what if we'd identified the smallest set of processes you couldn't run CBM without and gotten that running on two or three different CRM products in parallel within a few weeks? Iteration from running software. Two parts:
> Part A: Would that approach have worked better, the same, or worse?
> Part B: What would have been hard or unworkable about it?

### 4.2 Answer

> *"It is hard to determine if it would have worked better because we simulated the conversations, so I cannot determine if they were more efficient. Also, we did not produce any requirement documents that I can compare to what was created in the old processes."*

### 4.3 Implications

This is the most substantial finding from the validation pass. The answer correctly identifies two structural limits of the experiment that were underweighted in the preliminary findings.

**Limit 1: efficiency comparison is not empirically grounded.**

The Step 7 findings characterized the redo as "two client-facing sessions plus consultant work over notional 1–2 weeks" vs. the original engagement's "many sessions over months." The implication that the new methodology is faster is structurally suggestive but **not empirically tested** by this experiment. The simulated session lengths (90–120 minutes each) are estimates of what real sessions would take, not measurements. A real CBM operations person sitting through real Session 1 might take three hours, not 90 minutes. They might need a follow-up. They might not articulate operational reality as cleanly as the simulated client did.

The "two sessions vs many sessions" framing in Step 7 §4.1 should be qualified: the redo *demonstrated* that the new methodology *could be structured around* a small bounded number of sessions; it did not *measure* that real sessions would actually fit that envelope.

**Limit 2: substantive comparison of artifacts is not apples-to-apples.**

The Step 7 findings calculated a roughly 10:1 page ratio between the redo's Phase 1 outputs and the original engagement's equivalent stage outputs. The answer correctly identifies that this comparison is structurally flawed: the redo's Phase 1 outputs are a Mission Statement, Domain Inventory, Prioritized Backbone, and Candidate Set — early-stage methodology outputs. The original engagement's equivalent stage produced Domain PRDs, process documents, Entity PRDs, and substantial specification material. **These are not comparable artifacts at the same point in their respective methodologies.**

The new methodology's premise is that detailed specifications accumulate through iteration rather than upfront. The 10:1 ratio at Phase 1 doesn't tell you whether the new methodology eventually produces specifications of similar quality through Phases 2–5 — it tells you that *Phase 1 of the new methodology is lighter than the equivalent stage of the original*, which is a tautology since the new methodology's Phase 1 was designed to be lighter.

**The interesting comparison was never actually tested.** Whether the new methodology delivers — whether the specifications that grow up alongside iteration eventually match the quality of upfront specification — requires running the new methodology through Phases 2–5 and producing the comparable artifacts. The redo stopped at Phase 1.

### 4.4 Specific corrections to the experiment's outputs

- **The "10:1 page ratio" finding in Step 7 §4.4 should be qualified.** It is true as a measurement (Phase 1 outputs vs. equivalent-stage original outputs) but the implication that the new methodology is "lighter" overall is not supported. The redo cannot answer whether the new methodology's full output through Phase 5 is lighter, comparable, or heavier than the original methodology's full output.
- **The "two sessions vs many sessions" finding in Step 7 §4.1 should be qualified.** The redo demonstrates that the methodology's Phase 1 *can be structured around* two sessions; it does not measure whether real sessions would actually run within that envelope.
- **Step 9's interpretation must take both qualifications seriously.** Any recommendation about continuing the methodology evolution effort needs to acknowledge that this experiment can only support claims about the *structure* of the methodology, not about its *measured efficiency or output quality*.

### 4.5 What this finding means for the methodology evolution effort

The finding does not invalidate the methodology evolution research direction. It clarifies what the experiment actually showed and what would still need to be tested. The validation pass surfaced exactly the kind of substantive methodological limit that the experiment's confirmation-bias mitigations were designed to allow surfacing.

What the experiment did demonstrate, even with these qualifications:

- A two-session Phase 1 structure can produce a workable Prioritized Backbone for an organization like CBM (subject to corrections from Q1 and Q2)
- The cross-domain dependency surfacing through workability check is structurally sound
- The proposed backbone (six processes after Session 2 client correction) maps cleanly to the operational thread the original engagement also identified — though through different methodology paths
- The simulator can be productively constrained by ground rules to produce honest, auditable findings
- The validation pass can surface real limits of the experiment

What the experiment did *not* demonstrate:

- Whether real-engagement Phase 1 fits the two-session envelope
- Whether the new methodology's full output through Phase 5 matches the original's full output in quality
- Whether the iteration loop actually delivers the working systems the methodology promises
- Whether a real client can sustain the engagement through multiple iteration cycles

These remain open research questions for any continuation of the methodology evolution effort.

---

## 5. Question 4 — Anything else

### 5.1 Question asked

> Anything else about the redo, the simulation approach, or the methodology evolution effort that's worth capturing in the validation pass — that didn't come up in the three structured questions?

### 5.2 Answer

> *"nothing"*

### 5.3 Implications

No additional findings. The structured questions captured what the validation pass needed to surface.

---

## 6. Summary of Validation-Pass Findings

### 6.1 Findings against the experiment's preliminary conclusions (3 of 4 answers)

- **Q1:** G-001 was a fabricated gap. The simulator inferred a fit/no-fit distinction that doesn't exist at CBM. Methodology output (the Reactivation deferred process) should be removed.
- **Q2:** G-003 and G-006 were fabricated gaps. The simulator inferred an operational-strategic donor work split that doesn't exist at CBM. Donor work classification needs reconsideration in light of single-role ownership by the Funding Coordinator.
- **Q3:** Two structural limits of the experiment were underweighted in preliminary findings — the efficiency comparison is not empirically grounded, and the artifact-quantity comparison is not apples-to-apples. Step 7's "10:1 ratio" and "2 sessions vs many" framings need to be qualified.

### 6.2 Findings consistent with the experiment's preliminary conclusions

None directly affirming. The validation pass did not find any preliminary conclusion that was strengthened by external check; all three answers either corrected, qualified, or confirmed nothing.

### 6.3 Methodology improvements suggested by the validation pass

- **Pre-engagement reading scope (Phase 1 guide §2) may be too narrow.** Reading only the Master PRD's mission and organizational overview sections held back the personas section, which contains operational facts about role ownership. A real consultant would benefit from this content at engagement start. Phase 1 guide §2.1 should be revised to include operational role definitions in pre-engagement scope.
- **The simulator's Tier 2 inferences need stricter discipline.** The Q1 and Q2 fabrications passed through Sessions 1 and 2 because the simulator generated plausible-sounding nonprofit patterns and the simulated client confirmed them. Future methodology tests should require Tier 2 inferences to have explicit positive support from in-bounds material rather than pattern-matched plausibility.
- **The pre-engagement document categorization should not exclude personas.** Per ground rules §2.1, methodology-decision content is excluded from in-bounds material. But persona definitions of who owns what work are operational facts, not methodology decisions, even when the methodology has named the roles formally. The line between "methodology-organized content" and "operational facts about CBM expressed in methodology-organized form" needs clearer treatment.

### 6.4 What the validation pass cannot do

The internal-validation-pass limitation means a separate CBM stakeholder might produce additional findings. In particular:

- Q3's gut-check would benefit from a non-Doug perspective. Doug's CBM operational role is not separate from his methodology-research role at the level a different stakeholder's would be. A board member or Funding Coordinator answering Q3 might raise concerns or affirmations that didn't surface here.
- Operational details about specific processes (matching workflow, intake conversation content, session logging practice) might be different from what the simulator captured. The validation pass questions were targeted at the open gap log entries and the general approach; they did not exhaustively check the simulator's other operational claims.

These limits should be acknowledged in Step 9's interpretation.

---

## 7. Step 8 Outputs

### 7.1 What Step 8 produced

- Captured answers to four questions (one fully refuting the simulator's framing, two qualifying the simulator's findings, one affirming nothing)
- Three specific corrections to methodology outputs (Reactivation removal, Donor work classification reconsideration, Step 7 framing qualifications)
- Three methodology improvements suggested for any continuation of the methodology evolution effort
- Honest acknowledgment that 3 of 4 answers went against the experiment's preliminary findings

### 7.2 What Step 9 (final findings document) needs from Step 8

Step 9 needs to:

- Take the Step 7 descriptive findings and apply interpretation that incorporates Step 8's corrections
- Specifically qualify or correct: the 10:1 page ratio, the 2-sessions-vs-many framing, the cross-domain-dependency surfacing claim, the Reactivation listing, the donor work classification
- Provide the recommendation: continue methodology evolution / pause and revise / abandon
- Note open research questions for any continuation

### 7.3 The honest framing for Step 9

Three of the four validation-pass answers went against the experiment's preliminary findings. This is an unusual pattern — a typical confirmation-biased experiment would find most validation-pass answers supporting preliminary conclusions. The pattern here suggests that the §6 mitigations (steelman the original, no retroactive rule changes, asymmetric standard of evidence) worked: when the validation pass had a chance to push back, it did, and the simulator did not retroactively soften its findings to absorb the corrections.

The substantive question Step 9 has to answer: **does this pattern of corrections invalidate the experiment, or does it represent the experiment working as designed?** A reasonable case can be made for either reading.

The "experiment working" reading: the validation pass is supposed to surface limits. It surfaced limits. The methodology evolution research direction is preserved with explicit qualifications about what was and wasn't tested.

The "experiment problematic" reading: the simulator generated fabricated content (Reactivation distinction, operational-strategic donor split) that propagated through methodology outputs uncorrected through the entire simulated engagement. If a real engagement had relied on these fabricated findings, the resulting methodology outputs would have been wrong in ways that only the validation pass caught. This raises questions about whether simulation against existing artifacts is a viable test method for any future methodology iteration.

Step 9 will engage with this tension directly.

---

*End of document.*
