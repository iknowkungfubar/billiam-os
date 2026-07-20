"""
tests/test_tts_package.py
Billiam OS - TTS package scaffold contract test.

The monolithic core/tts.py was split into the core/tts/ package
(config.py, protocol.py, module.py) with core/tts/__init__.py
re-exporting the original public surface. These tests lock in the
backward-compatibility contract so future refactors cannot silently
break legacy imports such as ``from core.tts import TTSModule`` or
``from core.tts import PIPER_CACHE_DIR``.
"""

import importlib

import pytest

# Re-import the package fresh to ensure the public surface is stable.
import core.tts as tts_pkg


def test_package_is_importable():
    """core.tts must resolve as a package, not the old monolith module."""
    assert tts_pkg.__file__.endswith("core/tts/__init__.py")


def test_ttsmodule_reachable_from_package():
    """TTSModule must remain importable from the core.tts package."""
    from core.tts import TTSModule

    assert TTSModule is tts_pkg.TTSModule
    # Instantiation must still work after the split.
    assert isinstance(TTSModule().voice, str)


def test_constants_reachable_from_package():
    """Module-level constants must remain importable from core.tts."""
    from core.tts import (
        BACKEND_PRIORITY,
        DEFAULT_PITCH,
        DEFAULT_RATE,
        DEFAULT_VOICE,
        FALLBACK_VOICE,
        PIPER_CACHE_DIR,
        PIPER_HF_MODEL_URL,
        PIPER_VOICE_NAME,
    )

    assert DEFAULT_VOICE == "en-GB-RyanNeural"
    assert BACKEND_PRIORITY == ["edge-tts", "piper", "espeak-ng"]
    assert DEFAULT_RATE == "+0%"
    assert DEFAULT_PITCH == "+0Hz"
    assert FALLBACK_VOICE == "en"
    assert PIPER_VOICE_NAME.endswith("-medium")
    assert ".cache/billiam-os" in PIPER_CACHE_DIR
    assert PIPER_HF_MODEL_URL.startswith("https://huggingface.co/")


def test_protocol_and_registry_reachable():
    """Backend protocol and registry helpers must remain importable."""
    from core.tts import (
        TTSBackend,
        TTSSimpleBackend,
        get_available_backends,
        register_backend,
    )

    assert callable(register_backend)
    assert callable(get_available_backends)
    assert get_available_backends() == []  # nothing registered by default


def test_submodules_present():
    """The package must expose the split sub-modules."""
    from core.tts import config, module, protocol

    assert config.DEFAULT_VOICE == "en-GB-RyanNeural"
    assert hasattr(module, "TTSModule")
    assert hasattr(protocol, "TTSBackend")
