#!/usr/bin/env bash
# Production deploy for the CRMBuilder V2 API (REQ-477 / PI-398, DEC-909).
#
# HUMAN-RUN ONLY (GVR-240): production deploy is Doug's step. This script
# refuses to run without an interactive terminal and a typed confirmation,
# so no build or agent session can trigger it.
#
# What a deploy is on this system (established by the authorized inspection
# recorded in DEC-909): /opt/crmbuilder on the droplet is an rsync-deployed
# copy of this repo, installed editable into /opt/crmbuilder/.venv, served
# by the systemd unit crmbuilder-v2-api.service behind Caddy. Copying the
# committed tree, migrating the store, and restarting the unit is a
# complete deploy; there is no build step.
#
# Steps (each aborts loudly on failure):
#   1. Local preflight  — on main, clean tree, main == origin/main
#   2. Remote preflight — SSH up, service active, uv.lock unchanged
#   3. Copy             — rsync the committed tree (config never touched)
#   4. Migrate          — alembic (pg) upgrade head, before serving
#   5. Restart          — systemctl restart crmbuilder-v2-api
#   6. Verify           — service, health, public endpoint, migration head
set -euo pipefail

HOST="root@138.197.72.15"
DEST="/opt/crmbuilder"
UNIT="crmbuilder-v2-api"
PUBLIC_URL="https://api.crmbuilder.ai"
ALEMBIC_INI="crmbuilder-v2/migrations/pg/alembic.ini"
REMOTE_PY="$DEST/.venv/bin/python"

