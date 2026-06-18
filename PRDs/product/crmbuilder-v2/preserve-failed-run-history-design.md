# Preserve Failed-Run History — design

**Status:** design (requirement-first). No implementation in the originating
session; this document is the design deliverable for human review.

**Project:** PRJ-038 — Preserve Failed-Run History (Release Pipeline). Sibling
design successor to PRJ-031 (Release Pipeline & Staged Delivery, complete).

**Governance:** Topic TOP-098 (under TOP-094); session SES-213; provenance
conversation CNV-134. Requirements **REQ-259** (parent) + **REQ-260..264**
(children), all `confirmed`. Approving decision **DEC-546**. Episode of record:
**DEC-545** (the REL-004 cleanup).

---

## 1. Why this exists

The first real release-pipeline fleet build, **REL-004**, scoped the build-batch
project **PRJ-037** (PIs 229/230/231), ran the agent fleet through freeze →
reconciliation → architect-decompose → development, completed the first PI's
Design phase, and **halted** on a malformed duplicate-phase decomposition (since
fixed by PI-233 / REQ-258). The operator then "cleaned up the wreckage." That
cleanup **destroyed history**:

- the `project_belongs_to_release` scope edge (PRJ-037 → REL-004) was
  **hard-deleted** to free the project for a re-run;
- the 6 phase workstreams (WSK-144..149) were **soft-deleted**;
- the only surviving first-class record of "this project was processed through
  this release and failed here" is the narrative decision DEC-545 plus low-level
  `change_log` events.

For a system whose entire purpose is traceability, silently losing the record of
a real (failed) execution is a defect.

### 1.1 The root cause is a model flaw, not just operator error

`project_belongs_to_release` is **single-membership** — and the guard in
`access/repositories/references.py` counts *all* existing edges from the project,
not just edges into an active release:

```python
if relationship == "project_belongs_to_release":
    existing_count = session.scalar(
        select(func.count(Reference.id)).where(
            Reference.source_type == "project",
            Reference.source_id == source_id,
            Reference.relationship_kind == "project_belongs_to_release",
        )
    )
    if existing_count and existing_count > 0:
        raise UnprocessableError(... "delete the existing ... edge first")
```

So a project belongs to **at most one release ever**. To re-scope a project for a
re-run, the prior edge **must be deleted**, which erases the prior attempt from
the release's composition. Under today's model, "clean for a re-run" and
"preserve the failed-run history" are **mutually exclusive**. That is the flaw
the requirement set targets.

### 1.2 There is no first-class run/outcome record

A `Release` carries its pipeline-stage `release_status` and lifecycle stamps, and
its composition is **purely derived** from the live `project_belongs_to_release`
edges (`releases._in_scope_projects`). The cancel path is a plain
`transition(... "cancelled")` — there is no `cancel()` that captures *what
happened*, no halt point, no cause, no findings link. The closest analogue,
`deposit_event`, records *applies*, not release runs. A failed run is therefore
answerable only by raw `change_log` archaeology or by reading a decision's prose.

---

## 2. What REL-004 lost vs. retained (reconstruction)

Established by querying `change_log` on the live `v2-unified.db` (ENG-001).

**REL-004 lifecycle** (7 release `change_log` events) — the run walked every gate
cleanly before it was abandoned:

| time | transition |
|---|---|
| 17:44:35 | insert → `preliminary_planning` |
| 17:47:52 | → `development_planning` |
| 17:47:52 | → `reconciliation` (freeze) |
| 17:49:23 | → `architecture_planning` |
| 17:50:41 | → `ready` (planned-completely) |
| 17:50:41 | → `development` (single-occupancy) |
| **19:20:52** | → **`cancelled`** |

**The scope edge** — REF-4982 (PRJ-037 → REL-004) was **inserted 17:44:35** and
**hard-deleted 19:20:52** (same second as the cancel).

**The phase workstreams** — WSK-144..149 are **soft-deleted** (recoverable with
`?include_deleted=true`):

| WS | phase | status |
|---|---|---|
| WSK-144 | Design | Complete |
| WSK-145 | Develop | Ready |
| WSK-146 | Test | Ready |
| WSK-147 | Design | Ready  ← malformed second triple |
| WSK-148 | Develop | Ready |
| WSK-149 | Test | Ready |

**Surface impact, today:** `GET /releases/REL-004/composition` returns
`{"projects": []}`. The releases panel shows the cancelled run as having
contained **nothing**. Its real composition survives only outside the
first-class model.

### 2.1 Is the trace actually recoverable? — Yes (and that is the worked example)

