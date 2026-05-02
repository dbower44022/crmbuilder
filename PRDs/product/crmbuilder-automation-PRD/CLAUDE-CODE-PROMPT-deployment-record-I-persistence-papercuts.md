# Claude Code Prompt — Deployment Record Series, Prompt I

**Series:** deployment-record (productize the Deployment Record artifact)
**Prompt ID:** I
**Descriptor:** persistence-papercuts
**Filename:** `CLAUDE-CODE-PROMPT-deployment-record-I-persistence-papercuts.md`
**Repository:** `crmbuilder`
**Depends on:** Prompts A through H merged (this prompt extends the schema and the regeneration flow they established)
**Last Updated:** 05-02-26 17:00
**Version:** 1.0

---

## Status

Two small papercut fixes observed during the post-Prompt-H smoke test of the regeneration flow against the live CBM Test instance. Both are gaps in how the regeneration dialog handles Documentation Inputs that the user types: today they're treated as transient runtime state and discarded, when they should be persisted so the dialog pre-fills correctly on subsequent regenerations.

The two papercuts:

- **FU-1: Proton Pass entry names are not persisted.** The Documentation Inputs page in the wizard (Prompt B) and the Documentation Inputs section of the regeneration dialog (Prompt C) collect three Proton Pass entry names from the user (admin password, DB root password, hosting account). These are written into the generated `.docx` and then discarded. On every subsequent regeneration the dialog pre-fills templated defaults derived from the Instance code, which the user must then re-edit to match their actual entry names. Two regenerations in a row require entering the same three values twice.
- **FU-2: Document version always renders as `1.0`.** The `AdministratorInputs.document_version` field has a hardcoded default of `"1.0"` and there is no logic to read the previous file's version and increment it. Every regeneration produces a v1.0 document. The Revision History table inside the document is therefore misleading after the first regeneration.

Both have the same shape: a value the user enters or the system computes once should be remembered for next time.

After Prompt I: the regeneration dialog pre-fills correctly with the user's actual Proton Pass entry names, and document version increments automatically (1.0 → 1.1 → 1.2 ...) on each regeneration that overwrites the canonical filename.

---

## What this prompt accomplishes

1. **Schema migration `_client_v11`** adding three columns to `InstanceDeployConfig`:
   - `proton_pass_admin_entry TEXT`
   - `proton_pass_db_root_entry TEXT`
   - `proton_pass_hosting_entry TEXT`
   - All nullable, default NULL. Existing rows are unaffected.
2. **Schema migration `_client_v12`** adding one column to `InstanceDeployConfig`:
   - `last_record_version TEXT` — the document_version string most recently written to the canonical Deployment Record `.docx` for this instance. Nullable, default NULL.
3. **Round-trip the new columns** in `automation/core/deployment/deploy_config_repo.py`'s `InstanceDeployConfig` dataclass and `_row_to_config` / `save_deploy_config` helpers.
4. **Update the regeneration dialog (Prompt C's `regenerate_record_dialog.py`)** to:
   - Read the three Proton Pass entry columns from `InstanceDeployConfig` if non-NULL when populating the dialog's Documentation Inputs fields, falling back to the existing templated defaults only when NULL.
   - Persist the user's edits to those three columns when the user clicks Generate (alongside the existing persistence of `domain_registrar`, `dns_provider`, `droplet_id`, `backups_enabled`).
5. **Update the wizard's Documentation Inputs page (Prompt B's contribution to `wizard_dialog.py`)** with the same persist-on-success behavior.
6. **Update document version handling**:
   - Read `last_record_version` from `InstanceDeployConfig` when initializing `AdministratorInputs.document_version`.
   - If NULL, default to `"1.0"`.
   - If non-NULL, increment the minor version (`1.0` → `1.1`, `1.5` → `1.6`, `2.3` → `2.4`). Major version bumps are out of scope and not handled.
   - Write the rendered version string back to `last_record_version` after a successful generation.
7. **Tests** for all of the above:
   - Migration tests verifying `_client_v11` and `_client_v12` apply cleanly and are idempotent.
   - `deploy_config_repo` tests verifying round-trip of all four new columns.
   - Regeneration dialog tests verifying the pre-fill reads from the persisted columns when present.
   - Regeneration worker tests verifying the persist-on-success writes the four new columns.
   - Version-increment unit tests covering NULL → 1.0, 1.0 → 1.1, 1.9 → 1.10 (or 2.0 — pick one and document; this prompt mandates 1.10 for simplicity), 2.5 → 2.6.

---

## What this prompt does NOT do

