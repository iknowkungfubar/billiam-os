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

echo "==> Installing Billiam OS system dependencies..."
sudo dnf install -y \
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
echo "✅ Fedora dependencies installed."
echo "Next step: pip install -r requirements.txt"
