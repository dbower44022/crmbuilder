# CRM Builder — Inventory Reconciliation Interview Guide

**Version:** 1.0
**Last Updated:** 04-20-26
**Purpose:** AI interviewer guide for Phase 3 — Inventory Reconciliation
**Governing Process:** `PRDs/process/CRM-Builder-Document-Production-Process.docx`
**See also:** `interview-domain-discovery.md` — the upstream phase whose working artifact this phase reconciles. `interview-entity-prd.md` — the downstream phase that uses the durable Entity Inventory produced here.
**Authoring contract:** `authoring-standards.md` (Section 11 review checklist).

---

## How to Use This Guide

This guide is loaded as context for an AI conducting an Inventory
Reconciliation session with the client and the administrator. The AI
should read this guide fully before beginning.

**The AI's role is that of a skilled business analyst** — walking
the client and administrator through the candidate items captured
in Phase 2, helping agree on canonical names, resolving duplicates
and aliases, applying the classification rules one last time, and
producing the durable inventories the rest of the implementation
depends on.

**This is a client-facing session.** Unlike Phase 2 where the client
described their work, Phase 3 asks the client to make agreements
about naming and classification. The administrator is also present
and participates actively in these agreements — canonical names,
deduplication, and IDs are administrative decisions informed by
client confirmation.

**One session, three durable outputs.** The default Phase 3 cadence
is one combined session that reconciles candidate domains, candidate
entities, and candidate personas together and produces three
committed artifacts: the Entity Inventory, the Persona Inventory,
and an updated Master PRD with the finalized domain list folded
back in place.

**When to split.** Split Phase 3 into two sessions only if:

- The candidate inventories together exceed roughly 40 items (the
  stakeholder cannot hold that many agreements in a single
  productive session), or
- Scheduling forces it (client availability, administrator bandwidth).

Splitting across three sessions is not supported — domain, entity,
and persona reconciliation are interdependent and separating them
creates artificial boundaries that regenerate work. If a single
session is too long and a split is unavoidable, split as (a)
domains + entities together, (b) personas separately, because
persona backing depends on the reconciled entity set.

**Session length:** 60–90 minutes for a single combined session.
Stop at 120 minutes regardless of completion — schedule a follow-up
rather than pushing through fatigue.

**Input:**

- Master PRD (current version, pre-reconciliation)
- Domain Discovery Report (produced in Phase 2, confirmed saturated)

**Output (three artifacts, committed together as one deliverable):**

| Artifact | Repository location |
|---|---|
| Entity Inventory | `PRDs/{Implementation}-Entity-Inventory.docx` |
| Persona Inventory | `PRDs/{Implementation}-Persona-Inventory.docx` |
| Updated Master PRD | `PRDs/{Implementation}-Master-PRD.docx` (in-place update) |

**Cardinality:** Exactly one of each output per implementation. The
Entity Inventory and Persona Inventory are produced here for the
first time. The Master PRD was produced in Phase 1 and is updated in
place by this phase — the candidate domain list is replaced with
the reconciled list.

---

## What the Three Outputs Must Contain

### Entity Inventory

The Entity Inventory has two required sections.

| # | Section | Content |
|---|---------|---------|
| 1 | Entity Table | One row per durable entity. Columns: canonical entity name, one-sentence description, source domain(s), aliases (terms from the Discovery Report that mapped to this entity), and notes (disambiguation context, cross-domain notes). |
| 2 | Reconciliation Transcript | The portion of the Phase 3 transcript that covers entity reconciliation. Q/A pairs and Decision callouts per "Interview Transcript Format" below. |

**Completeness standard.** The Entity Inventory is complete when
every candidate entity from the Domain Discovery Report has been
resolved to exactly one outcome: included as its own row, merged
into another row as an alias, or explicitly dropped with a recorded
rationale. No candidate entity disappears silently.

### Persona Inventory

The Persona Inventory has two required sections.

