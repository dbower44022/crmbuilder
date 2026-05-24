# CLAUDE-CODE-PROMPT — PI-030 Slice B: apply_close_out.py extensions for five new payload sections

**Last Updated:** 05-24-26 17:00
**Workstream:** Code Change Lifecycle (PI-030)
**Operating mode:** DETAIL
**Predecessor:** PI-030 slice A (resolves status-flip + methodology amendment) at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-030-A-resolves-flip-and-methodology.md` — MUST be applied before this slice runs. This slice depends on slice A's extended `POST /references` for the `resolves` kind.
**Successor:** PI-030 Slice C (`enumerate_commits.py` helper) at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-030-C-enumerate-commits-helper.md` — independent of this slice; can run in either order.
**Spec authority:**
- `PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md` v1.0+amendment — §4 (the five new payload sections: conversation, work_tickets, commits, resolves_planning_items, addresses_planning_items)
- `PRDs/product/crmbuilder-v2/governance-schema-specs/commit.md` v1.0 — §3.5 (commit POST behavior including embedded references)
- `PRDs/product/crmbuilder-v2/close-out-payloads/ses_070.json` — DEC-221 (full scope), DEC-222 (emit-time helper, full records in payload), DEC-223 (conversation block)

---

## Purpose

Extend `crmbuilder-v2/scripts/apply_close_out.py` so it can land all five new close-out payload sections introduced by the Code Change Lifecycle methodology and DEC-223:

1. `conversation` (singular block, parallel to `session`) — POSTed to `/conversations` with embedded `conversation_records_session` edge
2. `work_tickets` (array) — POSTed to `/work-tickets`; each entry's `addresses_planning_item` field becomes an embedded reference
3. `commits` (array) — POSTed to `/commits`; each entry's `commit_conversation_id` is populated from the payload's `conversation.conversation_identifier`
4. `resolves_planning_items` (array of `{planning_item_identifier}`) — translated per entry to `POST /references` with `relationship: resolves` (slice A's extension fires the atomic status flip)
5. `addresses_planning_items` (array of `{planning_item_identifier}`) — translated per entry to `POST /references` with `relationship: addresses`

Also: extend `vocab.py` to admit `conversation`, `work_ticket`, and `commit` as valid target_types for `deposit_event_wrote_record` so the apply's last-step deposit_event POST can record back-edges to the new record types (the access layer enforces `sum(records_summary) == len(wrote_records)`; without vocab admission, the new types' counts would have to skip, breaking audit chain).

The payload's existing four sections (session, planning_items, decisions, references) and their behavior are unchanged. The deposit_event lazy-create at apply-close is unchanged. Sections absent from the payload are skipped (no-op); this preserves backward compatibility with v0.7 payloads.

---

## Net effect

After this slice lands:

- `apply_close_out.py` honors the methodology §4 apply ordering verbatim: `session → conversation → work_tickets → planning_items → commits → decisions → references → resolves_planning_items → addresses_planning_items`.
- Conversation_identifier from the payload's conversation block propagates into every commit's `commit_conversation_id` automatically (the apply derives it once and threads it through).
- Work_ticket entries with an `addresses_planning_item` field have the addresses edge created atomically in the same work_ticket POST (no separate refs POST needed).
- `resolves_planning_items` entries translate to a POST /references that creates the edge and (via slice A) flips the target planning_item's status to Resolved atomically.
- `addresses_planning_items` entries translate to a POST /references with `relationship: addresses` (no status flip).
- vocab.py admits three new target_types for `deposit_event_wrote_record` so the deposit_event POST at apply close captures back-edges to the new record types.
- HTTP 409 = SKIP idempotency on re-run is preserved across all new sections (existing `_log()` behavior unchanged).
- Tests cover ordering, idempotency, conversation_id propagation, and the resolves/addresses translation.

---

## Pre-flight

