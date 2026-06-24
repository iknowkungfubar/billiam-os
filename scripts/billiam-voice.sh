#!/usr/bin/env bash
#
# scripts/billiam-voice.sh
# Billiam OS — Voice Trigger Script
#
# Records audio, transcribes via Billiam's STT, processes the
# command, and speaks the response via TTS (British butler voice).
#
# Usage: bash scripts/billiam-voice.sh [duration_seconds]
#
# Pipeline: arecord → STT (faster-whisper) → billiam --once --voice → TTS

set -euo pipefail

DURATION="${1:-5}"

cd "$(dirname "$0")/.."

# Ensure cleanup of temp file on exit or interrupt
TMPFILE=""
cleanup() {
    if [ -n "$TMPFILE" ] && [ -f "$TMPFILE" ]; then
        rm -f "$TMPFILE"
    fi
}
trap cleanup EXIT INT TERM

echo "🎤 Listening for ${DURATION}s... (speak after the beep)"
echo ""

# Beep to indicate recording start
echo -ne '\a'

# ── Record audio ───────────────────────────────────────────────────
TMPFILE=$(mktemp /tmp/billiam-voice-XXXXXXXX.wav)

arecord -r 16000 -c 1 -f S16_LE -d "$DURATION" "$TMPFILE" 2>/dev/null || {
    echo "Error: No recording device found."
    echo "Install alsa-utils: sudo pacman -S alsa-utils"
    cleanup
    exit 1
}

# ── Transcribe with STT ────────────────────────────────────────────
echo "Transcribing..."
TRANSCRIPT=$(python -c "
import sys
sys.path.insert(0, '.')
from core.stt import STTModule
stt = STTModule(model_size='base')
text = stt.transcribe('$TMPFILE')
if text:
    print(text)
" 2>/dev/null)

if [ -z "$TRANSCRIPT" ]; then
    echo "No speech detected."
    cleanup
    exit 0
fi

echo "You said: $TRANSCRIPT"

# ── Process through Billiam with TTS ───────────────────────────────
echo "Processing..."
python -m core.cli --once "$TRANSCRIPT" --voice 2>/dev/null

cleanup