- **No retroactive backfill.** Existing rows in `InstanceDeployConfig` get NULLs for the new columns. The user fills them in by performing one regeneration, after which they're persisted.
- **No major version bump logic.** Going from `1.x` to `2.0` is a manual operation outside the scope of automation; the auto-increment only ever bumps minor.
- **No changes to the JS generator** in the CBM repo.
- **No changes to the procedure document** (`cbm-test-instance-backfill-procedure.md`).
- **No changes to the `ConnectionConfigDialog`** (the original SSH-only backfill dialog from before the deployment-record series). It does not collect Proton Pass entry names; it shouldn't start.

---

## Constraints and conventions

- **Migration ordering matters.** `_client_v11` and `_client_v12` are sequential, both must apply, both must be idempotent. Match the existing patterns in `automation/db/migrations.py`.
- **Do not add `NOT NULL` constraints on the new columns.** Existing rows must continue to be valid after migration.
- **Version increment edge cases:**
  - `"1.0"` → `"1.1"` (basic increment)
  - `"1.9"` → `"1.10"` (no rollover; lexically the version string just gets a longer minor)
  - Non-numeric inputs (e.g., `"draft"`, `"1.0-rc1"`): preserve the input and append `+1`-style suffix? No — keep it simple: if the version doesn't match the regex `^(\d+)\.(\d+)$`, fall back to the previous behavior of using the existing string as-is and emit a log warning. Do not crash.
- **Persist-on-success means after the generator succeeds, not before.** A failed generation should not modify `last_record_version` or any other persisted field. If the user opted for "Write versioned copy with timestamp suffix" (the non-default radio), do not bump `last_record_version` because the canonical file was not overwritten.
- **Python 3.11+, type hints, docstrings, pytest** — same conventions as the rest of the codebase.

---

## Detailed implementation

### 1. Migration `_client_v11`

In `automation/db/migrations.py`, add a new function (matching the existing pattern of `_client_v10`):

```python
def _client_v11(conn: sqlite3.Connection) -> None:
    """Add Proton Pass entry-name columns to InstanceDeployConfig.

    Three columns, all nullable, for persisting the Documentation
    Inputs that previously got entered fresh on every regeneration.
    """
    cur = conn.cursor()
    cols = [r[1] for r in cur.execute(
        "PRAGMA table_info(InstanceDeployConfig)"
    ).fetchall()]
    for col in (
        "proton_pass_admin_entry",
        "proton_pass_db_root_entry",
        "proton_pass_hosting_entry",
    ):
        if col not in cols:
            cur.execute(
                f"ALTER TABLE InstanceDeployConfig ADD COLUMN {col} TEXT"
            )
```

Register `_client_v11` in the migration sequence the same way `_client_v10` is registered.

### 2. Migration `_client_v12`

Same pattern:

```python
def _client_v12(conn: sqlite3.Connection) -> None:
    """Add last_record_version column for auto-increment.

    Holds the document_version most recently rendered to the canonical
    Deployment Record .docx for this instance. Nullable; defaults to
    NULL for existing rows.
    """
    cur = conn.cursor()
    cols = [r[1] for r in cur.execute(
        "PRAGMA table_info(InstanceDeployConfig)"
    ).fetchall()]
    if "last_record_version" not in cols:
        cur.execute(
            "ALTER TABLE InstanceDeployConfig "
            "ADD COLUMN last_record_version TEXT"
        )
```

### 3. Round-trip in `deploy_config_repo.py`

Add the four new fields to the `InstanceDeployConfig` dataclass:

```python
@dataclasses.dataclass
class InstanceDeployConfig:
    # ... existing fields ...
    proton_pass_admin_entry: str | None = None
    proton_pass_db_root_entry: str | None = None
    proton_pass_hosting_entry: str | None = None
    last_record_version: str | None = None
```

Update `_row_to_config` to populate from the row tuple. Update `save_deploy_config` to write the four new columns. Match the existing patterns.

### 4. Regeneration dialog pre-fill

In `automation/ui/deployment/regenerate_record_dialog.py`, find the dialog's pre-fill logic (the place where the three Proton Pass entry fields get their initial text). Today it falls back to templated defaults derived from the instance code (e.g., `f"{code}-ESPOCRM-{Env} Instance Admin"`).

Update to read from `deploy_config.proton_pass_admin_entry` (etc.) first if non-NULL, falling back to the templated default only when NULL. Pseudocode:

```python
admin_default = (
    deploy_config.proton_pass_admin_entry
    or f"{instance.code}-ESPOCRM-{instance.environment.title()} Instance Admin"
)
self._admin_proton_pass_entry.setText(admin_default)
# similar for db_root and hosting
```

### 5. Wizard Documentation Inputs page

