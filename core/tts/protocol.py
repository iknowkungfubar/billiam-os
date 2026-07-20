"""core/tts/protocol.py - TTS backend protocol and registry.

Split from core/tts.py (monolith) into the core/tts/ package for
maintainability. Defines the TTSBackend protocol, a convenience base
class for CLI-driven backends, and the backend registry.

These symbols are re-exported from core/tts/__init__.py so that
``from core.tts import TTSBackend, register_backend`` keeps working.
"""

import shutil
from typing import Protocol


class TTSBackend(Protocol):
    """Protocol for TTS backends. Each backend implements speak()."""

    name: str
    """Unique backend identifier (e.g. 'edge-tts', 'piper')."""

    def is_available(self) -> bool:
        """Check if this backend can be used."""
        ...

    def speak(self, text: str, audio_path: str | None = None) -> bool:
        """Speak the given text. Returns True on success."""
        ...


class TTSSimpleBackend:
    """Convenience base for backends that just call a CLI tool."""

    name: str = ""
    binary: str = ""

    @classmethod
    def is_available(cls) -> bool:
        return bool(shutil.which(cls.binary))

    def speak(self, text: str, audio_path: str | None = None) -> bool:
        raise NotImplementedError


# ── Registry ──
# Backends register here with priority order

_registry: list[type[TTSBackend]] = []


def register_backend(backend_cls: type[TTSBackend]) -> None:
    """Register a TTS backend class."""
    _registry.append(backend_cls)


def get_available_backends() -> list[type[TTSBackend]]:
    """Return registered backends that are available on this system."""
    return [b for b in _registry if b.is_available()]


__all__ = [
    "TTSBackend",
    "TTSSimpleBackend",
    "get_available_backends",
    "register_backend",
]
