# CLAUDE-CODE-PROMPT — PI-030 Slice A: Resolves status-flip server behavior + methodology amendment

**Last Updated:** 05-24-26 17:00
**Workstream:** Code Change Lifecycle (PI-030)
**Operating mode:** DETAIL
**Predecessor:** PI-029 slice B (commits access layer + REST endpoints) — landed in commits c578503/a9cfe13/8e51195/9269095/4b0ac9f; the four DEC-211..214 build-planning decisions live in SES-067.
**Successor:** PI-030 Slice B (`apply_close_out.py` extensions) at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-030-B-apply-close-out-extensions.md` — depends on this slice's resolves status-flip behavior.
**Spec authority:**
- `PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md` v1.0 — §4 (close-out payload format), §5.4 (when a planning_item is resolved)
- `PRDs/product/crmbuilder-v2/close-out-payloads/ses_070.json` (this conversation's close-out) — DEC-223 (conversation block; methodology amended) and DEC-224 (POST /references extended for resolves)

---

## Purpose

Two coupled changes that prepare the v2 governance machinery for PI-030 slice B:

1. **Server-side extension** of `references.create()` and `POST /references` so that when `relationship_kind == 'resolves'`, the same transaction also flips the target planning_item's status from `Open` to `Resolved`. This is the atomic-edge-plus-status-flip the methodology requires for the `resolves_planning_items` close-out payload section.

2. **Methodology document amendment** of `PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md` adding §4.0 for the new `conversation` block (per DEC-223) and updating §4's top-of-section apply-ordering bullet to insert `conversation` between `session` and `work_tickets`.

The methodology amendment is doc-only. The server-side extension is small but needs careful tests. Total estimate: ~40 lines of code change + ~80 lines of new tests + ~25 lines of methodology amendment.

---

## Net effect

After this slice lands:

- POST /references with `{source_type: "conversation", source_id: "CONV-NNN", target_type: "planning_item", target_id: "PI-NNN", relationship: "resolves"}` creates the reference row AND sets `planning_item.status = "Resolved"` in the same transaction. If the planning_item is already `Resolved`, the status update is a no-op and the reference still gets created (no 409 on the flip; only the existing-reference 409 path applies).
- The rejection path for `resolves` edges with wrong source/target (e.g., `source_type=session`) remains the existing `_kinds_for_pair` validation — slice A does NOT add new rejection logic; the existing CHECK constraint and vocab validation already covers it (verified: see vocab.py line 362 admits `resolves` only for `(conversation, planning_item)`).
- methodology-code-change-lifecycle.md gains a §4.0 paragraph + updated §4 apply-ordering line. Document version stays at v1.0; the change log gets one new row dated 05-24-26.

After this slice lands, slice B (`apply_close_out.py` extensions) can call the extended endpoint to translate `resolves_planning_items` payload entries into atomic edge+flip operations.

---

## Pre-flight

```bash
cd ~/Dropbox/Projects/crmbuilder
git status                                 # expect clean
git pull --rebase origin main              # ensure latest
ls crmbuilder-v2/src/crmbuilder_v2/access/repositories/references.py  # exists
ls crmbuilder-v2/src/crmbuilder_v2/access/repositories/planning_items.py  # exists
ls PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md  # exists
cd crmbuilder-v2 && uv run pytest tests/crmbuilder_v2/ -x -q 2>&1 | tail -5
# Expect 1481 passed + 3 skipped (or whatever current baseline is after slice B applied)
```

If pytest baseline differs from documented, capture the actual count before proceeding so the post-change delta is meaningful.

---

## Changes

### 1. Extend `references.create()` to flip planning_item status on `resolves`

File: `crmbuilder-v2/src/crmbuilder_v2/access/repositories/references.py`

Add an import of the planning_items module at the top of the file (the import must be local-scoped to avoid a circular-import problem at module load — planning_items.py imports nothing from references, so a top-of-file import in references.py should work, but if pytest surfaces an ImportError at collection, fall back to a lazy `from crmbuilder_v2.access.repositories import planning_items` inside the `create()` function body).

After the `session.flush()` in `create()` (line 222 in current file), and after the `after = _row_dict(row)` line but BEFORE the `emit(...)` call, insert the status-flip branch:

```python
    # PI-030 slice A: atomic edge + status flip for `resolves` kind.
    # When a conversation `resolves` a planning_item, the planning_item's
    # status transitions to "Resolved" in the same transaction. The
    # transition is idempotent — if the target is already Resolved, the
    # update is a no-op. Source/target type validation is enforced
    # upstream by `_kinds_for_pair` in vocab.py (which admits `resolves`
    # only for (conversation, planning_item) pairs); a reference whose
    # types don't match would have been rejected before this code runs.
    if relationship == "resolves":
        from crmbuilder_v2.access.repositories import planning_items
        target_record = planning_items.get(session, target_id)
        if target_record["status"] != "Resolved":
            planning_items.update(session, target_id, status="Resolved")