```bash
cd ~/Dropbox/Projects/crmbuilder
git status                                              # expect clean
git pull --rebase origin main                           # ensure slice A landed
git log --oneline -5                                    # confirm slice A's commit is at top

# Verify slice A's references.create extension landed
grep -n 'relationship == "resolves"' crmbuilder-v2/src/crmbuilder_v2/access/repositories/references.py
# Expect 1 match (the new branch). If 0, slice A hasn't been applied yet — halt.

# Verify methodology amendment landed
grep -n '### 4.0' PRDs/product/crmbuilder-v2/methodology-code-change-lifecycle.md
# Expect 1 match. If 0, slice A's methodology edit didn't land — halt.

cd crmbuilder-v2 && uv run pytest tests/crmbuilder_v2/ -x -q 2>&1 | tail -5
# Capture the baseline (e.g., 1486 passed after slice A). This slice should
# add roughly 18-22 tests on top of that.
```

If pre-flight surfaces any issue, halt and report. Slice B cannot run without slice A's resolves extension.

---

## Changes

### 1. Extend `vocab.py` for new wrote_record target types

File: `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`

Find the existing block (current lines 353-359):

```python
    if source_type == "deposit_event" and target_type in (
        "session",
        "decision",
        "planning_item",
        "reference",
    ):
        kinds.add("deposit_event_wrote_record")
```

Extend to admit the new entity types:

```python
    if source_type == "deposit_event" and target_type in (
        "session",
        "decision",
        "planning_item",
        "reference",
        # v0.8 additions (PI-030 slice B). The new entity types that the
        # extended close-out payload format can write. Audit chain stays
        # intact: every record the apply POSTs gets a wrote_record
        # back-edge, regardless of which entity type the record is.
        "conversation",
        "work_ticket",
        "commit",
    ):
        kinds.add("deposit_event_wrote_record")
```

No Alembic migration needed — the DB CHECK constraint on `refs.relationship_kind` checks only the kind value (and `deposit_event_wrote_record` is already in the allowed set); the (source_type, target_type, kind) compatibility lives in `_kinds_for_pair` at the access layer.

### 2. Rewrite `_SECTION_ENDPOINTS` to support per-section shape functions

File: `crmbuilder-v2/scripts/apply_close_out.py`

Current `_SECTION_ENDPOINTS` (lines 49-54):

```python
_SECTION_ENDPOINTS: list[tuple[str, str, bool, str, str]] = [
    ("session", "/sessions", True, "session", "sessions"),
    ("decisions", "/decisions", False, "decision", "decisions"),
    ("planning_items", "/planning-items", False, "planning_item", "planning_items"),
    ("references", "/references", False, "reference", "references"),
]
```

Replace with a richer structure that accommodates per-section transformation. The simplest workable shape: each section is a named tuple or dataclass carrying its config plus an optional `shape_fn` that takes `(entry, context) -> dict` returning the body to POST.

Use a plain dataclass for clarity:

