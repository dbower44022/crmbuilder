# Pattern Library Specification

**Document type:** Active design work for an evolved methodology (research / not adopted)
**Repository:** `crmbuilder`
**Path:** `PRDs/process/research/evolved-methodology/pattern-library-specification.md`
**Last Updated:** 04-30-26 22:30
**Version:** 0.1 (initial draft)

---

## Status

This document is **active design work for an evolved methodology that has not been adopted.** It specifies the structure and mechanics of the pattern library referenced by `phase-1-interview-guide.md` §8 but not previously specified. The current 13-phase Document Production Process and existing interview guides remain authoritative for any active engagement.

This specification is the first concrete next step from the CBM redo's Step 9 §6.4 recommendation. The library it specifies does not yet exist in populated form; the first entry (`pattern-library-entry-nonprofit-mentoring.md`) is a separate artifact that will be drafted against this specification once the specification is committed.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 0.1 | 04-30-26 22:30 | Doug Bower / Claude | Initial draft of the pattern library specification, addressing the test-method correction identified in the CBM redo Step 9 §4.2. |

---

## Change Log

**Version 0.1 (04-30-26 22:30):** Initial creation. Specifies the two-document structure (spec separate from entries), the entry content structure (hybrid descriptive plus prescriptive with confidence levels), the tested-vs-observed separation for handling single-source content, the consultation mechanics during pre-engagement and between-sessions work, the contribution mechanics for accumulating learning across engagements, and the failure modes the library design tries to prevent.

---

## 1. Why This Specification Exists

This section is bounded — it captures the reasoning that motivated the spec without becoming a discussion of methodology test results.

The CBM redo experiment (`cbm-redo/`, completed 04-30-26) surfaced that without org-type-specific knowledge available to the consultant during pre-engagement and between-sessions work, both human consultants and the simulator default to pattern-matching against generic operational patterns. Two specific fabrications produced during the redo — a fit/no-fit client distinction and an operational-strategic donor work split — were both plausible patterns from generic nonprofit operations that turned out not to apply to CBM specifically. The fabrications propagated unnoticed through the simulation because the simulated client (also produced by the simulator) confirmed them.

The pattern library is the methodology's response to this failure mode. It is the place where org-type-specific knowledge lives, structured so that consultants encounter explicit content about *what's typical for this org type* and *what varies significantly between instances*. With the library populated, pattern-matching has a disciplined source rather than being an open-ended generation of plausible-sounding content.

Library entries that don't exist yet — meaning the methodology operates without library-disciplined pattern-matching — are explicitly marked as low-confidence engagements during which the consultant should be more cautious about accepted defaults. This is the "no library entry exists" mode already referenced in `phase-1-interview-guide.md` §8.1.

This specification draws on the Step 9 §4.2 finding that the pattern library is more important than initially modeled, and on the §5.3 recommendation that future methodology testing not rely on simulation alone. The specification is structured to support both human consultants and any future automated agents in resisting confirmation-biased pattern-matching.

The specification stops here on motivation. The rest of the document proceeds forward-looking.

---

## 2. What the Pattern Library Is

The pattern library is a structured collection of **org-type entries**, each capturing accumulated knowledge about how organizations of that type typically operate, what's typical of the type, what varies significantly between instances, and what defaults have proven workable.

### 2.1 Scope

The library covers organizational structure, operational patterns, technology constraints, and methodology defaults. It does not cover product-specific guidance (which CRM does X better), implementation details (how to configure a particular CRM for a particular feature), or client-specific information (which would be in client documentation, not the library).

### 2.2 Library structure

The library is a directory of entries. Each entry is a single markdown document covering one org type. Org types are defined narrowly enough that the entry's content actually applies — "nonprofit volunteer-driven mentoring organization" is more useful than "nonprofit," because the latter is too broad to produce useful operational generalizations.

Entries reside in `PRDs/process/research/evolved-methodology/pattern-library/` (or a similar location once the methodology is adopted; for the research period, the location may differ). The first entry will be `pattern-library-entry-nonprofit-mentoring.md` for nonprofit volunteer-driven mentoring organizations.

### 2.3 Library identity

The library belongs to the methodology, not to any specific engagement. Multiple engagements contribute to and consult the library; no single engagement owns it.

### 2.4 Library scope is open-ended over time

