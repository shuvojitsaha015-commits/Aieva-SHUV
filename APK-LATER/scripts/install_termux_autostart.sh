#!/usr/bin/env bash
# Start Aieva with the board (Android / Termux).
#
#   ./scripts/install_termux_autostart.sh
#
# On an Android board there is no Windows task scheduler. Termux has its own
# ways to start a program when the board is switched on:
#
#   1. the systemd unit of the user (the best way - it restarts Aieva when
#      it crashes);
#   2. the boot service of Termux (``termux-boot``), for the boards where
#      systemd is not available.
#
# The unit is written to ~/.config/systemd/user/aieva.service and enabled.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${AIEVA_PYTHON:-python3}"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT_FILE="$UNIT_DIR/aieva.service"

echo "[aieva] the project: $PROJECT_DIR"

if ! command -v systemctl >/dev/null 2>&1; then
    echo "[aieva] systemd is not available in this Termux."
    echo "[aieva] use the boot service instead:"
    echo "        pkg install termux-boot"
    echo "        mkdir -p ~/.termux/boot"
    echo "        cp $PROJECT_DIR/scripts/termux_boot.sh ~/.termux/boot/aieva.sh"
    echo "        chmod +x ~/.termux/boot/aieva.sh"
    exit 0
fi

mkdir -p "$UNIT_DIR"

cat > "$UNIT_FILE" <<UNIT
[Unit]
Description=Aieva - the background service of the smart board
After=graphical-session.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$PYTHON -m aieva.core.service run --overlay
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
UNIT

echo "[aieva] the unit was written: $UNIT_FILE"
systemctl --user daemon-reload
systemctl --user enable --now aieva.service

echo ""
echo "[aieva] the board service is running. To see what it does:"
echo "        ./.venv/bin/python -m aieva.core.service status"
echo "[aieva] to stop it:"
echo "        systemctl --user stop aieva.service"
