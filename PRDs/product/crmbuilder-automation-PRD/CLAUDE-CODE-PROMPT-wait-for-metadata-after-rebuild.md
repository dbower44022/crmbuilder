# Claude Code Prompt — Wait for entity metadata after rebuild before downstream operations

**Repository:** `dbower44022/crmbuilder`
**Branch:** `main` (commit directly)
**Type:** Bug fix — async race condition

---

## 1. Problem statement

A Configure run that creates a brand-new custom entity and then
immediately attempts downstream operations against it fails with
HTTP 500 / 403 errors on every step after entity creation. Live
evidence from a recent MN-Session.yaml run:

```
=== ENTITY CREATION ===
[CHECK]   Entity Session (CSessions) ...
[CREATE]  CSessions ...
[CREATE]  CSessions ... OK
[REBUILD] Triggering cache rebuild ...
[REBUILD] Cache rebuild complete

=== ENTITY SETTINGS ===
[CHECK]   Session settings ...
[ERROR]   Session settings ... HTTP 200            ← 200 with empty body

=== FIELD OPERATIONS ===
[CREATE]  CSessions.sessionType ... ERROR (HTTP 500)
[CREATE]  CSessions.meetingLocationType ... ERROR (HTTP 500)
... (all 7 fields fail with HTTP 500)

=== LAYOUT OPERATIONS ===
[LAYOUT]  Session.detail ... ERROR (HTTP 403)
[LAYOUT]  Session.list ... ERROR (HTTP 403)

=== RELATIONSHIP OPERATIONS ===
[RELATIONSHIP]  Session → Contact (mentorAttendees) ... ERROR (HTTP 500)
... (all 3 relationships fail)
```

In the same run, an existing entity (`CEngagement`, created in a
previous run) processes cleanly through the same code paths —
because its metadata was already materialized server-side before
this run started.

The "ERROR HTTP 200" on entity_settings is the smoking gun. The
settings step calls
`get_entity_full_metadata(espo_name="CSessions")` which returns
`(200, None)` — EspoCRM accepted the GET and returned an empty
body. That happens when the scope name resolves but the metadata
for it isn't yet in the cache.

The downstream HTTP 500s and 403s are downstream symptoms of the
same underlying state: EspoCRM's metadata cache has not yet
materialized the new entity's full definition, so subsequent
fieldManager / layout / EntityManager-link operations fail with
non-deterministic errors.

## 2. Root cause

`espo_impl/core/entity_manager.py`, `rebuild_cache()` method
(lines 67–90):

```python
def rebuild_cache(self) -> bool:
    self.output_fn("[REBUILD] Triggering cache rebuild ...", "white")
    status_code, body = self.client.rebuild()
    ...
    if status_code == 200:
        self.output_fn("[REBUILD] Cache rebuild complete", "green")
        return True
    ...
```

`POST /Admin/rebuild` is **fire-and-forget on the EspoCRM side.**
It returns 200 immediately to acknowledge the request, but the
actual rebuild (clearing `data/cache/`, regenerating compiled
metadata, repopulating the in-memory metadata cache) runs
asynchronously in the EspoCRM PHP process.

The engine treats 200 from `POST /Admin/rebuild` as "rebuild
complete" and proceeds to the next step. But the rebuild may not
have finished yet — the cache may still be partially populated.
For brand-new entities created in the same run, this race
manifests as:

- `get_entity_full_metadata(name)` returning `(200, None)` —
  request resolved against the new scope, but the entityDefs
  block isn't there yet.
- `POST /Admin/fieldManager/{entity}` returning 500 — the field
  manager couldn't load the entity's metadata to validate the
  payload against.
- `PUT /Layout/{entity}/detail` returning 403 — the layout
  endpoint's permission check couldn't resolve the entity scope
  yet.

The race is invisible when the entity already existed before
this run (its metadata was already cached). It surfaces only on
the first run that creates the entity.

## 3. Fix

After triggering the rebuild, **poll the metadata API for each
just-created entity until its full entityDefs are returned, or a
hard timeout elapses.** Polling is more reliable than a fixed
sleep because EspoCRM's rebuild duration depends on how much
metadata exists on the instance — a fresh install rebuilds in
under a second, an instance with dozens of custom entities and
hundreds of fields takes longer.

### Polling strategy

After `rebuild_cache()` reports complete, for each entity the
caller passes in:

1. Issue `GET /Metadata?key=entityDefs.{entity_name}` (the
   existing `client.get_entity_full_metadata(...)` method).
2. If the response is `(200, dict)` with a non-empty dict, the
   entity's metadata is materialized. Move on.