The wizard's Documentation Inputs page (added by Prompt B in `wizard_dialog.py`) collects the same three Proton Pass entry names during a fresh deploy. Currently they go into `AdministratorInputs` and from there into the generator, then are discarded. Update the page so the user's edits are persisted to the new `InstanceDeployConfig` columns when the deploy worker calls `save_deploy_config` post-success.

This may already happen via the existing administrator-inputs persistence flow — check first. If the persistence already writes the four Prompt B columns (`domain_registrar`, etc.), the three new columns can ride along the same path. If a full re-thread is needed, do that.

### 6. Document version handling

In `record_generator.py` (or wherever `AdministratorInputs.document_version` originates for non-CLI invocations — verify by searching for `document_version=`):

- **Compute the version on dialog initialization:** read `deploy_config.last_record_version`. If NULL, set `document_version = "1.0"`. If non-NULL, parse the existing string with regex `^(\d+)\.(\d+)$`, increment the minor, format as `f"{major}.{minor + 1}"`, and use that.
- **Persist after success:** when the worker writes back to `InstanceDeployConfig`, include `last_record_version = values.document_version`.
- **Do not bump on versioned-copy mode.** If the user picked "Write versioned copy with timestamp suffix", the canonical file was not overwritten, so `last_record_version` should not change.

A small helper function for the version logic:

```python
def increment_minor_version(version: str | None) -> str:
    """Compute the next document_version given the previous one.

    None → '1.0' (first generation).
    'M.N' (numeric major.minor) → 'M.{N+1}' (e.g., '1.0' → '1.1').
    Non-matching strings → returned unchanged with a warning logged
    by the caller (this function does not log).
    """
    if version is None:
        return "1.0"
    match = re.match(r"^(\d+)\.(\d+)$", version.strip())
    if not match:
        return version  # caller should log a warning
    major, minor = match.groups()
    return f"{major}.{int(minor) + 1}"
```

Place this helper next to `_read_espocrm_version` and similar private helpers in `record_generator.py`, or at the top of `regenerate_record_worker.py` if it makes more sense there. Use whichever location keeps the call sites cleanest.

### 7. Tests

Add or extend:

- `tests/db/test_migrations.py` (or wherever migration tests live):
  - `test_client_v11_adds_proton_pass_columns`
  - `test_client_v11_idempotent`
  - `test_client_v12_adds_last_record_version`
  - `test_client_v12_idempotent`
- `tests/test_deploy_config_repo.py`:
  - `test_round_trip_proton_pass_entries`
  - `test_round_trip_last_record_version`
- `tests/test_regenerate_record_dialog.py`:
  - `test_dialog_prefills_proton_pass_from_persisted_config`
  - `test_dialog_falls_back_to_templated_defaults_when_columns_null`
- `tests/test_regenerate_record_worker.py`:
  - `test_worker_persists_proton_pass_entries_on_success`
  - `test_worker_persists_last_record_version_on_overwrite`
  - `test_worker_does_not_persist_last_record_version_on_versioned_copy`
- `tests/test_record_generator.py`:
  - `test_increment_minor_version_initial`
  - `test_increment_minor_version_basic`
  - `test_increment_minor_version_handles_double_digit`
  - `test_increment_minor_version_passes_through_non_numeric`

---

## Acceptance criteria

- Migrations `_client_v11` and `_client_v12` apply cleanly and are idempotent.
- The regeneration dialog pre-fills the three Proton Pass entry fields from the persisted columns when present.
- After a successful regeneration that overwrites the canonical file, `InstanceDeployConfig` rows for the regenerated instance show non-NULL values for `proton_pass_admin_entry`, `proton_pass_db_root_entry`, `proton_pass_hosting_entry`, and `last_record_version`.
- A second regeneration of the same instance opens the dialog with all four prior values pre-filled correctly.
- The second regeneration's document renders `Version: 1.1` (incremented from `1.0`).
- All existing tests in the deployment-record series continue to pass.
- New tests added by this prompt pass.
- `uv run ruff check` is clean on touched files.

---

## Notes for the implementer

- These are persistence-of-existing-values fixes, not new features. The values already exist in memory during the dialog's lifecycle; the only change is "remember them across invocations." Keep that framing in mind to resist scope creep.
- The double-digit minor version case (`1.9` → `1.10`) is a deliberate choice. Some projects use semver-style rollover (`1.9` → `2.0`), others use strict-increment (`1.9` → `1.10`). For this application, the document version is descriptive metadata, not a software version, so strict-increment is correct.
- After this prompt, the persistent-state shape of `InstanceDeployConfig` finally matches the full set of values the deployment-record series introduces. The schema is at v12; no further extensions are anticipated for this work track.
