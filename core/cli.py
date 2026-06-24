"""
core/cli.py
Billiam OS — CLI Entry Point

Extracted from core/ai_core.py for testability.
Provides the argparse interface and main() entry point.
"""

import argparse
import logging
import os
import signal
import sys

from .ai_core import AICore
from .billiam import BILLIAM_PROFILE
from .config import get_config_value, load_config

logger = logging.getLogger("billiam.cli")

_PID_FILE = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR", os.path.expanduser("~/.cache/billiam-os")),
    "billiam.pid",
)


def setup_logging() -> None:
    """Configure root logger from config."""
    config = load_config()
    level = get_config_value(config, "logging.level", "INFO")
    fmt = get_config_value(
        config,
        "logging.format",
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logging.basicConfig(level=level, format=fmt)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description=f"{BILLIAM_PROFILE['name']} OS — AI Core Orchestrator",
    )
    parser.add_argument(
        "--once",
        type=str,
        help="Process a single request and exit",
        default=None,
    )
    parser.add_argument(
        "--voice", "--tts",
        action="store_true",
        help="Enable voice output (British butler TTS)",
    )
    parser.add_argument(
        "--stt",
        action="store_true",
        help="Enable speech-to-text (wake word + voice commands)",
    )
    parser.add_argument(
        "--api-base",
        type=str,
        default=None,
        help="LLM API base URL (overrides config)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM model name (overrides config)",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as a persistent system daemon (forks, writes PID file, handles signals)",
    )
    parser.add_argument(
        "--no-fork",
        action="store_true",
        help="With --daemon, run in foreground (do not fork)",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command")

    # Config subcommand
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_parser.add_argument(
        "action",
        nargs="?",
        choices=["validate"],
        default="validate",
        help="Config action (default: validate)",
    )
    config_parser.add_argument(
        "--file", "-f",
        type=str,
        default=None,
        help="Path to config file to validate",
    )

    # Smoke-test subcommand
    subparsers.add_parser("smoke-test", help="Run smoke tests to verify the system works")

    # Docs subcommand
    subparsers.add_parser("docs", help="Open documentation in browser or show in terminal")

    # Check subcommand
    subparsers.add_parser("check", help="Validate all system dependencies")

    # Setup wizard subcommand
    subparsers.add_parser("setup", help="First-run wizard: checks LLM, tests voice, saves config")

    return parser


def _handle_docs(args: argparse.Namespace) -> int:
    """Display Billiam OS documentation.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code.
    """
    print("""
Billiam OS — Documentation
===========================

Quick Start:
  billiam --once "What's my hostname?"
    Process a single request and exit.

  billiam --voice
    Interactive mode with British butler voice.

  billiam smoke-test
    Run diagnostics to verify the system works.

  billiam check
    Validate all system dependencies.

  billiam config validate
    Validate your configuration file.

Architecture:
  core/ai_core.py       Main orchestration loop
  core/cli.py           CLI entry point with subcommands
  core/tts.py           Text-to-Speech (Piper/espeak/edge-tts)
  core/stt.py           Speech-to-Text (faster-whisper)
  core/sandbox.py       3-layer security guardrail
  core/memory.py        Persistent memory layer
  core/config.py        YAML + env config with validation

Configuration:
  Config file: ~/.config/billiam-os/config.yaml
  Env vars:    BILLIAM_API_BASE, BILLIAM_MODEL, etc.

Online docs: https://github.com/iknowkungfubar/billiam-os
""")
    return 0


def _handle_check(args: argparse.Namespace) -> int:
    """Validate all system dependencies and report status.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 = all good).
    """
    import shutil
    import socket
    import sys

    from .config import load_config
    from .tts import TTSModule

    passed = 0
    failed = 0

    def check(name: str, ok: bool, detail: str = ""):
        nonlocal passed, failed
        if ok:
            print(f"  ✓ {name}")
            passed += 1
        else:
            print(f"  ✗ {name}: {detail}")
            failed += 1

    print("Billiam OS — System Check")
    print("=" * 60)

    check("Python 3.10+", sys.version_info >= (3, 10), f"Python {sys.version}")

    # Core deps
    tts = TTSModule(use_edge=False, use_piper=False)  # Don't trigger downloads
    check("Config loads", bool(load_config()))
    check("edge-tts available", tts._edge_available)
    check("piper-tts installed", tts._piper_available)
    check("espeak-ng installed", tts._espeak_available)
    check("Piper model cached", tts._piper_model_ready)

    # Audio playback tools
    for tool in ["ffplay", "paplay", "aplay"]:
        check(f"Audio player: {tool}", bool(shutil.which(tool)))

    # Audio capture tools
    for tool in ["arecord", "parec"]:
        check(f"Audio capture: {tool}", bool(shutil.which(tool)))

    # Network — probe common LLM backend ports
    ports_to_check = [
        (11434, "Ollama"),
        (1234, "LM Studio / OpenAI-compatible"),
        (8080, "llama.cpp / common"),
    ]
    any_llm = False
    for port, name in ports_to_check:
        ok, detail = _check_llm_port(port, name)
        check(f"LLM backend {name} (port {port})", ok, detail)
        if ok:
            any_llm = True
    if not any_llm:
        check("LLM backend (any)", False, "No LLM backend detected on common ports")

    print("=" * 60)
    total = passed + failed
    if failed == 0:
        print(f"  Result: ALL {total} CHECKS PASSED ✓")
        return 0
    else:
        print(f"  Result: {passed}/{total} passed, {failed} failed")
        return 1


def _handle_smoke_test(args: argparse.Namespace) -> int:
    """Run comprehensive smoke tests to verify Billiam OS is functional.

    Tests:
    1. Core module imports
    2. Configuration loading
    3. Memory initialization
    4. Guardrail security (blocks bad, allows safe)
    5. Intent classification
    6. Billiam persona

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 = all pass).
    """
    import os
    import tempfile

    passed = 0
    failed = 0

    def check(name: str, ok: bool, detail: str = ""):
        nonlocal passed, failed
        if ok:
            print(f"  ✓ {name}")
            passed += 1
        else:
            print(f"  ✗ {name}: {detail}")
            failed += 1

    print("Billiam OS Smoke Test")
    print(f"{'=' * 60}")

    # 1. Core imports
    try:
        from core.ai_core import AICore  # noqa: F401
        from core.billiam import system_prompt_injection  # noqa: F401
        from core.config import load_config  # noqa: F401
        from core.memory import AssistantMemoryLayer
        from core.sandbox import GuardrailError, IntentClassification, SecureExecutionSandbox
        check("All core modules import correctly", True)
    except ImportError as e:
        check("All core modules import correctly", False, str(e))

    # 2. Configuration
    try:
        config = load_config()
        assert "billiam" in config
        assert "llm" in config
        check("Configuration loads with defaults", True)
    except Exception as e:
        check("Configuration loads with defaults", False, str(e))

    # 3. Memory initialization
    try:
        tmp_dir = tempfile.mkdtemp()
        mem_path = os.path.join(tmp_dir, "test_memory.json")
        mem = AssistantMemoryLayer(storage_path=mem_path)
        assert mem.get_user_name() == "Developer"
        check("Memory layer initializes", True)
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as e:
        check("Memory layer initializes", False, str(e))

    # 4. Guardrail - blocks dangerous
    try:
        sandbox = SecureExecutionSandbox()
        sandbox.validate_command("rm -rf /")
        check("Guardrail blocks dangerous commands", False, "Command was not blocked")
    except GuardrailError:
        check("Guardrail blocks dangerous commands", True)
    except Exception as e:
        check("Guardrail blocks dangerous commands", False, str(e))

    # 5. Guardrail - allows safe
    try:
        rc, stdout, stderr = sandbox.execute_safely("echo 'smoke test'")
        check("Guardrail allows safe commands", rc == 0, f"exit code {rc}")
    except Exception as e:
        check("Guardrail allows safe commands", False, str(e))

    # 6. Intent classification
    try:
        cls, score, _ = IntentClassification.classify("echo hello")
        check("Intent classification (safe)", cls == "SAFE", f"got {cls}")
        cls2, score2, _ = IntentClassification.classify("format /dev/sda1")
        check(
            "Intent classification (dangerous)",
            cls2 == "DANGEROUS",
            f"got {cls2} (score={score2:.1f})",
        )
    except Exception as e:
        check("Intent classification", False, str(e))

    # 7. Billiam persona
    try:
        prompt = system_prompt_injection()
        check("Billiam persona in system prompt", "Billiam" in prompt and "Butler" in prompt)
        check("Persona mentions butler and TOOL format",
              "TOOL:" in prompt or "tool" in prompt.lower())
    except Exception as e:
        check("Billiam persona", False, str(e))

    # Summary
    print(f"{'=' * 60}")
    total = passed + failed
    if failed == 0:
        print(f"  Result: ALL {total} TESTS PASSED ✓")
        return 0
    else:
        print(f"  Result: {passed}/{total} passed, {failed} failed")
        return 1


def _handle_config(args: argparse.Namespace) -> int:
    """Handle the 'config' subcommand.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code.
    """
    from .config import find_config_file, load_yaml_config, validate_config

    config_path = args.file or find_config_file()
    if not config_path:
        print("No config file found.")
        return 1

    print(f"Validating: {config_path}")
    data = load_yaml_config(config_path)
    errors = validate_config(data)

    if errors:
        print(f"Found {len(errors)} error(s):")
        for err in errors:
            print(f"  ✗ {err}")
        return 1
    else:
        print("  ✓ Configuration is valid.")
        return 0


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
            # Parent exits — child continues as daemon
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
    import socket
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
    """Daemon event loop — voice-driven, never reads from stdin.

    Sets up the STT → LLM → TTS pipeline, then sleeps until a
    signal (SIGTERM/SIGINT) triggers shutdown.  Safe to call after
    ``sys.stdin.close()`` (i.e. after daemonization).

    Args:
        core: Initialized :class:`AICore` instance.
    """
    import time

    logger.info("Daemon event loop starting")

    # Wire up STT → LLM → TTS pipeline via the audio daemon
    if core._audio_daemon:
        core._audio_daemon.set_command_callback(core.process_input)
        core._audio_daemon.start()
        wake_word = BILLIAM_PROFILE.get("wake_word", "billiam")
        logger.info("Voice listening active (wake word: '%s')", wake_word)
    else:
        logger.warning(
            "No voice subsystem available — daemon running idle. "
            "Install edge-tts and faster-whisper for voice support."
        )

    # Register signal handlers for clean shutdown (PID file removal,
    # audio daemon stop).
    signal.signal(signal.SIGTERM, _cleanup_daemon)
    signal.signal(signal.SIGINT, _cleanup_daemon)

    # Main loop — signals interrupt ``sleep()`` and trigger shutdown
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        if core._audio_daemon:
            core._audio_daemon.stop()
        logger.info("Daemon event loop exited")


def _handle_setup(args: argparse.Namespace) -> int:
    """First-run setup wizard for Billiam OS.

    Checks for a running LLM backend, tests TTS and STT,
    and saves a configuration file.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 = all good).
    """
    import shutil
    import sys
    import tempfile
    import time

    from .config import DEFAULT_CONFIG, save_config
    from .stt import STTModule
    from .tts import TTSModule

    CONFIG_PATH = os.path.expanduser("~/.config/billiam-os/config.yaml")

    results: list[dict] = []

    def record(name: str, ok: bool, detail: str = ""):
        results.append({"name": name, "ok": ok, "detail": detail})
        if ok:
            print(f"  ✓ {name}")
        else:
            print(f"  ✗ {name}: {detail}")

    print("╔" + "═" * 58 + "╗")
    print("║  Billiam OS — First-Run Setup Wizard                ║")
    print("╚" + "═" * 58 + "╝")
    print()

    # ── Step 1: LLM Backend ────────────────────────────────────────
    print("Step 1: LLM Backend Check")
    print("-" * 40)

    ports_to_check = [
        (11434, "Ollama"),
        (1234, "LM Studio"),
        (8080, "llama.cpp"),
    ]

    found_llm = False
    for port, name in ports_to_check:
        ok, detail = _check_llm_port(port, name)
        record(f"LLM: {name} (port {port})", ok, detail)
        if ok:
            found_llm = True

    if not found_llm:
        instructions = (
            "\n  No LLM backend detected. Start one of:\n"
            "    • Ollama:    ollama serve  (or: systemctl start ollama)\n"
            "    • LM Studio: Open app, start local inference server on port 1234\n"
            "    • llama.cpp: ./server -m model.gguf --host 0.0.0.0 --port 8080\n"
            "  Then re-run:  billiam setup"
        )
        print(instructions)
        print()

    # ── Step 2: TTS Test ───────────────────────────────────────────
    print("Step 2: TTS (Text-to-Speech) Test")
    print("-" * 40)

    tts = TTSModule(use_edge=False, use_piper=True)
    available_backends = tts.backends
    if available_backends:
        record("TTS backends available", True, f"Found: {', '.join(available_backends)}")
    else:
        record("TTS backends available", False, "No TTS backend found")

    if tts.is_available:
        print("  → Playing test phrase: 'Hello, I am Billiam, your AI butler.'")
        ok = tts.speak("Hello, I am Billiam, your AI butler.", force_offline=True)
        record("TTS playback test", ok, "Spoke test phrase" if ok else "Playback failed")
    else:
        record("TTS playback test", False, "No TTS backend to test")

    print()

    # ── Step 3: STT Test ───────────────────────────────────────────
    print("Step 3: STT (Speech-to-Text) Test")
    print("-" * 40)

    has_recording_tool = bool(shutil.which("arecord") or shutil.which("parec"))
    record("Recording tool available", has_recording_tool,
           "arecord or parec found" if has_recording_tool else "Install arecord (alsa-utils) or parec (pulseaudio-utils)")

    if has_recording_tool:
        print("  → Loading speech recognition model (first-time download is ~1.5GB)...")
        import concurrent.futures

        stt = None
        stt_init_future = None
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            stt_init_future = executor.submit(STTModule, model_size="tiny")
            try:
                stt = stt_init_future.result(timeout=120)
            except concurrent.futures.TimeoutError:
                record("STT module init", False,
                       "Timed out downloading model (>120s). Check your internet connection.")
            except Exception as e:
                record("STT module init", False, str(e))

        if stt is not None:
            record("STT module initialized", True)

            # Record a short sample
            tmp_wav = os.path.join(tempfile.mkdtemp(), "setup_test.wav")
            recorder = None
            if shutil.which("arecord"):
                recorder = ["arecord", "-r", "16000", "-c", "1", "-f", "S16_LE",
                            "-d", "2", tmp_wav]
            elif shutil.which("parec"):
                recorder = ["parec", "--rate=16000", "--channels=1",
                            "--format=s16le", "--record", "2",
                            f"--file={tmp_wav}"]

            if recorder:
                print("  → Recording 2 seconds of audio for STT test...")
                print("  → (Speak a short phrase now)")
                try:
                    subprocess.run(recorder, capture_output=True, timeout=5)
                    # Transcribe
                    text = stt.transcribe(tmp_wav)
                    if text and text.strip():
                        record("STT transcription test", True,
                               f"Transcribed: '{text.strip()[:60]}'")
                    else:
                        record("STT transcription test", False,
                               "No speech detected (try speaking louder)")
                except Exception as e:
                    record("STT transcription test", False, str(e))
                finally:
                    # Cleanup
                    import shutil as shu
                    shu.rmtree(os.path.dirname(tmp_wav), ignore_errors=True)
            else:
                record("STT recording", False, "No audio capture tool found")
    else:
        record("STT recording", False, "No recording tool (install alsa-utils)")

    print()

    # ── Step 4: Save Config ────────────────────────────────────────
    print("Step 4: Save Configuration")
    print("-" * 40)

    # Merge detected settings into default config
    config = DEFAULT_CONFIG.copy()
    config["billiam"]["name"] = "Billiam"
    config["billiam"]["wake_word"] = "billiam"
    config["billiam"]["polite_mode"] = True

    # If we found an LLM, set the api_base based on first found
    for port, name in ports_to_check:
        ok, _ = _check_llm_port(port, name)
        if ok:
            if port == 11434:
                config["llm"]["api_base"] = "http://localhost:11434/v1"
                config["llm"]["model"] = "qwen2.5-coder:3b"
            elif port == 1234:
                config["llm"]["api_base"] = "http://localhost:1234/v1"
            elif port == 8080:
                config["llm"]["api_base"] = "http://localhost:8080/v1"
            break

    ok = save_config(config, CONFIG_PATH)
    if ok:
        record("Configuration saved", True, f"Saved to {CONFIG_PATH}")
    else:
        record("Configuration saved", False, "Failed to save config")

    print()

    # ── Summary ────────────────────────────────────────────────────
    print("╔" + "═" * 58 + "╗")
    print("║  Setup Summary                                          ║")
    print("╚" + "═" * 58 + "╝")

    passed = sum(1 for r in results if r["ok"])
    failed = sum(1 for r in results if not r["ok"])
    total = len(results)

    for r in results:
        status = "✓" if r["ok"] else "✗"
        print(f"  {status} {r['name']}")

    print()
    if failed == 0:
        print(f"  Result: ALL {total} CHECKS PASSED ✓")
        print("  Billiam OS is ready to use!")
    else:
        print(f"  Result: {passed}/{total} passed, {failed} failed")
        print("  Some checks need attention. Review the details above.")
        print("  Re-run: billiam setup")

    return 0 if failed == 0 else 1


def main() -> int:
    """CLI entry point for Billiam OS.

    Returns:
        Exit code (0 for success).
    """
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        try:
            import importlib.metadata
            ver = importlib.metadata.version("billiam-os")
        except Exception:
            from . import __version__  # noqa: F811
            ver = __version__
        print(f"Billiam OS v{ver}")
        return 0

    # Handle subcommands
    if args.command == "config":
        return _handle_config(args)
    elif args.command == "smoke-test":
        return _handle_smoke_test(args)
    elif args.command == "docs":
        return _handle_docs(args)
    elif args.command == "check":
        return _handle_check(args)
    elif args.command == "setup":
        return _handle_setup(args)

    # Deprecation warning for --daemon when used without actual daemon intent
    # (old behavior was just interactive with voice — now it truly daemonizes)
    if args.daemon:
        logger.info(
            "--daemon now performs true daemonization (fork+PID+signals). "
            "For interactive mode with voice use: billiam --voice --stt"
        )

    # Allow CLI args to override config defaults
    config = load_config()
    api_base = args.api_base or get_config_value(config, "llm.api_base", "http://localhost:8080/v1")
    model = args.model or get_config_value(config, "llm.model", "qwen-2.5-coder-3b-instruct")

    core = AICore(
        api_base=api_base,
        model=model,
        enable_tts=args.voice or args.daemon,
        enable_stt=args.stt or args.daemon,
    )

    if args.once:
        response = core.run_once(args.once)
        print(response)
        return 0

    if args.daemon:
        print(f"{core.assistant_name} OS Daemon starting...")
        _daemonize(foreground=args.no_fork)
        _run_daemon_event_loop(core)
    else:
        core.run_interactive()

    return 0


if __name__ == "__main__":
    sys.exit(main())
