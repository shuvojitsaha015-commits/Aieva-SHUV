#!/usr/bin/env bash
# Run the whole test suite headless.
#
# Starts a virtual X server (Xvfb) when no DISPLAY is available so that the Kivy
# UI tests can create a window.
set -euo pipefail

cd "$(dirname "$0")/.."

export MPLBACKEND=Agg
export KIVY_NO_ARGS=1

XVFB_PID=""
cleanup() {
  if [ -n "${XVFB_PID}" ]; then
    kill "${XVFB_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if [ -z "${DISPLAY:-}" ]; then
  if command -v Xvfb >/dev/null 2>&1; then
    DISPLAY_NUM=":99"
    Xvfb "${DISPLAY_NUM}" -screen 0 1280x720x24 >/dev/null 2>&1 &
    XVFB_PID=$!
    export DISPLAY="${DISPLAY_NUM}"
    sleep 1
  else
    echo "[aieva] No DISPLAY and no Xvfb - UI tests will be skipped."
  fi
fi

python -m pytest "$@"
