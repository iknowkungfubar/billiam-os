"""
core/stt.py
Billiam OS — Speech-to-Text Module

Provides speech recognition using local inference:
1. faster-whisper (primary) — local model, offline capable
2. arecord/parec (capture) — system audio input

Supports wake word detection, push-to-talk, and continuous listening.
"""

import logging
import os
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable

logger = logging.getLogger("billiam.stt")

# Wake words (lowercase, for matching)
DEFAULT_WAKE_WORDS = ["billiam", "hey billiam", "okay billiam"]

# Default STT language
DEFAULT_LANGUAGE = "en"

# Audio recording parameters
SAMPLE_RATE = 16000
CHANNELS = 1
DEFAULT_RECORD_SECONDS = 10


class STTModule:
    """Speech-to-Text module using faster-whisper locally.

    Handles audio capture, wake word detection, and transcription.

    Usage:
        stt = STTModule()
        text = stt.listen()  # Record and transcribe
        stt.listen_loop(callback)  # Continuous listening
    """

    def __init__(
        self,
        model_size: str = "base",
        language: str = DEFAULT_LANGUAGE,
        wake_words: list | None = None,
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        """Initialize the STT module.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large).
            language: Language code for transcription (default: en).
            wake_words: List of wake word phrases to detect.
            device: Compute device (cpu, cuda, auto).
            compute_type: Quantization type (int8, float16, float32).
        """
        self.model_size = model_size
        self.language = language
        self.wake_words = wake_words or list(DEFAULT_WAKE_WORDS)
        self.device = device
        self.compute_type = compute_type

        self._model = None
        self._listening = False
        self._vad_available = self._check_vad()
        self._checked_hardware: bool | None = None

        logger.info(
            "STTModule initialized (model=%s, lang=%s, device=%s, vad=%s)",
            model_size, language, device, self._vad_available,
        )

    def _get_model(self):
        """Lazy-load the whisper model."""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
                logger.info("Whisper model loaded: %s", self.model_size)
            except ImportError:
                logger.error(
                    "faster-whisper not installed. "
                    "Run: pip install faster-whisper"
                )
                raise
            except Exception as e:
                logger.error("Failed to load whisper model: %s", e)
                raise
        return self._model

    @staticmethod
    def _check_vad() -> bool:
        """Check if webrtcvad is available for voice activity detection."""
        try:
            import webrtcvad  # noqa: F401
            return True
        except ImportError:
            return False

    def _has_capture_hardware(self) -> bool:
        """Check if audio capture hardware is available without blocking.

        Returns:
            True if at least one capture method is usable.
        """
        if self._checked_hardware is not None:
            return self._checked_hardware

        self._checked_hardware = False
        # Check if either arecord or parec is installed
        for tool in ["arecord", "parec"]:
            try:
                subprocess.run(
                    ["which", tool], capture_output=True, timeout=2
                )
                self._checked_hardware = True
                break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        return self._checked_hardware

    def _capture_audio(self, duration: float = DEFAULT_RECORD_SECONDS) -> str:
        """Record audio from the default microphone.

        Checks hardware availability first to avoid blocking.
        Tries: parec (PipeWire), arecord (ALSA), then raises.

        Args:
            duration: Recording duration in seconds.

        Returns:
            Path to the recorded WAV file.
        """
        if not self._has_capture_hardware():
            raise RuntimeError(
                "No audio capture backend available. "
                "Install arecord (alsa-utils) or parec (pipewire)"
            )
        tmp_file = tempfile.NamedTemporaryFile(
            suffix=".wav", delete=False
        )
        tmp_path = tmp_file.name
        tmp_file.close()

        # Try PipeWire first, then ALSA
        capture_cmds = [
            [
                "parec",
                "--rate", str(SAMPLE_RATE),
                "--channels", str(CHANNELS),
                "--format", "s16le",
                tmp_path.replace(".wav", ".raw"),
            ],
            [
                "arecord",
                "-r", str(SAMPLE_RATE),
                "-c", str(CHANNELS),
                "-f", "S16_LE",
                "-d", str(int(duration)),
                tmp_path,
            ],
        ]

        for cmd_template in capture_cmds:
            try:
                if "parec" in cmd_template[0]:
                    # parec outputs raw PCM — capture it and wrap in WAV
                    raw_file = tmp_path.replace(".wav", ".raw")
                    proc = subprocess.Popen(
                        cmd_template,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    try:
                        proc.wait(timeout=duration + 5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()

                    if proc.returncode == 0 and os.path.exists(raw_file):
                        file_size = os.path.getsize(raw_file)
                        if file_size > 1000:  # At least 1KB of audio
                            # Convert raw PCM to WAV using the wave module
                            import wave
                            with wave.open(tmp_path, "wb") as wav:
                                wav.setnchannels(CHANNELS)
                                wav.setsampwidth(2)  # 16-bit = 2 bytes
                                wav.setframerate(SAMPLE_RATE)
                                with open(raw_file, "rb") as raw:
                                    wav.writeframes(raw.read())
                            logger.debug("Captured %d bytes via parec", file_size)
                            return tmp_path
                    logger.debug("parec capture failed or too small")
                    continue

                logger.debug("Recording %ss audio via %s...", duration, cmd_template[0])
                result = subprocess.run(
                    cmd_template, capture_output=True, text=True,
                    timeout=duration + 5,
                )
                if result.returncode == 0 and os.path.exists(tmp_path):
                    file_size = os.path.getsize(tmp_path)
                    if file_size > 1000:  # At least 1KB of audio
                        logger.debug("Captured %d bytes", file_size)
                        return tmp_path
                logger.debug("Capture via %s failed or too small", cmd_template[0])
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                logger.debug("Capture via %s unavailable: %s", cmd_template[0], e)
                continue
            finally:
                # Clean up raw file if created
                raw_file = tmp_path.replace(".wav", ".raw")
                if os.path.exists(raw_file):
                    try:
                        os.unlink(raw_file)
                    except OSError:
                        pass

        # If we got here, all capture methods failed
        raise RuntimeError(
            "No audio capture backend available. "
            "Install arecord (alsa-utils) or parec (pipewire)"
        )

    def transcribe(self, audio_file: str) -> str:
        """Transcribe audio file to text using faster-whisper.

        Args:
            audio_file: Path to WAV audio file.

        Returns:
            Transcribed text string.
        """
        if not os.path.exists(audio_file):
            logger.error("Audio file not found: %s", audio_file)
            return ""

        try:
            model = self._get_model()
            segments, info = model.transcribe(
                audio_file,
                language=self.language,
                beam_size=3,
                vad_filter=self._vad_available,
            )

            text = " ".join(segment.text for segment in segments)
            text = text.strip()
            logger.info(
                "Transcribed %s (lang=%s, prob=%.2f): %s",
                audio_file, info.language, info.language_probability,
                text[:80],
            )
            return text

        except Exception as e:
            logger.error("Transcription failed: %s", e)
            return ""

    def listen(self, duration: float = DEFAULT_RECORD_SECONDS) -> str:
        """Record audio and transcribe it.

        Args:
            duration: Recording duration in seconds.

        Returns:
            Transcribed text, or empty string on failure.
        """
        try:
            audio_file = self._capture_audio(duration=duration)
            text = self.transcribe(audio_file)
            # Clean up
            try:
                os.unlink(audio_file)
            except OSError:
                pass
            return text

        except RuntimeError as e:
            logger.error(str(e))
            return ""
        except Exception as e:
            logger.error("Listen failed: %s", e)
            return ""

    def detect_wake_word(self, text: str) -> bool:
        """Check if transcribed text contains a wake word.

        Args:
            text: Transcribed text to check.

        Returns:
            True if a wake word was detected.
        """
        if not text:
            return False
        text_lower = text.lower().strip()
        for wake_word in self.wake_words:
            if text_lower.startswith(wake_word) or wake_word in text_lower:
                return True
        return False

    def strip_wake_word(self, text: str) -> str:
        """Remove the wake word from the beginning of text.

        Args:
            text: Text that may contain a wake word.

        Returns:
            Text with wake word removed, or original text.
        """
        if not text:
            return ""
        text_lower = text.lower().strip()
        for wake_word in self.wake_words:
            if text_lower.startswith(wake_word):
                # Remove the wake word and any following punctuation/space
                after = text[len(wake_word):].strip().lstrip(",.!?:; ")
                return after
            # Also check if wake word appears anywhere
            idx = text_lower.find(wake_word)
            if idx >= 0:
                after = text[idx + len(wake_word):].strip().lstrip(",.!?:; ")
                return after
        return text

    def listen_loop(
        self,
        callback: Callable[[str], None],
        wake_word_required: bool = True,
        interval: float = 1.0,
        stop_event: threading.Event | None = None,
    ) -> None:
        """Continuous listening loop.

        Args:
            callback: Function to call with transcribed text.
            wake_word_required: If True, only call callback on wake word.
            interval: Check interval in seconds.
            stop_event: Event to signal stopping.
        """
        self._listening = True
        logger.info(
            "Listening loop started (wake=%s, interval=%.1fs)",
            wake_word_required, interval,
        )

        while self._listening:
            if stop_event and stop_event.is_set():
                break

            try:
                text = self.listen(duration=interval + 0.5)
                if not text:
                    time.sleep(0.1)
                    continue

                if wake_word_required:
                    if self.detect_wake_word(text):
                        command = self.strip_wake_word(text)
                        logger.info("Wake word detected: %s", command[:60])
                        callback(command)
                else:
                    callback(text)

            except Exception as e:
                logger.error("Listen loop error: %s", e)
                time.sleep(1.0)

        self._listening = False
        logger.info("Listening loop stopped.")

    def stop_listening(self) -> None:
        """Stop the listening loop."""
        self._listening = False

    @property
    def is_listening(self) -> bool:
        """Check if the listening loop is active."""
        return self._listening

    @property
    def model_loaded(self) -> bool:
        """Check if the whisper model is loaded."""
        return self._model is not None

    def __repr__(self) -> str:
        return (
            f"<STTModule model={self.model_size} "
            f"lang={self.language} vad={self._vad_available}>"
        )
