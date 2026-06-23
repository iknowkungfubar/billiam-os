"""
core/cli.py
Billiam OS — CLI Entry Point

Extracted from core/ai_core.py for testability.
Provides the argparse interface and main() entry point.
"""

import argparse
import logging
import sys

from .ai_core import AICore
from .billiam import BILLIAM_PROFILE
from .config import get_config_value, load_config

logger = logging.getLogger("billiam.cli")


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
        help="Run as a persistent daemon",
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

    # Network
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(("localhost", 8080))
        check("LLM backend (localhost:8080)", result == 0, f"connect returned {result}")
        s.close()
    except Exception as e:
        check("LLM backend (localhost:8080)", False, str(e))

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


def main() -> int:
    """CLI entry point for Billiam OS.

    Returns:
        Exit code (0 for success).
    """
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        from . import __version__
        print(f"Billiam OS v{__version__}")
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
    elif args.daemon:
        print(f"{core.assistant_name} OS Daemon starting...")
        if core._audio_daemon:
            core._audio_daemon.start()
        core.run_interactive()
    else:
        core.run_interactive()

    return 0


if __name__ == "__main__":
    sys.exit(main())
