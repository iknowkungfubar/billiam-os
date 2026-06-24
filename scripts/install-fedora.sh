#!/usr/bin/env bash
#
# scripts/install-fedora.sh
# Billiam OS — Fedora Install Helper
#
# Installs system dependencies for Fedora-based distributions.
# Run this before pip install.
#
# Usage:
#   bash scripts/install-fedora.sh
#

set -euo pipefail

echo "📦 Billiam OS — Fedora System Dependency Install"
echo "=================================================="
echo ""

if ! command -v dnf &>/dev/null; then
    echo "❌ This script is for Fedora-based systems (dnf not found)."
    exit 1
fi

echo "==> Installing build dependencies (needed by faster-whisper)..."
sudo dnf install -y \
    gcc-c++ \
    cmake \
    cython

echo ""
echo "==> Installing Billiam OS system dependencies..."
sudo dnf install -y \
    espeak-ng \
    ffmpeg \
    alsa-utils \
    python3-pip \
    pciutils \
    mbrola

echo ""
echo "==> Installing Piper TTS (offline neural TTS)..."
if command -v piper &>/dev/null; then
    echo "  ✓ piper already installed"
else
    echo "  → Installing piper-tts..."
    sudo dnf install -y piper-tts 2>/dev/null || {
        echo "  ⚠ piper-tts not found in dnf repositories."
        echo "    Install manually from: https://github.com/rhasspy/piper/releases"
    }
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
echo "✅ Fedora dependencies installed."
echo "Next step: pip install -r requirements.txt"
