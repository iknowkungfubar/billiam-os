"""
Billiam OS — AI-Powered Linux Desktop Assistant.

A fully FOSS AI-native operating system layer that turns your Linux desktop
into a voice-controllable, agent-driven personal digital assistant with
a British butler personality named Billiam.
"""

__version__ = "0.2.0"
__author__ = "Billiam OS Contributors"
__license__ = "GPL-3.0"

from .ai_core import AICore
from .audio import AudioDaemon
from .billiam import (
    BILLIAM_PROFILE,
    CATCHPHRASES,
    get_catchphrase,
    get_greeting,
    system_prompt_injection,
)
from .config import (
    find_config_file,
    get_config_value,
    load_config,
    load_yaml_config,
)
from .memory import AssistantMemoryLayer
from .sandbox import GuardrailException, IntentClassification, SecureExecutionSandbox
from .stt import STTModule
from .tts import TTSModule

__all__ = [
    "AICore",
    "AssistantMemoryLayer",
    "SecureExecutionSandbox",
    "GuardrailException",
    "TTSModule",
    "STTModule",
    "AudioDaemon",
    "BILLIAM_PROFILE",
    "CATCHPHRASES",
    "system_prompt_injection",
    "get_greeting",
    "get_catchphrase",
    "load_config",
    "load_yaml_config",
    "find_config_file",
    "get_config_value",
]
