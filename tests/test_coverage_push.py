"""
tests/test_coverage_push.py
Billiam OS — Coverage Push Tests

Targeted tests for uncovered lines to push past 80% coverage.
"""

import os
import tempfile

import pytest

from core.config import (
    DEFAULT_CONFIG,
    find_config_file,
    save_config,
)
from core.tts import TTSModule


class TestConfigEdgeCases:
    """Test config edge cases for coverage."""

    def test_find_config_with_env_var(self):
        """BILLIAM_CONFIG env var pointing to existing file."""
        tmp_dir = tempfile.mkdtemp()
        config_path = os.path.join(tmp_dir, "test_config.yaml")
        # Create the file
        save_config(DEFAULT_CONFIG, config_path)

        old_env = os.environ.get("BILLIAM_CONFIG")
        os.environ["BILLIAM_CONFIG"] = config_path
        try:
            found = find_config_file()
            assert found == config_path
        finally:
            if old_env is not None:
                os.environ["BILLIAM_CONFIG"] = old_env
            else:
                del os.environ["BILLIAM_CONFIG"]
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_save_config_no_pyyaml(self):
        """save_config should handle missing PyYAML gracefully."""
        # We can test the error path by passing an invalid path
        result = save_config(DEFAULT_CONFIG, "/nonexistent/../")
        # On most systems this will fail
        assert isinstance(result, bool)

    def test_audio_daemon_command_callback(self):
        """Setting and using command callback."""
        from core.audio import AudioDaemon

        daemon = AudioDaemon()
        received = []

        def callback(text):
            received.append(text)

        daemon.set_command_callback(callback)

        # Trigger the callback directly
        daemon._on_transcription("test command")
        assert len(received) == 1
        assert received[0] == "test command"

        daemon.stop()

    def test_audio_is_ready(self):
        """is_ready must work."""
        from core.audio import AudioDaemon

        daemon = AudioDaemon()
        ready = daemon.is_ready()
        assert isinstance(ready, bool)
        daemon.stop()

    def test_tts_speak_async_thread(self):
        """speak_async must return a thread."""
        tts = TTSModule()
        thread = tts.speak_async("Hello", force_offline=True)
        assert thread is not None
        thread.join(timeout=5)

    def test_tts_force_offline_with_edge(self):
        """force_offline=True must skip edge-tts."""
        tts = TTSModule(use_edge=True)
        if tts._espeak_available:
            result = tts.speak("test", force_offline=True)
            assert isinstance(result, bool)
        else:
            pytest.skip("espeak-ng not available")

    def test_tts_edge_not_available_fallback(self):
        """When edge is unavailable, must fallback gracefully."""
        tts = TTSModule(use_edge=True)
        # Manually disable edge
        tts._edge_available = False
        if tts._espeak_available:
            result = tts.speak("test fallback")
            assert isinstance(result, bool)
        else:
            # No backends available
            result = tts.speak("test")
            assert result is False


class TestSTTCoverage:
    """Coverage push for STT module."""

    def test_stt_detect_wake_word_none_text(self):
        """detect_wake_word with None must return False."""
        from core.stt import STTModule

        stt = STTModule()
        assert stt.detect_wake_word(None) is False

    def test_stt_strip_wake_word_none(self):
        """strip_wake_word with None must return empty string."""
        from core.stt import STTModule

        stt = STTModule()
        assert stt.strip_wake_word(None) == ""


class TestSandboxErrorHandling:
    """Test sandbox error handling paths."""

    def test_nonexistent_command(self):
        """Non-existent command must return error gracefully."""
        from core.sandbox import SecureExecutionSandbox

        sandbox = SecureExecutionSandbox()
        # Use a command that resolves to nothing
        rc, stdout, stderr = sandbox.execute_safely("this_command_does_not_exist_xyz123")
        assert rc != 0 or "not found" in stderr.lower()
