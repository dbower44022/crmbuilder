#!/usr/bin/env bash
# Terminate whatever is serving the crmbuilder-v2 REST API on a port (default
# 8765) and restart it from the CURRENT checkout, so a stale pre-PI-β/γ process
# is replaced with current `main` code. Detached, logging to the rotating
# api.log. Verifies the new process answers with a post-PI-β `/admin/version`
# (a single `schema` block, not `engagement_schema`/`meta_schema`).
#
# Usage:
#   crmbuilder-v2/scripts/restart_api.sh            # restart on 8765
#   crmbuilder-v2/scripts/restart_api.sh 8766        # restart on 8766
set -euo pipefail

PORT="${1:-8765}"

# Resolve the repo root from this script's location (…/crmbuilder-v2/scripts).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

echo "==> Stopping anything on port ${PORT}…"
# fuser kills every process holding the TCP port (the uvicorn parent + workers).
if fuser -k "${PORT}/tcp" 2>/dev/null; then
  echo "    sent SIGKILL to listeners on ${PORT}"
else
  echo "    nothing was listening on ${PORT}"
fi

# Wait until the port is actually free (up to ~10s).
for _ in $(seq 1 20); do
  if ! fuser "${PORT}/tcp" >/dev/null 2>&1; then break; fi
  sleep 0.5
done

echo "==> Starting crmbuilder-v2-api on ${PORT} from $(git -C "${REPO_ROOT}" rev-parse --short HEAD)…"
# Detached so it survives this shell. api_port defaults to 8765; override via env
# for any other port. Application logs go to crmbuilder-v2/data/logs/api.log.
CRMBUILDER_V2_API_PORT="${PORT}" nohup uv run crmbuilder-v2-api \
  > "/tmp/crmbuilder-v2-api-${PORT}.out" 2>&1 &
NEW_PID=$!
echo "    started pid ${NEW_PID} (stdout: /tmp/crmbuilder-v2-api-${PORT}.out)"

echo "==> Waiting for readiness…"
VERSION=""
for _ in $(seq 1 30); do
  if VERSION="$(curl -s --max-time 2 "http://127.0.0.1:${PORT}/admin/version" 2>/dev/null)" \
     && [ -n "${VERSION}" ]; then
    break
  fi
  sleep 0.5
done

if [ -z "${VERSION}" ]; then
  echo "!! API did not answer on ${PORT} within ~15s. Last 20 stdout lines:"
  tail -20 "/tmp/crmbuilder-v2-api-${PORT}.out" || true
  exit 1
fi

echo "==> /admin/version:"
echo "    ${VERSION}"
if echo "${VERSION}" | grep -q '"engagement_schema"\|"meta_schema"'; then
  echo "!! WARNING: this still looks PRE-PI-β (engagement_schema/meta_schema present)."
  echo "   The checkout may be on an old commit — check 'git -C ${REPO_ROOT} log -1'."
  exit 2
fi
echo "==> OK: API on ${PORT} is serving current code (single 'schema' block)."