The library starts with one entry and grows as the methodology is applied to additional client types. There is no fixed number of entries. New entries can be created when the methodology encounters an org type that doesn't fit any existing entry, and existing entries can be split when a single entry tries to cover instances diverse enough that the generalizations don't hold.

---

## 3. Entry Content Structure

This is the most consequential part of the specification because the entry's content structure is what disciplines pattern-matching during consultation.

### 3.1 The two-section split: tested vs. observed

Every entry has two main content sections.

**Section A — Tested generalizations.** Content that has been observed across multiple instances of the org type and demonstrated to hold beyond a single client. This content can be used as defaults during pre-engagement reading and between-sessions consultant work. Confidence is high enough that proposing it confidently in Session 2 is defensible (subject to client verification per Phase 1 guide §5.4).

**Section B — Observed at single instances.** Content that has been observed at one or more specific clients but has not yet been confirmed across enough instances to qualify as a tested generalization. This content is reference material the consultant reads as starting hypotheses to test, not as defaults to apply. The consultant treats observed content as low-confidence input — it shapes what to ask about, but does not shape what to assume.

The split is explicit and structural. A consultant reading the entry knows immediately which section content comes from and treats it accordingly.

### 3.2 The promotion mechanism

Content moves from Section B to Section A when it has been observed at multiple instances and either confirmed consistent or shown to hold across the variation observed. The library does not specify a fixed threshold (e.g., "three engagements") because some patterns may be confirmed cleanly at two engagements while others remain ambiguous after five. The promotion mechanism is deliberately judgment-based — the methodology owner reviews accumulated observations periodically and promotes content that has earned the higher-confidence status.

When content is promoted, the entry's revision control records what evidence supported the promotion and which engagements contributed.

### 3.3 The demotion mechanism

Content moves from Section A back to Section B (or is removed entirely) when a new engagement contradicts a tested generalization. The library is designed to be self-correcting — false generalizations that slip into Section A get caught when they fail to apply, and the failure is preserved as a record of the variation that exists in the org type.

Demoted content is not deleted; it is moved to a third section described in §3.5.

### 3.4 Confidence levels within Section A

Even within tested generalizations, confidence varies. Section A content is tagged with one of three confidence levels:

- **High confidence** — observed consistently across multiple engagements with no significant variation. Used as a default with light verification during Session 1 or 2.
- **Medium confidence** — observed across multiple engagements but with notable variation in some dimension. Used as a starting point that should be verified explicitly with each new client because the variation might apply.
- **Low confidence (in Section A)** — promoted from Section B but with limited supporting evidence. Used as a hypothesis the consultant tests early in Session 1 rather than as a default.

The high/medium/low distinction prevents the single-section structure of Section A from flattening real differences in how settled different content is.

### 3.5 Disconfirmed observations section

When content is demoted from Section A or directly contradicted by a new engagement, it moves to **Section C — Disconfirmed observations** rather than being deleted. This section preserves the record of what was once thought typical but proved variable. The methodology benefits from this preservation: when a future consultant is tempted to assume something is typical, they can check whether it has been disconfirmed in past engagements.

Section C content is read as a warning, not as guidance. *"This was once thought typical of the org type but has been observed not to apply at instance X. Verify rather than assume."*

### 3.6 Within each section, content categories

Each entry's Section A and Section B (and where applicable, Section C) is organized by category. The categories are consistent across all entries to support comparison and consultation. The standard categories are:

1. **Mission and operational center** — what this org type does at its operational core; what distinguishes it from related org types
2. **Funding model** — how money flows; who funds; what constraints the funding model imposes
3. **Staffing model** — paid vs. volunteer; full-time vs. part-time; specialized vs. generalist; typical org size
4. **Stakeholder structure** — who has authority; who has oversight; how decisions get made; common multi-stakeholder patterns
5. **Domains and processes** — what kinds of work this org type typically does; what's typically mission-critical; what's typically supporting; what's typically deferred
6. **Cross-domain dependencies** — common handoffs that surface in workability checks for this org type
7. **Technology constraints and preferences** — typical FOSS-vs-commercial leanings; typical user demographics; typical integration needs
8. **Common backbone shapes** — typical iteration-1 backbones for this org type, with notes on what's usually mission-critical and what's usually supporting
9. **Common deferral patterns** — what this org type typically defers in iteration 1 with low risk
10. **Common pitfalls** — patterns that look right but typically aren't, things that often surprise consultants

