# Claude Code Prompt — content_version Support

## Context

YAML program files now have a `content_version` field at the top level:

```yaml
version: "1.0"
content_version: "1.0.0"
description: "..."
```

`version` is the YAML schema version (unchanged).
`content_version` is the content version, incremented by the author
when making changes. Uses semantic versioning (MAJOR.MINOR.PATCH).

This prompt adds support for `content_version` in the tool — parsing it,
displaying it in the UI, and including it in reports.

Read these files before starting:
- `espo_impl/core/models.py`
- `espo_impl/core/config_loader.py`
- `espo_impl/ui/program_panel.py`
- `espo_impl/ui/main_window.py`
- `espo_impl/core/reporter.py`

---

## Task 1 — Update `core/models.py`

Add `content_version` to `ProgramFile`:

```python
content_version: str = "1.0.0"
```

Add after `description`.

---

## Task 2 — Update `core/config_loader.py`

In `load_program()`, parse `content_version`:

```python
content_version=str(raw.get("content_version", "1.0.0")),
```

Add to the `ProgramFile(...)` constructor call.

---

## Task 3 — Update `espo_impl/ui/program_panel.py`

The program panel displays a list of YAML files. Currently it shows just
the filename. Update it to show the content_version alongside the filename.

Read the current program_panel.py carefully to understand how files are
displayed, then add the version so the list shows:

```
cbm_contact_fields.yaml  v1.0.0
cbm_account_fields.yaml  v1.0.0
cbm_engagement_fields.yaml  v1.0.0
```

The version should be displayed in a muted/secondary style (smaller or
greyed out) so the filename remains the primary visual element.

Parse the content_version directly from the YAML file when building the
list — do not require the file to be fully loaded/validated first. Use
a lightweight parse (just read the top-level `content_version` key).

If `content_version` is missing from a file, display nothing (don't show
a default — only show a version if explicitly set).

---

## Task 4 — Update `espo_impl/core/reporter.py`

Include `content_version` in both report outputs.

**Log file header** — add content_version line:
```
Program File  : cbm_contact_fields.yaml
Version       : 1.0.0
Instance      : CBM Test
...
```

**JSON report** — add to metadata:
```json
{
  "program_file": "cbm_contact_fields.yaml",
  "content_version": "1.0.0",
  ...
}
```

**Report filename** — optionally include version in filename:
```
trial_crm_run_20260323_155604_v1.0.0.log
```

Only add the version suffix if `content_version` is set and not the
default "1.0.0" — this avoids cluttering filenames during initial
deployment. Actually on reflection, always include it — it makes reports
unambiguous. Format: replace dots with underscores in the filename:
```
trial_crm_run_20260323_155604_v1_0_0.log
```

---

## Task 5 — Update `docs/process.md`

Add a "Content Versioning" subsection to Section 4.2 (YAML Structure):

```markdown
### Content Versioning

Every YAML file has a `content_version` field using semantic versioning:

```yaml
content_version: "1.0.0"
```

Increment the version when making changes:

| Change | Version bump | Example |
|---|---|---|
| Description updates, comment fixes | PATCH | 1.0.0 → 1.0.1 |
| New fields added, enum values added | MINOR | 1.0.0 → 1.1.0 |
| Fields removed, types changed, entity restructured | MAJOR | 1.0.0 → 2.0.0 |

The version is displayed in the Program File panel, included in run/verify
report headers, and embedded in report filenames. This makes it easy to
confirm which version of a program file was used for a given deployment.
```

---

## Task 6 — Tests

Add to `tests/test_config_loader.py`:
- `content_version` parsed correctly when present
- Default `"1.0.0"` used when `content_version` absent

Add to `tests/test_reporter.py`:
- `content_version` appears in log file header
- `content_version` appears in JSON report
- Report filename includes version suffix

Run `uv run pytest tests/ -v` and confirm all tests pass.

---

## Implementation Notes

### Lightweight YAML parse in program_panel.py

To avoid parsing the full YAML just to get the version, use:

```python
import yaml
try:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    version = raw.get("content_version", "") if isinstance(raw, dict) else ""
except Exception:
    version = ""
```

### Backward compatibility

YAML files without `content_version` are still valid. The tool treats
them as version "1.0.0" internally but displays nothing in the UI
(so existing files without the field don't look broken).
