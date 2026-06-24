#!/usr/bin/env bash
#
# scripts/install.sh
# Billiam OS — Automated Installation & Uninstallation Script
#
# Installs all dependencies, creates config directories,
# detects hardware capabilities, and sets up Billiam OS.
#
# Usage:
#   bash scripts/install.sh           # Install
#   bash scripts/install.sh --uninstall  # Remove Billiam OS
#   bash scripts/install.sh --help       # Show help
#
# Supported distributions:
#   - Arch Linux (pacman)
#   - Debian / Ubuntu (apt-get)
#   - Fedora (dnf)
#

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

BILLIAM_HOME="${XDG_CONFIG_HOME:-$HOME/.config}/billiam-os"
SERVICE_NAME="billiam-os.service"

# ── Package Manager Detection ────────────────────────────────────────────────
detect_package_manager() {
    if command -v pacman &>/dev/null; then
        echo "pacman"
    elif command -v apt-get &>/dev/null; then
        echo "apt-get"
    elif command -v dnf &>/dev/null; then
        echo "dnf"
    else
        echo "unsupported"
    fi
}

PACKAGE_MANAGER="$(detect_package_manager)"
SYSTEM_DEPS=()

case "$PACKAGE_MANAGER" in
    pacman)
        SYSTEM_DEPS=(
            "ffmpeg:ffmpeg"
            "espeak-ng:espeak-ng"
            "arecord:alsa-utils"
            "lspci:pciutils"
        )
        PKG_INSTALL="sudo pacman -S --noconfirm"
        PKG_QUERY="pacman -Qi"
        ;;
    apt-get)
        SYSTEM_DEPS=(
            "ffmpeg:ffmpeg"
            "espeak-ng:espeak-ng"
            "arecord:alsa-utils"
            "lspci:pciutils"
        )
        PKG_INSTALL="sudo apt-get install -y"
        PKG_QUERY="dpkg -l"
        ;;
    dnf)
        SYSTEM_DEPS=(
            "ffmpeg:ffmpeg"
            "espeak-ng:espeak-ng"
            "arecord:alsa-utils"
            "lspci:pciutils"
        )
        PKG_INSTALL="sudo dnf install -y"
        PKG_QUERY="rpm -q"
        ;;
    *)
        echo -e "${RED}Error: Unsupported Linux distribution.${NC}"
        echo ""
        echo "Billiam OS officially supports:"
        echo "  - Arch Linux (pacman)"
        echo "  - Debian / Ubuntu (apt-get)"
        echo "  - Fedora (dnf)"
        echo ""
        echo "For other distributions, please manually install:"
        echo "  - ffmpeg"
        echo "  - espeak-ng"
        echo "  - alsa-utils (arecord)"
        echo "  - pciutils (lspci)"
        echo "  - python3-pip"
        echo ""
        echo "Then run: pip install -r requirements.txt"
        exit 1
        ;;
esac

show_help() {
    echo "Billiam OS — Installation Script"
    echo ""
    echo "Usage: bash scripts/install.sh [OPTION]"
    echo ""
    echo "Options:"
    echo "  --help        Show this help message"
    echo "  --uninstall   Remove Billiam OS and its files"
    echo "  (no option)   Install Billiam OS"
    echo ""
    echo "Manual setup after install:"
    echo "  1. Start an LLM backend (llama.cpp, Ollama, etc.)"
    echo "  2. Run: billiam --voice"
    echo "  3. Or enable the systemd service: systemctl --user enable --now billiam-os.service"
    echo ""
    exit 0
}

# ── Uninstall ─────────────────────────────────────────────────────────────────
do_uninstall() {
    echo -e "${YELLOW}==> Uninstalling Billiam OS...${NC}"

    # Stop and disable systemd service
    if systemctl --user is-enabled "$SERVICE_NAME" &>/dev/null 2>&1; then
        echo -e "  ${YELLOW}→ Disabling systemd service...${NC}"
        systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
        systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
        echo -e "  ${GREEN}✓${NC} Service disabled"
    fi

    SERVICE_FILE="$HOME/.config/systemd/user/$SERVICE_NAME"
    if [ -f "$SERVICE_FILE" ]; then
        rm -f "$SERVICE_FILE"
        systemctl --user daemon-reload 2>/dev/null || true
        echo -e "  ${GREEN}✓${NC} Service file removed"
    fi

    # Remove config directory (ask first)
    if [ -d "$BILLIAM_HOME" ]; then
        echo -e "  ${YELLOW}→ Remove config directory $BILLIAM_HOME? [y/N]${NC}"
        read -r confirm
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            rm -rf "$BILLIAM_HOME"
            echo -e "  ${GREEN}✓${NC} Config directory removed"
        else
            echo -e "  ${YELLOW}⚠${NC} Config directory preserved at $BILLIAM_HOME"
        fi
    fi

    echo ""
    echo -e "${GREEN}Billiam OS uninstalled.${NC}"
    echo "Manual cleanup (optional):"
    echo "  rm -rf $PWD  # Remove the project directory"
    exit 0
}

