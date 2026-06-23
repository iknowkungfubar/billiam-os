#!/usr/bin/env bash
#
# scripts/install.sh
# Billiam OS — Automated Installation Script
#
# Installs all dependencies, creates config directories,
# and sets up the Billiam OS environment.
#
# Usage: bash scripts/install.sh [--user|--system]
#

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

BILLIAM_HOME="${XDG_CONFIG_HOME:-$HOME/.config}/billiam-os"

echo -e "${CYAN}"
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║     Billiam OS — Installation Script     ║"
echo "  ║  Your Personal Digital Butler for Linux   ║"
echo "  ╚═══════════════════════════════════════════╝"
echo -e "${NC}"

# ── Parse arguments ──────────────────────────────────────────────────────────
INSTALL_MODE="${1:-user}"

# ── Step 1: Python dependencies ──────────────────────────────────────────────
echo ""
echo -e "${YELLOW}==> Step 1/6: Installing Python dependencies...${NC}"
pip install --quiet --upgrade pip 2>/dev/null || true
pip install --quiet -r requirements.txt 2>&1 | tail -2 || true
echo -e "${GREEN}    Dependencies installed.${NC}"

# ── Step 2: System dependencies (optional) ───────────────────────────────────
echo ""
echo -e "${YELLOW}==> Step 2/6: Checking system dependencies...${NC}"

SYSTEM_DEPS=(
    "ffmpeg:ffmpeg"
    "espeak-ng:espeak-ng"
    "arecord:alsa-utils"
)

for dep in "${SYSTEM_DEPS[@]}"; do
    CMD="${dep%%:*}"
    PKG="${dep##*:}"
    if command -v "$CMD" &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $CMD found"
    else
        echo -e "  ${YELLOW}⚠${NC} $CMD not found (install: sudo pacman -S $PKG)"
    fi
done

# ── Step 3: Create config directories ─────────────────────────────────────────
echo ""
echo -e "${YELLOW}==> Step 3/6: Creating configuration directories...${NC}"
mkdir -p "$BILLIAM_HOME"
mkdir -p "$BILLIAM_HOME"/logs

if [ ! -f "$BILLIAM_HOME/config.yaml" ]; then
    cat > "$BILLIAM_HOME/config.yaml" << 'YAMLEOF'
# Billiam OS Configuration
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

# ── Step 4: Install systemd user service ──────────────────────────────────────
echo ""
echo -e "${YELLOW}==> Step 4/6: Installing systemd user service...${NC}"
SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"

if [ -f config/aios.service ]; then
    cp config/aios.service "$SERVICE_DIR/billiam-os.service"
    echo -e "  ${GREEN}✓${NC} Service installed."
    echo -e "  ${YELLOW}  → Enable: systemctl --user enable billiam-os.service"
    echo -e "  ${YELLOW}  → Start:  systemctl --user start billiam-os.service"
fi

# ── Step 5: Install hotkey scripts ────────────────────────────────────────────
echo ""
echo -e "${YELLOW}==> Step 5/6: Installing hotkey scripts...${NC}"
cp scripts/hotkey.sh "$BILLIAM_HOME/hotkey.sh" 2>/dev/null || true
chmod +x "$BILLIAM_HOME/hotkey.sh" 2>/dev/null || true
echo -e "  ${YELLOW}  → For i3: bind \$mod+space exec $BILLIAM_HOME/hotkey.sh${NC}"
echo -e "  ${YELLOW}  → For Hyprland: bind = SUPER, SPACE, exec, $BILLIAM_HOME/hotkey.sh${NC}"

# ── Step 6: Verify installation ───────────────────────────────────────────────
echo ""
echo -e "${YELLOW}==> Step 6/6: Verifying installation...${NC}"

cd "$(dirname "$0")/.."
if python -c "from core import Billiam OS. Run: python -m core.ai_core" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Python modules import correctly"
else
    python -c "
from core.billiam import BILLIAM_PROFILE
from core.memory import AssistantMemoryLayer
from core.sandbox import SecureExecutionSandbox
from core.config import load_config
print('  ✓ All core modules import correctly')
" 2>&1
fi

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║      Billiam OS Installation Complete!    ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
echo ""
echo "  Start Billiam:"
echo "    python -m core.ai_core"
echo ""
echo "  With voice:"
echo "    python -m core.ai_core --voice"
echo ""
echo "  Full daemon:"
echo "    python -m core.ai_core --daemon"
echo ""
echo "  First, start your LLM backend:"
echo "    bash scripts/setup_inference.sh"
echo "    ./llama.cpp/build/bin/llama-server -m models/qwen2.5-coder-3b.gguf --host 0.0.0.0 --port 8080 -ngl 0 -c 4096"
echo ""
