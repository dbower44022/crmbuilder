# PI-230 / WTK-173 — Release Planning-Item Status-Counts Read API: Design

**Design-phase deliverable** for **PI-230** ("Design requirement approval and
status-counts capabilities"), workstream **WSK-150** (phase: Design). API area.
Specifies the read-API-reachable process that reports, for a release, the count
of its in-scope planning items grouped by lifecycle status — **REQ-242**
(*"Release planning-item status counts"*).

Governing design: `multi-agent-release-pipeline-architecture.md` (the release
container + its release-scoped composition) and the release repository
`access/repositories/releases.py` (the `composition` / `_in_scope_*` traversal
this design reuses). Provenance: REQ-242 ← `CNV-126` ← `TOP-096`, approved by
`DEC-536`.

This is a **specification only**. The implementing code + tests land in the
downstream Development workstream (`WSK-151`, `blocked_by` WSK-150). The design
is written to be implementable verbatim.

## 1. Problem

A planner looking at a forming or in-lane release wants to see, at a glance, how
much of the release's work remains and in what state — the spread of its
in-scope planning items across the lifecycle (`Draft`, `Decomposed`, `Ready`,
`In Progress`, `In Review`, `Resolved`, `Deferred`, `Cancelled`;
`vocab.PLANNING_ITEM_STATUSES`). The release read surface today exposes the
*membership* of that scope — `GET /releases/{id}/composition` returns the
release's release-scoped Projects and the Planning Item identifiers under each —
but a client wanting status counts must fetch every PI individually and tally
client-side. There is no single read that answers "how many PIs are in each
status" for a release.

The other release reports are status-shaped but PI-status-blind: `freeze`,
`temperature`, and `planning-readiness` report the *release's* stage and gate
readiness, not the distribution of its constituent PIs. A planner-facing
roll-up of PI status across the whole release scope is missing.

## 2. Scope model (what "in-scope planning items" means)

A release's in-scope planning items are **exactly** the set the freeze /
planned-completely gates and `composition` already traverse — there is no new
notion of scope:

```
release  --(project_belongs_to_release, inbound)-->  Project*
Project  --(planning_item_belongs_to_project, inbound)-->  Planning Item*
```

i.e. a PI is in-scope for a release iff it `planning_item_belongs_to_project` a
Project that `project_belongs_to_release` the release. This is precisely
`releases._in_scope_projects` → `releases._in_scope_planning_items`, the helpers
that already back `composition` and the freeze gate. A Project belongs to
exactly one release (single-membership, REQ-211), so the PI set is naturally
disjoint across a release's Projects; the implementation still de-duplicates
defensively (a PI identifier is counted once even if it appeared under two
Projects).

Deleted Planning Items are excluded: `planning_items.get` already filters
`*_deleted_at IS NULL` for a normal read, and a PI whose identifier resolves to
no live row is skipped (it contributes to no status bucket) — mirroring
`pm._safe_pi`, which treats a missing PI as absent rather than erroring.

## 3. Semantics (the normative rule)

> **For a release, the status-counts read returns the number of its in-scope
> planning items in each lifecycle status, covering every status that is
> present in the scope.** A status with at least one in-scope PI appears in the
> result with its count (a positive integer); a status with no in-scope PI is
> **omitted** ("covering every status present" — not "every status defined").
> Each in-scope PI is counted exactly once, under its current
> `planning_item_status`. The sum of the counts equals the release's total
> in-scope PI count.

The map is keyed by the canonical `PLANNING_ITEM_STATUSES` string values. A
release with no in-scope PIs (no scoped Project, or scoped Projects with no PIs)
returns an empty map and a `total` of `0` — a well-formed answer, not an error.

### 3.1 Why "present" and not "all eight, zero-filled"

REQ-242's acceptance is *"the number of its in-scope planning items in each
lifecycle status, covering every status present"*. Returning only the statuses
that actually occur keeps the payload an honest picture of the release's scope
and avoids implying eight buckets always exist. A client that wants a
zero-filled eight-key view derives it trivially by overlaying the result onto
`PLANNING_ITEM_STATUSES`; the API does not bake that presentation choice in. The
ordering of the present statuses follows the canonical lifecycle order (see
§5.1) so a consumer can render the spread left-to-right without re-sorting.

### 3.2 What does **not** change

- This is a **pure read**. It never mutates a PI, a release, or an edge, and it
  is reachable only by GET. It does not gate or influence any release
  transition.
- It does **not** alter `composition`, the freeze gate, or any existing
  release report; it is a sibling read over the same scope traversal.
- It does **not** recurse into workstreams or work-tasks — the count is over
  Planning Items, the granularity REQ-242 names. (The work-task `blocked_by`
  graph the planned-completely gate inspects is a separate concern.)

## 4. Schema / migration / vocab

**None.** The read composes existing edges
(`project_belongs_to_release`, `planning_item_belongs_to_project`) and the
existing `planning_item_status` column over the existing
`vocab.PLANNING_ITEM_STATUSES`. No column, migration, or vocab change.

## 5. API surface

One new read endpoint on the existing releases router, in the family of the
release's other derived reads (`composition`, `freeze`, `temperature`):

```
GET /releases/{identifier}/planning-item-status-counts
```

Response (the standard `{data, meta, errors}` envelope; `data` shape):

```jsonc
{
  "release_identifier": "REL-007",
  "counts": {            // only statuses present in scope; canonical order
    "In Progress": 4,
    "In Review": 1,
    "Resolved": 6
  },
  "total": 11            // == sum(counts.values()) == in-scope PI count
}
```

- A release with no in-scope PIs ⇒ `{"release_identifier": "...", "counts": {},
  "total": 0}`.
- An unknown / soft-deleted release ⇒ `404` via `NotFoundError("release",
  identifier)`, matching `GET /releases/{id}` and the other per-release reads
  (the repository's `_get_row` already raises `NotFoundError` for a missing or
  deleted release, so the read fails closed before any traversal).

### 5.1 Ordering note

`counts` is emitted in canonical lifecycle order — the fixed sequence `Draft,
Decomposed, Ready, In Progress, In Review, Resolved, Deferred, Cancelled` —
filtered to the present statuses. A plain dict preserves insertion order in the
JSON the envelope serialises, so the repository builds the dict by iterating the
canonical order and inserting only the buckets with a non-zero count. This is a
presentation aid, not a contract a consumer must depend on; the keys are the
authority.

## 6. Implementation pointer (for WSK-151)

Two modules, mirroring the existing `composition` read end-to-end:

**`crmbuilder_v2/access/repositories/releases.py`** — a new derived-read
function beside `composition`:

```python
# Canonical lifecycle order for a stable, readable counts payload (§5.1).
_PI_STATUS_ORDER: tuple[str, ...] = (
    "Draft", "Decomposed", "Ready", "In Progress",
    "In Review", "Resolved", "Deferred", "Cancelled",
)


def planning_item_status_counts(session: Session, identifier: str) -> dict:
    """In-scope Planning Items grouped by lifecycle status (REQ-242).

    Counts every PI under a Project that ``project_belongs_to_release`` this
    release, by its ``planning_item_status``; only statuses present in scope
    appear, in canonical lifecycle order. Sums to the in-scope PI total.
    """
    _get_row(session, identifier)  # 404s a missing/deleted release
    pi_ids: set[str] = set()
    for prj in _in_scope_projects(session, identifier):
        pi_ids.update(_in_scope_planning_items(session, prj))
    tally: dict[str, int] = {}
    for pid in pi_ids:
        pi = _safe_pi(session, pid)          # skip deleted/missing (pm pattern)
        if pi is None:
            continue
        tally[pi["status"]] = tally.get(pi["status"], 0) + 1
    counts = {s: tally[s] for s in _PI_STATUS_ORDER if s in tally}
    return {
        "release_identifier": identifier,
        "counts": counts,
        "total": sum(counts.values()),
    }
```

- Reuse `_in_scope_projects` / `_in_scope_planning_items` verbatim — the same
  traversal `composition` uses. Do **not** add a parallel scope notion.
- `_safe_pi(session, pid)` is the `pm._safe_pi` pattern (`planning_items.get`
  wrapped to return `None` on `NotFoundError`); either import/reuse it or inline
  the same try/except so a missing PI is skipped rather than 500-ing the read.
  `planning_items.get` returns a dict whose `status` key is the
  `planning_item_status` value (the `pm._project_planning_items` reader relies
  on exactly this).
- A `set` de-duplicates PI identifiers across Projects (§2).

**`crmbuilder_v2/api/routers/releases.py`** — a new GET beside `composition`:

```python
@router.get("/{identifier}/planning-item-status-counts")
def planning_item_status_counts(identifier: str):
    """In-scope Planning Items grouped by lifecycle status (REQ-242)."""
    with readonly_session() as s:
        return ok(releases.planning_item_status_counts(s, identifier))
```

No request body, no schema addition (it is a path-only GET, like `composition`
and `versions`). No other module is touched.

## 7. Tests (for WSK-151, grounded in existing conventions)

Add to the release API test module (the suite that exercises
`GET /releases/{id}/composition` — its release / project / PI factory + edge
helpers and the `project_belongs_to_release` / `planning_item_belongs_to_project`
edge-driven setup already model this scope exactly). Cases:

1. **mixed spread (REQ-242 core).** A release with ≥1 scoped Project holding
   PIs across several statuses (e.g. two `In Progress`, one `In Review`, three
   `Resolved`) ⇒ `counts == {"In Progress": 2, "In Review": 1, "Resolved": 3}`,
   `total == 6`, and absent statuses (`Draft`, `Ready`, …) are **not** keys.
2. **canonical ordering.** Given PIs whose statuses are inserted out of
   lifecycle order, assert `list(counts.keys())` is the present statuses in
   `Draft → … → Cancelled` order (§5.1).
3. **empty scope.** A release with no scoped Project (and a release with a
   scoped Project but no PIs) ⇒ `counts == {}`, `total == 0`, HTTP 200.
4. **multi-project sum + de-dup.** A release scoping two Projects each with PIs
   ⇒ `total` equals the union count and `sum(counts.values()) == total`; no PI
   double-counted.
5. **deleted PI excluded.** A scoped PI that is soft-deleted does not appear in
   any bucket and is not in `total`.
6. **unknown / deleted release ⇒ 404**, matching `GET /releases/{id}`.

Run on SQLite and, where the suite is PG-gated
(`CRMBUILDER_V2_TEST_PG_URL`), on Postgres — no dialect-specific behavior is
introduced (it is edge traversal + an in-Python tally).

## 8. Requirement traceability

| REQ | Acceptance | Where in this design |
|---|---|---|
| REQ-242 — release planning-item status counts | "Given a release, the system returns the number of its in-scope planning items in each lifecycle status, covering every status present; the counts are reachable through the read API." | §2 (in-scope set) + §3 (normative rule: count per present status, sums to total) + §5 (the `GET /releases/{id}/planning-item-status-counts` read); tests 1/4 cover the per-status counts, test 3 the empty/total edge, test 6 reachability/error parity |