```python
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class _Section:
    name: str                          # payload key
    endpoint: str                      # POST path
    is_singular: bool                  # session and conversation are dicts; others are lists
    entity_type: str                   # for wrote_record back-edges
    summary_key: str                   # for records_summary dict
    shape_fn: Optional[Callable[[dict, dict], dict]] = None  # transform per-entry; None = identity


def _shape_work_ticket(entry: dict, context: dict) -> dict:
    """Translate work_ticket payload entries: pop `addresses_planning_item`
    if present and add it to the embedded references list."""
    body = {k: v for k, v in entry.items() if k != "addresses_planning_item"}
    target_pi = entry.get("addresses_planning_item")
    if target_pi:
        existing_refs = list(body.get("references") or [])
        existing_refs.append({
            "target_type": "planning_item",
            "target_id": target_pi,
            "relationship": "addresses",
        })
        body["references"] = existing_refs
    return body


def _shape_commit(entry: dict, context: dict) -> dict:
    """Inject `commit_conversation_id` from the payload's conversation
    block. The payload's per-entry commit records don't carry the FK
    (per methodology §4.1 — 'the close-out's owning conversation; no
    explicit field needed in the payload entry'); the apply derives it."""
    conv_id = context.get("conversation_identifier")
    if not conv_id:
        raise ValueError(
            "commits section present but no conversation block in payload — "
            "every commit needs commit_conversation_id. Add a conversation "
            "block per methodology §4.0."
        )
    body = dict(entry)
    body.setdefault("commit_conversation_id", conv_id)
    return body


def _shape_resolves_pi(entry: dict, context: dict) -> dict:
    """Translate {planning_item_identifier: PI-NNN} to a full POST /references
    body with relationship=resolves. The conversation source is derived from
    the payload's conversation block."""
    conv_id = context.get("conversation_identifier")
    if not conv_id:
        raise ValueError(
            "resolves_planning_items section present but no conversation "
            "block in payload — resolves edges flow from the conversation. "
            "Add a conversation block per methodology §4.0."
        )
    target_pi = entry["planning_item_identifier"]
    return {
        "source_type": "conversation",
        "source_id": conv_id,
        "target_type": "planning_item",
        "target_id": target_pi,
        "relationship": "resolves",
    }


def _shape_addresses_pi(entry: dict, context: dict) -> dict:
    """Translate {planning_item_identifier: PI-NNN} to a full POST /references
    body with relationship=addresses. Same source-derivation as resolves; no
    status flip."""
    conv_id = context.get("conversation_identifier")
    if not conv_id:
        raise ValueError(
            "addresses_planning_items section present but no conversation "
            "block in payload — addresses edges flow from the conversation. "
            "Add a conversation block per methodology §4.0."
        )
    target_pi = entry["planning_item_identifier"]
    return {
        "source_type": "conversation",
        "source_id": conv_id,
        "target_type": "planning_item",
        "target_id": target_pi,
        "relationship": "addresses",
    }


_SECTIONS: list[_Section] = [
    _Section("session",                  "/sessions",       True,  "session",        "sessions"),
    _Section("conversation",             "/conversations",  True,  "conversation",   "conversations"),
    _Section("work_tickets",             "/work-tickets",   False, "work_ticket",    "work_tickets", _shape_work_ticket),
    _Section("planning_items",           "/planning-items", False, "planning_item",  "planning_items"),
    _Section("commits",                  "/commits",        False, "commit",         "commits",       _shape_commit),
    _Section("decisions",                "/decisions",      False, "decision",       "decisions"),
    _Section("references",               "/references",     False, "reference",      "references"),
    _Section("resolves_planning_items",  "/references",     False, "reference",      "references",    _shape_resolves_pi),
    _Section("addresses_planning_items", "/references",     False, "reference",      "references",    _shape_addresses_pi),
]
```

Keep the old `_SECTION_ENDPOINTS` name available as a backward-compatibility alias if other code in the script references it — but no other code should; the loop is the only consumer. Search the file for any remaining `_SECTION_ENDPOINTS` reference and update.

### 3. Wire a context dict through the apply loop

The shape functions need access to the conversation_identifier from the payload's conversation block. Build a context dict at the top of `main()`, after the payload is parsed, that captures any cross-section values:

```python
    context: dict[str, str] = {}
    conversation_block = payload.get("conversation")
    if isinstance(conversation_block, dict):
        ci = conversation_block.get("conversation_identifier")
        if isinstance(ci, str):
            context["conversation_identifier"] = ci
```

Pass `context` into the per-entry POST loop. For each record:

```python
            body = record if section.shape_fn is None else section.shape_fn(record, context)
            status, response = _request("POST", section.endpoint, body)
```

The existing `_log` and 409-handling code paths apply unchanged.

### 4. Update `records_summary` initialization to include new keys

Current:

