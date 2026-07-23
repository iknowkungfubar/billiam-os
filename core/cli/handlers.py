"""
handlers.py - CLI subcommand handlers

Each _handle_* function implements a billiam subcommand.
"""

import argparse
import os
import shutil
import sys
import tempfile

from ..billiam import system_prompt_injection
from ..config import find_config_file, load_yaml_config, validate_config
from ..memory import AssistantMemoryLayer
from ..sandbox import GuardrailError, IntentClassification, SecureExecutionSandbox
from .daemon import _check_llm_port

# NOTE: _handle_check uses inline imports for load_config and TTSModule
# to preserve test patch targets (core.cli.load_config, core.tts.TTSModule)


def _handle_docs(args: argparse.Namespace) -> int:
    """Display Billiam OS documentation.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code.
    """
    print("""
Billiam OS - Documentation
==========================

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
  core/cli/             CLI entry point with subcommands
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
    from ..config import load_config
    from ..tts import TTSModule

    passed = 0
    failed = 0

    def check(name: str, ok: bool, detail: str = ""):
        nonlocal passed, failed
        if ok:
            print(f"  / {name}")
            passed += 1
        else:
            print(f"  X {name}: {detail}")
            failed += 1

    print("Billiam OS - System Check")
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

    # Network - probe common LLM backend ports
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
        print(f"  Result: ALL {total} CHECKS PASSED /")
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
    passed = 0
    failed = 0

    def check(name: str, ok: bool, detail: str = ""):
        nonlocal passed, failed
        if ok:
            print(f"  / {name}")
            passed += 1
        else:
            print(f"  X {name}: {detail}")
            failed += 1

    print("Billiam OS Smoke Test")
    print(f"{'=' * 60}")

    # 1. Core imports
    try:
        from ..ai_core import AICore  # noqa: F401
        from ..billiam import system_prompt_injection  # noqa: F401
        from ..config import load_config  # noqa: F401
        from ..memory import AssistantMemoryLayer
        from ..sandbox import GuardrailError, IntentClassification, SecureExecutionSandbox

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
        check(
            "Persona mentions butler and TOOL format",
            "TOOL:" in prompt or "tool" in prompt.lower(),
        )
    except Exception as e:
        check("Billiam persona", False, str(e))

    # Summary
    print(f"{'=' * 60}")
    total = passed + failed
    if failed == 0:
        print(f"  Result: ALL {total} TESTS PASSED /")
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
            print(f"  X {err}")
        return 1
    else:
        print("  / Configuration is valid.")
        return 0


def _handle_setup(args: argparse.Namespace) -> int:
    """First-run setup wizard for Billiam OS.

    Delegates to setup_steps module for individual step functions.
    """
    from ..setup_steps import run_setup_wizard

    return run_setup_wizard()
