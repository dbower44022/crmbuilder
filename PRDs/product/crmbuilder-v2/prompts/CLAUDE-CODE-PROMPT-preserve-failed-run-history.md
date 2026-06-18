# Claude Code prompt — design "preserve failed-run history" (requirement-first)

## Why you are doing this

The first real release-pipeline **fleet build** (`REL-004`, scoping the build-batch
project **PRJ-037** → PI-229/230/231) ran the agent fleet through freeze →
reconciliation → architect-decompose → development lane, completed the first PI's
Design phase, and then **halted** (a malformed duplicate-phase decomposition — since
fixed by PI-233). The operator then "cleaned up the wreckage." That cleanup
**destroyed history**:

- the `project_belongs_to_release` edge (PRJ-037 → REL-004) was **hard-deleted** to
  free the project for a re-run, so REL-004's composition no longer shows it ever
  contained PRJ-037;
- the 6 phase workstreams were **soft-deleted**;
- the only surviving record of "this project was processed through this release and
  failed here" is a narrative decision (`DEC-545`) plus low-level `change_log` events —
  there is **no queryable, first-class record of the failed run**.

For a system whose entire purpose is traceability, silently losing the record of a real
(failed) execution is a defect. **"Clean up" must mean "retire while preserving the
record," never "delete the evidence."**

The root cause is a real model flaw, not just an operator error: **`project_belongs_to_release`
is single-membership** — a project's release link is one *current pointer*, not history —
so re-scoping a project for a re-run forces removing the edge, which erases the prior
attempt. Under today's model, "clean for a re-run" and "preserve the failed-run history"
are mutually exclusive.

## Your job

Design — **requirement-first, no implementation code in this session** — the capability that
**failed and abandoned release/fleet runs remain first-class, preserved, queryable history**.
Produce: a confirmed requirement (or small requirement set) with provenance, and a design
document. Decomposition into build PIs can follow; the deliverable here is the *requirement +
design*, reviewed.

Treat the process lesson as itself in scope: encode, somewhere durable, that **retiring a run
preserves its record** (cancel/supersede ≠ delete).

## Investigate first (read-only)

1. **Reconstruct exactly what REL-004 lost vs. retained.** Query the `change_log` for
   `release` REL-004, for the workstreams WSK-144..149, and for the deleted reference edge;
   read `DEC-545`. Establish precisely what is recoverable (soft-deleted workstreams; raw
   events) and what is gone (the hard-deleted scope edge). Decide whether any of REL-004's
   trace should be reconstructed now as part of the fix, or left as the worked example.
2. **Characterize the single-membership tension.** Read `access/repositories/references.py`
   (the `project_belongs_to_release` single-membership guard) and
   `access/repositories/releases.py` (`_in_scope_projects`, the lifecycle, cancel). Confirm
   that a project can belong to at most one release and that re-scoping requires deleting the
   edge.
3. **Survey existing run/attempt records.** Is there ANY first-class record of a release or
   fleet run's outcome? (`deposit_event` records *applies*, not release runs.) Look at the
   release lifecycle, the ADO workstream/work-task lifecycle, and whether a halted run leaves
   any durable "this was attempted and failed here" object beyond `change_log`.
4. **Read the governing context:** the release pipeline memory note in CLAUDE.md, the
   release-pipeline architecture docs (`multi-agent-release-pipeline-architecture.md`,
   `pi-205-release-entity-architecture.md`), and the ADO design docs.

## Design (the deliverable)

Address at least these, and recommend a coherent option for each:

- **Retire-not-delete.** A first-class "abandon / supersede a release run" operation that
  keeps the release's composition and its workstreams as the record (the failed phases stay
  visible, marked retired), instead of deleting edges/rows. Mirrors the project-supersede
  philosophy ("never reopen; make a new one") at the run grain.
- **Single-membership vs. history.** Should `project_belongs_to_release` relax to "at most one
  **active/in-flight** release" so a project's history can span multiple releases (the
  cancelled run keeps the project in its composition; a new release can re-scope it)? Or is a
  separate history record better? Work the trade-offs and the schema/guard impact.
- **A queryable run/outcome record.** Should there be a first-class release-run / attempt
  entity (what it scoped, which phases ran, where it halted, why, the resulting findings) so a
  failed run is queryable, not just narrated in a decision? Compare to the `deposit_event`
  pattern.
- **Surfacing.** How a cancelled/failed release shows what it attempted and why it died — in
  the Releases panel and in the data model.
- **The cleanup contract.** State explicitly, as a rule, that retiring a failed run preserves
  its record; "cleanup" never hard-deletes the evidence.

## Process to follow (practice what the project preaches)

- Orient per the Session orientation protocol; read `TOP-013` before authoring governance.
- **Requirement-first:** open the requirement(s) with provenance (a topic + a conversation),
  and confirm via the approving-decision path (NOT a status edit). Then write the design doc.
  Do not write implementation code in this session — the deliverable is the confirmed
  requirement + the design, for review.
- Real-time governance via API POST (Claude Code default).

## Context pointers

- The episode: `DEC-545`; the decompose fix `PI-233`/`REQ-258`/`DEC-544`; the build batch
  `PRJ-037` (PI-229/230/231 → REQ-251/249/242). The fleet's design docs are on the
  `prj-037-fleet` branch.
- Single-membership guard: `access/repositories/references.py` (the
  `project_belongs_to_release` branch). Release lifecycle + composition:
  `access/repositories/releases.py`.
- The standing lesson this is an instance of: cleanup/teardown must not destroy traceable
  history — the same family as the "ADO can't share main's working tree" hazard. See the ADO
  orchestration memory.
