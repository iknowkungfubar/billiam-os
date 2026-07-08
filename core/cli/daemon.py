"""
daemon.py - Daemon lifecycle and port checking

Provides _daemonize(), _cleanup_daemon(), _run_daemon_event_loop(),
and _check_llm_port().
"""

import logging
import os
import signal
import socket
import sys

from ..ai_core import AICore
from ..billiam import BILLIAM_PROFILE

logger = logging.getLogger("billiam.cli")

_PID_FILE = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR", os.path.expanduser("~/.cache/billiam-os")),
    "billiam.pid",
)


def _daemonize(foreground: bool = False) -> None:
    """Fork into background and write PID file.

    Args:
        foreground: If True, skip forking (run in foreground with PID file).
    """
    pid_dir = os.path.dirname(_PID_FILE)
    os.makedirs(pid_dir, exist_ok=True)

    if not foreground:
        pid = os.fork()
        if pid > 0:
            # Parent exits - child continues as daemon
            sys.exit(0)
        # Child continues
        os.setsid()
        # Second fork to fully detach
        pid2 = os.fork()
        if pid2 > 0:
            sys.exit(0)
        # Grandchild continues

    # Write PID file
    with open(_PID_FILE, "w") as f:
        print(os.getpid(), file=f)

    # Redirect stdio to /dev/null for daemon mode
    if not foreground:
        sys.stdin.close()
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")

    logger.info("Daemon PID %d started (pidfile=%s)", os.getpid(), _PID_FILE)


def _cleanup_daemon(signum: int, frame) -> None:
    """Signal handler: remove PID file and exit."""
    if os.path.exists(_PID_FILE):
        os.unlink(_PID_FILE)
    logger.info("Daemon shutting down (signal %d)", signum)
    sys.exit(0)


def _check_llm_port(port: int, name: str) -> tuple[bool, str]:
    """Check if an LLM backend is listening on a port.

    Args:
        port: TCP port to check.
        name: Human-readable backend name.

    Returns:
        (ok, detail) tuple.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(("127.0.0.1", port))
        s.close()
        if result == 0:
            return True, f"Found {name} on port {port}"
        return False, f"No {name} detected on port {port}"
    except Exception as e:
        return False, str(e)


def _run_daemon_event_loop(core: AICore) -> None:
    """Daemon event loop - voice-driven, never reads from stdin.

    Sets up the STT - LLM - TTS pipeline, then sleeps until a
    signal (SIGTERM/SIGINT) triggers shutdown.  Safe to call after
    ``sys.stdin.close()`` (i.e. after daemonization).

    Args:
        core: Initialized :class:`AICore` instance.
    """
    import time

    logger.info("Daemon event loop starting")

    # Wire up STT - LLM - TTS pipeline via the audio daemon
    if core._audio_daemon:
        core._audio_daemon.set_command_callback(core.process_input)
        core._audio_daemon.start()
        wake_word = BILLIAM_PROFILE.get("wake_word", "billiam")
        logger.info("Voice listening active (wake word: '%s')", wake_word)
    else:
        logger.warning(
            "No voice subsystem available - daemon running idle. "
            "Install edge-tts and faster-whisper for voice support."
        )

    # Register signal handlers for clean shutdown (PID file removal,
    # audio daemon stop).
    signal.signal(signal.SIGTERM, _cleanup_daemon)
    signal.signal(signal.SIGINT, _cleanup_daemon)

    # Main loop - signals interrupt ``sleep()`` and trigger shutdown
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        if core._audio_daemon:
            core._audio_daemon.stop()
        logger.info("Daemon event loop exited")
