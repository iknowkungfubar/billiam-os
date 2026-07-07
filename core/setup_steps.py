"""Extracted setup steps for billiam-os CLI.

The original _handle_setup in cli.py was a 220-line procedural monolith.
Each step is now a standalone function returning a SetupResult.
SetupReporter accumulates results and renders the summary.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SetupResult:
    """Result of a single setup step."""
    name: str
    ok: bool
    detail: str = ""


@dataclass
class SetupReporter:
    """Accumulates setup step results and renders them."""
    results: list[SetupResult] = field(default_factory=list)

    def record(self, name: str, ok: bool, detail: str = "") -> None:
        self.results.append(SetupResult(name=name, ok=ok, detail=detail))
        if ok:
            print(f"  {name}")
        else:
            print(f"  X {name}: {detail}")

    def summary(self) -> int:
        """Print summary and return exit code (0 = all passed)."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.ok)
        failed = total - passed
        print(f"\nSetup complete: {passed}/{total} checks passed")
        if failed:
            print(f"{failed} check(s) need attention")
        return 0 if failed == 0 else 1


def check_llm_port(port: int, name: str) -> tuple[bool, str]:
    """Check if an LLM backend is running on a given port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        if result == 0:
            return True, "Port open"
        return False, "No response"
    except Exception as e:
        return False, str(e)


def check_llm_backends(reporter: SetupReporter) -> bool:
    """Check common LLM backend ports."""
    ports_to_check = [
        (11434, "Ollama"),
        (1234, "LM Studio"),
        (8080, "llama.cpp"),
    ]
    found = False
    for port, name in ports_to_check:
        ok, detail = check_llm_port(port, name)
        reporter.record(f"LLM: {name} (port {port})", ok, detail)
        if ok:
            found = True
    if not found:
        instructions = (
            "\n  No LLM backend detected. Start one of:\n"
            "    - Ollama:    ollama serve  (or: systemctl start ollama)\n"
            "    - LM Studio: Open app, start local inference server on port 1234\n"
            "    - llama.cpp: ./server -m model.gguf --host 0.0.0.0 --port 8080\n"
            "  Then re-run:  billiam setup"
        )
        print(instructions)
    return found


def check_tts(reporter: SetupReporter) -> bool:
    """Check TTS backend availability."""
    from .tts import TTSModule
    try:
        tts = TTSModule()
        available = tts.is_available
        backend = "Unknown"
        if available:
            # Check which backend is available
            for name in ["edge-tts", "espeak-ng", "piper"]:
                if shutil.which(name):
                    backend = name
                    break
        reporter.record(
            "Text-to-Speech (TTS)",
            available,
            backend if available else "No backend found",
        )
        return available
    except Exception as e:
        reporter.record("Text-to-Speech (TTS)", False, str(e))
        return False


def check_stt(reporter: SetupReporter) -> bool:
    """Check STT and microphone availability."""
    from .stt import STTModule
    try:
        stt = STTModule()
        # Check for capture hardware
        has_hw = stt._has_capture_hardware()
        # Try a quick model test
        model_ok = True
        try:
            stt._get_model()
        except Exception:
            model_ok = False
        ok = has_hw and model_ok
        detail = "Microphone OK" if has_hw else "No microphone"
        if not model_ok:
            detail += ", model failed to load"
        reporter.record("Speech-to-Text (STT)", ok, detail)
        return ok
    except Exception as e:
        reporter.record("Speech-to-Text (STT)", False, str(e))
        return False


def create_config(reporter: SetupReporter, config_path: str) -> bool:
    """Create default config file if it doesn't exist."""
    from .config import DEFAULT_CONFIG, save_config
    try:
        if not os.path.exists(config_path):
            save_config(DEFAULT_CONFIG, config_path)
            reporter.record("Config file created", True, config_path)
        else:
            reporter.record("Config file exists", True, config_path)
        return True
    except Exception as e:
        reporter.record("Config file", False, str(e))
        return False


def setup_systemd_service(reporter: SetupReporter) -> bool:
    """Install systemd user service for autostart."""
    service_content = """[Unit]
Description=Billiam OS - AI Personal Digital Butler
After=network.target

[Service]
Type=simple
ExecStart=%s daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""
    try:
        service_path = os.path.expanduser("~/.config/systemd/user/billiam.service")
        os.makedirs(os.path.dirname(service_path), exist_ok=True)
        billiam_bin = shutil.which("billiam") or sys.argv[0]
        with open(service_path, "w") as f:
            f.write(service_content % billiam_bin)
        # Enable and start the service
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            capture_output=True, timeout=10,
        )
        subprocess.run(
            ["systemctl", "--user", "enable", "billiam"],
            capture_output=True, timeout=10,
        )
        reporter.record("Systemd service installed", True, service_path)
        return True
    except Exception as e:
        reporter.record("Systemd service", False, str(e))
        return False


def run_setup_wizard() -> int:
    """Run the full setup wizard. Returns exit code."""
    from .config import DEFAULT_CONFIG

    config_path = os.path.expanduser("~/.config/billiam-os/config.yaml")

    print("Billiam OS -- First-Run Setup Wizard")
    print()

    reporter = SetupReporter()

    # Step 1: LLM Backend
    print("Step 1: LLM Backend Check")
    print("-" * 40)
    check_llm_backends(reporter)
    print()

    # Step 2: TTS
    print("Step 2: Text-to-Speech Check")
    print("-" * 40)
    check_tts(reporter)
    print()

    # Step 3: STT
    print("Step 3: Speech-to-Text Check")
    print("-" * 40)
    check_stt(reporter)
    print()

    # Step 4: Config
    print("Step 4: Configuration")
    print("-" * 40)
    create_config(reporter, config_path)
    print()

    # Step 5: Systemd Service
    print("Step 5: Autostart (systemd)")
    print("-" * 40)
    setup_systemd_service(reporter)
    print()

    return reporter.summary()
