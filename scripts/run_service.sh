#!/usr/bin/env bash
# Start the Aieva background service (Linux / macOS / Termux on a board).
#
#   ./scripts/run_service.sh
#   ./scripts/run_service.sh --overlay
#
# The service watches the board in the background, reads what is written
# there, solves it and draws the graph.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="python3"
fi

exec "$PYTHON" -m aieva.core.service run "$@"