```python
        records_summary: dict[str, int] = {
            key: 0 for _section, _ep, _singular, _entity_type, key in _SECTION_ENDPOINTS
        }
```

Update to iterate the new `_SECTIONS` and de-duplicate keys (since `references`, `resolves_planning_items`, `addresses_planning_items` all share the `references` summary key):

```python
        records_summary: dict[str, int] = {}
        for section in _SECTIONS:
            records_summary.setdefault(section.summary_key, 0)
```

### 5. Update `_record_target_id` for the conversation entity

Current (line 183-188):

```python
def _record_target_id(entity_type: str, response_data: dict) -> str | None:
    """Extract the addressable identifier from a created record's response."""
    if entity_type == "reference":
        return response_data.get("reference_identifier")
    return response_data.get("identifier")
```

Extend to handle entity-type-specific identifier field names (conversation, work_ticket, commit each have their own prefixed identifier field):

```python
def _record_target_id(entity_type: str, response_data: dict) -> str | None:
    """Extract the addressable identifier from a created record's response."""
    # Most entities use a plain `identifier` field at the row level; some
    # carry a parent-prefixed field name. Match each known entity type
    # explicitly so the apply doesn't fall through to a missing field.
    field_by_type = {
        "session": "identifier",
        "decision": "identifier",
        "planning_item": "identifier",
        "reference": "reference_identifier",
        "conversation": "conversation_identifier",
        "work_ticket": "work_ticket_identifier",
        "commit": "commit_identifier",
    }
    field = field_by_type.get(entity_type, "identifier")
    return response_data.get(field)
```

### 6. Skip-from-wrote_records logic preserved for references

The existing code (lines 366-376) skips references from `wrote_records`. KEEP THIS BEHAVIOR for the three sections that produce reference records (`references`, `resolves_planning_items`, `addresses_planning_items`) — these all set `entity_type == "reference"` and the existing `if entity_type != "reference":` guard handles them all.

DO add conversation, work_ticket, and commit to wrote_records (vocab now admits them per change 1).

The existing block:

```python
                if status in (200, 201):
                    response_data = _extract_data(response)
                    target_id = _record_target_id(entity_type, response_data)
                    if target_id:
                        if entity_type != "reference":
                            wrote_records.append((entity_type, target_id))
                            records_summary[summary_key] += 1
```

Works unchanged after the shape and section table updates.

### 7. Update the apply loop's iteration over the section table

Current (line 350):

```python
        for section, endpoint, is_singular, entity_type, summary_key in _SECTION_ENDPOINTS:
            if section not in payload or not payload[section]:
                continue
            records = [payload[section]] if is_singular else payload[section]
```

Update to use the dataclass:

```python
        for section in _SECTIONS:
            section_name = section.name
            if section_name not in payload or not payload[section_name]:
                continue
            records = [payload[section_name]] if section.is_singular else payload[section_name]
            print(
                f"=== {section_name} ({len(records)} record{'s' if len(records) != 1 else ''}) ==="
            )
            for record in records:
                body = record if section.shape_fn is None else section.shape_fn(record, context)
                status, response = _request("POST", section.endpoint, body)
                rec_ok = _log(_record_label(section_name, record), status, response)
                ok &= rec_ok
                total_processed += 1
                if status in (200, 201):
                    response_data = _extract_data(response)
                    target_id = _record_target_id(section.entity_type, response_data)
                    if target_id:
                        if section.entity_type != "reference":
                            wrote_records.append((section.entity_type, target_id))
                            records_summary[section.summary_key] += 1
                elif status not in (200, 201, 204, 409) and first_error is None:
                    # ... existing first_error capture unchanged
                    errors = response.get("errors") if isinstance(response, dict) else None
                    err_msg = (
                        json.dumps(errors)[:300]
                        if errors
                        else str(response)[:300]
                    )
                    first_error = {
                        "kind": "http_error" if status > 0 else "connection_failure",
                        "message": err_msg,
                        "step": section_name,
                        "http_status": status,
                    }
            print()
```

