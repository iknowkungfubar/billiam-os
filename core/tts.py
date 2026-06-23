"""
core/tts.py
Billiam OS — Text-to-Speech Module

Provides British butler voice output using multiple backends:
1. edge-tts (primary) — natural British voice via Edge TTS API
2. espeak-ng (fallback) — fully offline, no internet needed

All audio is played through the system's default audio output device.
"""

import asyncio
import logging
import os
import subprocess
import tempfile
import threading

logger = logging.getLogger("billiam.tts")

# Default British butler voice
DEFAULT_VOICE = "en-GB-RyanNeural"
DEFAULT_RATE = "+0%"
DEFAULT_PITCH = "+0Hz"
FALLBACK_VOICE = "mb-en1"


class TTSModule:
    """Text-to-Speech module with British butler voice.

    Primary: edge-tts (natural British male voice, requires internet).
    Fallback: espeak-ng (fully offline, robotic but intelligible).

    Usage:
        tts = TTSModule()
        tts.speak("Good day, sir. How may I be of assistance?")
    """

    def __init__(
        self,
        voice: str = DEFAULT_VOICE,
        rate: str = DEFAULT_RATE,
        pitch: str = DEFAULT_PITCH,
        use_edge: bool = True,
        device: str | None = None,
    ):
        """Initialize the TTS module.

        Args:
            voice: Edge TTS voice name (default: en-GB-RyanNeural — British male).
            rate: Speech rate adjustment (default: +0%).
            pitch: Pitch adjustment (default: +0Hz).
            use_edge: Whether to use edge-tts as primary (True) or espeak-ng (False).
            device: Audio output device (None = system default).
        """
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.use_edge = use_edge
        self.device = device

        self._edge_available = self._check_edge()
        self._espeak_available = self._check_espeak()

        if not self._edge_available and not self._espeak_available:
            logger.warning("No TTS backend available. Speech output disabled.")

        logger.info(
            "TTSModule initialized (edge=%s, espeak=%s, voice=%s)",
            self._edge_available,
            self._espeak_available,
            self.voice,
        )

    @staticmethod
    def _check_edge() -> bool:
        """Check if edge-tts is available."""
        try:
            import edge_tts
            return True
        except ImportError:
            return False

    @staticmethod
    def _check_espeak() -> bool:
        """Check if espeak-ng is installed."""
        try:
            subprocess.run(
                ["espeak-ng", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _play_audio(self, audio_file: str) -> bool:
        """Play audio file through system audio output.

        Tries: ffplay, paplay, aplay, then falls back to subprocess.

        Args:
            audio_file: Path to audio file.

        Returns:
            True if playback succeeded.
        """
        players = []

        # Try ffplay (from ffmpeg)
        if self.device:
            players.append(
                ["ffplay", "-nodisp", "-autoexit", "-v", "0",
                 "-audio_device", self.device, audio_file]
            )
        else:
            players.append(
                ["ffplay", "-nodisp", "-autoexit", "-v", "0", audio_file]
            )

        # Try PipeWire
        players.append(["paplay", audio_file])
        # Try ALSA
        players.append(["aplay", audio_file])

        for cmd in players:
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    return True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        logger.error("No audio player available to play TTS output.")
        return False

    def _speak_edge(self, text: str) -> bool:
        """Speak using edge-tts (natural British voice).

        Args:
            text: Text to speak.

        Returns:
            True if speech succeeded.
        """
        try:
            import edge_tts

            communicate = edge_tts.Communicate(
                text, self.voice, rate=self.rate, pitch=self.pitch
            )

            with tempfile.NamedTemporaryFile(
                suffix=".mp3", delete=False
            ) as tmp:
                tmp_path = tmp.name

            async def _run_tts():
                await communicate.save(tmp_path)

            asyncio.run(_run_tts())
            result = self._play_audio(tmp_path)
            os.unlink(tmp_path)
            return result

        except Exception as e:
            logger.warning("edge-tts failed: %s. Trying fallback.", e)
            return False

    def _speak_espeak(self, text: str) -> bool:
        """Speak using espeak-ng (offline fallback).

        Uses MBROLA voice for British accent if available.

        Args:
            text: Text to speak.

        Returns:
            True if speech succeeded.
        """
        try:
            # Try MBROLA British voice first
            cmd = ["espeak-ng", "-v", FALLBACK_VOICE, "-s", "150", "-p", "50", text]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0

        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.error("espeak-ng failed: %s", e)
            return False

    def speak(self, text: str, force_offline: bool = False) -> bool:
        """Speak text aloud using the configured TTS backend.

        Args:
            text: The text to speak.
            force_offline: If True, skip edge-tts and use espeak-ng directly.

        Returns:
            True if the speech was successfully played.
        """
        if not text or not text.strip():
            return False

        logger.info("Speaking: %s", text[:80])

        # Try edge-tts first (if not forced offline)
        if self.use_edge and not force_offline and self._edge_available:
            if self._speak_edge(text):
                return True
            logger.info("edge-tts failed, falling back to espeak-ng")

        # Fallback to espeak-ng
        if self._espeak_available:
            if self._speak_espeak(text):
                return True

        logger.error("All TTS backends failed.")
        return False

    def speak_async(self, text: str, force_offline: bool = False) -> threading.Thread:
        """Speak text in a background thread (non-blocking).

        Args:
            text: The text to speak.
            force_offline: If True, skip edge-tts and use espeak-ng directly.

        Returns:
            The background thread object.
        """
        thread = threading.Thread(
            target=self.speak, args=(text, force_offline), daemon=True
        )
        thread.start()
        return thread

    @property
    def is_available(self) -> bool:
        """Check if at least one TTS backend is available."""
        return self._edge_available or self._espeak_available

    @property
    def backends(self) -> list:
        """List available TTS backends."""
        backends = []
        if self._edge_available:
            backends.append("edge-tts")
        if self._espeak_available:
            backends.append("espeak-ng")
        return backends

    def __repr__(self) -> str:
        return (
            f"<TTSModule voice={self.voice} "
            f"backends={self.backends}>"
        )
