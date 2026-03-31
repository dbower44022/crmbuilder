# Claude Code Prompt — Bug Fixes from First Deployment Run

## Context

Two bugs were found during the first live deployment run. Both are small,
targeted fixes. Read the affected files before making any changes.

---

## Bug 1 — Validate/Preview doesn't count relationships

### Observed behavior

When a YAML file contains only a `relationships` block (no `entities`),
the validate message says:

```
[VALIDATE] OK — 0 entities, 0 fields found
```

And the preview summary shows:

```
===========================================
PLANNED CHANGES
===========================================
===========================================
To create : 0
To update : 0
No change : 0
===========================================
```

This is misleading — the file has 11 relationships but they're invisible
in the output.

### Fix location

`espo_impl/ui/main_window.py` — `_on_validate_clicked` method.

### Fix

Update the validate success message to include relationship count:

```python
total_fields = sum(len(e.fields) for e in program.entities)
total_relationships = len(program.relationships)

# Build a meaningful summary string
parts = []
if program.entities:
    parts.append(f"{len(program.entities)} entities, {total_fields} fields")
if total_relationships:
    parts.append(f"{total_relationships} relationships")
if not parts:
    parts.append("no entities or relationships")

self.output_panel.append_line(
    f"[VALIDATE] OK — {', '.join(parts)} found",
    "green",
)
```

Also update the preview summary in `core/field_manager.py` — the
`_build_planned_changes_summary` method or equivalent — to note when
a file has relationships that will be processed during Run but are not
shown in the preview:

```
===========================================
PLANNED CHANGES
===========================================
To create : 0
To update : 0
No change : 0

Note: 11 relationships defined — processed during Run, not shown in preview.
===========================================
```

Find the preview output method and add this note when
`program.relationships` is non-empty.

---

## Bug 2 — WorkshopAttendance → Contact missing VERIFIED line

### Observed behavior

```
[RELATIONSHIP] WorkshopAttendance → Contact (contact) ... CREATED OK
[RELATIONSHIP] WorkshopAttendance → Engagement (engagement) ... CHECKING
```

The VERIFIED line after CREATED OK is missing for
`WorkshopAttendance → Contact`. The next relationship starts immediately
after CREATED OK with no verification step logged.

### Fix location

`espo_impl/core/relationship_manager.py` — the process method.

### Investigation

Read the relationship manager carefully. Find the code path that handles
a successful create and determine why verify is not being called or not
being logged for this specific case.

Likely causes:
- Verify is skipped when the HTTP response for create doesn't return
  the expected status
- The verify method is called but an exception is swallowed silently
- A conditional check incorrectly bypasses verify for certain link types

### Fix

Ensure verify is called and logged for every successfully created
relationship without exception. The expected output for every created
relationship is:

```
[RELATIONSHIP] Entity → Entity (linkName) ... CHECKING
[RELATIONSHIP] Entity → Entity (linkName) ... MISSING
[RELATIONSHIP] Entity → Entity (linkName) ... CREATING
[RELATIONSHIP] Entity → Entity (linkName) ... CREATED OK
[RELATIONSHIP] Entity → Entity (linkName) ... VERIFIED
```

Add a test case to `tests/test_relationship_manager.py`:

```python
def test_verify_always_logged_after_create():
    """Verify is always called and logged after a successful create."""
    # Mock a successful create followed by a successful verify check
    # Confirm the VERIFIED message is emitted
    ...
```

---

## Bug 3 — Relationship verify fails due to c-prefix on linkForeign

### Observed behavior

All 6 Partner relationships showed VERIFY FAILED after CREATED OK.
The metadata API returns:
```json
{"type":"belongsTo","foreign":"cPartnerAgreements","entity":"Account",...}
```

But `_compare_link` compares against `rel.link_foreign` which is
`"cPartnerAgreements"` in the YAML — so this should match. However
for relationships where the foreign side is on a native entity (Account,
Contact), EspoCRM may store the foreign link name differently.

### Investigation

