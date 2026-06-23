"""
tests/test_stt.py
Billiam OS — STT Module Test Suite

Tests the Speech-to-Text module with wake word detection.
"""

import pytest
from core.stt import STTModule, DEFAULT_WAKE_WORDS


class TestSTTModule:
    """Test STT module initialization and wake word detection."""

    def test_init_defaults(self):
        """STT module must initialize with defaults."""
        stt = STTModule()
        assert stt.model_size == "base"
        assert stt.language == "en"
        assert stt.wake_words == ["billiam", "hey billiam", "okay billiam"]

    def test_init_custom_wake_words(self):
        """STT module must accept custom wake words."""
        stt = STTModule(wake_words=["computer", "jarvis"])
        assert "computer" in stt.wake_words
        assert "jarvis" in stt.wake_words

    def test_is_listening_default(self):
        """STT must not be listening by default."""
        stt = STTModule()
        assert stt.is_listening is False

    def test_model_not_loaded_by_default(self):
        """Whisper model must not be loaded on init (lazy loading)."""
        stt = STTModule()
        assert stt.model_loaded is False

    # ── Wake Word Detection ────────────────────────────────────────────────

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("billiam what time is it", True),
            ("Hey Billiam, check the weather", True),
            ("Okay Billiam do something", True),
            ("what time is it", False),
            ("hello world", False),
            ("", False),
            ("BILLIAM do this", True),
        ],
    )
    def test_detect_wake_word(self, text, expected):
        """Wake word detection must work correctly."""
        stt = STTModule()
        assert stt.detect_wake_word(text) == expected

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("billiam what time is it", "what time is it"),
            ("Hey Billiam, check the weather", "check the weather"),
            ("Okay Billiam do something", "do something"),
            ("no wake word here", "no wake word here"),
            ("", ""),
            ("BILLIAM do this", "do this"),
        ],
    )
    def test_strip_wake_word(self, text, expected):
        """Wake word stripping must work correctly."""
        stt = STTModule()
        assert stt.strip_wake_word(text) == expected

    # ── VAD Check ──────────────────────────────────────────────────────────

    def test_vad_check(self):
        """VAD availability check must return bool."""
        stt = STTModule()
        assert isinstance(stt._check_vad(), bool)

    # ── Transcription ──────────────────────────────────────────────────────

    def test_transcribe_missing_file(self):
        """Transcribing a missing file must return empty string."""
        stt = STTModule()
        result = stt.transcribe("/nonexistent/file.wav")
        assert result == ""

    # ── Listen ─────────────────────────────────────────────────────────────

    def test_listen_returns_string(self):
        """Listen must return a string (empty if no hardware)."""
        stt = STTModule()
        result = stt.listen(duration=0.5)
        assert isinstance(result, str)

    def test_stop_listening(self):
        """Stop listening must set flag."""
        stt = STTModule()
        assert stt.is_listening is False
        stt.stop_listening()
        assert stt.is_listening is False

    # ── Edge Cases ─────────────────────────────────────────────────────────

    def test_detect_wake_word_none(self):
        """None input must not crash."""
        stt = STTModule()
        assert stt.detect_wake_word(None) is False

    def test_strip_wake_word_none(self):
        """None input must return empty string."""
        stt = STTModule()
        assert stt.strip_wake_word(None) == ""

    def test_repr(self):
        """Repr must contain module info."""
        stt = STTModule()
        rep = repr(stt)
        assert "STTModule" in rep
