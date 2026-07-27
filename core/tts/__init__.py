# Copyright (C) 2025 Billiam OS Contributors
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
core/tts - Billiam OS Text-to-Speech Package

Provides British butler voice output using multiple backends:
1. edge-tts (online) - natural British voice via Edge TTS API
2. Piper TTS (offline) - high-quality local neural TTS, FOSS
3. espeak-ng (offline) - fully offline fallback, robotic but reliable

Split from the monolithic core/tts.py for maintainability:
  - config.py:    default voices, Piper TTS model URLs/paths, fallback voice
  - protocol.py:  TTSBackend protocol, TTSSimpleBackend base, backend registry
  - module.py:    TTSModule orchestrator (backend detection + speak pipeline)

All public symbols are re-exported here so that legacy imports such as
``from core.tts import TTSModule`` and ``from core.tts import PIPER_CACHE_DIR``
continue to work unchanged.
"""

from .config import (
    BACKEND_PRIORITY,
    DEFAULT_PIPER_MODEL,
    DEFAULT_PITCH,
    DEFAULT_RATE,
    DEFAULT_VOICE,
    FALLBACK_VOICE,
    PIPER_CACHE_DIR,
    PIPER_CONFIG_FILE,
    PIPER_HF_CONFIG_URL,
    PIPER_HF_LANG_PATH,
    PIPER_HF_MODEL_URL,
    PIPER_HF_QUALITY,
    PIPER_HF_REPO,
    PIPER_HF_SPEAKER,
    PIPER_LANG_CODE,
    PIPER_LANG_FAMILY,
    PIPER_MODEL_FILE,
    PIPER_VOICE_NAME,
    PIPER_VOICE_PARTS,
)
from .module import TTSModule
from .protocol import (
    TTSBackend,
    TTSSimpleBackend,
    get_available_backends,
    register_backend,
)

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
    "TTSBackend",
    "TTSModule",
    "TTSSimpleBackend",
    "get_available_backends",
    "register_backend",
]
