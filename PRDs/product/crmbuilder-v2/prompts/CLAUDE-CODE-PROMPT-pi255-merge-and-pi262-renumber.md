# CLAUDE-CODE-PROMPT-pi255-merge-and-pi262-renumber.md

## Operating mode: DETAIL

## Purpose

Merge `pi-255` to `main`, resolve the 0079 migration number collision with the
in-flight PI-262 publish-runs WIP, and leave both `main` and the PI-262 worktree
clean for Prompt B (PI-255 REST + reconciler slice).

---

## Pre-flight

```bash
# Confirm the main working tree is on main and clean
cd ~/Dropbox/Projects/CRMBuilder
git status
git branch
git log --oneline -3

# Confirm the pi-255 worktree location and its HEAD
git worktree list

# Check what migration numbers are currently in the pi-255 branch
ls ~/Dropbox/Projects/crmbuilder-pi255/crmbuilder-v2/migrations/versions/ | sort | tail -5
```

Confirm:
- Main working tree is on `main`, clean
- `pi-255` worktree is at `~/Dropbox/Projects/crmbuilder-pi255` (or wherever it lives — adjust path below)
- The pi-255 branch has `0079_pi_255_source_mapping_tables.py` (SQLite) and a PG companion

Also check whether PI-262 has an uncommitted `0079_pi_262_*.py` in the main working tree:

```bash
ls ~/Dropbox/Projects/CRMBuilder/crmbuilder-v2/migrations/versions/ | sort | tail -5
git -C ~/Dropbox/Projects/CRMBuilder status -- crmbuilder-v2/migrations/versions/
```

---

## Step 1 — Merge pi-255 to main

```bash
cd ~/Dropbox/Projects/CRMBuilder
git fetch origin
git merge --no-ff origin/pi-255 -m "v2: merge pi-255 — source mapping foundation (vocab, models, migration 0079, repositories)"
```

