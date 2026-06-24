#!/usr/bin/env bash
#
# scripts/install-ubuntu.sh
# Billiam OS — Ubuntu/Debian Install Helper
#
# Installs system dependencies for Debian/Ubuntu-based distributions.
# Run this before pip install.
#
# Usage:
#   bash scripts/install-ubuntu.sh
#

set -euo pipefail

echo "📦 Billiam OS — Ubuntu/Debian System Dependency Install"
echo "========================================================"
echo ""

if ! command -v apt-get &>/dev/null; then
    echo "❌ This script is for Debian/Ubuntu-based systems (apt-get not found)."
    exit 1
fi

echo "==> Updating package lists..."
sudo apt-get update -qq

echo ""
echo "==> Installing build dependencies (needed by faster-whisper)..."
sudo apt-get install -y \
    build-essential \
    cmake \
    cython3

echo ""
echo "==> Installing Billiam OS system dependencies..."
sudo apt-get install -y \
    espeak-ng \
    ffmpeg \
    alsa-utils \
    python3-pip \
    pciutils

echo ""
echo "==> Installing Piper TTS (offline neural TTS)..."
if command -v piper &>/dev/null; then
    echo "  ✓ piper already installed"
elif apt-cache show piper-tts &>/dev/null 2>&1; then
    echo "  → Installing piper-tts from apt..."
    sudo apt-get install -y piper-tts
else
    echo "  → piper-tts not in apt. Downloading static binary..."
    PIPER_VERSION="2023.11.14-2"
    PIPER_URL="https://github.com/rhasspy/piper/releases/download/v${PIPER_VERSION}/piper_linux_x86_64.tar.gz"
    PIPER_TMP="/tmp/piper-tts"
    mkdir -p "$PIPER_TMP"
    wget -q --show-progress "$PIPER_URL" -O "$PIPER_TMP/piper.tar.gz" || {
        echo "  ⚠ Failed to download Piper static binary."
        echo "    Install manually: https://github.com/rhasspy/piper/releases"
    }
    if [ -f "$PIPER_TMP/piper.tar.gz" ]; then
        tar -xzf "$PIPER_TMP/piper.tar.gz" -C "$PIPER_TMP"
        # Install system-wide or user-local
        if [ -d /usr/local/bin ]; then
            sudo cp "$PIPER_TMP/piper/piper" /usr/local/bin/piper 2>/dev/null || true
        fi
        if ! command -v piper &>/dev/null; then
            mkdir -p "$HOME/.local/bin"
            cp "$PIPER_TMP/piper/piper" "$HOME/.local/bin/piper" 2>/dev/null || true
        fi
        rm -rf "$PIPER_TMP"
        if command -v piper &>/dev/null; then
            echo "  ✓ piper installed from static binary"
        else
            echo "  ⚠ piper binary copied — add ~/.local/bin to PATH"
        fi
    fi
fi

echo ""
echo "==> Verifying installation..."
for cmd in ffmpeg espeak-ng arecord lspci pip3; do
    if command -v "$cmd" &>/dev/null; then
        echo "  ✓ $cmd found"
    else
        echo "  ⚠ $cmd not found"
    fi
done

echo ""
echo "✅ Ubuntu/Debian dependencies installed."
echo "Next step: pip install -r requirements.txt"
