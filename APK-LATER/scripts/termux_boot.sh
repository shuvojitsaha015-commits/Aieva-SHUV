#!/usr/bin/env bash
# Aieva - the boot script of the board (Termux).
#
# The file belongs into ~/.termux/boot/ - Termux runs it when the board is
# switched on. It starts the background service of the board, so nothing has
# to be typed in the morning.
#
#     mkdir -p ~/.termux/boot
#     cp scripts/termux_boot.sh ~/.termux/boot/aieva.sh
#     chmod +x ~/.termux/boot/aieva.sh
set -u

PROJECT_DIR="${AIEVA_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
PYTHON="${AIEVA_PYTHON:-$PROJECT_DIR/.venv/bin/python}"

cd "$PROJECT_DIR" || exit 1

# The service writes its log into a file - the board has no terminal.
exec "$PYTHON" -m aieva.core.service run --overlay >> "$PROJECT_DIR/aieva.log" 2>&1
