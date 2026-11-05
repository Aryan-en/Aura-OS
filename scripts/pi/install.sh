#!/usr/bin/env bash
# ==============================================================================
# AURA OS — Raspberry Pi installer (Pi 3B+ "lite" and Pi 4/5 "full" profiles)
#
# Run on the Pi, as your normal user, from a clone of the repo:
#     sudo -v && bash scripts/pi/install.sh
# Result: on every boot the Pi starts the Aura daemon + HUD and shows it fullscreen on HDMI.
#
# Needs: Raspberry Pi OS Lite 64-bit (Bookworm or newer), internet.
# Env overrides: AURA_PROFILE=lite|full  AURA_KIOSK=0 (skip display stack)  AURA_OUTPUT_DEVICE=plughw:0,1
# ==============================================================================
set -euo pipefail

CYAN="\033[0;36m"; GREEN="\033[0;32m"; YELLOW="\033[0;33m"; RED="\033[0;31m"; RESET="\033[0m"
info() { echo -e "${CYAN}[aura]${RESET} $*"; }
ok()   { echo -e "${GREEN}[aura] ✓${RESET} $*"; }
warn() { echo -e "${YELLOW}[aura] ⚠${RESET} $*"; }
die()  { echo -e "${RED}[aura] ✗${RESET} $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] && die "Run as your normal user (it will call sudo itself), not as root."
case "$(uname -m)" in aarch64|arm64) ;; *) die "64-bit OS required (got $(uname -m)). Flash 'Raspberry Pi OS Lite (64-bit)'." ;; esac
command -v apt-get >/dev/null || die "This installer supports Debian-based systems (Raspberry Pi OS)."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
AURA_USER="$(id -un)"
AURA_HOME="$HOME"
AURA_UID="$(id -u)"
cd "$ROOT"

MODEL="$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo unknown)"
RAM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
PROFILE="${AURA_PROFILE:-}"
if [[ -z "$PROFILE" ]]; then
  if [[ "$MODEL" == *"Raspberry Pi 3"* || "$RAM_MB" -lt 3000 ]]; then PROFILE=lite; else PROFILE=full; fi
fi
info "Board: $MODEL | RAM: ${RAM_MB} MB | profile: $PROFILE"
[[ "$PROFILE" == lite && "$RAM_MB" -lt 1500 ]] && warn "1 GB board: using the cloud-assisted lite profile (needs internet + Gemini key)."

# ---- 1. system packages -------------------------------------------------------
info "Installing system packages..."
sudo apt-get update -y
PKGS=(python3 python3-venv python3-pip alsa-utils espeak-ng sox bubblewrap git curl)
if [[ "${AURA_KIOSK:-1}" == 1 ]]; then
  CHROMIUM=chromium; apt-cache show chromium >/dev/null 2>&1 || CHROMIUM=chromium-browser
  PKGS+=(cage "$CHROMIUM" fonts-noto-color-emoji fonts-dejavu-core seatd)
fi
[[ "$PROFILE" == full ]] && PKGS+=(pipewire wireplumber v4l-utils libgl1 libglib2.0-0 python3-dev build-essential)
sudo apt-get install -y --no-install-recommends "${PKGS[@]}"
ok "Packages installed."

# ---- 2. python environment ------------------------------------------------------
info "Creating Python environment..."
python3 -m venv --system-site-packages "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install --upgrade pip wheel >/dev/null
EXTRA=""; [[ "$PROFILE" == full ]] && EXTRA="[rpi]"
"$ROOT/.venv/bin/pip" install -e ".${EXTRA}"
ok "Aura installed ($PROFILE profile)."

# ---- 3. config + secrets --------------------------------------------------------
mkdir -p "$AURA_HOME/.config/aura"; chmod 700 "$AURA_HOME/.config/aura"
CFG="$AURA_HOME/.config/aura/aura.yaml"
if [[ ! -f "$CFG" ]]; then
  cp "$ROOT/config/$([[ $PROFILE == lite ]] && echo rpi3 || echo rpi5).yaml" "$CFG"
  if [[ -n "${AURA_OUTPUT_DEVICE:-}" ]]; then
    "$ROOT/.venv/bin/python" - "$CFG" "$AURA_OUTPUT_DEVICE" <<'PY'
import sys, yaml
p, dev = sys.argv[1:]
c = yaml.safe_load(open(p)); c.setdefault("voice", {})["output_device"] = dev
yaml.safe_dump(c, open(p, "w"))
PY
  fi
  ok "Config written to $CFG"
fi
SECRETS="$AURA_HOME/.config/aura/secrets.env"
if [[ ! -f "$SECRETS" ]]; then
  if [[ -t 0 ]]; then
    read -r -p "Gemini API key (https://aistudio.google.com/apikey) — Enter to skip: " KEY || KEY=""
  else KEY=""; fi
  umask 077; echo "GEMINI_API_KEY=${KEY}" > "$SECRETS"
  [[ -z "$KEY" ]] && warn "No key set: Aura will only understand built-in device commands. Add it later in $SECRETS or in HUD > Settings."
fi

# ---- 4. permissions -------------------------------------------------------------
for g in audio video input render; do getent group "$g" >/dev/null && sudo usermod -aG "$g" "$AURA_USER"; done

# ---- 5. systemd units -----------------------------------------------------------
info "Installing services..."
for unit in aura-core aura-ui $([[ "${AURA_KIOSK:-1}" == 1 ]] && echo aura-kiosk); do
  sed -e "s|@USER@|$AURA_USER|g" -e "s|@HOME@|$AURA_HOME|g" -e "s|@ROOT@|$ROOT|g" -e "s|@UID@|$AURA_UID|g" \
      -e "s|@CHROMIUM@|$(command -v chromium || command -v chromium-browser || echo chromium)|g" \
      "$ROOT/services/systemd/$unit.service" | sudo tee "/etc/systemd/system/$unit.service" >/dev/null
done
# Allow the daemon (and only it) to reboot/power off for the "shut down" voice command.
echo "$AURA_USER ALL=(root) NOPASSWD: /usr/bin/systemctl reboot, /usr/bin/systemctl poweroff" \
  | sudo tee /etc/sudoers.d/aura-power >/dev/null
sudo chmod 440 /etc/sudoers.d/aura-power
sudo visudo -cf /etc/sudoers.d/aura-power >/dev/null || { sudo rm -f /etc/sudoers.d/aura-power; warn "sudoers rule rejected; power voice commands disabled."; }
sudo systemctl daemon-reload
sudo systemctl enable aura-core aura-ui
if [[ "${AURA_KIOSK:-1}" == 1 ]]; then
  sudo systemctl enable seatd 2>/dev/null || true
  sudo systemctl enable aura-kiosk
  sudo systemctl set-default graphical.target   # kiosk unit owns tty1; no desktop is installed
  # Chromium needs a GPU-less-friendly tmp and the tty must not run a login prompt
  sudo systemctl disable getty@tty1.service 2>/dev/null || true
fi

# ---- 6. swap safety net for 1 GB boards ----------------------------------------
if [[ "$RAM_MB" -lt 1500 ]] && ! swapon --show | grep -q .; then
  sudo apt-get install -y systemd-zram-generator 2>/dev/null && ok "zram swap enabled." || warn "Could not enable zram."
fi

echo
ok "Done. Reboot to start Aura on the HDMI display:   sudo reboot"
echo "   Voice: say \"Aura\" (or \"Hey Jarvis\" with openWakeWord) then a command."
echo "   Diagnostics: $ROOT/.venv/bin/python scripts/pi/doctor.py"
