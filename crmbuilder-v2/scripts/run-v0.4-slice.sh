#!/usr/bin/env bash
#
# run-v0.4-slice.sh — launch Claude Code with a v0.4 build prompt as the
# operating prompt for the conversation.
#
# Usage:
#   ./crmbuilder-v2/scripts/run-v0.4-slice.sh <slice-letter>
#   slice-letter: A | B | C | D | E | F
#
# Example:
#   ./crmbuilder-v2/scripts/run-v0.4-slice.sh B
#
# The script:
#   1. Validates the slice letter and resolves the prompt path.
#   2. Pre-flights repo state: on main, clean tree, pulled.
#   3. Launches `claude` interactively with a short instruction that tells
#      Claude Code to read the prompt file from disk and execute it. The
#      prompt itself is not passed on the command line — Claude Code reads
#      it with its `view` tool — which avoids shell quoting issues with
#      multi-page markdown and keeps the command-line argument small.
#
# Notes:
#   - Slice A (foundation) was executed 05-14-26 (SES-019 if backfilled in
#     order; otherwise whatever SES is next). The script still maps A →
#     foundation for the rare case slice A needs re-running.
#   - The historical `A-ses-011-closeout.md` prompt is NOT mapped here. It
#     was executed in May 2026 to close out SES-011 and is not part of the
#     v0.4 build sequence.
#   - The script does not write session records. Per the F-closeout prompt
#     step 2, Doug writes session records through the desktop New Session
#     dialog at the close of each Claude Code execution conversation.

set -euo pipefail

SLICE="${1:-}"
if [[ -z "$SLICE" ]]; then
  cat >&2 <<EOF
Usage: $0 <slice-letter>
  slice-letter: A | B | C | D | E | F

Slices:
  A — foundation (vocab, refs CHECK migration, sidebar group, retrofits)
  B — domains-panel
  C — entities-panel
  D — processes-panel
  E — crm-candidates-panel
  F — closeout (version bump, README, regression pass, smoke)
EOF
  exit 64
fi

case "$SLICE" in
  A|a) SLICE="A"; NAME="foundation" ;;
  B|b) SLICE="B"; NAME="domains-panel" ;;
  C|c) SLICE="C"; NAME="entities-panel" ;;
  D|d) SLICE="D"; NAME="processes-panel" ;;
  E|e) SLICE="E"; NAME="crm-candidates-panel" ;;
  F|f) SLICE="F"; NAME="closeout" ;;
  *)
    echo "Error: unknown slice '$SLICE'. Must be one of: A, B, C, D, E, F." >&2
    exit 64
    ;;
esac

# Resolve repo root from this script's location (script lives at
# <root>/crmbuilder-v2/scripts/run-v0.4-slice.sh).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

PROMPT_REL="PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.4-${SLICE}-${NAME}.md"
PROMPT_ABS="$REPO_ROOT/$PROMPT_REL"

if [[ ! -f "$PROMPT_ABS" ]]; then
  echo "Error: prompt file not found:" >&2
  echo "  $PROMPT_ABS" >&2
  exit 66
fi

# Pre-flight: claude executable in PATH
if ! command -v claude >/dev/null 2>&1; then
  echo "Error: 'claude' command not found in PATH." >&2
  echo "Install Claude Code per https://docs.claude.com/en/docs/claude-code/installation" >&2
  exit 127
fi

# Pre-flight: branch
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "main" ]]; then
  echo "Warning: not on main (currently on '$BRANCH')."
  read -r -p "Continue anyway? (y/N) " ans
  [[ "$ans" =~ ^[Yy]$ ]] || exit 1
fi

# Pre-flight: clean tree
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Warning: uncommitted changes present. Slice prompts assume a clean tree."
  git status --short
  read -r -p "Continue anyway? (y/N) " ans
  [[ "$ans" =~ ^[Yy]$ ]] || exit 1
fi

# Pre-flight: pull latest
echo "→ git pull --rebase origin main"
git pull --rebase origin main

# Build the initial-message instruction. Small command-line argument; the
# prompt itself is read from disk by Claude Code's own tools.
INITIAL_MESSAGE="Read the file at \`${PROMPT_REL}\` and execute it as your operating prompt for this conversation. It contains the full v0.4 slice ${SLICE} build instructions. Follow the prompt's reading order, pre-flight checks, and step sequence. Do not summarize the prompt back to me — execute it. Report progress and findings as you go."

echo ""
echo "→ Launching Claude Code with slice ${SLICE} (${NAME})"
echo "→ Prompt: ${PROMPT_REL}"
echo ""

# exec replaces this shell with claude, so the interactive session inherits
# the terminal cleanly.
exec claude "$INITIAL_MESSAGE"
