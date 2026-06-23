# Billiam OS — AI-Powered Linux OS Layer

> A fully FOSS, AI-native operating system layer that turns your Linux desktop into a voice-controllable, agent-driven personal digital assistant.

## Overview

Billiam OS is a **personalized digital assistant operating system layer** for Linux. It listens, understands, plans, executes, and speaks back — turning natural language requests into system actions. Built on 100% Free and Open Source Software.

### Architecture

```
                  ┌──────────────────────┐
                  │    User Microphone   │
                  └──────────┬───────────┘
                             │ Audio Stream
                             ▼
                  ┌──────────────────────┐
                  │   whisper.cpp Daemon │
                  └──────────┬───────────┘
                             │ Text (STT) Event
                             ▼
┌──────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│ Memory Store │◄─┤   AI Core Orchestrator◄─┤  llama.cpp Server    │
│ (JSON/Redis) │  └─────┬───────────▲────┘  │ (OpenVINO Backend)   │
└──────────────┘        │           │       └──────────────────────┘
            Bash Script │           │ Stdout/Stderr
                        ▼           │
                  ┌─────────────────┴────┐
                  │  Deterministic       │
                  │  Guardrail Sandbox   │
                  └─────────┬────────────┘
                            │ Safe Command Execution
                            ▼
                  ┌──────────────────────┐
                  │ Linux OS Subsystems  │
                  └──────────────────────┘
```

### Components

| Component | Role | Technology |
|-----------|------|------------|
| **AI Core Orchestrator** | Central decision loop — routes input to LLM, processes tool calls, manages conversation | Python + llama.cpp |
| **Guardrail Sandbox** | Three-layer safety — regex filter, intent classification, human-in-the-loop confirmation | Python (subprocess) |
| **Memory Layer** | Persistent personalization — remembers user identity, preferences, facts across sessions | JSON file |
| **Inference Engine** | Local LLM inference server with Intel OpenVINO acceleration | llama.cpp / llama-server |
| **Audio Capture** | Voice activity detection and speech-to-text | whisper.cpp |
| **Voice Synthesis** | Text-to-speech output | Kokoro-82M (ONNX) |

### Three-Layer Guardrail System

```
 [User Input]
      │
      ▼
┌───────────┐     Matched Banned Keyword? (e.g., "rm -rf")
│  Layer 1  ├──────────────────────────────────────────────┐
└─────┬─────┘                                              │
      │ No                                                 │
      ▼                                                    │
┌───────────┐     LLM Classifies Action: Safe or Dangerous? │
│  Layer 2  ├────────────────────────────────────────┐     │
└─────┬─────┘                                        │     │
      │ Safe                                         │     │
      ▼                                              ▼     ▼
┌───────────┐                                  ┌───────────────┐
│  Layer 3  │                                  │ Intercept &   │
│ Execute   │                                  │ Require Voice │
└───────────┘                                  │ Confirmation  │
                                               └───────────────┘
```

## Target Hardware

- **Tested on:** Dell Latitude 5400
- **CPU:** Intel i5-8365U (8th gen, 4 cores, 8 threads)
- **RAM:** 16 GB DDR4
- **GPU:** Intel UHD Graphics 620 (integrated)
- **OS Base:** EndeavourOS (Arch Linux)

## Quick Start

### 1. System Dependencies

```bash
sudo pacman -Syu
sudo pacman -S --needed base-devel cmake git python-pip openvino opencl-intel pipewire wireplumber
```

### 2. Set Up Inference Engine

```bash
bash scripts/setup_inference.sh
```

This compiles `llama.cpp` with OpenVINO support and downloads the Qwen-2.5-Coder-3B-Instruct model.

### 3. Launch the Server

```bash
./llama.cpp/build/bin/llama-server \
  -m models/qwen2.5-coder-3b.gguf \
  --host 0.0.0.0 \
  --port 8080 \
  -ngl 0 \
  -c 4096
```

> **Note:** `-ngl 0` means no GPU offloading (CPU + iGPU via OpenVINO). The OpenVINO backend in llama.cpp uses the Intel GPU automatically when built with `-DGGML_OPENVINO=ON`.

### 4. Run the Assistant

```bash
python -m core.ai_core
```

### 5. (Optional) Enable systemd Service

```bash
cp config/aios.service ~/.config/systemd/user/
systemctl --user enable --now aios.service
```

## Project Structure

```
billiam-os/
├── core/
│   ├── __init__.py          # Package init
│   ├── ai_core.py           # Main orchestrator daemon
│   ├── sandbox.py           # Guardrail execution sandbox
│   └── memory.py            # State persistence and personality layer
├── scripts/
│   └── setup_inference.sh   # llama.cpp + OpenVINO build automation
├── tests/
│   ├── test_sandbox.py      # Guardrail unit tests
│   ├── test_memory.py       # Memory layer tests
│   └── test_ai_core.py      # AI core integration tests
├── config/
│   └── aios.service         # systemd user unit
├── docs/
│   └── architecture.md      # Full architecture documentation
├── models/                  # GGUF model files (downloaded by setup script)
├── requirements.txt         # Python dependencies
├── LICENSE                  # GPL-3.0
├── pyproject.toml           # Project metadata
└── README.md                # This file
```

## Performance Targets

| Metric | Target |
|--------|--------|
| Inference Speed | > 15 tokens/sec (Qwen-2.5-Coder-3B, OpenVINO) |
| STT Latency | < 0.6s processing delay |
| Memory Usage | < 6GB RAM during active loop |
| Guardrail Overhead | < 10ms per command |

## Safety

Billiam OS uses a **three-layer guardrail** system to prevent destructive commands:

1. **Layer 1 (Deterministic):** Regex-based banned pattern matching (rm -rf, mkfs, dd, fork bombs, etc.)
2. **Layer 2 (Intent):** LLM classifies its own generated commands as safe or dangerous
3. **Layer 3 (Human-in-the-Loop):** Privileged operations (sudo, pacman, reboot) require explicit confirmation

## License

GNU General Public License v3.0 — See [LICENSE](LICENSE).

Built with ❤️ for the FOSS community.
