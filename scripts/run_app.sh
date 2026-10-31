#!/usr/bin/env bash
# Start the Aieva Kivy application.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

exec python -m aieva.ui.app "$@"
