#!/usr/bin/env bash
# Deploy latest code to the Pi: sudo /opt/sensor/update.sh
set -euo pipefail

INSTALL_DIR=/opt/sensor
SERVICE=sensor

echo "==> Pulling latest code"
git -C "$INSTALL_DIR" pull

echo "==> Updating dependencies"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

echo "==> Restarting service"
systemctl restart "$SERVICE"
systemctl status "$SERVICE" --no-pager -l

echo ""
echo "Done. Logs: journalctl -u $SERVICE -f"
