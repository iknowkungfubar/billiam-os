# Changelog

All notable changes to Billiam OS are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] — 2026-06-23

### Added
- **Setup wizard** (`billiam setup`): First-run wizard that checks for running LLM
  backends (Ollama on 11434, LM Studio on 1234, llama.cpp on 8080), tests TTS and STT,
  and saves configuration to `~/.config/billiam-os/config.yaml`.
- **Multi-distro install scripts**: `scripts/install-fedora.sh` and
  `scripts/install-ubuntu.sh` alongside existing Arch-based install.
- **Daemon mode**: True daemonization with PID file, signal handling, and
  `--no-fork` foreground option.
- **`billiam check` subcommand**: Validates all system dependencies (Python version,
  TTS backends, audio tools, network connectivity) in one command.
- **`billiam docs` subcommand**: Displays documentation and quick-start guide
  directly in the terminal.

### Changed
- **Piper TTS voice switched to male**: Changed default Piper voice from
  `en_GB-southern_english_female-medium` to `en_GB-vctk-k_southern_english_male-medium`
  for a British male butler persona. HuggingFace download URLs are now auto-derived
  from the voice name for easier customization.
- **Temp file security** (`scripts/billiam-voice.sh`): `mktemp` now uses 8 `X`s for
  better uniqueness; added `trap cleanup EXIT INT TERM` ensuring temp files are
  removed even on interrupt.
- **Configuration schema**: Added Pydantic validation for LLM configuration fields
  (temperature range, max_tokens > 0).

### Fixed
- **Service file** (`config/aios.service`): Corrected SystemD unit for reliable
  daemon startup.

## [1.0.0] — 2026-06-22

### Added
- **Core AI orchestration**: `AICore` class with interactive and single-request
  modes. Supports OpenAI-compatible LLM backends (Ollama, llama.cpp, LM Studio).
- **British butler persona**: Billiam, your AI butler, with a carefully crafted
  system prompt (`core/billiam.py`) enforcing polite, professional responses.
- **Voice output (TTS)**: Three-tier TTS backend:
  - `edge-tts` (online, natural British voice)
  - `Piper TTS` (offline, high-quality neural TTS)
  - `espeak-ng` (offline, robotic fallback)
- **Speech input (STT)**: `faster-whisper`-based speech-to-text with wake word
  detection (`"billiam"`) and language support.
- **3-layer security guardrail** (`core/sandbox.py`):
  - Intent classification (SAFE / DANGEROUS / SHELL / FILE)
  - Banned command patterns (rm -rf, dd, mkfs, etc.)
  - Privilege confirmation for sensitive operations
- **Persistent memory** (`core/memory.py`): Conversation history, user preferences,
  name recall, and catchphrases stored in JSON.
- **Configuration management** (`core/config.py`): YAML + env var config with
  Pydantic schema validation and default values.
- **CLI interface** (`core/cli.py`): `billiam` command with `--once`, `--voice`,
  `--stt`, `--api-base`, `--model` flags, and `config validate` / `smoke-test`
  subcommands.
- **Install script** (`scripts/install.sh`): Automated setup for Arch Linux with
  dependency detection and virtual environment creation.
- **SystemD service** (`config/aios.service`): User-level service file for
  auto-starting Billiam OS.
- **Project scaffolding**: `pyproject.toml` with ruff linting, pytest configuration,
  and proper package metadata.

### Security
- **Sandbox execution**: All shell commands go through `SecureExecutionSandbox`
  with intent classification, pattern blocking, and timeout enforcement.
- **Path traversal protection**: Sandbox rejects commands with `..`, `~`, or
  absolute paths outside allowed prefixes.
- **Dangerous command detection**: Blocks `rm -rf /`, `dd`, `mkfs`, `:(){ :|:& };:`,
  and 30+ other dangerous patterns.

[1.1.0]: https://github.com/iknowkungfubar/billiam-os/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/iknowkungfubar/billiam-os/releases/tag/v1.0.0