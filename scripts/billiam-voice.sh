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

# Run Billiam with STT + TTS enabled for one voice command
python -m core.cli --once "Listen and process voice command for ${DURATION} seconds" --voice --stt 2>/dev/null || {

    # Fallback: use arecord directly + whisper
    echo "Direct recording mode..."
    TMPFILE=$(mktemp /tmp/billiam-voice-XXXXXXXX.wav)

    arecord -r 16000 -c 1 -f S16_LE -d "$DURATION" "$TMPFILE" 2>/dev/null || {
        echo "Error: No recording device found."
        echo "Install alsa-utils: sudo pacman -S alsa-utils"
        cleanup
        exit 1
    }

    # Transcribe via Billiam
    echo "Transcribing..."
    python -c "
import sys
sys.path.insert(0, '.')
from core.stt import STTModule
stt = STTModule(model_size='base')
text = stt.transcribe('$TMPFILE')
if text:
    print('You said:', text)
    # Process through AI Core
    from core.ai_core import AICore
    core = AICore(enable_tts=True)
    response = core.process_input(text)
    print('Billiam:', response)
else:
    print('No speech detected.')
" 2>/dev/null

    cleanup
}
