#!/usr/bin/env bash
# install.sh - Automated installer for klipper-env-sensor
# SPDX-License-Identifier: GPL-3.0-or-later

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}==> Installing klipper-env-sensor...${NC}"

# Resolve repository directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="${SCRIPT_DIR}"

# Allow custom Klipper path
KLIPPER_PATH="${HOME}/klipper"
if [ -n "$1" ]; then
    KLIPPER_PATH="$1"
fi

EXTRAS_PATH="${KLIPPER_PATH}/klippy/extras"

if [ ! -d "${EXTRAS_PATH}" ]; then
    echo -e "${RED}[ERROR] Klipper extras directory not found at:${NC}"
    echo "  ${EXTRAS_PATH}"
    echo
    echo "Usage: ./install.sh [path_to_klipper]"
    echo "Example: ./install.sh /home/pi/klipper"
    exit 1
fi

TARGET_LINK="${EXTRAS_PATH}/env_sensor"

# Stop Klipper (best effort)
echo "==> Stopping Klipper service (if running)..."
sudo systemctl stop klipper 2>/dev/null || true

# Create / update symlink (pointing directly to the python module subfolder)
# This prevents relative import errors inside Python.
if [ -d "${PACKAGE_DIR}/env_sensor" ]; then
    SOURCE_DIR="${PACKAGE_DIR}/env_sensor"
else
    SOURCE_DIR="${PACKAGE_DIR}"
fi

echo "==> Creating symlink: ${TARGET_LINK} -> ${SOURCE_DIR}"
ln -sfn "${SOURCE_DIR}" "${TARGET_LINK}"

# Verify
if [ -L "${TARGET_LINK}" ] && [ -d "${TARGET_LINK}" ]; then
    echo -e "${GREEN}==> Symlink created successfully.${NC}"
else
    echo -e "${RED}[ERROR] Failed to create symlink.${NC}"
    exit 1
fi

# Restart Klipper
echo "==> Starting Klipper service..."
sudo systemctl start klipper 2>/dev/null || {
    echo -e "${YELLOW}[WARNING] Could not restart klipper service automatically.${NC}"
    echo "Please restart Klipper manually."
}

echo
echo -e "${GREEN}==> Installation complete!${NC}"
echo
echo "Next steps:"
echo "  1. Add an [env_sensor ...] section to your printer.cfg"
echo "  2. Restart Klipper if it wasn't restarted automatically"
echo "  3. Check the logs for any errors"