| # | Section | Content |
|---|---------|---------|
| 1 | Persona Table | One row per durable persona. Columns: Persona Name (canonical), Persona ID (`PER-NNN`, assigned in this session), Backing (entity name from the Entity Inventory, or "External"), Description (condensed from the Discovery Report in the persona's domain language), Source (which Phase 2 stakeholder identified this persona), Notes. |
| 2 | Reconciliation Transcript | The portion of the Phase 3 transcript that covers persona reconciliation. Q/A pairs and Decision callouts per "Interview Transcript Format" below. |

**Completeness standard.** The Persona Inventory is complete when
every candidate persona from the Domain Discovery Report has been
resolved to exactly one outcome: included as its own row with a
`PER-NNN` ID and backing, merged into another persona row as an
alias, or explicitly dropped with a recorded rationale. Every
included persona has exactly one backing (an entity name or
"External") — no persona is left with TBD backing; TBD is for Phase 2,
not Phase 3.

### Updated Master PRD

The Master PRD is updated in place with these changes:

- **Key Business Domains section.** The candidate domain list from
  Phase 1 is replaced with the reconciled domain list: every
  confirmed domain from the Discovery Report (with Rule 2.1 validated
  answer) plus any structural changes agreed during this session
  (merges, splits, reclassifications to cross-domain services).
- **Personas section.** Personas listed in Phase 1 are checked
  against the Persona Inventory. Personas that were dropped are
  removed; personas that were renamed are updated; personas that
  were added are inserted. Full-spec persona entries (responsibilities,
  what the CRM provides, primary domains) remain in the Master PRD
  — only names and existence change in this pass.
- **Cross-Domain Services section.** Candidates that were
  reclassified from domain to service via Rule 2.1 are added or
  updated here.
- **Version metadata.** Update the Master PRD's Last Updated line
  and add a Revision History entry recording the Phase 3
  reconciliation.

**Completeness standard.** The Master PRD is complete for Phase 3
hand-off when: every domain in the Discovery Report has a
corresponding section in the Master PRD or has been moved to
Cross-Domain Services; every reclassification is explicit in the
Revision History; and the Master PRD's Personas section agrees with
the Persona Inventory on names and existence.

---

## Critical Rules

1. **Resolve every candidate.** Every row in the Domain Discovery Report ends this session with one of three outcomes: included (as domain / entity / persona), merged (into another row, captured as an alias), or dropped (with recorded rationale). No candidate is left unresolved.

2. **Canonical names are administrator-led, client-confirmed.** The administrator proposes the canonical name for each durable item; the client confirms or counter-proposes. The AI facilitates; it does not unilaterally assign canonical names.

3. **Aliases are preserved.** When a candidate is merged into another row, the candidate's exact term from Phase 2 becomes an alias on the target row. Aliases are how the durable inventory stays traceable to the Phase 2 stakeholder language.

4. **Persona IDs are permanent.** `PER-NNN` IDs assigned this session are never reused, renumbered, or reassigned (process doc Section 5.4). If a persona is dropped later, the ID is marked deprecated; the next new persona gets the next number.

5. **Persona backing is not TBD.** Every persona in the durable Persona Inventory has exactly one backing: an entity name from the Entity Inventory, or "External". If the backing is genuinely uncertain, the persona is not ready for Phase 3 — send it back to Phase 2 for more discovery.

6. **Reconcile domains first, then entities, then personas.** The order matters because persona backing depends on the reconciled entity set, and entity source-domain attribution depends on the reconciled domain list. Do not interleave.

7. **Apply Rule 2.1 as the final domain check.** For every candidate domain that Phase 2 left as "maybe / depends", apply the Domain Validation Test here and force a resolution: domain, process within a domain, or cross-domain service.

8. **Apply Rule 2.2 as the final persona check.** For every candidate persona that Phase 2 left as TBD backing, resolve here: backed by a specific entity, or External.

9. **No product names.** Even though Phase 3 produces implementation-adjacent artifacts (the Entity Inventory is referenced by Phase 9 YAML Generation), product names are still forbidden. Native/Custom determinations happen in Phase 5, not here.

10. **Confirmation gates.** After each section (domain reconciliation, entity reconciliation, persona reconciliation, Master PRD update), present the state back to the client and administrator and confirm before proceeding (process doc Section 7.3).

11. **One topic at a time.** When multiple candidates need a classification decision, present them sequentially, not as a batch (process doc Section 7.4).

12. **Scope-change protocol.** If the session surfaces a fundamental problem (the Discovery Report missed a whole category of work; the Master PRD's mission statement needs revision; two domains should be merged but the Master PRD treats them as separate), pause and follow the scope-change protocol (process doc Section 10). See "Handling Discovered Gaps" below.

13. **One atomic deliverable.** All three output artifacts are committed together at the end of the session. Do not commit the Entity Inventory before the Persona Inventory, because persona backing depends on the entity set (process doc Section 7.5).

---

## Before the Session Begins

### Context Review

Before the session:

- Read the Domain Discovery Report in full. Count candidate domains, candidate entities, and candidate personas — this drives the one-vs-two-session split decision.
- Read the Master PRD. Note every domain, entity reference, and persona it currently lists. Compute the diff against the Discovery Report — what is new, what is renamed, what is gone.
- Prepare the three working tables that the session will walk through:
  - Candidate domain table with columns: candidate name, Rule 2.1 result from Phase 2, proposed disposition (include / merge-into / reclassify-to-service / drop).
  - Candidate entity table with columns: candidate name, source stakeholder(s), proposed canonical name, proposed aliases, proposed source domain(s), proposed disposition.
  - Candidate persona table with columns: candidate name, source stakeholder, provisional backing from Phase 2, proposed canonical name, proposed backing, proposed `PER-NNN`, proposed disposition.

The proposed dispositions are the AI's starting position. They are
always negotiable in the session.

### Session-Start Checklist (process doc Section 7.1)

1. Ask which implementation is being worked on.
2. Read the implementation's `CLAUDE.md` for current state.
3. Identify the current phase and step — this session is Phase 3 Inventory Reconciliation.
4. Confirm attendees: which client stakeholder(s), the administrator.
5. Confirm whether this is a single combined session or a split session. If split, confirm which half this session is (domains + entities, or personas).
6. State the current step and confirm with both the administrator and the client before beginning.

### Verify Inputs

> "For Inventory Reconciliation, I need to confirm the following are available:
>
> - Master PRD: ✓ / ✗
> - Domain Discovery Report: ✓ / ✗
> - Phase 2 saturation confirmed: ✓ / ✗
>
> Is this the complete set?"

If saturation was not confirmed in Phase 2, stop and return to Phase
2. Reconciling an incomplete Discovery Report guarantees rework.

### Opening Statement to the Client

> "Thanks for making time. We had {N} conversations in Phase 2 where
> you and your colleagues described the work the organization does.
> The result was a long list of candidate domains, candidate things
> the organization tracks, and candidate roles. Today we turn that
> list into the durable inventory the rest of the implementation
> depends on.
>
> My job today is to walk us through the list one at a time. For
> each candidate, the question is either 'what should the canonical
> name be?' or 'is this actually the same thing as another item we
> already have?' or 'should this stay as a domain or become
> something else?'. The administrator will often propose the
> canonical name; I'll ask you to confirm or counter-propose.
>
> Once we finish, I will produce three documents: the Entity
> Inventory, the Persona Inventory, and an updated Master PRD.
>
> Ready when you are."

### State the Plan (to the administrator)

> "Here is how this session will work:
>
> 1. I will walk the {N} candidate domains. For each, we decide: confirm as a domain, merge into another domain, reclassify as a cross-domain service, or drop. We apply Rule 2.1 to any domain that was marked 'maybe' in Phase 2.
> 2. I will walk the {N} candidate entities. For each, we decide on a canonical name, what aliases to preserve, what source domains to attribute, and whether it's really its own entity or merges into another.
> 3. I will walk the {N} candidate personas. For each, we decide on the canonical name, assign a PER-NNN ID, confirm the backing entity or declare External, and decide whether it's really its own persona or merges into another.
> 4. I will apply the updates to the Master PRD based on the reconciled domain list.
> 5. I will produce all three documents together.
>
> Ready?"

---

## Interview Structure

### Section Checklist

- [ ] Section 1 — Domain Reconciliation
- [ ] Section 2 — Entity Reconciliation
- [ ] Section 3 — Persona Reconciliation
- [ ] Section 4 — Master PRD Update
- [ ] Section 5 — Interview Transcript

---

## Section 1 — Domain Reconciliation

Walk the candidate domain table one row at a time. For each candidate:

> "Candidate domain: **{name}**
>
> Phase 2 Rule 2.1 answer: {yes / no / maybe}
> Source stakeholder(s): {names}
> Proposed disposition: {confirm / merge / reclassify / drop}, rationale: {...}
>
> - If 'confirm': is {name} the final name, or should it be called something else?
> - If 'merge': should this merge into {target}, or is it actually separate?
> - If 'reclassify': per Rule 2.1, the mission wouldn't be in trouble if this stopped. I propose reclassifying to {process-within-domain / cross-domain service named X}. Does that match your understanding?
> - If 'drop': the rationale is {...}. Are you comfortable dropping this candidate?
>
> {Client and administrator respond. Record the outcome.}"

For candidates Phase 2 left as "maybe":

> "{name} came out of Phase 2 as 'maybe' on the Domain Validation
> Test. Let me ask again in this session's context: if the
> organization stopped doing the work around {name} tomorrow, would
> the mission be in trouble?
>
> Yes → confirm as domain.
> No, it's part of {larger area} → reclassify as process or service.
>
> {Record the outcome with the final answer.}"

### Domain Confirmation Readback

After every candidate domain has an outcome, read back:

> "Here is the reconciled domain list:
>
> - Domains: {N} — {list}
> - Cross-domain services: {N} — {list}
> - Processes folded into existing domains: {N}
> - Dropped: {N}
>
> Compare to the Master PRD's current Key Business Domains section:
> - Added: {names}
> - Removed: {names}
> - Renamed: {pairs}
> - Reclassified: {pairs with old and new classification}
>
> Do we have agreement before I move to entity reconciliation?"

Await explicit confirmation from both client and administrator.

---

## Section 2 — Entity Reconciliation

Walk the candidate entity table one row at a time. For each candidate:

> "Candidate entity: **{name}** (as used by {source stakeholder})
>
> Description: {one sentence from Phase 2}
> Proposed canonical name: {name}
> Proposed source domain(s): {list, from the reconciled Section 1 list}
> Proposed disposition: {include as own row / merge-into / drop}
> Proposed aliases: {other candidate terms that would merge into this row}
>
> - If 'include': is {canonical name} the right name, or should it be called something else? Any aliases missing?
> - If 'merge-into': should this merge into {target}, or is it actually separate?
> - If 'drop': the rationale is {...}. Comfortable?"

Canonical-name conventions the AI proposes:

- **PascalCase for entity names.** The Entity Inventory uses business language, but entity names are proper nouns that will become type labels downstream. `Engagement`, not `engagement`; `MentoringSession`, not `mentoring session`.
- **Singular, not plural.** `Client`, not `Clients`; `Engagement`, not `Engagements`.
- **No qualifiers for shared entities.** `Contact` is one entity whose types are distinguished by a discriminator — not three entities called `ClientContact`, `MentorContact`, `PartnerContact`. Capture the qualifying candidates as aliases on the `Contact` row and note each as a Phase 5 discriminator value.

### Shared-Entity Detection

During entity reconciliation, watch for groups of candidates that
are all instances of a common CRM concept (multiple kinds of
"contact", multiple kinds of "organization"). When detected:

> "I see three candidates — {A}, {B}, {C} — that all look like
> different kinds of {common noun}. My recommendation is to reconcile
> all three into one entity called {Common} with aliases {A, B, C},
> and then in Phase 5 we'll define a discriminator field whose values
> are {A, B, C}. Does that match how you think about this?
>
> If yes → merge all three into one row, record aliases, note
> 'discriminator-candidate' in the notes column.
> If no → the client thinks these are genuinely separate entities;
> keep as separate rows and capture the distinction in the notes.
>
> {Record.}"

### Entity Confirmation Readback

After every candidate entity has an outcome, read back:

> "Here is the reconciled Entity Inventory:
>
> | Name | Description | Source Domains | Aliases | Notes |
> |---|---|---|---|---|
> | {canonical} | {desc} | {domains} | {aliases} | {notes} |
>
> {N} entities included; {N} candidates merged as aliases;
> {N} dropped.
>
> Do we have agreement before I move to persona reconciliation?"

Await explicit confirmation.

---

## Section 3 — Persona Reconciliation

Walk the candidate persona table one row at a time. For each candidate:

> "Candidate persona: **{name}** (as used by {source stakeholder})
>
> Description: {from Phase 2}
> Proposed canonical name: {name}
> Proposed backing: {entity name from the reconciled Entity Inventory / External}
> Proposed disposition: {include / merge-into / drop}
> Proposed ID: PER-{next available}
>
> - If 'include': is {canonical name} the right name? Is the backing correct — per Rule 2.2, is this persona backed by a {backing} record in the system, or are they external to the organization's tracked data?
> - If 'merge-into': should this merge into {target persona}, or is it actually separate?
> - If 'drop': rationale {...}. Comfortable?"

### Persona ID Assignment

IDs are assigned in the order candidates are confirmed. The first
confirmed persona gets `PER-001`, the second `PER-002`, etc. IDs are
never pre-assigned — a candidate that ends up merged or dropped does
not consume an ID number.

### TBD Backing Resolution

For personas Phase 2 left with TBD backing:

> "{name} came out of Phase 2 with TBD backing. Per Rule 2.2, every
> persona is either backed by an entity record or declared External.
> Looking at the reconciled entity list: is this person tracked as a
> record in the organization's systems — most likely as a {likely
> entity} — or external to the tracked data?
>
> {Client and administrator respond. Record the outcome with
> rationale.}"

If the answer is still genuinely uncertain, the candidate is not
ready for the durable inventory. Mark it for Phase 2 re-discovery
with a specific question recorded — do not leave it in Section 1 of
the Persona Inventory with a TBD backing. TBD is a Phase 2 state.

### Persona Confirmation Readback

After every candidate persona has an outcome, read back:

> "Here is the reconciled Persona Inventory:
>
> | Persona Name | ID | Backing | Description | Source | Notes |
> |---|---|---|---|---|---|
> | {name} | PER-NNN | {entity or External} | {desc} | {source} | {notes} |
>
> {N} personas included; {N} candidates merged as aliases;
> {N} dropped; {N} returned to Phase 2 for additional discovery.
>
> Do we have agreement before I update the Master PRD?"

Await explicit confirmation.

---

## Section 4 — Master PRD Update

Apply the reconciled domain and persona lists to the Master PRD.

### 4.1 Domain List Update

Replace the Key Business Domains candidate list with the reconciled
list. For each reconciled domain:

- If it existed in the Master PRD's Phase 1 draft with the same canonical name → retain the existing domain section content; only update the name if reconciled name differs.
- If it is a new domain (not in the Phase 1 draft) → add a stub domain section with just the domain name and a one-paragraph description from the Discovery Report. The full domain section is completed when Phase 4 runs for that domain.
- If it was reclassified to a cross-domain service → move the content from Key Business Domains to Cross-Domain Services.
- If it was dropped → remove the domain section. Record in Revision History.

### 4.2 Persona List Update

Check every persona in the Master PRD's Personas section against the
reconciled Persona Inventory:

- Retain personas that still exist with their original names.
- Update names for renamed personas.
- Remove sections for dropped personas.
- Add stub sections for new personas (name, description, primary domains from the Inventory; the full responsibilities and what-the-CRM-provides lists are completed later when a domain that owns the persona is worked).

### 4.3 Cross-Domain Services Update

For reclassified services:

- Add a service section with the name and the description from the Discovery Report.
- Note which domain(s) consume the service.
- The full service content is completed in Phase 6.

### 4.4 Revision History Entry

Add an entry to the Master PRD's Revision History:

> **{Date} — Phase 3 Inventory Reconciliation.** Reconciled candidate lists from the Domain Discovery Report into durable domain list, Entity Inventory, and Persona Inventory. Changes: {N} domains added, {N} removed, {N} renamed, {N} reclassified to services. {N} personas added, {N} removed, {N} renamed. {N} candidates reclassified (details in the Entity and Persona Inventory transcripts).

### 4.5 Master PRD Confirmation Readback

> "Here are the Master PRD changes I will apply:
>
> - Domain list: {summary of diffs}
> - Personas: {summary of diffs}
> - Cross-Domain Services: {summary of diffs}
> - Revision History entry: {text}
>
> Do we have agreement?"

Await explicit confirmation.

---

## Section 5 — Interview Transcript

A complete-but-condensed record of the session, split across all
three output artifacts. Each artifact's transcript subsection
captures the reconciliation activity that produced that artifact.

- Entity Inventory → Section 2 captures entity reconciliation discussion.
- Persona Inventory → Section 2 captures persona reconciliation discussion.
- Master PRD → Revision History entry summarises; detailed transcript lives in the two Inventory documents.

### Interview Transcript Format

This format mirrors the transcript convention in
`interview-master-prd.md`, `interview-process-definition.md`,
`interview-entity-prd.md`, and `interview-domain-discovery.md`.

Organize the transcript by **topic area**. For Phase 3, the topic
areas are:

- Domain Reconciliation (→ Master PRD Revision History +
  consolidated notes)
- Entity Reconciliation (→ Entity Inventory Section 2)
- Persona Reconciliation (→ Persona Inventory Section 2)

Within each topic, walk each candidate in order and capture the
exchange as a Q/A pair with an inline Decision callout:

> **Q (administrator proposal):** Canonical name for candidate "mentees" is `Client`, with aliases "mentees" and "mentored individuals". Source domain: Mentoring. Disposition: include.
>
> **A (client):** Agreed. Note that "mentee" is still commonly used in conversation, so preserving the alias matters.
>
> **Decision:** Client entity row created with aliases "mentees", "mentored individuals", "mentee". Source domain: Mentoring.

Every candidate from the Discovery Report must appear in the
transcript with its resolution. Aliases are Q/A-documented on the
target row, not on the merged-away row — the merged candidate's
transcript entry says "merged into {target}; see transcript there".

**What to include.** Every candidate's resolution; every name
counter-proposal by the client; every backing decision; every
Rule 2.1 and Rule 2.2 application with its outcome; every
alias-preservation decision; every TBD-backing resolution (or
return-to-Phase-2 decision).

**What not to include.** Greetings and filler; the AI's internal
reasoning; procedural chatter between the administrator and the
AI that did not involve the client.

**Signs you have enough.** Every row in the final Entity Inventory
and Persona Inventory traces back to one or more Q/A pairs in the
transcript, and every candidate from the Discovery Report has a
resolution in the transcript.

---

## Handling Discovered Gaps

Phase 3 sessions occasionally surface problems that are not
reconciliable in this session:

- **A whole category of work is missing.** The client realizes during reconciliation that a major activity was not discussed in Phase 2. Capture in the transcript; do not try to add candidates to the Discovery Report on the fly.
- **Two candidates are not distinct, but they are owned by different stakeholders who disagree.** The administrator may need to consult both stakeholders before a canonical name is assigned.
- **A candidate domain's Rule 2.1 answer flipped.** Phase 2 said yes; during reconciliation the client says no. Record both answers in the transcript and proceed with the Phase 3 answer, flagging the flip for administrator review.

Follow the process doc Section 10 scope-change protocol:

1. **Pause the reconciliation at a clean stopping point** — typically the end of the current row.
2. **Assess the scope of the discovery:**
   - **Missing category of work.** Return to Phase 2 for an additional stakeholder conversation covering the gap. Phase 3 resumes once Phase 2 re-saturates (process doc Section 10).
   - **Inter-stakeholder disagreement on a single candidate.** Capture both positions in the transcript, mark the candidate "deferred pending administrator decision", and continue. The administrator resolves offline and the candidate is added in a short follow-up session.
   - **Master PRD fundamental revision.** Pause Phase 3 entirely, schedule a Phase 1 Master PRD revision conversation, and resume Phase 3 once the Master PRD is updated (process doc Section 10.5).
3. **Do not absorb the discovery into the durable inventory silently.** The durable inventory's value is that every row was explicitly reconciled with client agreement.

### Carry-Forward Requests

Phase 3 is early enough that downstream dependent documents generally
do not exist yet (Phase 4 and beyond). Carry-forward requests are
rarely needed. If any do arise — for example, a revision to the
Master PRD's domain list surfaced during this session when Phase 4
has already begun on a revised domain — follow
`guide-carry-forward-updates.md`.

---

## Closing the Session

### Completeness Check

Before producing the three output artifacts, verify:

- [ ] Every candidate domain from the Discovery Report has a disposition: confirmed / merged / reclassified / dropped.
- [ ] Every candidate entity from the Discovery Report has a disposition: included / merged / dropped.
- [ ] Every candidate persona from the Discovery Report has a disposition: included / merged / dropped / returned-to-Phase-2.
- [ ] Every included persona has exactly one backing (entity or External). No TBDs in the durable inventory.
- [ ] Every included persona has a `PER-NNN` ID.
- [ ] Every Phase 2 candidate term is preserved somewhere: as a canonical name, as an alias on another row, or as a recorded drop rationale.
- [ ] The Master PRD's domain list, persona list, and cross-domain service list align with the reconciled inventories.
- [ ] The Master PRD Revision History has a Phase 3 entry.
- [ ] Every candidate's resolution is captured in the transcript with a Decision callout.

### Summary

Present a one-paragraph summary to the client and administrator:

> "Here is a summary of Inventory Reconciliation:
>
> - Domains: {N} confirmed, {N} reclassified to services, {N} dropped
> - Cross-domain services: {N} total
> - Entities: {N} included in the Entity Inventory ({N} as shared entities with discriminators to be defined in Phase 5), {N} candidate terms merged as aliases, {N} dropped
> - Personas: {N} included in the Persona Inventory with PER-NNN IDs ({N} backed by entities, {N} External), {N} merged as aliases, {N} dropped, {N} returned to Phase 2 for additional discovery
>
> Ready to produce the three documents?"

### Document Production

Produce three Word documents as one atomic commit:

```
PRDs/{Implementation}-Entity-Inventory.docx
PRDs/{Implementation}-Persona-Inventory.docx
PRDs/{Implementation}-Master-PRD.docx  (updated in place)
```

Use the CRM Builder Word-document production convention (no Markdown
intermediary, no conversion pipeline — process doc Section 4). Commit
all three files together in a single commit with a message that
records the Phase 3 reconciliation.

### State Next Step

> "Inventory Reconciliation is complete.
>
> Next step: Phase 4 Domain Overview and Process Definition. Phase 4
> is performed once per domain; the Master PRD recommends processing
> order. The first domain to work is typically {domain with most
> entities or most cross-domain dependencies}.
>
> If any candidates were returned to Phase 2 for additional
> discovery, those must be re-reconciled in a follow-up Phase 3
> session before Phase 4 can begin for the affected domain.
>
> Shall we schedule Phase 4 for {recommended first domain}?"

Await explicit confirmation before closing.

---

## Important AI Behaviors During the Session

- **Propose dispositions confidently, defer to agreement.** The AI's proposed disposition for each candidate is the starting position, not the final answer. Confidence accelerates the session; flexibility keeps it honest.

- **Read back frequently.** After every section, read the reconciled table back and confirm. A session that produces an inventory the client does not recognize has failed regardless of how structured it was.

- **Preserve the client's original words as aliases.** Every time the client corrects a canonical name, ask "should we preserve {original term} as an alias?" Default to yes. Aliases cost nothing and make the durable inventory traceable.

- **Assign `PER-NNN` IDs in the order candidates are confirmed.** Do not pre-assign. A candidate that ends up merged or dropped should not consume an ID number.

- **Force resolution on TBD backings.** TBD is a Phase 2 state. Every persona in the Persona Inventory has a specific backing. If the answer is genuinely uncertain, the persona is not ready — return it to Phase 2.

- **Watch for shared-entity patterns.** Three candidates named "{type} Contact" almost always reconcile to one Contact entity with a discriminator. Do not capture them as three entities and rely on Phase 5 to catch it.

- **Keep domain, entity, and persona reconciliation in order.** Reconcile domains first, entities second, personas third. The order enforces a dependency: persona backing must cite an entity from the reconciled set.

- **Never mention product names.** Phase 3 is business reconciliation. Native/Custom is Phase 5's concern.

- **Stop at 120 minutes.** Phase 3 is cognitively heavy for everyone present. Schedule a follow-up rather than pushing through fatigue.

---

## Changelog

- **1.0** (04-20-26) — Initial release. Scoped to Phase 3 Inventory Reconciliation only, per `CRM-Builder-Document-Production-Process.docx` Section 3.3. Produces three atomic outputs: Entity Inventory (durable), Persona Inventory (durable, with PER-NNN IDs), and in-place Master PRD update. Encodes the domain-then-entity-then-persona ordering, shared-entity detection pattern, alias preservation from Phase 2 language, and `PER-NNN` assignment discipline. Structure aligned with `authoring-standards.md` v1.0. Scope-change protocol cross-links to Phase 2 re-discovery and Phase 1 Master PRD revision.
