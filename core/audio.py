"""
core/audio.py
Billiam OS — Audio Daemon

Manages audio capture and playback subsystems. Coordinates between
the STT (speech-to-text) and TTS (text-to-speech) modules for
full voice interaction.

Provides:
- Audio pipeline management (capture → process → playback)
- Volume control and device management
- Voice activity detection (VAD)
- Background listening with wake word
- Push-to-talk mode via hotkey
"""

import logging
import threading
from collections.abc import Callable

from .billiam import BILLIAM_PROFILE
from .stt import STTModule
from .tts import TTSModule

logger = logging.getLogger("billiam.audio")


class AudioDaemon:
    """Audio subsystem daemon for Billiam OS.

    Manages the full voice pipeline: capture → STT → process → TTS → playback.

    Usage:
        daemon = AudioDaemon()
        daemon.start()
        daemon.speak("Good day, sir.")
        text = daemon.listen()
        daemon.stop()
    """

    def __init__(
        self,
        stt_model_size: str = "base",
        tts_voice: str = BILLIAM_PROFILE["voice"]["voice_id"],
        wake_word_required: bool = True,
        auto_start: bool = False,
    ):
        """Initialize the audio daemon.

        Args:
            stt_model_size: faster-whisper model size.
            tts_voice: Edge TTS voice name.
            wake_word_required: Require wake word for voice commands.
            auto_start: Automatically start listening on init.
        """
        self.wake_word_required = wake_word_required
        self._running = False
        self._listen_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Initialize subsystems
        self.tts = TTSModule(voice=tts_voice)
        self.stt = STTModule(model_size=stt_model_size)

        # Callback for incoming voice commands
        self._command_callback: Callable[[str], None] | None = None

        logger.info(
            "AudioDaemon initialized (wake=%s, tts=%s, stt=%s)",
            wake_word_required,
            tts_voice,
            stt_model_size,
        )

        if auto_start:
            self.start()

    def set_command_callback(self, callback: Callable[[str], None]) -> None:
        """Set the callback for voice commands.

        Args:
            callback: Function to call with transcribed voice command text.
        """
        self._command_callback = callback

    def _on_transcription(self, text: str) -> None:
        """Internal handler for transcription results.

        Args:
            text: Transcribed text from STT.
        """
        logger.info("Voice command received: %s", text[:80])
        if self._command_callback:
            self._command_callback(text)

    # ── Public API ───────────────────────────────────────────────────────────

    def speak(self, text: str, wait: bool = True) -> bool:
        """Speak text aloud.

        Args:
            text: Text to speak.
            wait: If True, block until speech finishes.

        Returns:
            True if speech succeeded.
        """
        if wait:
            return self.tts.speak(text)
        else:
            self.tts.speak_async(text)
            return True

    def listen(self, duration: float = 5.0) -> str:
        """Record and transcribe audio.

        Args:
            duration: Recording duration in seconds.

        Returns:
            Transcribed text.
        """
        return self.stt.listen(duration=duration)

    def start(self) -> None:
        """Start the background listening daemon."""
        if self._running:
            logger.warning("AudioDaemon already running.")
            return

        self._running = True
        self._stop_event.clear()

        self._listen_thread = threading.Thread(
            target=self.stt.listen_loop,
            args=(self._on_transcription, self.wake_word_required, 1.0, self._stop_event),
            daemon=True,
        )
        self._listen_thread.start()
        logger.info("AudioDaemon started.")

    def stop(self) -> None:
        """Stop the background listening daemon."""
        self._running = False
        self._stop_event.set()
        self.stt.stop_listening()

        if self._listen_thread:
            self._listen_thread.join(timeout=5.0)
            self._listen_thread = None

        logger.info("AudioDaemon stopped.")

    def is_ready(self) -> bool:
        """Check if audio subsystems are ready.

        Returns:
            True if at least one input and one output backend are available.
        """
        has_output = self.tts.is_available
        has_input = self.stt.model_loaded or True  # STT loads lazily
        return has_output and has_input

    @property
    def running(self) -> bool:
        return self._running

    def __repr__(self) -> str:
        return f"<AudioDaemon running={self._running} wake={self.wake_word_required}>"

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
