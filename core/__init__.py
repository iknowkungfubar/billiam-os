"""
Billiam OS — AI-Powered Linux Desktop Assistant.

A fully FOSS AI-native operating system layer that turns your Linux desktop
into a voice-controllable, agent-driven personal digital assistant with
a British butler personality named Billiam.
"""

import importlib.metadata

__author__ = "Billiam OS Contributors"
__license__ = "GPL-3.0"

try:
    __version__ = importlib.metadata.version("billiam-os")
except importlib.metadata.PackageNotFoundError:
    __version__ = "1.1.0"  # fallback when not installed

from .ai_core import AICore
from .audio import AudioDaemon
from .billiam import (
    BILLIAM_PROFILE,
    CATCHPHRASES,
    get_catchphrase,
    get_greeting,
    system_prompt_injection,
)
from .cli import build_parser, main, setup_logging
from .config import (
    find_config_file,
    get_config_value,
    load_config,
    load_yaml_config,
)
from .memory import AssistantMemoryLayer
from .sandbox import GuardrailError, IntentClassification, SecureExecutionSandbox
from .stt import STTModule
from .tts import TTSModule

__all__ = [
    "BILLIAM_PROFILE",
    "CATCHPHRASES",
    "AICore",
    "AssistantMemoryLayer",
    "AudioDaemon",
    "GuardrailError",
    "IntentClassification",
    "STTModule",
    "SecureExecutionSandbox",
    "SecureExecutionSandbox",
    "TTSModule",
    "build_parser",
    "find_config_file",
    "get_catchphrase",
    "get_config_value",
    "get_greeting",
    "load_config",
    "load_yaml_config",
    "main",
    "setup_logging",
    "system_prompt_injection",
]