If there are conflicts, they will be in `migrations/versions/` — resolve by keeping
**both** files (pi-255's `0079_pi_255_*` and any other 0079 if it somehow landed on main).
There should be no conflicts in source files since pi-255 added net-new files only.

After merge, verify:

```bash
git log --oneline -5
# Confirm pi-255 content is on main
ls crmbuilder-v2/migrations/versions/ | sort | tail -5
ls crmbuilder-v2/src/crmbuilder_v2/access/repositories/ | grep -E "source_mapping|field_mapping|value_mapping|mapping_candidate"
```

---

## Step 2 — Verify the migration chain is intact on main

```bash
cd ~/Dropbox/Projects/CRMBuilder/crmbuilder-v2
uv run alembic -c migrations/alembic.ini heads
uv run alembic -c migrations/alembic.ini history --verbose | head -20
```

Expected: single SQLite head at `0079_pi_255_source_mapping_tables`. If there are
two heads (meaning PI-262's 0079 somehow already landed on main), stop here and
report — do not proceed until resolved.

---

## Step 3 — Check PI-262 migration collision

```bash
# Is there an uncommitted 0079_pi_262_* file in the main working tree?
ls ~/Dropbox/Projects/CRMBuilder/crmbuilder-v2/migrations/versions/ | grep 0079

# Is there a pi-262 worktree?
git worktree list | grep pi-262

# If a pi-262 worktree exists, check its migration file
ls <pi-262-worktree-path>/crmbuilder-v2/migrations/versions/ | grep 0079
```

If PI-262 has a `0079_pi_262_*.py` file (committed on its branch OR uncommitted in
the main tree), it must be renumbered to **0080** before it can merge to main.

---

## Step 4 — Renumber PI-262's migration from 0079 to 0080

**If the file is uncommitted in the main working tree:**

```bash
cd ~/Dropbox/Projects/CRMBuilder/crmbuilder-v2/migrations/versions/

# Find the exact filename
ls | grep 0079_pi_262

# Rename the file
mv 0079_pi_262_<descriptor>.py 0080_pi_262_<descriptor>.py
```

**If the file is committed on a pi-262 branch (worktree):**

```bash
cd <pi-262-worktree-path>/crmbuilder-v2/migrations/versions/
mv 0079_pi_262_<descriptor>.py 0080_pi_262_<descriptor>.py
```

**In either case, update the file's internal revision strings:**

Open `0080_pi_262_<descriptor>.py` and update:

```python
# Change:
revision: str = "0079_pi_262_<descriptor>"
down_revision: str | None = "0078_pi_249_release_back_half"

# To:
revision: str = "0080_pi_262_<descriptor>"
down_revision: str | None = "0079_pi_255_source_mapping_tables"
```

The `down_revision` must now point at pi-255's `0079_pi_255_source_mapping_tables`
as the new chain head on main.

**If PI-262 also has a Postgres companion migration** (e.g. `0037_pi_262_*.py`),
check whether it needs renumbering too — only if 0037 was already taken on main's
PG chain. Check:

```bash
ls ~/Dropbox/Projects/CRMBuilder/crmbuilder-v2/migrations/pg/ | sort | tail -5
```

If 0036 is the current PG head (from pi-255's PG companion), renumber PI-262's
PG companion from 0036 (if it exists as 0036) to 0037 and update its `revision`
and `down_revision` strings accordingly.

---

## Step 5 — Verify the renumbered migration compiles

```bash
# If the PI-262 file is in the main working tree, verify from main:
cd ~/Dropbox/Projects/CRMBuilder/crmbuilder-v2
python -c "import importlib.util; spec = importlib.util.spec_from_file_location('m', 'migrations/versions/0080_pi_262_<descriptor>.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('revision:', m.revision); print('down_revision:', m.down_revision)"

# Verify alembic sees a single clean chain (no two heads)
uv run alembic -c migrations/alembic.ini heads
```

Expected: single head, either `0079_pi_255_source_mapping_tables` (if PI-262 not yet
staged) or `0080_pi_262_<descriptor>` (if PI-262 staged). Never two heads.

---

## Step 6 — Run the full test suite on main to confirm no regressions

```bash
cd ~/Dropbox/Projects/CRMBuilder/crmbuilder-v2
uv run pytest tests/ -x -q --ignore=tests/ui
```

Expected: same green result as pi-255 slice 1 (1403+ passed, 1 skip, 5 xfail).
The 29 new pi-255 tests should be in this count.

---

## Step 7 — Commit the PI-262 renumber (if the file was in the main working tree)

If the `0079_pi_262_*.py` was an **uncommitted** file in the main working tree,
commit it now as the renumbered version:

```bash
cd ~/Dropbox/Projects/CRMBuilder
git add crmbuilder-v2/migrations/versions/0080_pi_262_<descriptor>.py
git commit -m "v2: renumber PI-262 migration 0079ₒ0080 after pi-255 merge (chain conflict resolution)"
```

If it was on the pi-262 **branch/worktree** (not yet on main), commit it there:

```bash
cd <pi-262-worktree-path>
git add crmbuilder-v2/migrations/versions/0080_pi_262_<descriptor>.py
git commit -m "v2: renumber PI-262 migration 0079ₒ0080 (pi-255 landed first on main)"
```

---

## Step 8 — Final state verification

```bash
cd ~/Dropbox/Projects/CRMBuilder/crmbuilder-v2

# Single alembic head on main
uv run alembic -c migrations/alembic.ini heads

# pi-255 repositories are present on main
ls src/crmbuilder_v2/access/repositories/ | grep -E "source_mapping|field_mapping|value_mapping|mapping_candidate"

# pi-255 vocab constants are present
python -c "from crmbuilder_v2.access.vocab import SOURCE_MAPPING_DECISION_TYPES, MAPPING_CANDIDATE_TYPES, INSTANCE_MEMBERSHIP_STATES; print('SMG types:', SOURCE_MAPPING_DECISION_TYPES); print('candidate types:', MAPPING_CANDIDATE_TYPES); print('membership states:', INSTANCE_MEMBERSHIP_STATES)"

git log --oneline -6
```

---

## Done

Do NOT push. Doug pushes.

Reply with:
- Merge commit SHA
- Final migration head on main (SQLite)
- Confirmation that the pi-255 repositories and vocab constants are visible on main
- Where the PI-262 renumber landed (main working tree commit, or pi-262 branch commit)
- Test suite result (pass count)
- Whether any unexpected conflicts or deviations occurred
