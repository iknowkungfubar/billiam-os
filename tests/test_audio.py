"""
tests/test_audio.py
Billiam OS — Audio Daemon Test Suite

Tests the audio subsystem daemon.
"""

import pytest
from core.audio import AudioDaemon


class TestAudioDaemon:
    """Test AudioDaemon initialization."""

    def test_init_defaults(self):
        """AudioDaemon must initialize with defaults."""
        daemon = AudioDaemon()
        assert daemon.wake_word_required is True
        assert daemon.running is False

    def test_init_no_wake_word(self):
        """AudioDaemon must support disabling wake word."""
        daemon = AudioDaemon(wake_word_required=False)
        assert daemon.wake_word_required is False

    def test_init_with_tts_voice(self):
        """AudioDaemon must accept custom TTS voice."""
        daemon = AudioDaemon(tts_voice="en-GB-SoniaNeural")
        assert daemon.tts.voice == "en-GB-SoniaNeural"

    def test_speak_method(self):
        """Speak must return a boolean."""
        daemon = AudioDaemon()
        result = daemon.speak("Hello")
        assert isinstance(result, bool)

    def test_listen_method(self):
        """Listen must return a string."""
        daemon = AudioDaemon()
        result = daemon.listen(duration=0.5)
        assert isinstance(result, str)

    def test_start_stop(self):
        """Start and stop must work without error."""
        daemon = AudioDaemon()
        daemon.start()
        assert daemon.running is True
        daemon.stop()
        assert daemon.running is False

    def test_double_start(self):
        """Starting an already running daemon must not crash."""
        daemon = AudioDaemon()
        daemon.start()
        daemon.start()  # Should log warning, not crash
        daemon.stop()

    def test_audio_daemon_repr(self):
        """Repr must contain module info."""
        daemon = AudioDaemon()
        rep = repr(daemon)
        assert "AudioDaemon" in rep

    def test_context_manager(self):
        """Context manager must start and stop."""
        with AudioDaemon() as daemon:
            assert daemon.running is True
        assert daemon.running is False

    def test_set_command_callback(self):
        """Setting a command callback must not crash."""
        daemon = AudioDaemon()

        def callback(text):
            pass

        daemon.set_command_callback(callback)
        daemon.stop()

    def test_is_ready(self):
        """is_ready must return a boolean."""
        daemon = AudioDaemon()
        ready = daemon.is_ready()
        assert isinstance(ready, bool)