3. Otherwise, sleep briefly and retry.
4. After a hard timeout (default 30 seconds), give up and return
   False from the wait. Log a clear warning so the user sees
   what happened.

Backoff schedule: 0.5s, 0.5s, 1.0s, 1.0s, 2.0s, 2.0s, 2.0s,
2.0s, 2.0s, 2.0s, 2.0s, 2.0s, 2.0s, 2.0s, 2.0s — totals ~30
seconds across 15 polls. Cheap on EspoCRM's metadata endpoint;
catches both fast and slow rebuilds without rigid sleeping.

### API surface

A new public method on `EntityManager`:

```python
def wait_for_metadata_ready(
    self,
    entity_def_names: list[str],
    timeout_seconds: float = 30.0,
) -> bool:
    """Poll EspoCRM's metadata API until every named entity's
    entityDefs are materialized in the cache, or the timeout
    elapses.

    Called after rebuild_cache() to close the async race window
    between rebuild completion and downstream operations. The
    underlying issue is that POST /Admin/rebuild returns 200 to
    acknowledge the request, but the rebuild itself runs
    asynchronously on the EspoCRM PHP process. Subsequent
    operations against newly-created entities can fail with
    HTTP 500 / 403 errors if the metadata for that entity isn't
    yet in the cache.

    :param entity_def_names: List of YAML-natural entity names
        (e.g. ["Engagement", "Session"]). Each is resolved to its
        EspoCRM internal name via get_espo_entity_name() before
        polling.
    :param timeout_seconds: Hard upper bound on how long to wait
        across all entities. Default 30 seconds.
    :returns: True if every entity's metadata was materialized
        before timeout; False if at least one timed out. On False
        return, callers should still proceed but should expect
        downstream operations to potentially fail and log
        accordingly.
    """
```

The method should be implemented to honor the timeout
**globally** across all entities — not per-entity — so a
slow-to-materialize first entity doesn't push the second
entity's poll past a per-entity budget.

### Call site

In `espo_impl/workers/run_worker.py`, the entity_creations step
(currently lines 360–368). After the `rebuild_cache()` call, add
a `wait_for_metadata_ready` call passing the names of just-
created entities:

```python
def _entity_creations_body() -> None:
    self.output_line.emit("", "white")
    self.output_line.emit("=== ENTITY CREATION ===", "white")
    successful_creates: list[str] = []
    for entity_def in creates:
        ok = entity_mgr._create_entity(entity_def)
        if not ok:
            create_fail_count["value"] += 1
        else:
            successful_creates.append(entity_def.name)
    entity_mgr.rebuild_cache()
    if successful_creates:
        entity_mgr.wait_for_metadata_ready(successful_creates)
    had_entity_ops_state["value"] = True
```