Critically, the hard-deleted scope edge **is not truly gone**: the delete
`change_log` row carries the full edge in its `before_payload`
(`REF-4982 … source_id=PRJ-037 … target_id=REL-004 …`). The workstreams are
soft-deleted. So REL-004's entire trace **can** be reconstructed from
`change_log` + `?include_deleted=true`.

**Recommendation: do NOT reconstruct REL-004 now.** Leave it as the *worked
example* that motivates the model change, exactly as DEC-545 narrates it.
Reconstituting it into a new run-outcome record is best done *with* the new model
(it would otherwise be a one-off hand-built artifact in a shape the model does not
yet define). DEC-546's consequences note records that the trace is recoverable
and may be reconstituted when the model lands. (One secondary gap to note for the
build: the delete event's `before_payload` captured the edge, but a hard-delete
of *both* sides of a richer record could lose more — see §7.)

---

## 3. Design

The five child requirements map to five design moves. Each below states the
recommended option and works the trade-offs.

### 3.1 Retire-not-delete (REQ-260)

**A first-class "abandon a run" operation** that keeps the run, its composition,
and its phase records as the preserved evidence, marking the run as a closed
attempt — instead of deleting edges/rows.

- **Recommended:** add a `releases.abandon(identifier, *, reason, halt_point)`
  repository operation (and `POST /releases/{id}/abandon`) that performs the
  `→ cancelled` (or `→ superseded`) transition **and** writes the run-outcome
  record (§3.3) **and explicitly does not touch the scope edges or phase
  workstreams**. The scope edges remain; the workstreams remain (their terminal
  statuses already tell the story — Design Complete, the rest Ready). This is the
  *only* sanctioned cleanup path.
