#!/usr/bin/env bash
#
# reconcile-divergence.sh
#
# Rebase local commits on top of origin/main, run the v2 test suite to confirm
# no breakage, and push. Designed for the v0.5 / v0.6 parallel-workstream
# divergence: local has v0.5 slice commits (B-E); origin has a v0.6 slice-A
# commit that landed while local was working.
#
# Run from the crmbuilder repo root. Idempotent — re-running after successful
# push is a no-op.
#
# Conflict policy: stops and reports if rebase has conflicts. Does not attempt
# automatic resolution. Most likely conflict point is named in the error
# message so resolution is mechanical.

set -euo pipefail

# ---------------------------------------------------------------- Pre-flight

echo "==> Pre-flight checks"

if [[ ! -d ".git" ]] || [[ ! -d "PRDs/product/crmbuilder-v2" ]]; then
  echo "ERROR: must run from crmbuilder repo root"
  exit 1
fi

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "$CURRENT_BRANCH" != "main" ]]; then
  echo "ERROR: expected to be on main, currently on $CURRENT_BRANCH"
  exit 1
fi

if ! git diff --quiet || ! git diff --staged --quiet; then
  echo "ERROR: working tree is not clean. Commit or stash changes first."
  echo ""
  git status --short
  exit 1
fi

GIT_NAME=$(git config user.name || true)
GIT_EMAIL=$(git config user.email || true)
if [[ "$GIT_NAME" != "Doug Bower" ]] || [[ "$GIT_EMAIL" != "doug@dougbower.com" ]]; then
  echo "ERROR: git identity not set correctly"
  echo "  expected: Doug Bower <doug@dougbower.com>"
  echo "  actual:   $GIT_NAME <$GIT_EMAIL>"
  exit 1
fi

echo "    ok: on main, working tree clean, identity correct"

# ---------------------------------------------------------------- Divergence

echo ""
echo "==> Fetching origin to compute divergence"
git fetch origin main

LOCAL_AHEAD=$(git rev-list --count origin/main..HEAD)
ORIGIN_AHEAD=$(git rev-list --count HEAD..origin/main)
LOCAL_HEAD_SHORT=$(git rev-parse --short HEAD)
ORIGIN_HEAD_SHORT=$(git rev-parse --short origin/main)

echo "    Local HEAD:   $LOCAL_HEAD_SHORT"
echo "    Origin HEAD:  $ORIGIN_HEAD_SHORT"
echo "    Local ahead by:   $LOCAL_AHEAD commit(s)"
echo "    Origin ahead by:  $ORIGIN_AHEAD commit(s)"

if [[ "$LOCAL_AHEAD" == "0" ]] && [[ "$ORIGIN_AHEAD" == "0" ]]; then
  echo ""
  echo "Already in sync with origin. Nothing to reconcile."
  exit 0
fi

# ---------------------------------------------------------------- Show plan

if [[ "$ORIGIN_AHEAD" != "0" ]]; then
  echo ""
  echo "==> Local commits to replay on top of origin/main"
  git log --oneline origin/main..HEAD

  echo ""
  echo "==> Origin commits to rebase onto"
  git log --oneline HEAD..origin/main

  REBASE_NEEDED=1
else
  echo ""
  echo "Origin has no new commits beyond local. Skipping rebase."
  REBASE_NEEDED=0
fi

# ---------------------------------------------------------------- Rebase

if [[ "$REBASE_NEEDED" == "1" ]]; then
  echo ""
  echo "==> Rebasing local onto origin/main"
  if ! git pull --rebase origin main; then
    echo ""
    echo "ERROR: rebase produced conflicts. Resolve manually:"
    echo "  1. git status                       # see conflicted files"
    echo "  2. edit conflicted files; keep both intents"
    echo "  3. git add <resolved files>"
    echo "  4. git rebase --continue"
    echo "  5. re-run this script (it will skip the rebase and run tests + push)"
    echo ""
    echo "Most likely conflict point:"
    echo "  crmbuilder-v2/src/crmbuilder_v2/ui/app.py"
    echo "    v0.5 slice A added the Engagements sidebar group container above"
    echo "    Governance; v0.6 slice A may be restyling the sidebar around the"
    echo "    same code region. Keep BOTH: the new group container AND the"
    echo "    styling retrofit. See ui-PRD-v0.5.md §9 for the coordination"
    echo "    posture and DEC-095/096/097 for v0.6's slice plan."
    echo ""
    echo "Secondary conflict points (lower likelihood):"
    echo "  crmbuilder-v2/src/crmbuilder_v2/ui/panels/sidebar.py"
    echo "  crmbuilder-v2/src/crmbuilder_v2/__init__.py (v0.6 may bump version)"
    exit 1
  fi
  echo "    rebase clean"
fi

# ---------------------------------------------------------- Post-rebase tests

echo ""
echo "==> Running v2 test suite (will take a few minutes)"
if ! ( cd crmbuilder-v2 && uv run pytest tests/crmbuilder_v2/ --tb=short -q ); then
  echo ""
  echo "ERROR: tests failed after rebase. Do NOT push."
  echo "  The rebase may have surfaced a v0.5 / v0.6 interaction. Investigate"
  echo "  with: cd crmbuilder-v2 && uv run pytest tests/crmbuilder_v2/ -v"
  echo "  Once fixed, re-run this script."
  exit 1
fi
echo "    tests pass"

# ---------------------------------------------------------------- Push

echo ""
echo "==> Pushing to origin/main"
git push origin main
echo "    push succeeded"

# ---------------------------------------------------------- Post-push verify

echo ""
echo "==> Verifying local and origin in sync"
git fetch origin main
LOCAL_HEAD=$(git rev-parse HEAD)
ORIGIN_HEAD=$(git rev-parse origin/main)
if [[ "$LOCAL_HEAD" == "$ORIGIN_HEAD" ]]; then
  echo "    in sync at $(git rev-parse --short HEAD)"
else
  echo "ERROR: local and origin disagree after push (unexpected race condition)"
  echo "  Local HEAD:  $LOCAL_HEAD"
  echo "  Origin HEAD: $ORIGIN_HEAD"
  exit 1
fi

echo ""
echo "Done. Divergence resolved."
