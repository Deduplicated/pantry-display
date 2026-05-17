#!/bin/bash
# Install systemd service + daily refresh timer for Pantry Display.
# Run from the project root on the Pi:  bash deploy/install-services.sh

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo:  sudo bash deploy/install-services.sh"
  exit 1
fi

sed "s|/home/pi/pantry-display|${ROOT}|g" "${ROOT}/deploy/pantry-display.service" \
  > /etc/systemd/system/pantry-display.service
sed "s|/home/pi/pantry-display|${ROOT}|g" "${ROOT}/deploy/pantry-refresh.service" \
  > /etc/systemd/system/pantry-refresh.service
cp "${ROOT}/deploy/pantry-refresh.timer" /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now pantry-display.service
systemctl enable --now pantry-refresh.timer

echo "Done. Status:"
systemctl status pantry-display.service --no-pager || true
systemctl list-timers pantry-refresh.timer --no-pager
