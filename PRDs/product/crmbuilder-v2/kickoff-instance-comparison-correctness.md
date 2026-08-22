# Kickoff — Make instance comparison correct enough for a chapter network

**Target planning items:** PI-409 (declare the compared set), then PI-410 (the check).
**Engagement:** ENG-001. **Written:** 2026-08-22, from SES-359 / CNV-320.
**Prior session's records:** DEC-918…DEC-929, REQ-485…REQ-500, PI-406…PI-413, TERM-031.

---

## Orient first

Run the session bootstrap in this repo's `CLAUDE.md` before anything else: topic
**TOP-013** and its children (TOP-076…086), active `governance_rules`, active
`preferences`, the `reference_pointer` index, and `lessons` for any area you touch.
The database is the source of truth; do not orient from files, including this one.

Read these before forming a plan — they are the decisions this session builds on and
**must not relitigate**:

| Record | What it settled |
|---|---|
| DEC-922 | A chapter network is ONE engagement; chapters are instances under one design |
| DEC-921 | Four sets: captured / emitted / applied / compared — every exclusion names which it leaves |
| DEC-923 | Drift = any difference within a **declared** compared set, evaluated without runtime discretion |
| DEC-928 | The compared set itself: 30 compared, 9 identity keys, 34 excluded (+ a dated correction) |
| DEC-929 | A stored verdict must carry its age; **stale** is a distinct outcome |

The approved compared-set table is
`PRDs/product/crmbuilder-v2/compared-set-declaration.md`, referenced by **WT-068**.

---

## Why this session exists

At one instance, a wrong comparison is an annoyance — a person notices. At twenty
chapter instances nobody can eyeball the CRM, so **the comparison function IS the
maintenance model**. Every property below was found against live data in a single
afternoon; none was visible from reading the code. Assume more remain.

A comparison that is confidently wrong is worse than none, because it is believed.

---

## What was found — all verified 2026-08-22 against CBMTEST (INST-001)

### 1. The surface presents a stale verdict as current — the worst one

The reconcile screen showed `IntakeSubmission — Fields (0 differ)` for CBMTEST.
A live read the same day showed **two of the seven design fields absent** from the
instance: `reason` and `status` return NULL from
`Metadata?key=entityDefs.CIntakeSubmission.fields.<name>` (checked twice, targeted).

Both readings were correct. Stored `instance_membership` recorded them `present` at
an audit dated **2026-08-08**; nothing had re-read the instance since. The surface
reads stored membership by design — a deliberate, defensible choice — but nothing on
screen said the verdict was cached or how old it was.

`last_audited_at` is already stored on every membership row. **Nothing consumes it.**

Governed by DEC-929 / REQ-500.

### 2. The compared scope is emergent, not declared

`espo_impl/core/comparator.py` skips a property when the design leaves it unset **and**
when the API does not return it — the latter with its own comment recording that the
Metadata endpoint omits `label`, `translatedOptions` and some defaults. So what is
compared depends on what the API happened to return on that call, and can move across
EspoCRM versions with nothing reporting that it moved.

Both skip rules are superseded by REQ-490 and must not reach the conformance path.

### 3. Equality rules are being discovered one production surprise at a time

The V2 comparator's `_attr_equal` states that every attribute compares by `==` except
the enum option set, whose order-insensitive rule exists only because ordering produced
false drift (REQ-442). That is the pattern to break, not to continue.

### 4. Neutral-vs-engine representation — UNRESOLVED, and the sharpest trap

The design stores engine-neutral types; EspoCRM returns engine types
(`boolean`→`bool`, `long_text`→`text`, `text`→`varchar`). A textual comparison would
report drift on essentially every field of every entity, permanently.

**But** the reconcile surface displays `submitterEmail · Type` as `text` in all three
columns, which means the audit normalizes engine→neutral **at capture**. So the mapping
already happens somewhere.

The unresolved question, recorded in DEC-929's consequences and NOT decided:
**at which single boundary does the mapping belong** — the reader, or the comparator —
given that one consumer reads stored membership and another reads the instance live?
Applying it at both, or at neither, both produce wrong answers. Establish this before
writing comparison code.

### 5. The mapping layer exists but is empty