Not every entry has content in every category. Empty categories are explicitly marked "no observations yet" rather than omitted, so a consultant reading the entry knows what's missing rather than assuming missing content means nothing applies.

### 3.7 Entry header

Each entry begins with:

- **Org-type name** (the precise definition the entry covers)
- **Inclusion criteria** (what makes an organization fit this entry vs. a different one)
- **Adjacent org types** (cross-references to similar entries the consultant should consider)
- **Source engagements** (which client engagements contributed observations, anonymized if necessary)
- **Standard methodology document footer** (revision control, change log, last-updated timestamp)

The inclusion criteria are deliberately narrow. "Nonprofit volunteer-driven mentoring organization" doesn't apply to nonprofit advocacy organizations or to commercial mentoring platforms; the criteria say so explicitly.

---

## 4. Consultation Mechanics

This section specifies how the library is used during the methodology.

### 4.1 Pre-engagement consultation

Per Phase 1 guide §2 (with the §2 revision pending from Step 9 §6.4 step 2), the consultant performs pre-engagement reading. The library consultation happens here.

**Step 1 — identify candidate entry.** Based on the materials the client provided in pre-engagement, the consultant identifies which library entry (if any) applies. The match should be deliberate: not every nonprofit fits the nonprofit-mentoring entry, and overly broad matching defeats the discipline.

**Step 2 — read the matched entry.** The consultant reads the entry end-to-end. This is part of the pre-engagement preparation. Section A content informs the consultant's working hypotheses. Section B content informs what to listen for. Section C content alerts the consultant to assumptions that have failed in the past.

**Step 3 — note where the client appears to differ from the entry.** Even before Session 1, the pre-engagement materials may surface ways this client differs from the typical entry content. The consultant captures these differences as items to verify in Session 1, not as defaults to apply.

**Step 4 — when no entry matches.** Per Phase 1 guide §8.1, the consultant operates in "no library entry" mode: more cautious about accepted defaults, explicit acknowledgment in Session 2 that proposals are based on judgment rather than accumulated patterns. The lack of a matching entry is itself information — it suggests the engagement may produce content that becomes the seed of a new entry.

### 4.2 Between-sessions consultation

The consultant's between-sessions work (Phase 1 guide §4) uses the library as a reference for the proposed Prioritized Backbone and Initial CRM Candidate Set.

**For the Prioritized Backbone:** the entry's "Common backbone shapes" content (Section A, category 8) gives the consultant typical iteration-1 backbones for this org type. The consultant adapts the typical backbone to the specific client's Session 1 findings — this is not "use the library's backbone unchanged" but "use the library's backbone as a starting structure that the client's specific operations adjust."

**For cross-domain dependencies:** the entry's "Cross-domain dependencies" content (Section A, category 6) gives the consultant common handoffs that surface in workability checks for this org type. The workability check still has to be performed against the specific client's processes, but the library content disciplines what the consultant looks for.

**For the Candidate Set:** the entry's "Technology constraints and preferences" content (Section A, category 7) supports CRM candidate selection. If the entry says "this org type typically requires senior-accessible UI" with high confidence, the candidate set should reflect that constraint without re-eliciting it from the client.

**For deferred classifications:** the entry's "Common deferral patterns" content (Section A, category 9) gives the consultant org-type-specific deferrals that are typically safe in iteration 1. This disciplines the deferred-vs-supporting line by giving it accumulated evidence rather than per-engagement consultant judgment.

### 4.3 During Session 2

The library is mostly invisible during Session 2 — the consultant is presenting the proposed backbone, not citing library content. But the library shapes how the consultant frames the proposal. Specifically, per Phase 1 guide §8:

- **When a library entry exists** (especially Section A high-confidence content), the consultant frames the proposal as grounded in patterns observed across similar engagements: *"What we've seen consistently is X; based on what you described, your situation looks like that pattern with one variation: Y."*
- **When operating in no-entry mode** (or when relying on Section B observed-at-single-instance content), the consultant frames the proposal as grounded in judgment from this engagement plus consultant experience, with explicit acknowledgment that the proposal is more provisional than usual.

The framing distinction matters because clients respond differently to "we know this pattern is typical" vs. "we're inferring from what you said." Library-backed framing produces more substantive engagement; judgment-only framing invites more push-back. Both are appropriate to their actual confidence levels.

---

## 5. Contribution Mechanics

