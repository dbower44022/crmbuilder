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
#   7. Publish check    — validate-only publish against CBMTEST (advisory)
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
say "1/7 Local preflight"
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
say "2/7 Remote preflight"
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
Rebuild the venv on the droplet first, then re-run. Recipe (LSN-072): copy the \
committed pyproject.toml + uv.lock to $DEST, then on the droplet run \
'cd $DEST && UV_PROJECT_ENVIRONMENT=$DEST/.venv uv sync --frozen' — build AT the \
final path; a venv staged under another name bakes that path into every console \
script's shebang and the service crash-loops with 203/EXEC after the rename."
fi
echo "    uv.lock unchanged — code-only deploy"

# --- 3. Copy the committed tree --------------------------------------------
say "3/7 Copy committed tree -> $HOST:$DEST"
# Exactly the git-tracked files: gitignored local files (crmbuilder-v2/data/,
# instance profiles, caches) are never sent; no --delete, so droplet-local
# files (.venv, backups/, logs) are never removed.
git ls-files -z | rsync -az --files-from=- --from0 . "$HOST:$DEST/" \
    || die "rsync failed"

# --- 4. Migrate (before serving) -------------------------------------------
say "4/7 Migrate the live store (alembic pg upgrade head)"
rssh "cd $DEST && $REMOTE_PY -m alembic -c $ALEMBIC_INI upgrade head" \
    || die "alembic upgrade failed — service NOT restarted; investigate before retrying"

# --- 5. Restart ------------------------------------------------------------
say "5/7 Restart $UNIT"
rssh "systemctl restart $UNIT" || die "systemctl restart failed"

# --- 6. Verify -------------------------------------------------------------
say "6/7 Verify"
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

# --- 7. Publish check ------------------------------------------------------
# A healthy /health says the process is serving. It says nothing about whether
# publishing still works, and publishing is what silently broke: the 2026-07-01
# cutover left it broken in three independent places for weeks because nothing
# exercised it after a deploy (REQ-483 / DEC-915). This is that exercise, run
# where it matters most — right after the change that could have broken it.
#
# Validate-only against CBMTEST: generates the design, resolves the target's
# credentials, reads the live target and validates, writing nothing. Production
# (INST-002) is refused by the check itself, by name.
#
# Advisory, not fatal. The deploy has already copied, migrated and restarted
# successfully by this point; aborting here would report a completed deploy as a
# failure and invite a rollback of a working system — the exact mistake REQ-480
# fixed one step above.
#
# Run from HERE, not on the droplet, for two reasons. The droplet's environment
# file holds no API token and the service runs with principal auth enabled, so a
# check invoked there could only ever report "cannot authenticate" — and issuing
# it a token would add a credential to rotate for the sake of a health check,
# which is the shape DEC-914 declined. This machine already has the token the
# desktop uses. Going through the public URL rather than the droplet's loopback
# also exercises Caddy and the auth middleware, which is the path a real caller
# takes.
#
# Invoked as a module rather than the console script so a venv that has not been
# reinstalled since this entry point was added still runs it.
say "7/7 Publish check (validate-only, writes nothing)"
LOCAL_PY="$(git rev-parse --show-toplevel)/.venv/bin/python"
[ -x "$LOCAL_PY" ] || LOCAL_PY="python3"
# --base-url pins the check to the public service (REQ-545 / PI-443): the
# check resolves flag > environment > env file, so an operator shell that
# exports a local dev URL would otherwise send it to a service that isn't
# running (observed 2026-08-31: "via http://127.0.0.1:8765 ... CANNOT RUN").
if "$LOCAL_PY" -m crmbuilder_v2.publish.check --base-url "$PUBLIC_URL"; then
    echo "    publish path: healthy"
else
    rc=$?
    if [ "$rc" = 2 ]; then
        printf '    WARNING: publish check could not run (exit 2) — deploy is fine, the check is not\n'
    else
        printf '    WARNING: PUBLISH CHECK FAILED (exit %s). The deploy succeeded; publishing did not.\n' "$rc"
        printf '             Investigate before relying on publish: crmbuilder-v2-publish-check\n'
    fi
fi

printf '\nDEPLOY OK: commit %s | %s | alembic %s | %s\n' \
    "$commit" "v$version" "$head_after" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
