# Claude Code prompt — make "requirement-first governance" an explicit, binding precondition

## Why you are doing this

A working session built **multiple V2 capabilities as code (committed on branches) before any requirement, planning item, or project existed for them** — and in one case before even a PI existed. This is a direct violation of the requirements-provenance rule the project was rebuilt around (*"a capability can never be built without a traced, human-reviewable requirement"* — ENG-001's founding rule), and it happened **repeatedly in a single session without the agent noticing**, because the rule is implied by the architecture but **never stated as a hard, do-this-first precondition** in the files the agent actually reads each session.

The agent rationalized it this way (this is the exact failure mode you must close): the **Model A branch protocol** says "governance applies happen on `main` as a build-closure after merge." The agent over-read that as *"governance is a batch of records I write at the end,"* which let it write code first and plan to backfill the session/decision/deposit-log later. That conflates two different things:

- **WHEN the governance *bookkeeping* lands** (session record, decisions, deposit-event log) — yes, Model A defers these to a build-closure on `main` after merge.
- **WHEN the *requirement* must exist** — it must exist, be **human-approved**, and have an **implementing planning item** *before any code is written*. This is NOT deferrable. The requirement is the authorization to build; deferring it means building unauthorized work.

Your job: make that distinction explicit and binding in the governing files so no future session can rationalize building first.

## The rule to encode (state it plainly, prominently, and as a hard precondition)

> **Governance is a precondition, not a postscript.** Before any development work begins on a V2 capability — code, schema, migration, or build of any kind, on any branch — the following must already exist, **in this order**:
> 1. a **requirement** record stating the capability and why, with provenance (defined in a conversation, belonging to a topic);
> 2. that requirement **confirmed** through the approving-decision path (`requirement_approved_by_decision` → `activate_by_decision`), i.e. **human-reviewed and approved** — never by editing the status field;
> 3. a **planning item** that implements the requirement (`planning_item_implements_requirement` edge), inside a **project**.
>
> Only then is code written. The Model A build-closure defers the *session / decision / deposit-event bookkeeping* to `main` after merge — it does **not** defer the requirement or its approval or the implementing PI. Building before a confirmed requirement + implementing PI exist is a process violation, **even on a branch and even for a one-line or "obviously small" change**. There is no "too small for a requirement" exception; if the change is genuinely trivial and below the requirement threshold, that judgment must itself be stated, not assumed.

Also add the **self-check the agent failed to do**: *before writing or committing any code, confirm out loud that the requirement is confirmed and the implementing PI exists; if not, stop and create them first.*

## Where to put it

1. **`CLAUDE.md`** (primary — this is what every session reads). Add a short, prominent, **top-of-the-v2-governance** subsection titled something like *"Governance is a precondition, not a postscript (read before any V2 build)."* Put it where it cannot be missed — near the "Session orientation protocol" / "v2 session lifecycle" material, and cross-reference it from the "Working conventions" and "Branch-work protocol (Model A)" paragraphs so the Model A text can no longer be misread as "governance is batched at the end." Explicitly call out the WHEN-bookkeeping vs WHEN-requirement distinction above.

2. **The V2 governance recording rules in the database (topic `TOP-013` and its children).** Per DEC-393/394 the canonical governance rules live in V2 as `requirement` records under `TOP-013`, not in a markdown file. Read `TOP-013` first (`curl -s -H "X-Engagement: <ENG>" http://127.0.0.1:8765/topics/TOP-013` then its child topics), find the right child (e.g. the Core Recording Principles topic `TOP-076`, or Planning Item Records `TOP-082`), and **add a new requirement record stating the requirement-first precondition** — authored and **confirmed the correct way** (approving decision; do not hand-edit status), with provenance, so the rule is itself a governed, traced requirement and not an orphan. If you judge a new top-level rule topic is warranted, create one under `TOP-013`.

3. **Auto-memory** (`/home/doug/.claude/projects/-home-doug-Dropbox-Projects-crmbuilder/memory/`). There is already a `feedback_full_governance_always` memory. **Strengthen it (or add a sibling)** so the index line and body state the requirement-first precondition explicitly: never write code before a confirmed requirement + implementing PI exist; Model A defers bookkeeping, not the requirement. Add the one-line pointer to `MEMORY.md`.

## How to do it (process — practice what you encode)

- Read `CLAUDE.md`, then orient on the live V2 DB per the Session orientation protocol (Tier 1–2). Read `TOP-013` and its children before authoring any governance record.
- The CLAUDE.md and memory edits are **documentation of an existing rule**, not a new capability, so they do not themselves need a requirement. The **new `TOP-013` requirement record does** need to be authored + confirmed the proper way (approving decision) — let it be the worked example of the very rule.
- Keep the edits tight and unambiguous. The point is that a future session reading CLAUDE.md cannot rationalize building before the requirement exists.

## Verify before you finish

- `CLAUDE.md` has a prominent precondition subsection, and the Model A paragraph cross-references it (no longer readable as "governance is batched at close").
- A new **confirmed** requirement under `TOP-013` states the requirement-first precondition, with provenance, confirmed via an approving decision (check `requirement_approved_at` is stamped and a `requirement_approved_by_decision` edge exists — i.e. it did **not** go through a status edit).
- The memory index + file are updated.
- Report exactly what you changed and where.

## Context pointers (for the cold session)

- The provenance engine + its founding rule: `CLAUDE.md` → "Requirements-provenance & review rebuild — COMPLETE"; the approval gate is `access/repositories/requirement.py::activate_by_decision` (readability + provenance + topic gates, stamps `requirement_approved_at`); a `requirement_approved_by_decision` edge triggers it.
- The bypass that confirmed-via-status-edit (a *separate* fix, PI-228, closing the `update`/`patch` → `confirmed` hole) is being handled in the originating session; you do not need to touch code. Your scope is the **governing instructions**, so the requirement-first precondition is impossible to miss going forward.
- Model A branch protocol + the "v2 session lifecycle" bullets are in `CLAUDE.md`; that is the text most prone to the "governance is batched at the end" misreading.
