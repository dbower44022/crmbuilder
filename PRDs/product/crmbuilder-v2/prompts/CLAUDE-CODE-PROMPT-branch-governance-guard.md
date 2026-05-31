# CLAUDE-CODE-PROMPT — Branch governance guard (Model A)

**Last Updated:** 05-30-26 23:55

**Operating mode:** DETAIL. Make the surgical changes exactly as specified. Do not refactor surrounding code.

**Repo:** `dbower44022/crmbuilder`. **CLAUDE.md:** root (the only one).

---

## Purpose

Make it mechanically impossible to fork the governance identifier sequence or the committed `db-export/` snapshots off a branch. This is the structural fix behind the PI-112 fork, where `apply_close_out.py` was run on the `pi-112-migration` branch and advanced sessions, decisions, and snapshots there while `main` still treated those identifiers as free.

**Decided model (Model A):** governance applies and `db-export/` snapshot commits happen **only on `main`**. A `pi-NNN` branch carries only code, schema, and migration commits; the work's governance records are authored as a close-out payload and applied on `main` after merge, re-keyed to `main`'s heads. Mechanical guards enforce this; documentation explains it.

### Net Effect

When this prompt completes, the following will be true:

1. `crmbuilder-v2/scripts/apply_close_out.py` refuses to run on any branch other than `main` unless `--allow-branch-local` is passed (the Model B isolated-DB escape hatch).
2. A tracked pre-commit hook at `crmbuilder-v2/githooks/pre-commit` rejects staged files under `PRDs/product/crmbuilder-v2/db-export/` or `deposit-event-logs/` when `HEAD` is not `main`, overridable only with `CRMBUILDER_ALLOW_BRANCH_SNAPSHOT=1` (merge-time only). `core.hooksPath` is pointed at the tracked dir.
3. CLAUDE.md's Working conventions document the Branch-work protocol (Model A).

No governance records are created by this prompt. It is code + docs only and is safe to run on `main`.

---

## Pre-flight

```bash
cd ~/Dropbox/Projects/crmbuilder
git rev-parse --abbrev-ref HEAD          # must print: main
git status --porcelain                   # must be empty (clean tree)
git config user.email "doug@dougbower.com"
git config user.name  "Doug Bower"
git pull --rebase origin main
```

If `HEAD` is not `main` or the tree is dirty, stop and report — do not proceed.

---

## Change 1 — branch guard in `apply_close_out.py`

File: `crmbuilder-v2/scripts/apply_close_out.py`

**1a. Add the `subprocess` import.** The import block (lines ~15–21) currently has `argparse, importlib.util, io, json, sys`. Add `subprocess`, keeping alphabetical order:

```python
import subprocess
```
(place it between `import json` and `import sys`).

**1b. Add a branch-detection helper** immediately above `def main() -> int:`:

```python
def _current_git_branch() -> str | None:
    """Return the current git branch name, or None if it can't be determined."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
```

**1c. Register the override flag.** In `main()`, after the existing `--skip-validation` argument block and before `args = parser.parse_args()`, add:

```python
    parser.add_argument(
        "--allow-branch-local",
        action="store_true",
        help=(
            "Permit applying on a non-main branch (Model B isolated-DB work "
            "only). Requires CRMBUILDER_V2_DB_PATH to point at a gitignored "
            "branch-local engagement DB. Default refuses any apply off main."
        ),
    )
```

**1d. Enforce the guard.** Immediately after `args = parser.parse_args()` (and before `BASE = args.base`), insert:

```python
    branch = _current_git_branch()
    if branch is not None and branch != "main" and not args.allow_branch_local:
        print(
            f"✗ Refusing to apply a close-out on branch '{branch}'.",
            file=sys.stderr,
        )
        print(
            "  Governance applies must run on 'main' so the identifier "
            "sequence and\n  db-export snapshots advance on a single line "
            "(Model A). If this is\n  isolated-DB branch work, re-run with "
            "--allow-branch-local AND ensure\n  CRMBUILDER_V2_DB_PATH points "
            "at a gitignored branch-local engagement DB.",
            file=sys.stderr,
        )
        return 2
```

---

## Change 2 — pre-commit hook blocking snapshot commits off `main`

**2a. Create** `crmbuilder-v2/githooks/pre-commit` with exactly this content:

```sh
#!/bin/sh
# Model A guard: governance snapshots advance only on main.
# Blocks staged db-export/ and deposit-event-logs/ changes on any non-main
# branch. Merge-time override: CRMBUILDER_ALLOW_BRANCH_SNAPSHOT=1
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
if [ "$branch" = "main" ] || [ "${CRMBUILDER_ALLOW_BRANCH_SNAPSHOT:-}" = "1" ]; then
    exit 0
fi
blocked="$(git diff --cached --name-only \
    -- 'PRDs/product/crmbuilder-v2/db-export/' \
       'PRDs/product/crmbuilder-v2/deposit-event-logs/')"
if [ -n "$blocked" ]; then
    echo "✗ pre-commit: governance snapshots may not be committed on branch '$branch'." >&2
    echo "  Model A: db-export/ and deposit-event-logs/ advance only on main." >&2
    echo "  Staged offending files:" >&2
    echo "$blocked" | sed 's/^/    /' >&2
    echo "  Merge of a branch-local apply? Set CRMBUILDER_ALLOW_BRANCH_SNAPSHOT=1." >&2
    exit 1
fi
exit 0
```

