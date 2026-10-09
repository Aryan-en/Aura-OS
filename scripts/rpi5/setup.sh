#!/usr/bin/env bash
# ==============================================================================
# AURA OS — Automated Raspberry Pi 5 Provisioning & Installation Script
# Target: Raspberry Pi 5 (ARM64 / aarch64) running Raspberry Pi OS or Ubuntu 24.04
# ==============================================================================

set -euo pipefail

# Visual formatting
BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
CYAN="\033[0;36m"
RED="\033[0;31m"
RESET="\033[0m"

log_info() {
    echo -e "${CYAN}[AURA PI-SETUP]${RESET} $1"
}

log_success() {
    echo -e "${GREEN}[AURA PI-SETUP] ✓${RESET} $1"
}

log_warn() {
    echo -e "${YELLOW}[AURA PI-SETUP] ⚠${RESET} $1"
}

log_error() {
    echo -e "${RED}[AURA PI-SETUP] ✗${RESET} $1" >&2
}

echo -e "${BOLD}"
echo "=========================================================="
echo "          AURA OS — Raspberry Pi 5 Installation           "
echo "  Autonomous Unified Runtime Architecture for Ambient AI  "
echo "=========================================================="
echo -e "${RESET}"

# 1. Architecture Validation
ARCH=$(uname -m)
log_info "Verifying hardware architecture: ${ARCH}"
if [[ "${ARCH}" != "aarch64" && "${ARCH}" != "arm64" ]]; then
    log_error "Aura OS on Raspberry Pi requires a 64-bit ARM architecture (aarch64/arm64). Detected: ${ARCH}"
    log_error "Please ensure you have flashed a 64-bit OS image (Raspberry Pi OS 64-bit or Ubuntu 24.04 ARM64)."
    exit 1
fi
log_success "64-bit ARM architecture confirmed (${ARCH})."

# 2. Check Device Tree Model if available
if [[ -f "/proc/device-tree/model" ]]; then
    BOARD_MODEL=$(tr -d '\0' < /proc/device-tree/model)
    log_info "Detected Hardware: ${BOARD_MODEL}"
else
    log_info "Running on ARM64 Linux host."
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"

# 3. System Apt Dependencies
log_info "Installing system prerequisite packages via apt..."
if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -y
    sudo apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        build-essential \
        git \
        curl \
        jq \
        sqlite3 \
        bubblewrap \
        libasound2-dev \
        portaudio19-dev \
        alsa-utils \
        pipewire \
        pipewire-pulse \
        wireplumber \
        v4l-utils \
        libgl1 \
        libglib2.0-0
    log_success "System apt packages successfully installed."
else
    log_warn "apt-get not found. Skipping deb package installation. Ensure PipeWire, Bubblewrap, and build tools are present."
fi

# 4. User Group Permissions
CURRENT_USER=$(whoami)
log_info "Configuring hardware permissions for user: ${CURRENT_USER}..."
for grp in audio video input; do
    if getent group "${grp}" >/dev/null 2>&1; then
        sudo usermod -aG "${grp}" "${CURRENT_USER}" || true
    fi
done
log_success "User groups configured (audio, video, input)."

# 5. PipeWire Audio Subsystem Initialization
log_info "Ensuring PipeWire user services are active..."
systemctl --user enable --now pipewire wireplumber || {
    log_warn "Could not enable user pipewire service immediately. Verify in active desktop session."
}
log_success "PipeWire service configured."

# 6. Enable systemd user lingering (allows services to run headless without active SSH)
log_info "Enabling systemd linger for ${CURRENT_USER}..."
if command -v loginctl >/dev/null 2>&1; then
    sudo loginctl enable-linger "${CURRENT_USER}" || true
    log_success "Systemd linger enabled (daemons will persist headless)."
fi

# 7. Virtual Environment Setup
VENV_DIR="${PROJECT_ROOT}/.venv"
log_info "Setting up Python virtual environment in ${VENV_DIR}..."
if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv --system-site-packages "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"
python3 -m pip install --upgrade pip setuptools wheel

# 8. Install Aura-OS with Raspberry Pi optimizations
log_info "Installing Aura-OS Python packages with Raspberry Pi dependencies..."
python3 -m pip install -e ".[dev,rpi]"
log_success "Aura-OS installed into virtual environment."

# 9. Verify Tests
log_info "Running test suite to verify installation..."
pytest tests/unit/ -v

# 10. Install Systemd User Services
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
mkdir -p "${SYSTEMD_USER_DIR}"

log_info "Deploying systemd service units to ${SYSTEMD_USER_DIR}..."
cp "${PROJECT_ROOT}/services/systemd/aura-core.service" "${SYSTEMD_USER_DIR}/"
cp "${PROJECT_ROOT}/services/systemd/aura-ui.service" "${SYSTEMD_USER_DIR}/"

# Replace %h if necessary or rely on systemd %h expansion
systemctl --user daemon-reload
log_success "Systemd user services installed."

echo -e "\n${GREEN}${BOLD}=========================================================="
echo "          AURA OS Provisioning Complete!                  "
echo "==========================================================${RESET}"
echo -e "Next steps on Raspberry Pi 5:"
echo -e "  1. Test hardware & devices:   ${CYAN}python3 scripts/rpi5/test_hardware.py${RESET}"
echo -e "  2. Start core daemon:         ${CYAN}systemctl --user start aura-core${RESET}"
echo -e "  3. Start desktop Web HUD:     ${CYAN}systemctl --user start aura-ui${RESET}"
echo -e "  4. Check daemon status:       ${CYAN}aura status${RESET} or ${CYAN}systemctl --user status aura-core${RESET}"
echo -e "  5. Enable on boot:            ${CYAN}systemctl --user enable aura-core aura-ui${RESET}"
echo -e "  6. Access HUD from browser:   ${CYAN}http://<raspberry-pi-ip>:8765${RESET}\n"
