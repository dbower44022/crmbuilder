# Claude Code Prompt — Rename App to CRM Builder

## Context

The application was previously called "EspoCRM Implementation Tool".
It has been moved to a new repository called `crmbuilder`. Update all
user-facing references to reflect the new name: **CRM Builder**.

Read these files before making any changes:
- `espo_impl/ui/main_window.py`
- `pyproject.toml`
- `README.md`
- `CLAUDE.md`
- `docs/user-guide.md`

---

## Task 1 — Update application window title

In `espo_impl/ui/main_window.py`, find:

```python
self.setWindowTitle("EspoCRM Implementation Tool")
```

Replace with:

```python
self.setWindowTitle("CRM Builder")
```

---

## Task 2 — Update `pyproject.toml`

Update the project name and entry point:

- `name` — change to `crmbuilder`
- `description` — change to `"CRM Builder — EspoCRM configuration deployment tool"`
- The entry point script (under `[project.scripts]`) — change the command
  from `espo-impl` to `crmbuilder`

---

## Task 3 — Update `README.md`

Replace all references to "EspoCRM Implementation Tool" with "CRM Builder".
Update the launch command if it changed in Task 2.

---

## Task 4 — Update `CLAUDE.md`

Replace the opening description:

```
This is the **EspoCRM Implementation Tool**
```

with:

```
This is the **CRM Builder** — an EspoCRM configuration deployment tool.
```

---

## Task 5 — Update `docs/user-guide.md`

Replace the document title and any references to "EspoCRM Implementation Tool"
with "CRM Builder". Keep all technical content unchanged.

---

## Task 6 — Update other docs

Search all files under `docs/` and `PRDs/` for "EspoCRM Implementation Tool"
and replace with "CRM Builder". Use str_replace for each occurrence found.

---

## Task 7 — Tests

Run:
```bash
uv run pytest tests/ -q
```

All tests must pass. The rename is cosmetic — no logic changes.

---

## Task 8 — Commit

```
feat: rename application to CRM Builder
```

---

## Important Notes

- "CRM Builder" (two words, title case) is the display name
- `crmbuilder` (lowercase, no space) is the package/command name
- Do not rename any Python modules or file paths — only user-facing strings
- The launch command changes from `uv run espo-impl` to `uv run crmbuilder`