This section specifies how engagements contribute back to the library.

### 5.1 What gets contributed

After each engagement using the methodology completes Phase 1 (or any subsequent phase), the consultant captures observations that should feed the library:

- **Operational facts about the client** that confirm or contradict existing entry content
- **Patterns that recurred** across multiple processes or domains in the engagement
- **Cross-domain dependencies the workability check surfaced** that weren't in the entry
- **Defaults that worked** when applied during between-sessions consultant work
- **Defaults that failed** when client review or iteration deployment surfaced problems
- **Pitfalls or surprises** that didn't match the entry's expectations

### 5.2 How contributions are captured

A new section is added to the engagement's pre-validation findings document (the equivalent of `cbm-redo-step-7-pre-validation-findings.md` in the redo): a contribution log capturing what this engagement observed and how it relates to the library entry. This log is the input to library updates.

### 5.3 Library entry updates

The methodology owner reviews accumulated contribution logs periodically and updates the library entry. Updates are versioned per the standard methodology document revision control. Specifically:

- **New observations** are added to Section B with a reference to the contributing engagement
- **Confirming observations** raise the engagement count for existing Section B content; promotion to Section A happens when the count and consistency support it
- **Contradicting observations** trigger demotion of Section A content to Section C, with the contradiction preserved as evidence of variation

### 5.4 Anonymization

Client engagements are referenced in the library by anonymized identifiers when the client has not consented to public attribution. The library's purpose is methodology improvement; client-specific operational details should be generalized in entry content, not preserved verbatim.

For the research period (before broader methodology adoption), the CBM redo's contribution to the first entry is preserved with attribution because CBM is not yet a real client engagement under the new methodology — the redo was a test, not a client-serving engagement.

---

## 6. Library Lifecycle and Maintenance

### 6.1 Initial population

The library begins with one entry — the nonprofit volunteer-driven mentoring organization entry — populated initially from CBM redo observations. All initial content for that entry resides in Section B (single-source observations) since CBM is one engagement. Section A starts empty or with only the most universal content that holds across the methodology owner's prior consultant experience with related org types.

### 6.2 Growth path

The library grows as the methodology is applied to additional engagements. Each new engagement either:

- **Contributes to an existing entry** if the org type matches
- **Creates a new entry** if no existing entry fits
- **Splits an existing entry** if the engagement reveals that the existing entry was too broad

### 6.3 Maintenance triggers

The library is reviewed for promotion, demotion, and reorganization at three triggers:

- **After each engagement's Step 9 equivalent** — contribution logs are reviewed and entries are updated
- **At a periodic cadence** even when no engagement has just completed — to catch slow-growing patterns or accumulated low-priority observations
- **When the methodology itself is revised** — to ensure library structure still matches methodology assumptions

### 6.4 Methodology owner

The library has a single methodology owner who is responsible for review, promotion, demotion, and reorganization decisions. During the research period, this is Doug. As the methodology evolution effort matures, the methodology owner role would be formalized.

The methodology owner is not a sole authority — entry updates should be discussed and reviewed — but ownership prevents the library from drifting through inconsistent contributions.

---

## 7. Failure Modes the Library Tries to Prevent

This section captures the failure modes the library design is structured to address. Each failure mode references the experiment finding that surfaced it.

### 7.1 Pattern-matching against generic operations

**Failure mode:** consultant (or simulator) defaults to plausible-sounding content for an org type because no specific knowledge is available.

**Library prevention:** Section A content provides org-type-specific defaults that displace generic patterns. Section B content provides observed-but-not-tested patterns that explicitly require verification. Section C content warns away from patterns that have failed in the past.

**Source:** CBM redo Step 8 §2.3 (Q1 fabrication of fit/no-fit distinction) and §3.3 (Q2 fabrication of operational-strategic donor split).

### 7.2 Calcifying single-engagement specifics into "typical"

**Failure mode:** content from a single engagement gets treated as typical of the org type because no other evidence exists yet.

**Library prevention:** the tested-vs-observed split structurally prevents single-source content from being treated as a default. Section B content is reference material, not defaults.

**Source:** CBM redo Step 9 §5.2 (the simulator's pattern-matching produced fabrications that propagated because no library entry disciplined them; the same risk exists if a library is built from one engagement's content treated as universal).

### 7.3 Methodology drift through inconsistent contributions