```

The `planning_items.get()` call uses the existing function (line 38 of planning_items.py) which raises `NotFoundError` if the target doesn't exist. Since the references CHECK constraint already enforces target existence indirectly (the row insertion would fail on a non-existent target_id even without this check), `NotFoundError` here would indicate a race condition — surface it as-is; the existing transaction rolls back cleanly.

The lazy import inside the function body is a deliberate hedge against a circular-import problem; if a top-of-file import works cleanly under pytest, the local import can be lifted.

### 2. Add tests for the resolves status-flip behavior

File: `tests/crmbuilder_v2/access/test_references.py`

Add a new test block at the bottom of the file (after the existing tests). The block exercises four scenarios:

1. Happy-path: `Open` planning_item → reference created → status becomes `Resolved`.
2. Idempotent: `Resolved` planning_item → reference created → status stays `Resolved` (no-op update; no audit-log spam from the no-op).
3. Already-resolved-via-edge: re-creating the same edge returns 409 (existing ConflictError path) — confirms the existing reference-already-exists guard still fires.
4. Other-kind: a `decided_in` reference targeting a planning_item (if vocab admits it) does NOT flip status; confirms the flip is gated on `relationship == "resolves"` and not on the target type.

Use existing test fixtures (see the file's other tests for patterns). Each test creates a conversation record (the source), a planning_item record (the target), then exercises the references.create path.

Skeleton:

```python
class TestResolvesStatusFlip:
    """PI-030 slice A: POST /references with relationship=resolves flips
    target planning_item status to Resolved in the same transaction."""

    def _setup(self, session):
        # Conversation source
        from crmbuilder_v2.access.repositories import conversations, planning_items
        conv = conversations.create_conversation(
            session,
            identifier="CONV-991",
            title="Resolves test conversation",
            purpose="Validate atomic edge+flip behavior",
            description="",
            notes="",
            status="planned",
            references=None,
            timestamps=None,
        )
        # Planning item target (Open)
        pi = planning_items.create(
            session,
            identifier="PI-991",
            title="Test PI for resolves",
            item_type="pending_work",
            description="",
            status="Open",
            resolution_reference="",
        )
        return conv, pi

    def test_resolves_flips_open_to_resolved(self, v2_session):
        """Happy path: Open → Resolved on resolves edge creation."""
        # ... implementation per the pattern above
        pass

    def test_resolves_idempotent_on_already_resolved(self, v2_session):
        """Resolved → Resolved: no-op update; reference still created."""
        pass

    def test_duplicate_resolves_edge_returns_409(self, v2_session):
        """Second resolves edge with same source/target/kind returns
        ConflictError; status remains Resolved."""
        pass

    def test_non_resolves_kind_does_not_flip(self, v2_session):
        """A `is_about` edge from a conversation to a planning_item
        does NOT change the planning_item's status."""
        pass
```

Use the actual fixture name from `tests/crmbuilder_v2/conftest.py` (probably `v2_session` or `db_session`); look it up before writing the tests.

File: `tests/crmbuilder_v2/api/test_references.py`

Add one API-level test that goes through `POST /references` and verifies the planning_item's status flips:

```python
def test_post_references_resolves_flips_status(api_client, v2_env):
    """POST /references with relationship=resolves triggers the atomic
    status flip on the target planning_item."""
    # Create CONV-992 and PI-992
    # POST /references with the resolves edge
    # GET /planning-items/PI-992, assert status == "Resolved"
    pass
```

### 3. Methodology document amendment

File: `PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md`

Two edits:

**Edit 1 — Update the apply-ordering block at the top of §4.**

Find this text near line 168:

```
The v0.7 close-out payload structure (one session record, decisions array, planning_items array, references array) extends with four new top-level array sections. The apply script processes the sections in fixed order to honor dependency constraints:

```
session → work_tickets → planning_items → commits → decisions
       → references → resolves_planning_items → addresses_planning_items
```

Rationale for the order: work_tickets must exist before they can be referenced from is_about/addresses/opens-against edges; commits must exist before resolves/addresses edges can be authored against the conversation that produced them; resolves edges flip planning_item status, so the planning item record must exist first.
```

Replace with:

```
The v0.7 close-out payload structure (one session record, decisions array, planning_items array, references array) extends with **five** new top-level sections (one conversation block plus four array sections). The apply script processes the sections in fixed order to honor dependency constraints:

```
session → conversation → work_tickets → planning_items → commits → decisions
       → references → resolves_planning_items → addresses_planning_items
```

