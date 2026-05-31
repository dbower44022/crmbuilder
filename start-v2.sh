#!/usr/bin/env bash
#
# start-v2.sh — launch the CRMBuilder v2 desktop UI (which owns the API).
#
# The desktop UI spawns the REST API on 127.0.0.1:8765, crash-monitors it,
# and auto-restarts it on connection loss (PI-110 / DEC-333). This is the
# most robust workflow, so the default just launches the UI.
#
# Usage:
#   ./start-v2.sh          # launch the UI (it spawns + supervises the API)
#   ./start-v2.sh api      # launch ONLY the standalone API in the foreground
#   ./start-v2.sh both     # launch the API in the background, then the UI
#
# API logs (rotating) land at: crmbuilder-v2/data/logs/api.log

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

MODE="${1:-ui}"

case "$MODE" in
  ui)
    echo "Launching v2 desktop UI (it will spawn and supervise the API)..."
    exec uv run crmbuilder-v2-ui
    ;;

  api)
    echo "Launching standalone v2 API on 127.0.0.1:8765 (Ctrl-C to stop)..."
    echo "Logs: $REPO_ROOT/crmbuilder-v2/data/logs/api.log"
    exec uv run crmbuilder-v2-api
    ;;

  both)
    echo "Starting standalone v2 API in the background..."
    uv run crmbuilder-v2-api &
    API_PID=$!
    echo "API PID: $API_PID — logs at $REPO_ROOT/crmbuilder-v2/data/logs/api.log"

    # Wait for the API to answer /health before launching the UI.
    echo -n "Waiting for API to come up"
    for _ in $(seq 1 30); do
      if curl -fsS http://127.0.0.1:8765/health >/dev/null 2>&1; then
        echo " — ready."
        break
      fi
      echo -n "."
      sleep 1
    done

    # Stop the background API when the UI exits.
    trap 'echo; echo "Shutting down API ($API_PID)..."; kill "$API_PID" 2>/dev/null || true' EXIT

    echo "Launching v2 desktop UI (will use the external API on 8765)..."
    uv run crmbuilder-v2-ui
    ;;

  *)
    echo "Unknown mode: $MODE" >&2
    echo "Usage: $0 [ui|api|both]" >&2
    exit 1
    ;;
esac