**Failure mode:** different consultants contribute to the library in different ways, producing inconsistent content that confuses rather than disciplines.

**Library prevention:** standard category structure across all entries; methodology owner reviews contributions; entries are versioned with standard revision control.

**Source:** general methodology design principle, not specific to the redo.

### 7.4 Out-of-date content

**Failure mode:** library content that was true when written becomes outdated as org types evolve, but the library doesn't reflect the change.

**Library prevention:** the demotion mechanism and the periodic review cadence; Section C preserves disconfirmed content as evidence of variation rather than deleting it.

**Source:** general methodology design principle.

### 7.5 Library treated as authoritative rather than as accumulated evidence

**Failure mode:** consultant treats library content as binding on a specific client even when the client's actual operations differ.

**Library prevention:** the consultation mechanics in §4 explicitly frame library content as starting hypotheses rather than client truth; the framing distinction in §4.3 makes explicit that library-backed proposals are still subject to client verification.

**Source:** CBM redo Step 9 §4.2 ("Pattern library is more important than initially modeled" — but the library being more important does not mean it is authoritative).

---

## 8. What This Specification Does Not Cover

Acknowledged gaps for future work:

- **The detailed format of an entry's content within categories.** This specification names the ten standard categories but does not specify, for each category, exactly what content belongs there or how it is formatted. The first entry (`pattern-library-entry-nonprofit-mentoring.md`) will surface format questions that may need to be standardized later.
- **The promotion threshold.** §3.2 explicitly leaves the threshold for promotion from Section B to Section A as judgment-based rather than fixed. As the library grows, more concrete criteria may be useful.
- **Cross-entry inheritance.** Some content might apply across multiple entries (e.g., common patterns across "all volunteer-driven service-delivery nonprofits"). Whether entries should explicitly share content via cross-references or duplicate it is a design question deferred to when multiple entries exist.
- **Tooling for library management.** Library entries are markdown documents; consultation is by reading. Whether library content eventually warrants tooling (search, contribution forms, contradiction detection) is deferred.
- **Library access patterns for non-Phase-1 work.** This specification focuses on Phase 1 consultation. Library content may also be useful in later phases (Phase 2 Slice Planning's defaults; Phase 4 Iteration Review's comparison artifact). Specifying those access patterns is deferred to when the relevant phase guides are written or revised.
- **Public vs. private library content.** Some library content may eventually be appropriate to publish broadly; some may be confidential to the methodology owner or the client. Access control is deferred.

---

## 9. Connection to Other Methodology Artifacts

This specification connects to:

- **`phase-1-interview-guide.md` §2 (pre-engagement reading)** — the consultation point during pre-engagement. The Phase 1 guide §2 will need revision per Step 9 §6.4 step 2 to reference the library's expected mechanics.
- **`phase-1-interview-guide.md` §4 (between-sessions consultant work)** — the consultation point during proposed-backbone drafting. Phase 1 guide §4 will need revision to include explicit library consultation steps.
- **`phase-1-interview-guide.md` §8 (pattern library handling)** — already references the library as future work; revision will replace future-work language with concrete consultation mechanics from this specification.
- **`cbm-redo-ground-rules.md`** — when ground rules are updated to v0.3 per Step 9 §6.4 step 3, the simulator's interaction with the library should be specified (what the simulator may read from a library entry, how Tier 2 inferences are constrained by library content, etc.).
- **The first entry** — `pattern-library-entry-nonprofit-mentoring.md` will be drafted against this specification as the next concrete step.

---

## 10. What This Specification Enables

When populated, the library enables:

- **Faster, more disciplined pre-engagement preparation.** Consultants enter Session 1 with org-type-specific working hypotheses rather than generic ones.
- **More confident between-sessions proposals.** The proposed Prioritized Backbone is grounded in patterns observed across similar engagements rather than individual consultant judgment.
- **Better Session 2 conversations.** The framing distinction in §4.3 produces conversations that are appropriately confident or appropriately provisional based on library state.
- **Methodology improvement over time.** Each engagement contributes to the library, making subsequent engagements better-grounded than earlier ones.
- **Catching of confirmation bias.** The Section A / B / C split makes it visible when a consultant is reasoning from generic patterns vs. tested generalizations vs. single-source observations.

These are the design intentions. Whether they are realized depends on the library being populated honestly and maintained consistently, which is a function of the methodology's overall discipline rather than this specification alone.

---

*End of document.*
