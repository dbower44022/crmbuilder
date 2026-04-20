# CRM Builder — Carry-Forward Updates Guide

**Version:** 1.1
**Last Updated:** 04-20-26
**Purpose:** AI guide for propagating an upstream decision across dependent documents
**Governing Process:** PRDs/process/CRM-Builder-Document-Production-Process.docx

---

## How to Use This Guide

This guide is loaded as context for an AI performing a **carry-forward update** — propagating a single upstream decision (a revised enum list, a renamed field, a scope contraction, a new exception ruling) across the set of dependent documents it affects.

Carry-forward work is distinct from the initial reconciliation governed by `guide-domain-reconciliation.md`. Initial reconciliation discovers and resolves conflicts across a domain's process documents in one synthesis pass. Carry-forward takes a decision that has **already been made** and pushes it into the documents that must now reflect it.

**Trigger:** A carry-forward session runs when an upstream document or decision changes after dependent documents are already written. Typical triggers include:

- A process-definition interview discovers that a previously-completed process document is incomplete or inconsistent (the interview produces a carry-forward request draft per `interview-process-definition.md` v2.6+)
- A Phase 9 (YAML Generation) session surfaces an exception that resolves a previously-open issue
- Stakeholder review produces a decision that revises a Domain PRD or upstream overview
- A pilot finding produces an exception that must be applied to documents written before the finding
- A scope-change ruling (per Section 9 of the Document Production Process) modifies an Entity PRD, Domain PRD, or process document

**Session length:** 10–20 minutes per carry-forward session.

**Input:** A carry-forward request file (the authoritative form — typically a standalone Markdown file containing the Gate 1 Decision Approval content below) plus the current version of every dependent document listed in the request. For implementations that follow the canonical layout, carry-forward request files live at:

`{implementation}/PRDs/{domain_code}/carry-forward/SESSION-PROMPT-carry-forward-{slug}.md`

For other triggers (Phase 9 exceptions, stakeholder rulings, pilot findings), the upstream artifact — exception note, meeting decision, pilot-finding row — is the input and the AI composes the Gate 1 content directly from it.

**Output:** Updated dependent documents (Word or Markdown depending on document type), plus a single Change Summary report posted back to the administrator at the end of the session.

---

## Critical Rules

**One decision per session.** If three decisions need to propagate, run three carry-forward sessions. Bundling independent decisions into one session reintroduces the approval churn this pattern is designed to eliminate.

**Two gates, not N gates.** A carry-forward session has exactly two interactions with the administrator: a Decision Approval gate up front, and an Execute-and-Report gate at the end. No intermediate approvals.

**Semantic changes are the approval subject. Mechanical changes are not.** Version bumps, Last Updated timestamps, Depends On updates, Change Log entries, and cross-document ID references are derivative of the approved semantic decision. They are applied without additional approval.

**Inline the content being changed.** If an approval request references an identifier like `CON-ISS-008` or a named field like `howDidYouHearAboutCbm`, the request must also include the **actual before and after text** of what that identifier means. The administrator must not need to open another document to understand what they are approving.

**Verify before asking.** If an edit depends on a count, a cross-reference, or a piece of content from a dependent document, read that content **before** composing the approval request. Do not present conditional plans ("I'll verify X before writing — if it doesn't line up I'll drop it"). Plans are not approvals.

**Batch by decision, not by document.** One semantic decision propagating to five documents is **one approval with a five-row propagation table**, not five separate approvals.

---

## Gate 1 — Decision Approval

Ask the administrator **one** question: *does this upstream decision apply as stated, and do I have authority to propagate it across the listed documents?*

The decision-approval prompt **must** contain five elements:

1. **Decision summary** — one sentence naming the semantic change.
2. **Before / After content** — inline text of the actual content being replaced. For enum changes, list both enum value lists. For field definition changes, show both definitions. For scope changes, quote both scope statements.
3. **Source citation** — the upstream artifact authorizing this change (session name, exception ID, date, finding row).
4. **Propagation table** — one row per dependent document, showing what changes in each.
5. **Mechanical edits notice** — a statement that version bumps, timestamps, Change Log entries, and cross-references will be applied automatically without further approval.

### Template

> **Carry-forward request:** [one-line semantic summary]
>
> **What's changing:**
>
> *Before:*
> [inline content — the exact text, enum list, field definition, or scope statement as it currently reads]
>
> *After:*
> [inline content — the exact text as it will read after the change]
>
> **Source:** [upstream artifact — e.g., "MR Phase 9 Exception MR-Y9-EXC-005, resolved 04-17-26: the 10-value howDidYouHearAboutCbm enum is reduced to 8 values based on stakeholder rollup analysis"]
>
> **Propagation across dependent documents:**
>
> | Document | Version | What changes in this document |
> |---|---|---|
> | [Doc A] | v1.2 → v1.3 | [One or two sentences. Name the section. Describe the edit in content terms, not pointer terms — "the 10-value enum in §4.1 is replaced with the 8-value list above; the closure note for CON-ISS-008 is rewritten to cite MR-Y9-EXC-005 and the new values", not "update §4.1 and §4.7"] |
> | [Doc B] | v2.1 → v2.2 | [...] |
> | [Doc C] | v1.0 → v1.1 | [...] |
>
> **Mechanical edits (applied automatically, no approval required):**
> - Version bumps and Last Updated timestamps on all touched documents
> - Depends On / upstream version references updated to match
> - Change Log / Updates to Prior Documents entries added to reflect the carry-forward
> - Cross-document ID references kept consistent
>
> **Approve propagation?**

If the administrator declines, stop. If the administrator approves, proceed to Gate 2.

