# Session Prompt — Collapse Critical Rules / Important AI Behaviors (Part 2)

**Operating mode:** ARCHITECTURE
**Pulls from project:** dbower44022/crmbuilder
**Continuation of:** the conduct-sections collapse work begun on 05-24-26
**Pattern authority:** `PRDs/process/interviews/authoring-standards.md` v1.2 (already committed)

---

## Context

This session continues an editorial pass that collapses the redundant
`Critical Rules` and `Important AI Behaviors During the Interview`
(or `... During the Session` / `... During Reconciliation` / `...
During {Activity}`) sections in every phase guide under
`PRDs/process/interviews/` into a single `How to Conduct This Phase`
section.

The decision shape is **Option A** from the prior session (see commit
log around 05-24-26):

> **Pointer + phase-specific only.** "How to Conduct This Phase"
> opens with one paragraph pointing to the Interviewer Charter at
> `PRDs/process/conduct/charter.md` and the Question Library at
> `PRDs/process/conduct/question-library.md`, then lists ONLY the
> rules unique to this phase. Generic interviewer conduct
> (one-topic-at-a-time, confirmation gates, scope-change protocol,
> transcript capture, identifier discipline, listen-more-than-talk,
> avoid-leading-questions, etc.) is canonically governed by the
> Charter and is not restated per guide.

The pattern is now codified in `authoring-standards.md` v1.2
(Sections 5.1, 6.1, 6.3, 7, 11, 12, 13). That document is the
authoritative source for what each updated guide must look like.

---

## What was done in part 1 (05-24-26 sandbox session)

Five files were collapsed and committed:

| File | Old version | New version |
|---|---|---|
| `authoring-standards.md` | 1.1 | 1.2 |
| `interview-master-prd.md` | 1.2 (header) / 1.3 (changelog) | 1.4 |
| `interview-domain-discovery.md` | 1.0 | 1.1 |
| `interview-inventory-reconciliation.md` | 1.1 | 1.2 |
| `interview-entity-prd.md` | 1.1 | 1.2 |

Verify by inspecting the files in the cloned repo before starting.

---

## What remains

Eight files still carry the old structure. They split into two groups.

### Group A — standard guides with both old sections (six files)

For each: bump version, add Charter prereq paragraph to `How to Use
This Guide`, replace `Critical Rules` with `How to Conduct This
Phase` (phase-specific rules only), delete the `Important AI
Behaviors` section entirely, add changelog entry, set Last Updated
to the session's start time in MM-DD-YY HH:MM.

| File | Current version | New version |
|---|---|---|
| `interview-process-definition.md` | 2.7 | 2.8 |
| `guide-domain-overview.md` | 1.1 | 1.2 |
| `guide-domain-reconciliation.md` | 1.6 | 1.7 |
| `guide-carry-forward-updates.md` | 1.1 | 1.2 |
| `guide-crm-evaluation.md` | 1.0 | 1.1 |
| `guide-yaml-generation.md` | 1.1 | 1.2 |

Special note on `guide-crm-evaluation.md`: this is the Phase 10 guide
that carries the **explicit product-name carve-out** rather than the
ban. Per `authoring-standards.md` v1.2 Section 7.8, the carve-out
belongs in `How to Conduct This Phase` for this guide.

### Group B — delta guides without the old sections (two files)

These two guides already lack `Critical Rules` and `Important AI
Behaviors`. They are explicit delta documents whose conduct sections
are named `Additional AI Behaviors for {Service Processes|Service
Reconciliation}`.

For these: rename the section to `How to Conduct This Phase —
Additions` (preserve the explicit delta framing). Add the Charter
prereq paragraph to `How to Use This Guide`. Bump version, add
changelog entry, update Last Updated.

| File | Current version | New version |
|---|---|---|
| `interview-service-process-definition.md` | 1.1 | 1.2 |
| `guide-service-reconciliation.md` | 1.0 | 1.1 |

---

## Rules for selecting phase-specific items

When deciding what stays in `How to Conduct This Phase`, drop a rule
if it is canonically governed by the Charter. The seven
Charter-governed concerns are:

1. One-topic-at-a-time / one-question-at-a-time (Charter Section 4.1)
2. Confirmation gates / confirmation cadence (Charter Section 6)
3. Scope-change protocol (Charter Section 8)
4. Transcript capture format (Charter Section 9)
5. Identifier discipline — the generic rules, not the phase-specific
   identifier format (Charter Section 10)
6. Listen-more-than-talk, avoid-leading-questions, validate-understanding,
   follow-threads, stay-curious, tolerate-ambiguity (Charter Sections 3–5)
7. Session-start checklist / read-CLAUDE.md (covered by `kickoff.md`)

Keep a rule if it is:

- Phase-specific in content (e.g., "three-bucket sort" for Entity PRD,
  "Apply Rule 2.1 to every candidate domain" for Domain Discovery,
  "Required-field completeness is a reconciliation exit criterion"
  for Domain Reconciliation).
- The phase-specific identifier format (e.g., `MN-INTAKE-REQ-001`
  format for Process Definition).
- The no-product-names rule or the Phase 10 carve-out (Section 7.8 of
  the standards doc — not in the Charter).
- The one-deliverable contract for that specific phase (Section 7.5).
- A phase-specific operational reminder that is not a restatement of
  Charter material (e.g., "Stop at 90 minutes" for Entity PRDs,
  "Capture-back every 10–15 minutes" for Domain Discovery).

Two patterns from part 1 to follow:

1. The `Important AI Behaviors` section heading is deleted entirely.
   No stub, no deprecation note. The Charter prereq line at the top
   of the guide is sufficient signposting.
2. The first line of the new `How to Conduct This Phase` section is
   always: "Phase-specific rules for {phase name}. Generic
   interviewer conduct is governed by the Charter (see How to Use
   This Guide)."

---

## Working pattern for this session

1. **Read `crmbuilder/CLAUDE.md`** before doing any work.
2. **Verify the part-1 commit landed.** Run `git log --oneline -5`
   and confirm the commit referenced in this prompt is on `main`.
   Pull if necessary.
3. **Inspect `authoring-standards.md` v1.2 Sections 5.1, 6.1, 6.3, 7,
   11, 12, 13** to refresh the pattern.
4. **Process the six Group A files in order.** For each: read the
   current `Critical Rules` and `Important AI Behaviors` content,
   decide which rules are phase-specific, draft the new `How to
   Conduct This Phase`, apply the four edits (version bump, Charter
   prereq, section replace, section delete) plus the changelog entry.
5. **Process the two Group B files in order.** Rename the
   `Additional AI Behaviors` heading to `How to Conduct This Phase
   — Additions`. Add Charter prereq. Bump and changelog.
6. **Commit and push** all eight files in one commit with a message
   matching the part-1 commit style.

---

## What not to do

- **Do not re-edit the five part-1 files.** They are at the target
  state. Re-touching them risks regressing decisions.
- **Do not change rule wording beyond what the collapse requires.**
  If a rule is being kept, keep its existing wording. The objective
  is structural cleanup, not content rewriting.
- **Do not pull content from the deleted `Important AI Behaviors`
  section back into `How to Conduct This Phase` if it duplicates
  Charter material.** Even if it has nicer wording than the Charter
  version. The Charter is canonical; let it be canonical.
- **Do not add new cross-references to `authoring-standards.md`
  beyond what each guide already has.** Existing references stay.

---

## Done block

Reply at the end of the session with:

- The eight `{filename}: {old_version} → {new_version}` lines.
- The commit SHA(s) for this session's work.
- Confirmation that `git status` shows clean against `origin/main`.
- One line per Group A file naming the count of rules kept (e.g.,
  "guide-domain-reconciliation.md: 5 rules in How to Conduct This
  Phase").
- Any judgment calls that surfaced during the work and the reasoning
  applied (kept in this conversation only — do not write them to a
  doc unless they uncover a structural issue with
  `authoring-standards.md` v1.2 that needs its own changelog entry).