say()  { printf '\n==> %s\n' "$*"; }
die()  { printf 'DEPLOY ABORTED: %s\n' "$*" >&2; exit 1; }
rssh() { ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" "$@"; }

# Poll a check until it succeeds or the deadline passes (REQ-480 / PI-401).
#
# `systemctl is-active` reports a process active the moment it is spawned, which
# is before uvicorn binds its socket — so probing a network endpoint once,
# straight after a restart, tests timing rather than health. The 2026-08-08
# deploy aborted that way with production already healthy and fully migrated,
# which is the most dangerous shape of false alarm: it invites a re-run or a
# rollback of a working system. Same defect v1 fixed in `phase_verify`; this
# mirrors its backoff.
#
# Nothing is printed while waiting, so a check that passes first time leaves the
# output byte-identical to the single-probe version. Returns non-zero once the
# deadline passes, leaving the `|| die "<message>"` at each call site intact.
POLL_BACKOFF="1 1 2 2 3 3 5"
POLL_DEADLINE=60

poll_until() {
    local started elapsed waited=0
    started=$(date +%s)
    while true; do
        # `set -e` must not fire on an expected failed attempt.
        if "$@"; then return 0; fi
        elapsed=$(( $(date +%s) - started ))
        [ "$elapsed" -ge "$POLL_DEADLINE" ] && return 1
        # Walk the backoff, then hold at its last step.
        local i=0 step=5
        for s in $POLL_BACKOFF; do
            i=$((i + 1))
            if [ "$i" -gt "$waited" ]; then step=$s; break; fi
        done
        waited=$((waited + 1))
        sleep "$step"
    done
}

# --- Human gate (GVR-240) --------------------------------------------------
[ -t 0 ] && [ -t 1 ] || die "no interactive terminal — production deploy is human-run only (GVR-240)"
printf 'This deploys to PRODUCTION (%s).\nType exactly "deploy production" to continue: ' "$HOST"
read -r confirm
[ "$confirm" = "deploy production" ] || die "confirmation phrase not entered"

# --- 1. Local preflight ----------------------------------------------------
say "1/6 Local preflight"
cd "$(git rev-parse --show-toplevel)" || die "not inside the repository"
branch=$(git branch --show-current)
[ "$branch" = "main" ] || die "on branch '$branch' — deploys run from main only"
[ -z "$(git status --porcelain)" ] || die "working tree not clean — commit or stash first"
git fetch origin main --quiet || die "cannot fetch origin/main"
[ "$(git rev-parse main)" = "$(git rev-parse origin/main)" ] \
    || die "local main != origin/main — only reviewed, pushed code deploys"
commit=$(git rev-parse --short HEAD)
echo "    deploying commit $commit"

# --- 2. Remote preflight ---------------------------------------------------
say "2/6 Remote preflight"
rssh true || die "cannot reach $HOST over SSH"
[ "$(rssh systemctl is-active "$UNIT")" = "active" ] || die "$UNIT is not active on the droplet"
head_before=$(rssh "cd $DEST && $REMOTE_PY -m alembic -c $ALEMBIC_INI current 2>/dev/null | tail -1")
echo "    remote alembic: $head_before"
rssh "curl -sf -m 5 http://127.0.0.1:8765/health >/dev/null" || die "remote /health not ok before deploy"

# Dependency gate (DEC-909: fail loudly). The droplet venv has no pip/uv, so
# a uv.lock change cannot be applied in place — refuse rather than run new
# code on stale dependencies.
if ! rssh "cat $DEST/uv.lock" | diff -q - uv.lock >/dev/null 2>&1; then
    die "uv.lock differs from the deployed copy — dependencies changed. \
The droplet venv cannot be updated in place; rebuild it on the droplet first, then re-run."
fi
echo "    uv.lock unchanged — code-only deploy"

# --- 3. Copy the committed tree --------------------------------------------
say "3/6 Copy committed tree -> $HOST:$DEST"
# Exactly the git-tracked files: gitignored local files (crmbuilder-v2/data/,
# instance profiles, caches) are never sent; no --delete, so droplet-local
# files (.venv, backups/, logs) are never removed.
git ls-files -z | rsync -az --files-from=- --from0 . "$HOST:$DEST/" \
    || die "rsync failed"

# --- 4. Migrate (before serving) -------------------------------------------
say "4/6 Migrate the live store (alembic pg upgrade head)"
rssh "cd $DEST && $REMOTE_PY -m alembic -c $ALEMBIC_INI upgrade head" \
    || die "alembic upgrade failed — service NOT restarted; investigate before retrying"

# --- 5. Restart ------------------------------------------------------------
say "5/6 Restart $UNIT"
rssh "systemctl restart $UNIT" || die "systemctl restart failed"

# --- 6. Verify -------------------------------------------------------------
say "6/6 Verify"
for i in $(seq 1 15); do
    [ "$(rssh systemctl is-active "$UNIT" || true)" = "active" ] && break
    [ "$i" = 15 ] && die "$UNIT did not come back active after restart"
    sleep 2
done
echo "    service: active"
# Poll, don't race: the unit is "active" before uvicorn is listening (REQ-480).
poll_until rssh "curl -sf -m 5 http://127.0.0.1:8765/health >/dev/null" \
    || die "/health not ok after restart (waited ${POLL_DEADLINE}s)"
echo "    local /health: ok"
# Reachability first (the proxy can lag the app coming up), then read the version
# — so a slow proxy is waited out rather than reported as "not serving".
poll_until curl -sf -m 10 -o /dev/null "$PUBLIC_URL/" \
    || die "public endpoint $PUBLIC_URL not serving (waited ${POLL_DEADLINE}s)"
version=$(curl -sf -m 10 "$PUBLIC_URL/" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])') \
    || die "public endpoint $PUBLIC_URL served an unreadable response"
echo "    public endpoint: serving version $version"
head_after=$(rssh "cd $DEST && $REMOTE_PY -m alembic -c $ALEMBIC_INI current 2>/dev/null | tail -1")
heads=$(rssh "cd $DEST && $REMOTE_PY -m alembic -c $ALEMBIC_INI heads 2>/dev/null | tail -1")
case "$head_after" in
    "${heads%% *}"*) echo "    alembic: $head_after" ;;
    *) die "alembic current ($head_after) != head ($heads) after upgrade" ;;
esac

printf '\nDEPLOY OK: commit %s | %s | alembic %s | %s\n' \
    "$commit" "v$version" "$head_after" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
