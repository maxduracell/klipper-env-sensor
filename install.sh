#!/usr/bin/env bash
# install.sh - Automated installer for klipper-env-sensor
# SPDX-License-Identifier: GPL-3.0-or-later

set -e

# Visual formatting
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}==> Installing klipper-env-sensor...${NC}"

# 1. Resolve repository directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="${SCRIPT_DIR}"

# 2. Locate Klipper extras directory
KLIPPER_PATH="${HOME}/klipper"
EXTRAS_PATH="${KLIPPER_PATH}/klippy/extras"

if [ ! -d "${EXTRAS_PATH}" ]; then
    echo -e "${RED}[ERROR] Klipper installation not found at ${KLIPPER_PATH}${NC}"
    echo "Please ensure Klipper is installed in ${HOME}/klipper"
    exit 1
fi

TARGET_LINK="${EXTRAS_PATH}/env_sensor"

# 3. Stop Klipper service safely
echo "==> Stopping Klipper service..."
sudo systemctl stop klipper || true

# 4. Link package
echo "==> Symlinking env_sensor into Klipper extras..."
ln -sfn "${PACKAGE_DIR}" "${TARGET_LINK}"

# 5. Restart Klipper service
echo "==> Restarting Klipper service..."
sudo systemctl start klipper

echo -e "${GREEN}==> Installation complete!${NC}"
echo "You can now add [env_sensor <name>] sections to your printer.cfg."
