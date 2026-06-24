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
echo "==> Installing Billiam OS system dependencies..."
sudo apt-get install -y \
    espeak-ng \
    ffmpeg \
    alsa-utils \
    python3-pip \
    pciutils

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