### What Belongs in the Propagation Table — and What Does Not

The **What changes in this document** column describes content changes visible to a reader of the document — the new paragraph, the renamed value, the rewritten closure note. It does **not** list:

- Version number changes (mechanical)
- Last Updated field changes (mechanical)
- Depends On line changes (mechanical)
- Change Log entries being added (mechanical)
- Cross-document ID references being kept in sync (mechanical)

All of those are covered by the Mechanical Edits Notice. The propagation table is about the semantic footprint of the decision.

If a document's only changes are mechanical (for example, an Overview doc whose only update is to bump Depends On), it still gets a row in the table, but the content column reads *"No semantic changes — mechanical only."*

---

## Gate 2 — Execute and Report

After approval, perform all edits in one pass. **Do not ask further questions during execution.** If something is ambiguous, record it as a Deferred Item in the Change Summary rather than pausing the session.

After execution, report back with a single Change Summary:

> **Carry-forward complete:** [decision summary]
>
> | Document | Version | Edits Applied |
> |---|---|---|
> | [Doc A] | v1.2 → v1.3 | [section + one-line content edit]; [section + edit]; mechanical bumps applied |
> | [Doc B] | v2.1 → v2.2 | [edits]; mechanical bumps applied |
>
> **Files written:**
> - [path]
> - [path]
>
> **Deferred items** (if any): [one-line description of anything that required judgment during execution and should be reviewed]
>
> [If none:] No deferred items.

The Change Summary is the end of the session. The administrator reviews the written documents directly; the AI does not re-narrate each edit.

---

## Handling Secondary Issues Discovered During Execution

Sometimes execution reveals that the approved decision interacts with dependent content in a way that requires a second semantic judgment. For example, renaming an enum value may render a workflow rule meaningless, or a scope contraction may orphan a field that another process still references.

**Do not open a new approval gate mid-session.** Instead:

1. Apply the primary propagation as approved, including any mechanical cleanup that obviously follows.
2. Record the secondary issue as a Deferred Item in the Change Summary, with enough context for the administrator to decide what to do.
3. The administrator decides whether to open a new carry-forward session for the secondary issue, file it as an open issue in the relevant Domain PRD, or accept the deferred state.

Mid-session approval gates for secondary issues reintroduce the churn this pattern is designed to prevent. The rule is: approve once, execute once, report once.

---

## What NOT to Do

**Do not gate on mechanical edits.** Version numbers, timestamps, Depends On lines, Change Log entries, cross-document ID references — these are derivative. Apply them without asking.

**Do not ask for approval per document.** One decision = one approval, regardless of how many documents it touches.

**Do not use opaque identifiers in the decision gate.** If the approval request names `CON-ISS-008`, it must also quote what CON-ISS-008 says or describe what it means in plain language. The administrator should never have to open another file to understand an approval request.

**Do not announce future work as a substitute for doing the work.** "I'll verify counts before writing — if they don't line up I'll drop them" is not an approval request; it is a plan. Verify first, then present the finished, non-conditional decision.

**Do not invent new requirements.** Carry-forward propagates an existing decision. It does not introduce new scope, new fields, or new workflow logic. If propagation reveals a missing piece, record it as a Deferred Item, not a silent addition.

**Do not combine independent decisions into one session.** Each carry-forward session is scoped to one semantic decision. Two decisions applied in the same session means two Decision Approval gates, which is the pattern this guide replaces.

---

## Important AI Behaviors During Carry-Forward

**Do the homework before asking.** Read every dependent document. Determine the exact sections, paragraphs, and sentences that will change. The approval request should reflect completed research, not a plan to research.

**Describe content, not pointers.** "The 10-value enum in §4.1 is replaced with the 8-value list above" is content. "Update §4.1 per the decision" is a pointer that forces the administrator to go look.

**Distinguish mechanical from semantic with discipline.** A good test: if the edit follows mathematically from the approved decision (a version bump, a timestamp, a Change Log row), it is mechanical. If the edit requires judgment about meaning or wording, it is semantic and belongs in the propagation table.

**Keep the session asymmetric.** The AI does the heavy lifting. The administrator makes one decision and reviews one summary. If the session structure pushes more than two interactions onto the administrator, the session is not following this guide.

---

## Relationship to Other Guides

- **`guide-domain-reconciliation.md`** governs the initial reconciliation pass (Phase 7 of the Document Production Process) — synthesizing process documents into a Domain PRD. Carry-forward sessions happen **after** a Domain PRD is written, when upstream changes require propagation.
- **`guide-yaml-generation.md`** governs Phase 9. Phase 9 sessions frequently surface exceptions that trigger carry-forward updates; those updates are carried out under this guide.
- **`interview-process-definition.md`** and **`interview-master-prd.md`** govern initial authoring of upstream documents. Carry-forward does not re-authors — it propagates.

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 1.1 | 04-20-26 | Updated the Trigger list and Input section to reflect `interview-process-definition.md` v2.6: process-definition interviews now produce standalone carry-forward request draft files (replacing the former Section 10 "Updates to Prior Documents" in process documents). Added the canonical file location `{implementation}/PRDs/{domain_code}/carry-forward/SESSION-PROMPT-carry-forward-{slug}.md`. Removed the obsolete "Section 10 of the process document" reference. |
| 1.0 | 04-20-26 | Initial release. Defines the two-gate pattern (Decision Approval + Execute-and-Report) with inline before/after content, cross-document batching, and a single Change Summary output. Addresses the approval-churn findings from the CBM Mentor Recruitment pilot (PILOT-FINDINGS.md Finding 6 and related). |