# ── Parse arguments ───────────────────────────────────────────────────────────
if [ $# -gt 0 ]; then
    case "$1" in
        --help|-h) show_help ;;
        --uninstall|-u) do_uninstall ;;
        *) echo "Unknown option: $1"; echo "Usage: bash scripts/install.sh [--help|--uninstall]"; exit 1 ;;
    esac
fi

echo -e "${CYAN}"
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║     Billiam OS — Installation Script     ║"
echo "  ║  Your Personal Digital Butler for Linux   ║"
echo "  ╚═══════════════════════════════════════════╝"
echo -e "${NC}"

# ── Hardware Detection ───────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}==> Detecting hardware capabilities...${NC}"

TOTAL_RAM_MB=0
if [ -f /proc/meminfo ]; then
    TOTAL_RAM_MB=$(( $(grep MemTotal /proc/meminfo | awk '{print $2}') / 1024 ))
fi

CPU_VENDOR="unknown"
if grep -qi "intel" /proc/cpuinfo 2>/dev/null; then
    CPU_VENDOR="intel"
elif grep -qi "amd" /proc/cpuinfo 2>/dev/null; then
    CPU_VENDOR="amd"
fi

GPU_AVAILABLE="none"
if lspci 2>/dev/null | grep -qi "vga.*intel"; then
    GPU_AVAILABLE="intel"
elif lspci 2>/dev/null | grep -qi "vga.*amd\|vga.*advanced"; then
    GPU_AVAILABLE="amd"
elif lspci 2>/dev/null | grep -qi "vga.*nvidia"; then
    GPU_AVAILABLE="nvidia"
fi

HAS_OPENVINO=false
if command -v openvino_version &>/dev/null || ldconfig -p 2>/dev/null | grep -qi openvino; then
    HAS_OPENVINO=true
fi

echo "  RAM:       ${TOTAL_RAM_MB}MB $([ "$TOTAL_RAM_MB" -ge 16000 ] && echo '✓' || echo '(min 16GB recommended)')"
echo "  CPU:       $CPU_VENDOR ($(nproc) cores)"
echo "  GPU:       $GPU_AVAILABLE"
echo "  OpenVINO:  $HAS_OPENVINO"

if [ "$TOTAL_RAM_MB" -lt 8000 ]; then
    echo -e "${RED}  ⚠ Less than 8GB RAM detected. Billiam OS requires 16GB for smooth operation.${NC}"
    echo "  Continue anyway? [y/N]"
    read -r confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "Installation cancelled."
        exit 1
    fi
fi

# ── Step 1: Python dependencies ──────────────────────────────────────────────
echo ""
echo -e "${YELLOW}==> Step 1/5: Installing Python dependencies...${NC}"
pip install --quiet --upgrade pip 2>/dev/null || true
pip install --quiet -r requirements.txt 2>&1 | tail -2
pip install --quiet pyyaml 2>&1 | tail -1
echo -e "${GREEN}    Dependencies installed.${NC}"

# ── Step 2: System dependencies ──────────────────────────────────────────────
echo ""
echo -e "${YELLOW}==> Step 2/5: Checking system dependencies...${NC}"

for dep in "${SYSTEM_DEPS[@]}"; do
    CMD="${dep%%:*}"
    PKG="${dep##*:}"
    if command -v "$CMD" &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $CMD found"
    else
        echo -e "  ${YELLOW}⚠${NC} $CMD not found (install: $PKG_INSTALL $PKG)"
        echo -e "  ${YELLOW}  → Installing $PKG...${NC}"
        $PKG_INSTALL "$PKG" 2>&1 | tail -1
    fi
done

# ── Step 3: Create config directories ─────────────────────────────────────────
echo ""
echo -e "${YELLOW}==> Step 3/5: Creating configuration directories...${NC}"
mkdir -p "$BILLIAM_HOME"
mkdir -p "$BILLIAM_HOME"/logs

if [ ! -f "$BILLIAM_HOME/config.yaml" ]; then
    # Auto-configure based on hardware detection
    cat > "$BILLIAM_HOME/config.yaml" << YAMLEOF
# Billiam OS Configuration
# Auto-generated by install.sh on $(date -I)

billiam:
  name: Billiam
  wake_word: billiam
  polite_mode: true