- **Mirror:** this is the project-supersede philosophy ("never reopen; make a new
  one") at the *run* grain. A failed run is closed, not erased; a re-attempt is a
  *new* run.
- **Phase records:** the current soft-delete of the phase workstreams during
  cleanup is **prohibited** by REQ-264. The workstreams stay; if a re-run needs a
  clean decomposition it builds a *new* set under a *new* run, leaving the failed
  set attached to the abandoned run as evidence. (The decompose bug that produced
  the malformed triple is already fixed by PI-233, so a re-run will not recreate
  the malformation.)

### 3.2 Single-membership vs. history (REQ-261)

Two coherent options; the requirement permits either and asks the design to
choose.

**Option A — relax the guard to "at most one *active* release."**
Change the `project_belongs_to_release` guard to count only edges into a release
in an **active** (non-terminal) status — i.e. ignore edges into `cancelled` /
`superseded` / `shipped` releases. A project may then be scoped into a new run
while the cancelled run keeps it in its composition; the project's history spans
runs.

- *Pro:* the run-grain history falls out of the existing edge model for free;
  composition queries already derive from edges, so a cancelled run's composition
  is simply correct again.
- *Con:* the guard becomes a status-aware count (a join/lookup per insert);
  "active" must be defined precisely (recommend: not in `{cancelled, superseded,
  shipped}` — a shipped release's project is *complete*, so it should not be
  re-scoped either, but PI-227 already completes delivered projects, so this is
  naturally exclusive). The exclusivity invariant REQ-189/211 ("a project belongs
  to exactly one *active* release") is preserved in spirit.

**Option B — a separate immutable history record.**
Keep the edge strictly single-active-membership but, on abandon, copy the
composition into the run-outcome record (§3.3) as an immutable snapshot, then the
edge may be re-pointed. History lives in the outcome record, not the live edge
set.

- *Pro:* the live edge set stays minimal and the guard stays a simple count;
  history is explicitly a snapshot (cannot drift).
- *Con:* composition is now told in two places (live edges for active runs, the
  snapshot for closed runs); the panel and `composition()` must read both.

**Recommendation: Option A**, with the run-outcome record (§3.3) *also* capturing
a composition snapshot at abandon time as a convenience/robustness backstop. A is
the smaller, more honest change — it makes the *existing* derived-composition
query tell the truth for a cancelled run, rather than introducing a parallel
representation. The snapshot in the outcome record then guarantees the answer
even if edges are later (legitimately) re-pointed for a correction release.

### 3.3 A queryable run-outcome record (REQ-262)

**Recommended: a first-class `release_run` (or `run_outcome`) satellite record**
of the release, written at abandon/ship time, capturing:

- `scope` — the projects and planning items in the run at close (a snapshot, per
  §3.2 backstop);
- `phases_run` — each phase workstream and its terminal status (e.g. Design
  Complete, Develop Ready);
- `halt_point` — the stage/phase where it stopped (e.g. `development` /
  Develop-phase);
- `cause` — free text + optional structured code (e.g. `malformed_decomposition`);
- `findings` — links to any `finding` (FND-) records produced;
- `outcome` — `shipped` | `abandoned` | `superseded`.

**Compare to `deposit_event`:** this is deliberately the same *shape* as a
deposit event (a born-terminal, append-only outcome record of a process step),
applied to release runs instead of applies. A `deposit_event` answers "what did
this apply write?"; a `release_run` answers "what did this run attempt and where
did it die?". Recommend modeling it as an **engagement-scoped satellite with a
composite FK to `releases`**, born terminal (append-only), mirroring
`deposit_event`'s discipline. A release that runs the lane more than once (rework
bounce-backs, or a re-attempt under a correction release) can have more than one
run-outcome row, so do **not** make it 1:1 with the release.

*Lighter alternative considered:* store halt/cause as columns on `releases` and
call it done. Rejected — it is not a *record of a run* (a release can run the lane
multiple times), it cannot hold the composition snapshot cleanly, and it does not
generalize to fleet runs that are not 1:1 with a release.

### 3.4 Surfacing (REQ-263)

In the Releases panel, a cancelled/superseded run must **not** render an empty
Composition tab. Specifically:

- the **Composition tab** reads the run-outcome snapshot (or, under §3.2 Option A,
  the now-correct derived composition) and shows the scoped projects → PIs;
- a new **Outcome** section (or tab) shows: outcome badge (`abandoned` /
  `superseded` / `shipped`), the halt point, the cause, the per-phase terminal
  states, and links to findings;
- the run-outcome record is read via a new client method + detail-extras section,
  degrading independently (per the panel's existing one-failing-read-never-blanks
  rule, DEC-530).

Data-model-wise this just means `composition()` (or the outcome read) returns the
preserved scope for a closed run, and the panel surfaces the outcome fields.

### 3.5 The cleanup contract (REQ-264) — the standing rule

State explicitly, as durable governance, and bind it on humans **and** agents:

> **Cleaning up after a failed run means retiring it while preserving its
> record. No cleanup or teardown operation may hard-delete the evidence of what
> a run scoped, which phases ran, or where it failed.**

This belongs in the same family as the established lessons that *teardown must
not destroy traceable history* (the "ADO can't share main's working tree" hazard;
the project-supersede "never reopen" rule). Recommended homes:

- as the confirmed requirement REQ-264 (done);
- as a `governance_rule` (GVR-) row bound to the release/PI-Lead agent profiles in
  the Agent Profile Registry, so the agents that drive runs are *governed* by it
  (advisory→enforced as the abandon operation lands);
- echoed in the CLAUDE.md release-pipeline note when the build lands.

---

## 4. Decomposition sketch (for a later session — not built here)

A plausible PI breakdown (subject to the architecture pass):

1. **Relax the scope-membership guard** to at-most-one-*active* (§3.2 Option A) +
   tests.
2. **`release_run` satellite + migration** (engagement-scoped, composite FK,
   born-terminal) + repo + REST + tests.
3. **`releases.abandon()` operation** (transition + write outcome + preserve
   edges/workstreams) + `POST /releases/{id}/abandon` + tests.
4. **Panel surfacing** — Composition reads preserved scope; new Outcome section.
5. **Governance rule** (GVR-) bound to the release/PI-Lead profiles + CLAUDE.md
   note.
6. *(optional)* **Reconstitute REL-004** into a `release_run` from `change_log`
   once the model exists — the worked example becomes the first real record.

---

## 5. Open questions for review

1. **Entity name:** `release_run` vs `run_outcome` vs reusing/extending
   `deposit_event` with a release-run kind. (Recommend a distinct `release_run` —
   deposit events are tied to applies and the close-out machinery.)
2. **Fleet runs not 1:1 with a release:** the requirement says "release *or*
   fleet" run. Today a fleet run *is* a release run (the lane). If a future fleet
   run spans releases, the run-outcome record may need to be release-independent.
   Recommend modeling it against `releases` now and revisiting if a
   release-independent fleet run appears.
3. **Should `abandon` be the only path to `cancelled`/`superseded`?** Recommend
   yes for releases that have entered a lane state (i.e. actually *ran*); a
   release abandoned in `preliminary_planning`/`development_planning` never ran
   and can stay a plain transition (nothing to preserve). The build should gate
   the outcome-record requirement on "did it run."
