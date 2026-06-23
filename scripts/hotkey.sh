#!/usr/bin/env bash
#
# scripts/hotkey.sh
# Billiam OS — Hotkey Trigger Script
#
# Launched by window manager hotkey (i3, Hyprland).
# Opens a rofi/dmenu prompt, sends input to Billiam,
# and optionally speaks the response.
#
# Installation:
#   i3:       bindsym $mod+space exec /path/to/hotkey.sh
#   Hyprland: bind = SUPER, SPACE, exec, /path/to/hotkey.sh
#
set -euo pipefail

BILLIAM_HOME="${XDG_CONFIG_HOME:-$HOME/.config}/billiam-os"
BILLIAM_LOG="$BILLIAM_HOME/hotkey.log"

# ── Configuration ─────────────────────────────────────────────────────────────
# Set to "yes" for TTS voice output on hotkey queries
ENABLE_TTS="${BILLIAM_TTS:-no}"

# ── Get user input ────────────────────────────────────────────────────────────
# Try rofi first, then dmenu, then read from terminal
if command -v rofi &>/dev/null; then
    QUERY=$(rofi -dmenu -p "Billiam" -theme-str 'entry { placeholder: "Ask Billiam..."; }' 2>/dev/null)
elif command -v dmenu &>/dev/null; then
    QUERY=$(dmenu -p "Billiam:" </dev/null 2>/dev/null)
else
    echo -n "Ask Billiam: "
    read -r QUERY
fi

if [ -z "$QUERY" ]; then
    exit 0
fi

# ── Execute through Billiam ───────────────────────────────────────────────────
cd "$(dirname "$0")/.."

if [ "$ENABLE_TTS" = "yes" ]; then
    python -m core.ai_core --once "$QUERY" --voice 2>>"$BILLIAM_LOG"
else
    python -m core.ai_core --once "$QUERY" 2>>"$BILLIAM_LOG"
fi

# Show notification with response
LOG_ENTRY=$(tail -1 "$BILLIAM_LOG" 2>/dev/null || echo "")
if command -v notify-send &>/dev/null; then
    notify-send -t 5000 "Billiam" "Request processed: ${QUERY:0:50}..."
fi