Rationale for the order: the conversation must exist before commits can be FK-attached to it via `commit_conversation_id` (added by PI-030 slice A's amendment per DEC-223); work_tickets must exist before they can be referenced from is_about/addresses/opens-against edges; commits must exist before resolves/addresses edges can be authored against the conversation that produced them; resolves edges flip planning_item status, so the planning item record must exist first.
```

**Edit 2 — Insert §4.0 `conversation` block before §4.1.**

Find the line `### 4.1 \`commits\` section` near line 177.

Insert immediately before it:

```
### 4.0 `conversation` block

```json
"conversation": {
  "conversation_identifier": "CONV-046",
  "conversation_title": "PI-030 architecture planning — close-out payload extensions and apply integration",
  "conversation_purpose": "Settle Q0 (PI-030 scope), Q1 (commit-metadata helper architecture), and Q2 (conversation gap closure). Author the three PI-030 slice prompts.",
  "conversation_status": "complete",
  "conversation_completed_at": "2026-05-24T17:30:00-04:00",
  "references": [
    {
      "target_type": "session",
      "target_id": "SES-070",
      "relationship": "conversation_records_session"
    }
  ]
}
```

Generates one `conversation` record plus the embedded `conversation_records_session` edge to the session block's identifier in the same atomic POST. Required for any close-out that includes a `commits` section — the commits' `commit_conversation_id` FK targets this conversation. The conversation_identifier is computed client-side via `GET /conversations/next-identifier`. The status is typically `complete` at close-out time, but earlier statuses are admitted for in-flight close-outs that defer some fields to a subsequent edit. Omitting the conversation block when commits are present causes `commit_conversation_id_not_found` errors at apply time.

Authoring note: the conversation block was added in PI-030 (the methodology's downstream implementation conversation; see §8) per DEC-223. Prior close-out payloads (ses_001 through approximately ses_069) predate this section and used the v0.7 four-block format; backfill of conversation records for those sessions is PI-024/PI-025 scope.

```

**Edit 3 — Update §2 Change Log table to record the amendment.**

Find the Change Log block near line 23. Add a new entry at the top (most recent first):

```
**Version 1.0 amendment (05-24-26 17:30):** PI-030 slice A — added §4.0 `conversation` block and updated §4's apply-ordering bullet to insert `conversation` between `session` and `work_tickets`. The amendment was required by DEC-223 (close-out payload format gains a conversation block; methodology amended) to close the gap where sessions from SES-061 forward had no associated conversation records, blocking commits' FK to `commit_conversation_id`. Document version stays at v1.0 — the amendment is additive and clarifying.
```

**Edit 4 — Update Last Updated timestamp.**

Find the Last Updated line near line 12. Update from `05-23-26 22:30` (or whatever current value) to `05-24-26 17:30`.

---

## Verification

After all edits, run the v2 test suite:

```bash
cd crmbuilder-v2
uv run pytest tests/crmbuilder_v2/ -x -q 2>&1 | tail -10
```

Expected:
- Baseline (e.g., 1481) + 5 new tests (4 access + 1 API) = 1486 passed.
- Zero failures.

Sanity check the methodology change:

```bash
cd ..
head -50 PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md
# Expect: updated change log row at the top of §2, updated Last Updated timestamp

grep -A 3 "### 4.0" PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md
# Expect: §4.0 conversation block heading with JSON example

grep "session → conversation → work_tickets" PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md
# Expect: 1 match (the new apply-ordering line)

grep "session → work_tickets → planning_items → commits → decisions" PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md
# Expect: 0 matches (old apply-ordering line was replaced)
```

---

## Commit

```bash
cd ~/Dropbox/Projects/crmbuilder
git add crmbuilder-v2/src/crmbuilder_v2/access/repositories/references.py
git add tests/crmbuilder_v2/access/test_references.py
git add tests/crmbuilder_v2/api/test_references.py
git add PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md
git commit -m "v2: PI-030 slice A — POST /references atomic edge+flip for resolves; methodology §4.0 conversation block

Two coupled changes preparing v2 governance for PI-030 slice B:

1. references.create() extended: when relationship_kind == 'resolves',
   the same transaction also calls planning_items.update(target_id,
   status='Resolved'). Idempotent on already-Resolved targets. Validates
   the source/target shape via existing vocab/_kinds_for_pair (admits
   resolves only for conversation → planning_item).

2. methodology-code-change-lifecycle.md amended:
   - §4 apply-ordering bullet updated to insert 'conversation' between
     session and work_tickets
   - §4.0 conversation block added with JSON example and authoring note
   - Change log row added for the 05-24-26 amendment
   - Last Updated bumped to 05-24-26 17:30

Authority: DEC-223 (close-out payload format gains a conversation
block; methodology amended) and DEC-224 (POST /references extended
for resolves status-flip).

Tests: 5 new (4 access-layer, 1 API). Baseline + 5 = post-change count.

Closes the server-side prerequisite for PI-030 slice B's
resolves_planning_items section handling."

# Per the 'you commit, I push' convention in Claude Code context,
# do NOT push here. Doug reviews and pushes manually:
#   git pull --rebase origin main
#   git push
```

---

## Done

Reply with:

- pytest result: `<baseline>` + 5 = `<post-count>` passed, 0 failed
- Methodology change confirmed: §4.0 heading present, §4 apply-ordering line updated
- references.create extension confirmed: status flip happens for `resolves` kind only
- Commit SHA
- Next: PI-030 slice B at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-030-B-apply-close-out-extensions.md`
