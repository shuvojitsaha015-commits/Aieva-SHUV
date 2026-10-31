#!/usr/bin/env bash
# Start the Aieva fog/cloud server (FastAPI + uvicorn).
#
#   ./scripts/run_server.sh              # mock mode when no GEMINI_API_KEY is set
#   AIEVA_MOCK_LLM=false ./scripts/run_server.sh
set -euo pipefail

cd "$(dirname "$0")/.."

HOST="${AIEVA_SERVER_HOST:-0.0.0.0}"
PORT="${AIEVA_SERVER_PORT:-8000}"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if [ -z "${GEMINI_API_KEY:-}" ] && [ "${AIEVA_MOCK_LLM:-false}" != "true" ]; then
  echo "[aieva] No GEMINI_API_KEY found -> starting in MOCK mode (canned answers)."
  export AIEVA_MOCK_LLM=true
fi

echo "[aieva] server listening on http://${HOST}:${PORT}  (docs: /docs, health: /health)"
exec uvicorn server.main:app --host "${HOST}" --port "${PORT}" "$@"