**2b. Make it executable and wire it up** (local config — travels per clone, the script itself is tracked):

```bash
chmod +x crmbuilder-v2/githooks/pre-commit
git config core.hooksPath crmbuilder-v2/githooks
```

Note in the close-out / commit message that any other clone of this repo must run `git config core.hooksPath crmbuilder-v2/githooks` once, since `core.hooksPath` is not itself committed.

---

## Change 3 — document the protocol in CLAUDE.md

File: `CLAUDE.md`, in the **Working conventions** section. Insert the following as a new paragraph immediately **after** the existing `**Push convention.**` paragraph (currently line ~104):

```markdown
**Branch-work protocol (Model A).** Governance applies and `db-export/` snapshot commits happen only on `main`. A `pi-NNN` branch carries only code, schema, and migration commits — it never runs `apply_close_out.py` and never commits anything under `PRDs/product/crmbuilder-v2/db-export/` or `deposit-event-logs/`. The branch ships the migration; the work's sessions, decisions, and planning items are authored as a close-out payload and applied on `main` after merge, re-keyed to `main`'s current heads (the DEC-232 / SES-074 build-closure pattern). This keeps the governance identifier sequence and the committed snapshots advancing on a single line; two lines advancing them independently produces duplicate identifiers and hand-merges of machine-generated JSON. Enforced mechanically: `apply_close_out.py` refuses to run off `main` (override `--allow-branch-local` for Model B isolated-DB work, which also requires `CRMBUILDER_V2_DB_PATH` set to a gitignored branch-local engagement DB), and the `crmbuilder-v2/githooks/pre-commit` hook rejects staged snapshot commits off `main` (merge-time override `CRMBUILDER_ALLOW_BRANCH_SNAPSHOT=1`). The PI-073 isolated-DB note remains the worked example of the *capability*; this paragraph is the rule.
```

Also update the `Last Updated`/revision marker if CLAUDE.md carries one in its header; if it does not (it currently does not), leave the file's top as-is.

---

## Verification

```bash
# 1. Script syntax + import OK
cd ~/Dropbox/Projects/crmbuilder/crmbuilder-v2
uv run python -c "import ast; ast.parse(open('scripts/apply_close_out.py').read()); print('parse OK')"

# 2. Guard fires off main (throwaway branch, no real apply attempted)
cd ~/Dropbox/Projects/crmbuilder
git switch -c tmp-guard-test
cd crmbuilder-v2
uv run python scripts/apply_close_out.py /nonexistent.json; echo "exit=$?"
#   EXPECT: "✗ Refusing to apply a close-out on branch 'tmp-guard-test'." and exit=2
#   (guard must trip BEFORE the payload-not-found check)
cd ..
git switch main
git branch -D tmp-guard-test

# 3. Pre-commit hook blocks a snapshot stage off main
git switch -c tmp-hook-test
touch PRDs/product/crmbuilder-v2/db-export/_guardprobe.json
git add PRDs/product/crmbuilder-v2/db-export/_guardprobe.json
git commit -m "probe" ; echo "exit=$?"
#   EXPECT: hook rejects, exit nonzero
rm PRDs/product/crmbuilder-v2/db-export/_guardprobe.json
git restore --staged PRDs/product/crmbuilder-v2/db-export/_guardprobe.json 2>/dev/null
git switch main
git branch -D tmp-hook-test

# 4. Existing tests still green (if a suite covers the apply script)
cd crmbuilder-v2 && uv run pytest -q 2>/dev/null | tail -5
```

All four must pass. If the guard does **not** trip in step 2, or the hook does **not** reject in step 3, stop and report before committing.

---

## Commit

One commit on `main`. Claude Code commits; Doug pushes (per Push convention).

```bash
cd ~/Dropbox/Projects/crmbuilder
git add crmbuilder-v2/scripts/apply_close_out.py \
        crmbuilder-v2/githooks/pre-commit \
        CLAUDE.md
git commit -m "v2: enforce Model A branch-governance guard

- apply_close_out.py refuses to run off main (--allow-branch-local escape hatch)
- githooks/pre-commit blocks db-export/ + deposit-event-logs/ commits off main
- core.hooksPath wired to crmbuilder-v2/githooks
- CLAUDE.md: Branch-work protocol (Model A) documented

Structural fix for the PI-112 governance fork: identifier sequence and
snapshots now advance only on main, enforced mechanically."
```

Then Doug: `git push origin main`.

---

## Done block — reply with

1. The four verification results (parse OK / guard exit=2 / hook rejected / pytest tail).
2. Confirmation that `core.hooksPath` is set to `crmbuilder-v2/githooks`.
3. The commit SHA.
4. Reminder that any other clone must run `git config core.hooksPath crmbuilder-v2/githooks` once.
