"""
tests/test_tts.py
Billiam OS — TTS Module Test Suite

Tests the Text-to-Speech module with British butler voice.
"""

import pytest
from core.tts import TTSModule


class TestTTSModule:
    """Test TTS module initialization and capabilities."""

    def test_init_defaults(self):
        """TTS module must initialize with British voice defaults."""
        tts = TTSModule()
        assert tts.voice == "en-GB-RyanNeural"
        assert tts.use_edge is True

    def test_init_custom_voice(self):
        """TTS module must accept custom voice configuration."""
        tts = TTSModule(voice="en-GB-SoniaNeural", use_edge=True)
        assert tts.voice == "en-GB-SoniaNeural"

    def test_init_offline_mode(self):
        """TTS module must support offline (espeak) mode."""
        tts = TTSModule(use_edge=False)
        assert tts.use_edge is False

    @pytest.mark.skipif(
        not TTSModule._check_espeak(),
        reason="espeak-ng not installed",
    )
    def test_espeak_available(self):
        """espeak-ng must be detected when installed."""
        tts = TTSModule()
        assert tts._espeak_available is True

    def test_is_available(self):
        """is_available must return bool."""
        tts = TTSModule()
        assert isinstance(tts.is_available, bool)

    def test_backends(self):
        """backends must return a list."""
        tts = TTSModule()
        backends = tts.backends
        assert isinstance(backends, list)

    def test_speak_empty_text(self):
        """Speaking empty text must return False."""
        tts = TTSModule()
        assert tts.speak("") is False

    def test_speak_whitespace_text(self):
        """Speaking whitespace must return False."""
        tts = TTSModule()
        assert tts.speak("   ") is False

    def test_speak_offline_fallback(self):
        """Speaking with offline mode must use espeak-ng."""
        tts = TTSModule(use_edge=False)
        if tts._espeak_available:
            result = tts.speak("Hello", force_offline=True)
            assert isinstance(result, bool)
        else:
            pytest.skip("espeak-ng not available")

    def test_repr(self):
        """Repr must contain module info."""
        tts = TTSModule()
        rep = repr(tts)
        assert "TTSModule" in rep
        assert "en-GB-RyanNeural" in rep