For the entity_deletions step (lines 325–333), `wait_for_metadata_ready`
on deletion is less critical — downstream operations don't
target deleted entities, so the race window doesn't typically
hit. But in the interest of consistency, optionally call it on
the surviving entities (those that weren't deleted) — though
this is **out of scope** for this prompt and listed under
Section 6.

### Output behavior

Emit a status line per polling pass:

- On entry: `[WAIT] Waiting for metadata cache to materialize new entities ...`
- On each successful entity check: `[WAIT] {entity_name} ({espo_name}) ... ready` (gray)
- On per-entity timeout: `[WAIT] {entity_name} ({espo_name}) ... TIMED OUT after {n}s` (yellow)
- On overall completion: `[WAIT] Metadata cache ready` (green)
- On overall timeout: `[WAIT] Metadata wait timed out after {n}s — proceeding anyway` (yellow)

Yellow-warning the user on timeout (rather than failing the
step) is deliberate. The next step's CHECK->ACT flow will
surface real failures explicitly. False alarms on the wait
phase shouldn't mask the actual error mode downstream.

## 4. Required code changes

### 4.1 `espo_impl/core/entity_manager.py`

Add `time` to imports near the top of the file:

```python
import time
```

Add the new method `wait_for_metadata_ready` immediately after
`rebuild_cache()` (around line 91). Implementation outline:

```python
def wait_for_metadata_ready(
    self,
    entity_def_names: list[str],
    timeout_seconds: float = 30.0,
) -> bool:
    """[See docstring in Section 3.]"""
    if not entity_def_names:
        return True

    self.output_fn(
        "[WAIT]    Waiting for metadata cache to materialize "
        "new entities ...",
        "white",
    )

    # Polling backoff schedule.
    backoff_pattern = [0.5, 0.5, 1.0, 1.0] + [2.0] * 30

    pending = list(entity_def_names)
    deadline = time.monotonic() + timeout_seconds
    attempt = 0
    timed_out_any = False

    while pending and time.monotonic() < deadline:
        delay = backoff_pattern[
            min(attempt, len(backoff_pattern) - 1)
        ]
        time.sleep(delay)
        attempt += 1

        still_pending: list[str] = []
        for yaml_name in pending:
            espo_name = get_espo_entity_name(yaml_name)
            status_code, meta = self.client.get_entity_full_metadata(
                espo_name
            )
            if (
                status_code == 200
                and isinstance(meta, dict)
                and meta
            ):
                self.output_fn(
                    f"[WAIT]    {yaml_name} ({espo_name}) ... ready",
                    "gray",
                )
            else:
                still_pending.append(yaml_name)
        pending = still_pending

    if pending:
        timed_out_any = True
        for yaml_name in pending:
            espo_name = get_espo_entity_name(yaml_name)
            self.output_fn(
                f"[WAIT]    {yaml_name} ({espo_name}) ... "
                f"TIMED OUT after {timeout_seconds:.0f}s",
                "yellow",
            )

    if timed_out_any:
        self.output_fn(
            f"[WAIT]    Metadata wait timed out after "
            f"{timeout_seconds:.0f}s — proceeding anyway",
            "yellow",
        )
        return False

    self.output_fn("[WAIT]    Metadata cache ready", "green")
    return True
```

### 4.2 `espo_impl/workers/run_worker.py`

In `_entity_creations_body` (around line 360), as shown in
Section 3, track which creates succeeded and call
`wait_for_metadata_ready` on them after `rebuild_cache()`.

Replace:

```python
def _entity_creations_body() -> None:
    self.output_line.emit("", "white")
    self.output_line.emit("=== ENTITY CREATION ===", "white")
    for entity_def in creates:
        ok = entity_mgr._create_entity(entity_def)
        if not ok:
            create_fail_count["value"] += 1
    entity_mgr.rebuild_cache()
    had_entity_ops_state["value"] = True
```

with:

```python
def _entity_creations_body() -> None:
    self.output_line.emit("", "white")
    self.output_line.emit("=== ENTITY CREATION ===", "white")
    successful_creates: list[str] = []
    for entity_def in creates:
        ok = entity_mgr._create_entity(entity_def)
        if not ok:
            create_fail_count["value"] += 1
        else:
            # _create_entity returns True both for "created now"
            # and for "already exists." We only need to wait for
            # entities created in this run, but we don't have an
            # easy boolean for that — wait for all that succeeded
            # and let wait_for_metadata_ready short-circuit when
            # an entity is already cached. The poll is a single
            # GET /Metadata, which is cheap.
            successful_creates.append(entity_def.name)
    entity_mgr.rebuild_cache()
    if successful_creates:
        entity_mgr.wait_for_metadata_ready(successful_creates)
    had_entity_ops_state["value"] = True
```

The comment in the code is intentional — it documents why we
pass already-existed entities to the wait too. Their first
poll will succeed immediately and they'll fall out of `pending`.
No special-case path needed.

## 5. Required tests

Add to `tests/test_entity_manager.py` (or whichever existing
file covers `EntityManager`).

```python
def test_wait_for_metadata_ready_returns_true_immediately_when_cached():
    """When metadata is already cached, wait returns True on first
    poll without sleeping noticeably."""
    # Mock client.get_entity_full_metadata to return (200, {"name":
    # "CEngagement", ...}) on the first call. Construct
    # EntityManager. Call wait_for_metadata_ready(["Engagement"],
    # timeout_seconds=10.0). Assert True. Assert get_entity_full_metadata
    # called exactly once.


def test_wait_for_metadata_ready_polls_until_ready():
    """When metadata is initially unavailable, wait polls until
    it materializes, then returns True."""
    # Mock client.get_entity_full_metadata to return (200, None)
    # on first 2 calls, then (200, {"name": "CSessions", ...}) on
    # 3rd. Patch time.sleep to be a no-op (or use a very short
    # backoff). Call wait. Assert True. Assert call count is 3.


def test_wait_for_metadata_ready_returns_false_on_timeout():
    """When metadata never materializes within the timeout, wait
    returns False and emits a TIMED OUT line for each entity."""
    # Mock client.get_entity_full_metadata to always return
    # (200, None). Patch time.sleep to be a no-op AND patch
    # time.monotonic to advance past the deadline after a few
    # calls. Call wait_for_metadata_ready(["Session"],
    # timeout_seconds=5.0). Assert returns False. Capture emitted
    # lines and assert one contains "TIMED OUT".


def test_wait_for_metadata_ready_handles_mixed_entities():
    """When some entities are ready and others aren't, wait keeps
    polling only the unready ones."""
    # Mock client.get_entity_full_metadata to return (200, {...})
    # for 'CEngagement' on first call, and (200, None) for
    # 'CSessions' on first 2 calls then (200, {...}) on 3rd.
    # Call wait_for_metadata_ready(["Engagement", "Session"]).
    # Assert returns True. Assert CEngagement was polled exactly
    # once, CSessions was polled at least 3 times.


def test_wait_for_metadata_ready_no_entities_returns_true():
    """Calling with an empty list short-circuits to True with no
    polls."""
    # Construct EntityManager. Call wait_for_metadata_ready([]).
    # Assert True. Assert get_entity_full_metadata never called.
```

For the tests that mock `time.sleep` and/or `time.monotonic`,
use `unittest.mock.patch` on the names imported into
`entity_manager`. If the existing test file uses freezegun or
similar, prefer that idiom for consistency. The polling delay
itself is irrelevant to the test logic — what matters is the
sequence of API responses and the final return value.

## 6. Out of scope

- Do NOT add `wait_for_metadata_ready` to the entity_deletions
  step. The race doesn't manifest there — downstream operations
  don't target deleted entities. A separate small prompt can
  handle it later for consistency if it ever becomes a real
  problem.
- Do NOT change `rebuild_cache()` itself. The fire-and-forget
  rebuild call is fine; the wait happens outside it.
- Do NOT change the underlying `client.rebuild()` API method.
- Do NOT change deploy-engine behavior on existing entities.
  The wait method short-circuits cheaply for them.
- Do NOT modify any YAML files.

## 7. Verification steps

1. **Unit tests:** `uv run pytest tests/test_entity_manager.py -v`
   (or wherever the EntityManager tests live). All previously
   passing tests must still pass; the five new tests must pass.
2. **Lint:** `uv run ruff check espo_impl/`.
3. **End-to-end (manual, by Doug):** Re-run the five-file
   Configure batch (CR-Account, MN-Account, MN-Contact,
   MN-Engagement, MN-Session) against the live CBM instance
   after the manual deletion of the broken `CSessions` entity.
   Expected behavior:
   - CR-Account, MN-Account, MN-Contact, MN-Engagement: same as
     last run — all idempotent or NO_WORK except MN-Account
     which is already deployed and should now be MATCHES across
     the board.
   - **MN-Session: full clean deploy.** Entity creates, rebuild
     triggers, **`[WAIT] Waiting for metadata cache to
     materialize new entities ...`** appears, **`[WAIT] Session
     (CSessions) ... ready`** appears, then settings, fields,
     layouts, and relationships all proceed cleanly.
   - The total run time will be slightly longer (an extra
     0.5-2s for Session's metadata poll) but no longer breaks.

## 8. Commit

Single commit. Suggested message:

```
fix(entity-manager): wait for metadata cache after rebuild

A Configure run that creates a new custom entity and immediately
attempts downstream operations (settings, fields, layouts,
relationships) against it failed with HTTP 500 / 403 errors.
Live evidence: MN-Session.yaml first deploy created CSessions
successfully but then 7 of 7 fields, 2 of 2 layouts, and 3 of 3
relationships failed because the metadata cache hadn't
materialized the new entity yet. Same code paths worked cleanly
for an existing entity (CEngagement) in the same run.

Cause: POST /Admin/rebuild is fire-and-forget on the EspoCRM
side. It returns 200 to acknowledge the request, but the
actual cache rebuild runs asynchronously. The engine treated
the 200 as 'rebuild complete' and proceeded to downstream
operations before the new entity's entityDefs were available
in the cache.

Fix: add EntityManager.wait_for_metadata_ready(entity_names)
that polls GET /Metadata?key=entityDefs.{entity_name} for each
named entity until the response is (200, non-empty dict) or a
hard timeout (30s default) elapses. Backoff schedule of
0.5s/0.5s/1s/1s then 2s thereafter, totaling ~30s across 15
polls. The wait is called from RunWorker._entity_creations_body
after rebuild_cache() with the names of all entities that
succeeded in the create step. Already-cached entities resolve
on first poll with no observable delay; freshly-created
entities resolve as soon as EspoCRM finishes its async rebuild.

The wait emits per-entity readiness lines (gray) and
overall-status lines, escalating to yellow warnings on timeout
without failing the step — downstream CHECK->ACT will surface
real errors explicitly without being masked by a wait-phase
'failure'.

Five new tests cover: immediate-cached return; poll-until-ready;
timeout returns False; mixed ready/unready entities;
empty-list short-circuit.

EntityManager.rebuild_cache() itself is unchanged. Deletion
step is unchanged — race doesn't manifest there since
downstream operations don't target deleted entities.
```