llm:
  api_base: http://localhost:8080/v1
  model: qwen-2.5-coder-3b-instruct
  temperature: 0.2
  max_tokens: 512
  context_length: 4096

tts:
  enabled: true
  provider: edge-tts
  voice: en-GB-RyanNeural
  rate: "+0%"
  pitch: "+0Hz"
  fallback_provider: espeak-ng

stt:
  enabled: true
  model_size: base
  language: en
  wake_word_required: true
  device: cpu
  compute_type: int8

audio:
  input_device: null
  output_device: null
  sample_rate: 16000
  capture_timeout: 10

memory:
  storage_path: ~/.config/billiam-os/memory.json
  max_history: 100

logging:
  level: INFO
  file: ~/.config/billiam-os/billiam.log
  format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

security:
  banned_patterns: true
  require_privilege_confirmation: true
  max_command_timeout: 20
YAMLEOF
    echo -e "  ${GREEN}✓${NC} Default config created at $BILLIAM_HOME/config.yaml"
else
    echo -e "  ${GREEN}✓${NC} Config already exists at $BILLIAM_HOME/config.yaml"
fi

# Copy .env.example if it doesn't exist
if [ ! -f "$BILLIAM_HOME/.env" ] && [ -f .env.example ]; then
    cp .env.example "$BILLIAM_HOME/.env"
    echo -e "  ${GREEN}✓${NC} .env example copied to $BILLIAM_HOME/.env"
fi

# ── Step 4: Install systemd user service ──────────────────────────────────────
echo ""
echo -e "${YELLOW}==> Step 4/5: Installing systemd user service...${NC}"
SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"

if [ -f config/aios.service ]; then
    cp config/aios.service "$SERVICE_DIR/$SERVICE_NAME"
    echo -e "  ${GREEN}✓${NC} Service installed."
    echo -e "  ${YELLOW}  → Enable: systemctl --user enable $SERVICE_NAME"
    echo -e "  ${YELLOW}  → Start:  systemctl --user start $SERVICE_NAME"
    echo -e "  ${YELLOW}  → Status: systemctl --user status $SERVICE_NAME"
fi

# ── Step 5: Install hotkey scripts ────────────────────────────────────────────
echo ""
echo -e "${YELLOW}==> Step 5/5: Installing hotkey scripts...${NC}"
SCRIPT_DIR="$BILLIAM_HOME/scripts"
mkdir -p "$SCRIPT_DIR"

for script in scripts/hotkey.sh scripts/billiam-voice.sh; do
    if [ -f "$script" ]; then
        cp "$script" "$SCRIPT_DIR/"
        chmod +x "$SCRIPT_DIR/$(basename "$script")"
        echo -e "  ${GREEN}✓${NC} $(basename "$script") installed"
    fi
done

echo ""
echo -e "  ${YELLOW}  → For i3wm: bind \$mod+space exec $SCRIPT_DIR/hotkey.sh${NC}"
echo -e "  ${YELLOW}  → For Hyprland: bind = SUPER, SPACE, exec, $SCRIPT_DIR/hotkey.sh${NC}"
echo -e "  ${YELLOW}  → For voice trigger: bind = SUPER, V, exec, $SCRIPT_DIR/billiam-voice.sh${NC}"

# ── Verify ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}==> Verifying installation...${NC}"

cd "$(dirname "$0")/.." 2>/dev/null || true

python -c "
from core.billiam import BILLIAM_PROFILE
from core.memory import AssistantMemoryLayer
from core.sandbox import SecureExecutionSandbox
from core.config import load_config
import tempfile, os
d = tempfile.mkdtemp()
mp = os.path.join(d, 'mem.json')
from core.ai_core import AICore
c = AICore(memory_path=mp)
assert c.assistant_name == 'Billiam'
import shutil; shutil.rmtree(d)
print('  ✓ All core modules import correctly')
print('  ✓ Billiam OS ready')
" 2>&1 || {
    python -c "
from core.billiam import BILLIAM_PROFILE
from core.memory import AssistantMemoryLayer
from core.sandbox import SecureExecutionSandbox
from core.config import load_config
print('  ✓ All core modules import correctly')
"
}

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║      Billiam OS Installation Complete!    ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
echo ""
echo "  Quick start:"
echo "    billiam --once \"What's my hostname?\""
echo ""
echo "  Interactive mode with British butler voice:"
echo "    billiam --voice"
echo ""
echo "  Full daemon (voice + listening):"
echo "    billiam --daemon"
echo ""
echo "  First, start your LLM backend (see docs/architecture.md):"
echo "    bash scripts/setup_inference.sh"
echo ""
echo "  To uninstall:"
echo "    bash scripts/install.sh --uninstall"
echo ""