### 8. Update `_record_label` for new sections

Current (line 95-104):

```python
def _record_label(section: str, record: dict) -> str:
    ident = record.get("identifier")
    if ident:
        return f"POST {section}  {ident}"
    src = record.get("source_id")
    tgt = record.get("target_id")
    rel = record.get("relationship")
    if src and tgt and rel:
        return f"POST {section}  {src} {rel} {tgt}"
    return f"POST {section}  <unidentified record>"
```

The conversation, work_ticket, and commit records use prefixed identifier field names. Extend:

```python
def _record_label(section: str, record: dict) -> str:
    # Try plain identifier first, then prefixed variants
    ident = (
        record.get("identifier")
        or record.get("conversation_identifier")
        or record.get("work_ticket_identifier")
        or record.get("commit_identifier")
    )
    if ident:
        return f"POST {section}  {ident}"
    # resolves_planning_items / addresses_planning_items entries
    if record.get("planning_item_identifier"):
        return f"POST {section}  → {record['planning_item_identifier']}"
    # Reference entries with source/target/relationship
    src = record.get("source_id")
    tgt = record.get("target_id")
    rel = record.get("relationship")
    if src and tgt and rel:
        return f"POST {section}  {src} {rel} {tgt}"
    return f"POST {section}  <unidentified record>"
```

