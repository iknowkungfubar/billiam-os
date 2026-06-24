"""
core/tts.py
Billiam OS — Text-to-Speech Module

Provides British butler voice output using multiple backends:
1. edge-tts (online) — natural British voice via Edge TTS API
2. Piper TTS (offline) — high-quality local neural TTS, FOSS
3. espeak-ng (offline) — fully offline fallback, robotic but reliable

All audio is played through the system's default audio output device.
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import threading
import urllib.request
from pathlib import Path

logger = logging.getLogger("billiam.tts")

# Default voices
DEFAULT_VOICE = "en-GB-RyanNeural"
DEFAULT_RATE = "+0%"
DEFAULT_PITCH = "+0Hz"
FALLBACK_VOICE = "mb-en1"

# Piper TTS configuration
# Users can customize PIPER_VOICE_NAME to any available Piper voice:
#   - en_GB-vctk-k_southern_english_male-medium (British male, VCTK)
#   - en_GB-southern_english_female-medium      (British female, default)
#   - en_US-lessac-medium                       (American female)
#   - en_US-amy-medium                          (American female)
# See: https://github.com/rhasspy/piper-voices
PIPER_VOICE_NAME = "en_GB-vctk-k_southern_english_male-medium"
PIPER_MODEL_FILE = f"{PIPER_VOICE_NAME}.onnx"
PIPER_CONFIG_FILE = f"{PIPER_VOICE_NAME}.json"
PIPER_HF_REPO = "rhasspy/piper-voices"
# Voice URL is auto-derived from PIPER_VOICE_NAME parts:
#   en_GB-vctk-k_southern_english_male-medium →
#   en/en_GB/vctk-k_southern_english_male/medium/{file}
PIPER_VOICE_PARTS = PIPER_VOICE_NAME.replace("-medium", "").split("-", 1)
PIPER_LANG_CODE = PIPER_VOICE_PARTS[0]  # e.g. "en_GB"
PIPER_LANG_FAMILY = PIPER_LANG_CODE.split("_")[0]  # e.g. "en"
PIPER_HF_LANG_PATH = f"{PIPER_LANG_FAMILY}/{PIPER_LANG_CODE}"  # e.g. "en/en_GB"
PIPER_HF_SPEAKER = PIPER_VOICE_PARTS[1]
PIPER_HF_QUALITY = "medium"
PIPER_HF_MODEL_URL = (
    f"https://huggingface.co/{PIPER_HF_REPO}/resolve/main/"
    f"{PIPER_HF_LANG_PATH}/{PIPER_HF_SPEAKER}/{PIPER_HF_QUALITY}/{PIPER_MODEL_FILE}"
)
PIPER_HF_CONFIG_URL = (
    f"https://huggingface.co/{PIPER_HF_REPO}/resolve/main/"
    f"{PIPER_HF_LANG_PATH}/{PIPER_HF_SPEAKER}/{PIPER_HF_QUALITY}/{PIPER_CONFIG_FILE}"
)
PIPER_CACHE_DIR = os.path.expanduser("~/.cache/billiam-os/piper")


class TTSModule:
    """Text-to-Speech module with British butler voice.

    Priority order (best available wins):
    1. edge-tts — natural British male voice (requires internet)
    2. Piper TTS — high-quality offline neural TTS (FOSS, local)
    3. espeak-ng — offline fallback (always available)

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
        use_piper: bool = True,
        device: str | None = None,
    ):
        """Initialize the TTS module.

        Args:
            voice: Edge TTS voice name.
            rate: Speech rate adjustment.
            pitch: Pitch adjustment.
            use_edge: Whether to use edge-tts (online).
            use_piper: Whether to use Piper TTS (offline).
            device: Audio output device (None = system default).
        """
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.use_edge = use_edge
        self.use_piper = use_piper
        self.device = device

        self._edge_available = self._check_edge()
        self._espeak_available = self._check_espeak()
        self._piper_available = self._check_piper()
        self._piper_model_ready = self._check_piper_model() if self._piper_available else False

        if not self._edge_available and not self._piper_available and not self._espeak_available:
            logger.warning("No TTS backend available. Speech output disabled.")

        logger.info(
            "TTSModule initialized (edge=%s, piper=%s/%s, espeak=%s, voice=%s)",
            self._edge_available,
            self._piper_available,
            self._piper_model_ready,
            self._espeak_available,
            self.voice,
        )

    # ── Backend Detection ─────────────────────────────────────────────────────

    @staticmethod
    def _check_edge() -> bool:
        """Check if edge-tts Python package is available."""
        try:
            import edge_tts  # noqa: F401
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

    @staticmethod
    def _check_piper() -> bool:
        """Check if piper-tts CLI is installed."""
        try:
            subprocess.run(
                ["piper", "--help"],
                capture_output=True, text=True, timeout=5,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    # ── Piper Model Management ────────────────────────────────────────────────

    @staticmethod
    def _get_piper_model_path() -> str:
        """Get path to the Piper voice model file."""
        return os.path.join(PIPER_CACHE_DIR, PIPER_MODEL_FILE)

    @staticmethod
    def _get_piper_config_path() -> str:
        """Get path to the Piper voice config file."""
        return os.path.join(PIPER_CACHE_DIR, PIPER_CONFIG_FILE)

    def _check_piper_model(self) -> bool:
        """Check if a Piper voice model is already downloaded."""
        return os.path.exists(self._get_piper_model_path())

    @staticmethod
    def _urlretrieve_with_progress(url: str, path: str) -> None:
        """Download a file with optional tqdm progress bar.

        Falls back to plain urlretrieve if tqdm is not available.
        """
        try:
            from tqdm import tqdm

            with tqdm(unit="B", unit_scale=True, unit_divisor=1024,
                      miniters=1, desc="Downloading") as pbar:
                def reporthook(block_num: int, block_size: int, total_size: int) -> None:
                    if total_size > 0:
                        pbar.total = total_size
                    pbar.update(block_size)
                urllib.request.urlretrieve(url, path, reporthook=reporthook)
        except ImportError:
            urllib.request.urlretrieve(url, path)

    def download_piper_model(self) -> bool:
        """Download the Piper voice model from HuggingFace.

        The model is ~15MB (medium quality British female voice).

        Returns:
            True if model is now available.
        """
        model_path = self._get_piper_model_path()
        config_path = self._get_piper_config_path()

        if os.path.exists(model_path):
            logger.info("Piper model already cached: %s", model_path)
            self._piper_model_ready = True
            return True

        os.makedirs(PIPER_CACHE_DIR, exist_ok=True)

        try:
            logger.info("Downloading Piper TTS model from HuggingFace...")
            logger.info("  Voice: %s (~15MB)", PIPER_VOICE_NAME)

            # Download model (.onnx)
            logger.info("  Downloading model file...")
            self._urlretrieve_with_progress(PIPER_HF_MODEL_URL, model_path)

            # Download config (.json)
            logger.info("  Downloading config file...")
            self._urlretrieve_with_progress(PIPER_HF_CONFIG_URL, config_path)

            logger.info("Piper model downloaded successfully.")
            self._piper_model_ready = True
            return True

        except Exception as e:
            logger.error("Failed to download Piper model: %s", e)
            # Clean up partial downloads
            for path in [model_path, config_path]:
                if os.path.exists(path):
                    os.unlink(path)
            return False

    # ── Audio Playback ────────────────────────────────────────────────────────

    def _play_audio(self, audio_file: str) -> bool:
        """Play audio file through system audio output.

        Tries: ffplay, pw-play, paplay, aplay, then falls back to subprocess.

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

        # Try PipeWire (pw-play is the newer PipeWire client)
        players.append(["pw-play", audio_file])
        # Try PulseAudio/PipeWire (legacy)
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

    # ── Speaking Backends ─────────────────────────────────────────────────────

    def _speak_edge(self, text: str) -> bool:
        """Speak using edge-tts (natural British voice, requires internet).

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

    def _speak_piper(self, text: str) -> bool:
        """Speak using Piper TTS (fully offline, high quality).

        Pipes text through piper CLI to stdout, then plays via aplay.

        Args:
            text: Text to speak.

        Returns:
            True if speech succeeded.
        """
        try:
            model_path = self._get_piper_model_path()
            if not os.path.exists(model_path):
                logger.warning("Piper model not found. Downloading...")
                if not self.download_piper_model():
                    return False

            # Run: echo "text" | piper --model model.onnx --output-raw | aplay -r 22050 -f S16_LE
            try:
                piper_proc = subprocess.Popen(
                    ["piper", "--model", model_path, "--output-raw"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                aplay_proc = subprocess.Popen(
                    ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw"],
                    stdin=piper_proc.stdout,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                if piper_proc.stdin is not None:
                    piper_proc.stdin.write(text.encode("utf-8"))
                    piper_proc.stdin.close()
                piper_proc.wait(timeout=30)
                aplay_proc.wait(timeout=30)

                if aplay_proc.returncode == 0 or piper_proc.returncode == 0:
                    return True

            except (subprocess.TimeoutExpired, BrokenPipeError):
                logger.warning("Piper TTS timed out or pipe broken")
                return False

            return False

        except Exception as e:
            logger.warning("Piper TTS failed: %s", e)
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
            cmd = ["espeak-ng", "-v", FALLBACK_VOICE, "-s", "150", "-p", "50", text]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0

        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.error("espeak-ng failed: %s", e)
            return False

    # ── Public API ────────────────────────────────────────────────────────────

    def speak(self, text: str, force_offline: bool = False) -> bool:
        """Speak text aloud using the best available TTS backend.

        Priority:
        1. edge-tts (online, natural)
        2. Piper TTS (offline, high quality)
        3. espeak-ng (offline, basic)

        Args:
            text: The text to speak.
            force_offline: If True, skip edge-tts.

        Returns:
            True if the speech was successfully played.
        """
        if not text or not text.strip():
            return False

        logger.info("Speaking: %s", text[:80])

        # Try edge-tts first (online, highest quality)
        if self.use_edge and not force_offline and self._edge_available:
            if self._speak_edge(text):
                return True
            logger.info("edge-tts failed, trying Piper...")

        # Try Piper TTS (offline, high quality)
        if self.use_piper and self._piper_available and self._piper_model_ready:
            if self._speak_piper(text):
                return True
            logger.info("Piper TTS failed, trying espeak-ng...")
        elif self.use_piper and self._piper_available and not self._piper_model_ready:
            logger.info("Piper model not cached. Attempting download...")
            if self.download_piper_model():
                if self._speak_piper(text):
                    return True

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
            force_offline: If True, skip edge-tts.

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
        return self._edge_available or self._piper_available or self._espeak_available

    @property
    def backends(self) -> list:
        """List available TTS backends."""
        backends = []
        if self._edge_available:
            backends.append("edge-tts")
        if self._piper_available:
            piper_status = "ready" if self._piper_model_ready else "no-model"
            backends.append(f"piper-tts ({piper_status})")
        if self._espeak_available:
            backends.append("espeak-ng")
        return backends

    def __repr__(self) -> str:
        return (
            f"<TTSModule voice={self.voice} "
            f"backends={self.backends}>"
        )