`GET /field-mappings` for ENG-002 returns **zero** rows. Yet CBMTEST carries
`dispositionReason` and `intakeStatus`, which resemble the design's `reason` and
`status` but are differently named and differently typed. Nothing connects them, so a
name-based comparison calls two of them missing and two of them extra.

Whether they SHOULD be mapped is a content question for ENG-002, not this session.
What this session must decide is what the comparison does when a plausible-but-unmapped
counterpart exists — silently report both, or surface the candidate.

### 6. Drift is already substantial and undetected

`CIntakeSubmission` on CBMTEST carries **ten non-system fields the design does not
describe**: `contact`, `description`, `dispositionReason`, `dispositionedAt`,
`dispositionedBy`, `emailLink`, `intakeMessage`, `intakeStatus`, `payload`,
`submissionNotes`. The entity's own membership state is already `drifted`
(audited 2026-07-01), but the field rows all say `present`.

Use this entity as the test fixture. It is real, it is messy, and any comparison
function that reports it clean is wrong.

### 7. "Publish path healthy" is not "instance conformant"

The 2026-08-22 production deploy's step 7 reported `publish path: healthy` for INST-001
— correctly; it measures the pipeline. The same instance carries the drift in §6. The
two claims are easily conflated by a reader. Whatever this session builds must not be
mistakable for the other.

---

## What is NOT yet verified — check, do not assume

- Whether `field_externally_populated` has any deployed counterpart. DEC-928 excludes it
  on the belief it does not. **Unverified.**
- Whether other attributes in the approved table carry engine-neutral representations
  needing mapped comparison. DEC-928's correction flags a sweep as necessary and
  **it has not been done**.
- Whether option `translatedOptions` / label handling is stable across EspoCRM versions.
- Whether CBM Production (INST-002) shows the same shape. Only CBMTEST was read.
  **INST-002 is in the publish check's forbidden list — treat it as read-only at most,
  and confirm before touching it at all.**

---

## The work

Ordered. Each gates the next.

1. **Resolve the mapping boundary (§4).** One place, named, with the reasoning recorded.
   Nothing below is correct until this is settled.
2. **Sweep the approved table** for other neutral-representation attributes, and for the
   `field_externally_populated` assumption. Amend DEC-928 with dated corrections rather
   than rewriting it.
3. **Materialize the declaration** as per-attribute data on the design records — the
   table is the working proposal, the records are binding (REQ-490).
4. **Implement attribute-level unknown** (REQ-491) and retire both skip rules (§2).
5. **Implement staleness** (REQ-500): age on every result, `stale` as a distinct outcome.
6. **Prove it against `CIntakeSubmission`** — it must report the §6 drift, and running
   twice unchanged must produce an identical verdict (REQ-492).

---

## Constraints

- **Requirement-first (GVR-230).** These requirements are already confirmed. Anything
  NEW needs a requirement + approving decision + implementing PI before code.
- **`Governed-By: PI-NNN` on every code commit (GVR-229).** Trailers must be contiguous
  at the end of the message — a blank line splits the block and git parses only the last
  group, which happened twice in the prior session.
- **Commit with explicit pathspec; `-m` before `--` (GVR-235).**
- **Never call `put_metadata()`** — the endpoint does not exist (GVR-171).
- **Production deploy is Doug's step (GVR-240).** Prepare and verify; never execute.
- **No new terminology without Doug's approval (GVR-232).** `Chapter` is TERM-031;
  `standard` was deliberately dropped in favour of the four sets.
- **Demonstrable increment before the next PI (GVR-239).** Passing unit tests do not
  substitute; show the comparison running against a real instance.
- **cbm-client-intake is out of scope.** Surface obligations for its own process.

---

## What done looks like

A comparison function whose verdict a person can trust without checking the CRM, because:
it compares a declared set rather than whatever the API returned; it says how old its
reading is; it distinguishes *matches* from *could not read*; it gives the same answer
twice; and it reports the known drift on `CIntakeSubmission` rather than calling it clean.

If the session ends having only resolved the mapping boundary and swept the table, that
is a good session — everything downstream is wrong until those are right.

## Ask before assuming

`PRDs/process/conduct/charter.md` governs, in particular §11.6.b — inferences require
positive support. One question at a time, prose, not menus. The prior session's opening
prompt contained a confidently-stated premise about this repository that was simply
false; verify anything you intend to rely on.