Note `_record_label` receives the PRE-shape entry (the payload's raw record), so it sees `planning_item_identifier` for resolves/addresses entries.

### 9. Add tests for the new section behavior

File: `tests/crmbuilder_v2/scripts/test_apply_close_out.py`

Add a new test class at the bottom of the file. Use the existing fixtures (`routed`, `tmp_path`, `monkeypatch`, etc.). Mirror the existing test patterns.

Required test coverage:

```python
class TestPI030NewSections:
    """PI-030 slice B: apply_close_out.py extensions for the five new
    close-out payload sections."""

    def test_conversation_block_creates_record_with_records_session_edge(
        self, routed, tmp_path, monkeypatch
    ):
        """A payload's conversation block POSTs to /conversations with the
        embedded conversation_records_session edge."""
        # session + conversation, assert CONV created, assert refs edge exists

    def test_commits_section_propagates_conversation_id(
        self, routed, tmp_path, monkeypatch
    ):
        """Each commit entry's commit_conversation_id is auto-populated from
        the payload's conversation block."""
        # session + conversation + 1 commit (no explicit commit_conversation_id),
        # assert commit lands with commit_conversation_id == conversation's identifier

    def test_commits_without_conversation_block_raises_clear_error(
        self, routed, tmp_path, monkeypatch
    ):
        """A commits section present without a conversation block surfaces
        a clear error (not an HTTP 422 buried deep)."""
        # payload with commits but no conversation block — expect ValueError

    def test_work_ticket_addresses_pi_becomes_embedded_reference(
        self, routed, tmp_path, monkeypatch
    ):
        """work_tickets[].addresses_planning_item generates an embedded
        addresses edge in the work_ticket POST."""
        # session + 1 PI + 1 work_ticket with addresses_planning_item — assert
        # work_ticket lands, references list has the addresses edge

    def test_resolves_planning_items_translates_to_references_post(
        self, routed, tmp_path, monkeypatch
    ):
        """resolves_planning_items entries POST to /references with
        relationship=resolves. The slice A flip behavior runs server-side."""
        # session + conv + 1 PI (Open) + resolves_planning_items: [{PI}] —
        # assert refs row created, assert PI status == Resolved

    def test_addresses_planning_items_translates_to_references_post(
        self, routed, tmp_path, monkeypatch
    ):
        """addresses_planning_items entries POST to /references with
        relationship=addresses. No status flip."""
        # session + conv + 1 PI (Open) + addresses_planning_items: [{PI}] —
        # assert refs row created, assert PI status remains Open

    def test_apply_ordering_session_conversation_workticket_pi_commit(
        self, routed, tmp_path, monkeypatch
    ):
        """Full payload with all sections applies in methodology §4 order.
        Captures section-completion log lines and asserts ordering."""
        # Full payload, capture stdout, assert section headers appear in
        # the expected order

    def test_409_skip_idempotent_on_re_run_all_sections(
        self, routed, tmp_path, monkeypatch
    ):
        """Re-applying the same payload twice produces 409 SKIPs on every
        section's records, exits 0 both times."""
        # Apply once OK, apply same payload again, assert all records SKIP

    def test_v0_7_payload_still_applies_without_new_sections(
        self, routed, tmp_path, monkeypatch
    ):
        """Backward compatibility: an old-format payload (no conversation,
        no work_tickets, no commits, no resolves/addresses) applies as before."""
        # session + 1 decision + 1 PI + 2 references — applies cleanly

    def test_resolves_status_flip_audit_chain(
        self, routed, tmp_path, monkeypatch
    ):
        """The deposit_event at apply close includes wrote_record edges to
        every record created including conversation, work_ticket, commit
        — sum(records_summary) == len(wrote_records) holds."""
        # Full payload — assert the deposit_event's references list
        # matches records_summary totals

    def test_conversation_records_session_edge_atomic_with_conversation(
        self, routed, tmp_path, monkeypatch
    ):
        """If the conversation POST fails, no orphan refs row is left."""
        # payload with a malformed conversation block — assert conversation
        # didn't land AND no refs row landed

    def test_resolves_for_already_resolved_pi_is_idempotent(
        self, routed, tmp_path, monkeypatch
    ):
        """Re-running resolves against an already-Resolved PI returns 409
        SKIP and the PI status remains Resolved."""
```

Adapt the test bodies to the existing helper functions (`_payload_path`, `routed.app.dependency_overrides`, etc.). Target: 12 tests.

File: `tests/crmbuilder_v2/access/test_vocab.py` (or wherever vocab tests live — search if needed)

Add tests for the three new wrote_record target types:

```python
def test_deposit_event_wrote_record_admits_conversation():
    kinds = _kinds_for_pair("deposit_event", "conversation")
    assert "deposit_event_wrote_record" in kinds


def test_deposit_event_wrote_record_admits_work_ticket():
    kinds = _kinds_for_pair("deposit_event", "work_ticket")
    assert "deposit_event_wrote_record" in kinds


def test_deposit_event_wrote_record_admits_commit():
    kinds = _kinds_for_pair("deposit_event", "commit")
    assert "deposit_event_wrote_record" in kinds
```

Locate the vocab test file before writing; the function-name pattern (`_kinds_for_pair` etc.) may vary.

### 10. Update the apply script docstring

Top-of-file docstring (lines 1-30) describes the script as POSTing "any combination of session, decisions, planning_items, and references records". Update to list the five new sections. Keep the doc concise.

---

## Verification

```bash
cd crmbuilder-v2
uv run pytest tests/crmbuilder_v2/ -x -q 2>&1 | tail -10
# Expect: <baseline> + ~15 = post-count. Zero failures.

# Lint / import check
uv run python -c "import importlib.util, pathlib; \
  spec = importlib.util.spec_from_file_location('apply_close_out', \
  pathlib.Path('scripts/apply_close_out.py')); \
  mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); \
  print('import ok; sections:', [s.name for s in mod._SECTIONS])"
# Expect: 9 section names in methodology §4 order
```

Sanity check the apply script against a sample payload structure (no API running needed — dry-load):

```bash
cd ..
python3 -c "
import json
sample = {
    'label': 'Sample',
    'session': {'identifier': 'SES-999'},
    'conversation': {'conversation_identifier': 'CONV-999'},
    'work_tickets': [{'work_ticket_identifier': 'WT-999', 'addresses_planning_item': 'PI-999'}],
    'commits': [{'commit_sha': 'a'*40, 'commit_repository': 'crmbuilder'}],
    'resolves_planning_items': [{'planning_item_identifier': 'PI-999'}],
    'addresses_planning_items': [{'planning_item_identifier': 'PI-998'}],
}
import sys
sys.path.insert(0, 'crmbuilder-v2/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('aco', 'crmbuilder-v2/scripts/apply_close_out.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
ctx = {'conversation_identifier': 'CONV-999'}
print('work_ticket shaped:', m._shape_work_ticket(sample['work_tickets'][0], ctx))
print('commit shaped:', {k: v[:40] if isinstance(v, str) else v for k, v in m._shape_commit(sample['commits'][0], ctx).items()})
print('resolves shaped:', m._shape_resolves_pi(sample['resolves_planning_items'][0], ctx))
print('addresses shaped:', m._shape_addresses_pi(sample['addresses_planning_items'][0], ctx))
"
# Expect: 
#  - work_ticket shaped includes 'references': [{target_type: planning_item, target_id: PI-999, relationship: addresses}]
#  - commit shaped includes commit_conversation_id: CONV-999
#  - resolves shaped: {source_type: conversation, source_id: CONV-999, target_type: planning_item, target_id: PI-999, relationship: resolves}
#  - addresses shaped: similar but relationship: addresses
```

---

## Commit

```bash
cd ~/Dropbox/Projects/crmbuilder
git add crmbuilder-v2/src/crmbuilder_v2/access/vocab.py
git add crmbuilder-v2/scripts/apply_close_out.py
git add tests/crmbuilder_v2/scripts/test_apply_close_out.py
git add tests/crmbuilder_v2/access/test_vocab.py     # if vocab tests live there; adjust path
git commit -m "v2: PI-030 slice B — apply_close_out.py extensions for five new close-out payload sections

apply_close_out.py now lands all five new sections introduced by the
Code Change Lifecycle methodology + DEC-223:

  session → conversation → work_tickets → planning_items → commits
         → decisions → references → resolves_planning_items
         → addresses_planning_items

Section shape transforms:
  - work_tickets[].addresses_planning_item → embedded addresses ref
    (atomic with work_ticket POST)
  - commits[].commit_conversation_id auto-populated from the payload's
    conversation block
  - resolves_planning_items[] → POST /references with relationship=resolves
    (slice A's atomic edge+flip fires server-side)
  - addresses_planning_items[] → POST /references with relationship=addresses

vocab.py extended to admit conversation, work_ticket, and commit as
deposit_event_wrote_record target_types. The access-layer invariant
sum(records_summary) == len(wrote_records) holds for the new types
without skipping (the references skip pattern is preserved as the
DEC-215 Option I documented exception).

Backward compatibility: payloads without the new sections (v0.7 format)
apply unchanged. Sections absent or empty are skipped (no-op). HTTP 409
SKIP idempotency preserved.

Tests: 12 new in test_apply_close_out.py + 3 in test_vocab.py = 15
new tests on top of the slice A baseline.

Authority: DEC-221 (full scope), DEC-222 (emit-time helper, full
records in payload), DEC-223 (conversation block), DEC-224 (resolves
extension)."

# Per the 'you commit, I push' convention in Claude Code context,
# do NOT push here. Doug reviews and pushes manually:
#   git pull --rebase origin main
#   git push
```

---

## Done

Reply with:

- pytest result: `<slice-A-baseline>` + 15 = `<post-count>` passed, 0 failed
- Section count confirmed: 9 (`for s in _SECTIONS print(s.name)`)
- Shape dry-run: all four shape functions produce expected output
- Commit SHA
- Next: PI-030 slice C at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-pi-030-C-enumerate-commits-helper.md` (independent of this slice; can run in any order relative to slice C)