Read `_compare_link` carefully. The `existing.get("foreign")` value from
the API may be None, empty, or structured differently for certain link
types. Add defensive logging to show exactly what `existing` contains
when verify fails, to make future debugging easier.

### Fix

Update `_compare_link` to log the mismatch details when it returns False:

```python
def _compare_link(self, existing, rel, espo_entity_foreign):
    expected_type = LINK_TYPE_TO_METADATA.get(rel.link_type)
    if existing.get("type") != expected_type:
        logger.debug(
            "Link type mismatch: expected %s, got %s",
            expected_type, existing.get("type")
        )
        return False
    if existing.get("entity") != espo_entity_foreign:
        logger.debug(
            "Entity mismatch: expected %s, got %s",
            espo_entity_foreign, existing.get("entity")
        )
        return False
    # foreign key may be absent for some link types — treat as match if absent
    if "foreign" in existing and existing.get("foreign") != rel.link_foreign:
        logger.debug(
            "Foreign mismatch: expected %s, got %s",
            rel.link_foreign, existing.get("foreign")
        )
        return False
    return True
```

The key change: if the `foreign` key is absent from the metadata response,
treat it as a match rather than a failure. Some EspoCRM link types don't
return a `foreign` key.

Also add a test:
```python
def test_compare_link_missing_foreign_key():
    """Missing foreign key in metadata is treated as a match."""
    # existing has no "foreign" key
    # should return True if type and entity match
```

---

## Task 3 — Run tests

After both fixes:

```bash
uv run pytest tests/ -v
```

All 169+ tests must pass before committing.

---

## Task 4 — Commit

```
fix: show relationship count in validate message
fix: ensure verify always logged after relationship create
```

---

## Bug 4 — Verify step doesn't find relationship on native entity primary side

### Observed behavior

After successfully creating `Account → Contact (partnerLiaison)`, the
verify step logs VERIFY FAILED. The relationship was confirmed to exist
in EspoCRM as `cPartnerLiaison` — but the verify step checks for
`partnerLiaison` (without c-prefix) so it finds nothing.

### Root cause

The check step was already fixed to probe for the c-prefixed name first
on native entities. The verify step uses `rel.link` directly and needs
the same c-prefix logic.

### Fix location

`espo_impl/core/relationship_manager.py` — the verify call after CREATED OK.

### Fix

```python
# Verify — use c-prefixed name for native entity primary side
verify_link = rel.link
if rel.entity in NATIVE_ENTITIES:
    verify_link = "c" + rel.link[0].upper() + rel.link[1:]

verify = self._check_link_exists(espo_entity, verify_link)
```

Add a test:
```python
def test_verify_uses_c_prefix_for_native_entity():
    """Verify step checks c-prefixed link name for native entity primary side."""
```

---

## Bug 5 — Error handler doesn't log EspoCRM response body on 4xx

### Observed behavior

When EspoCRM returns HTTP 409 on createLink, the run report shows only
"HTTP 409" with no detail about why the request was rejected. This made
diagnosing the native entity link naming issue much harder.

### Fix location

`espo_impl/core/relationship_manager.py` — error handling block after
`client.create_link(payload)`. Also check `espo_impl/core/field_manager.py`.

### Fix

```python
if status_code not in (200, 201):
    error_detail = ""
    if isinstance(body, dict):
        error_detail = body.get("message", str(body))
    elif isinstance(body, str):
        error_detail = body[:200]
    self.output_fn(
        f"[RELATIONSHIP]  {prefix} ... ERROR (HTTP {status_code}: {error_detail})",
        "red"
    )
    logger.error("createLink failed: HTTP %s — %s", status_code, body)
```

Add a test:
```python
def test_error_includes_response_body():
    """Error output includes EspoCRM response body, not just status code."""
```

---

## Task 3 — Run tests

```bash
uv run pytest tests/ -v
```

All 175+ tests must pass before committing.

---

## Task 4 — Commit

```
fix: show relationship count in validate message
fix: ensure verify always logged after relationship create
fix: verify step uses c-prefix for native entity link names
fix: log full EspoCRM response body on relationship create errors
```
