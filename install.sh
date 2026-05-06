#!/usr/bin/env bash
# Run once on the Pi as root: sudo bash install.sh <repo-url>
# Example: sudo bash install.sh https://github.com/you/sensor.git
set -euo pipefail

REPO_URL="${1:-}"
INSTALL_DIR=/opt/sensor
SERVICE=sensor

if [[ -z "$REPO_URL" ]]; then
  echo "Usage: sudo bash install.sh <repo-url>"
  exit 1
fi

echo "==> Installing system packages"
apt-get update -qq
apt-get install -y git bluetooth bluez python3 python3-pip python3-venv

echo "==> Cloning repository"
if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "    Repo already present — pulling latest instead"
  git -C "$INSTALL_DIR" pull
else
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

echo "==> Creating Python virtualenv"
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

if [[ ! -f "$INSTALL_DIR/config.yaml" ]]; then
  cp "$INSTALL_DIR/config.example.yaml" "$INSTALL_DIR/config.yaml"
  echo ""
  echo "  !! Created $INSTALL_DIR/config.yaml from template."
  echo "  !! Edit it with your device MACs and API endpoints before starting."
fi

chmod +x "$INSTALL_DIR/update.sh"

echo "==> Installing systemd service"
cp "$INSTALL_DIR/systemd/sensor.service" /etc/systemd/system/"$SERVICE".service
systemctl daemon-reload
systemctl enable "$SERVICE"

echo ""
echo "Done. Next steps:"
echo ""
echo "  1. Pair your devices:"
echo "       bluetoothctl"
echo "       [bluetooth]# power on"
echo "       [bluetooth]# agent on"
echo "       [bluetooth]# scan on"
echo "       [bluetooth]# pair AA:BB:CC:DD:EE:FF"
echo "       [bluetooth]# trust AA:BB:CC:DD:EE:FF"
echo "       [bluetooth]# quit"
echo ""
echo "  2. Find paired MACs:   bluetoothctl paired-devices"
echo "  3. Edit config:        nano $INSTALL_DIR/config.yaml"
echo "  4. Start:              systemctl start $SERVICE"
echo "  5. Logs:               journalctl -u $SERVICE -f"
echo "  6. Future updates:     sudo $INSTALL_DIR/update.sh"
