"""core/tts/config.py - TTS module configuration constants.

Split from core/tts.py (monolith) into the core/tts/ package for
maintainability. Holds all module-level configuration: default voices,
Piper TTS model URLs/paths, and the fallback voice.

These constants are re-exported from core/tts/__init__.py so that
``from core.tts import PIPER_CACHE_DIR`` (and friends) keeps working.
"""

import os

# Default configuration
DEFAULT_VOICE = "en-GB-SoniaNeural"
DEFAULT_PIPER_MODEL = "en_GB-southern_english_female-medium"
BACKEND_PRIORITY = ["edge-tts", "piper", "espeak-ng"]

# ── Default voices ──
# NOTE: DEFAULT_VOICE is intentionally redefined below. The later assignment
# wins at runtime and is the effective default British butler voice.
DEFAULT_VOICE = "en-GB-RyanNeural"
DEFAULT_RATE = "+0%"
DEFAULT_PITCH = "+0Hz"
# Fallback voice for espeak-ng.
# 'en' is espeak-ng's built-in English voice (always available).
# To use the MBROLA British voice (requires mbrola package), change to 'mb-en1'.
FALLBACK_VOICE = "en"

# Piper TTS configuration
# Users can customize PIPER_VOICE_NAME to any available Piper voice:
#   - en_GB-vctk-k_southern_english_male-medium (British male, VCTK)
#   - en_GB-southern_english_female-medium      (British female, default)
#   - en_US-lessac-medium                       (American female)
#   - en_US-amy-medium                          (American female)
# See: https://github.com/rhasspy/piper-voices
PIPER_VOICE_NAME = "en_GB-vctk-k_southern_english_male-medium"
PIPER_MODEL_FILE = f"{PIPER_VOICE_NAME}.onnx"
PIPER_CONFIG_FILE = f"{PIPER_VOICE_NAME}.json"
PIPER_HF_REPO = "rhasspy/piper-voices"
# Voice URL is auto-derived from PIPER_VOICE_NAME parts:
#   en_GB-vctk-k_southern_english_male-medium →
#   en/en_GB/vctk-k_southern_english_male/medium/{file}
PIPER_VOICE_PARTS = PIPER_VOICE_NAME.replace("-medium", "").split("-", 1)
PIPER_LANG_CODE = PIPER_VOICE_PARTS[0]  # e.g. "en_GB"
PIPER_LANG_FAMILY = PIPER_LANG_CODE.split("_")[0]  # e.g. "en"
PIPER_HF_LANG_PATH = f"{PIPER_LANG_FAMILY}/{PIPER_LANG_CODE}"  # e.g. "en/en_GB"
PIPER_HF_SPEAKER = PIPER_VOICE_PARTS[1]
PIPER_HF_QUALITY = "medium"
PIPER_HF_MODEL_URL = (
    f"https://huggingface.co/{PIPER_HF_REPO}/resolve/main/"
    f"{PIPER_HF_LANG_PATH}/{PIPER_HF_SPEAKER}/{PIPER_HF_QUALITY}/{PIPER_MODEL_FILE}"
)
PIPER_HF_CONFIG_URL = (
    f"https://huggingface.co/{PIPER_HF_REPO}/resolve/main/"
    f"{PIPER_HF_LANG_PATH}/{PIPER_HF_SPEAKER}/{PIPER_HF_QUALITY}/{PIPER_CONFIG_FILE}"
)
PIPER_CACHE_DIR = os.path.expanduser("~/.cache/billiam-os/piper")

__all__ = [
    "BACKEND_PRIORITY",
    "DEFAULT_PIPER_MODEL",
    "DEFAULT_PITCH",
    "DEFAULT_RATE",
    "DEFAULT_VOICE",
    "FALLBACK_VOICE",
    "PIPER_CACHE_DIR",
    "PIPER_CONFIG_FILE",
    "PIPER_HF_CONFIG_URL",
    "PIPER_HF_LANG_PATH",
    "PIPER_HF_MODEL_URL",
    "PIPER_HF_QUALITY",
    "PIPER_HF_REPO",
    "PIPER_HF_SPEAKER",
    "PIPER_LANG_CODE",
    "PIPER_LANG_FAMILY",
    "PIPER_MODEL_FILE",
    "PIPER_VOICE_NAME",
    "PIPER_VOICE_PARTS",
]
