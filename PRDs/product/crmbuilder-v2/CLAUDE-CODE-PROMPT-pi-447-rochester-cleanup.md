# Session prompt — PI-447: Rochester clean-up (retire the ENG-006 design copy, re-register under ENG-002)

Copy everything below the line into a fresh Claude Code session in
`~/Dropbox/Projects/crmbuilder` once Doug releases the hold on PI-447.

---

Execute PI-447 (project PRJ-117): retire the ENG-006 design copy and re-register
the Rochester instance under ENG-002, per DEC-978.

## Gate — do this first

PI-447 is ON HOLD (Doug, 2026-08-31: Rochester reviews their ENG-006 test
instance first). Ask Doug to confirm the hold is released. If it is not
released, stop — do not begin the inventory.

## Context you must read before acting

Read fresh from the store (it may have moved since this prompt was written):

- **PI-447** — the work item and any status/description changes.
- **DEC-978** — the architecture this executes: the shared chapter design lives
  in ENG-002 (CBM) for now; other chapters' instances register as additional
  ENG-002 instances, each with its own stored feature selection, chapter named
  on the instance record. A dedicated product engagement is the declared
  destination; its trigger is the first chapter bringing its own stakeholders
  or requirements — not this session's concern.
- **DEC-976 / DEC-977** — the sibling decisions PRJ-117's description cites.
- **REQ-546 / PI-444** — the per-instance stored feature selection mechanism
  (live in production since 2026-08-31) the re-registered instance must use.

## The work

This is store/data operations, not code. If any step turns out to need a code,
schema, or migration change, stop and author a requirement first (GVR-230) —
do not code around it.

1. **Inventory ENG-006** before touching it: the cloned 29-entity design, the
   Rochester instance registration, and anything else scoped there
   (stakeholders, decisions, reference pointers). Show Doug the inventory and
   the plan — one approval gate for the whole reorganization (GVR-237), before
   any write.
2. **Re-register the Rochester instance under ENG-002**: chapter identified on
   the instance record, its own stored feature selection attached (the PI-444
   mechanism). Credentials must resolve on the headless host — v2 instance
   credentials are Fernet-encrypted in the shared store, never the OS keyring.
3. **Retire the ENG-006 design copy** so only one design circulates. Retire,
   don't delete (retain-not-delete): status transitions and supersedes edges,
   not row removal, unless Doug explicitly directs deletion.
4. **Verify**: the fleet view (PI-412, resolved) lists Rochester under ENG-002
   with its selection; nothing still resolves the ENG-006 design copy; a
   conformance check against the Rochester instance (PRJ-119's PI-410
   mechanism) runs clean or explains its differences.
5. **Record governance in real time** (GVR-231): session + conversation under
   PRJ-117, decisions at the moment they're made, PI-447 resolved via the
   conversation's `resolves` edge — never a status edit past its lifecycle.

## Boundaries

- Production deploy is human-only (GVR-240): no droplet code deploys, no
  service restarts, no live-schema edits. Store writes through the cloud API
  are the work itself and are fine.
- Interview-style questions to Doug: one decision per message, options with
  costs, recommendation first (PRF-002/PRF-009).
- ENG-006's engagement record itself: propose its end-state (retire vs. keep
  as an empty shell) as one of the decisions — do not choose silently.
