# Billiam OS — AI-Powered Linux Desktop Assistant

> **Your Personal Digital Butler for Linux** 🎩  
> A fully FOSS, AI-native operating system layer that turns your Linux desktop into a voice-controllable, agent-driven personal digital assistant with a British butler personality.

[![CI](https://github.com/iknowkungfubar/billiam-os/actions/workflows/ci.yml/badge.svg)](https://github.com/iknowkungfubar/billiam-os/actions)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-green.svg)](pyproject.toml)
[![Coverage](https://img.shields.io/badge/coverage-81%25-brightgreen)](tests/)

---

## 🎯 Overview

Billiam OS is a **personalized digital assistant operating system layer** for Linux. It listens, understands, plans, executes, and speaks back — turning natural language requests into system actions. Meet **Billiam**, your impeccably polite British butler.

```
👤  You: "What's my disk usage?"
🧠  Billiam: "One moment, sir..."
🗣️  Billiam: "You have 234GB free of 512GB, sir. That's approximately 54% utilisation."
```

### Key Features

| Feature | How It Works |
|---------|-------------|
| **🎤 Voice Control** | Wake word ("Billiam...") → STT (faster-whisper) → LLM → TTS (British butler voice) |
| **🗣️ British Butler TTS** | Edge TTS `en-GB-RyanNeural` (online) + espeak-ng (offline fallback) |
| **🧠 Local LLM** | llama.cpp with OpenVINO acceleration; Qwen-2.5-Coder-3B |
| **🛡️ 3-Layer Guardrails** | Regex (L1) → Intent Classification (L2) → Human Confirmation (L3) |
| **💾 Persistent Memory** | Remembers your name, preferences, and conversation history |
| **🔧 System Control** | Execute commands, manage files, query system stats via natural language |
| **⚡ Hotkey Integration** | i3/Hyprland hotkey triggers for quick queries |
| **🚀 systemd Service** | Auto-starts on boot, restarts on failure |
| **📦 Easy Install** | Single script install with hardware auto-detection |

---

## 🖥️ System Requirements

| Requirement | Minimum | Recommended |
|------------|---------|-------------|
| **RAM** | 8 GB | **16 GB** |
| **CPU** | Any x86_64 | Intel 8th-gen+ or AMD Ryzen |
| **GPU** | None (CPU-only) | Intel iGPU (OpenVINO) or AMD/NVIDIA |
| **OS** | Arch Linux / EndeavourOS | Any Linux with systemd |
| **Storage** | 500 MB + model files (~2 GB) | 10 GB free |
| **Python** | 3.10+ | 3.11+ |
| **Audio** | Any ALSA/PipeWire device | Microphone + speakers |

**CPU-only works fine** — OpenVINO gives a ~2x speedup on Intel GPUs but is optional.

---

## 🚀 Quick Start (5 Minutes)

### 1. Install

```bash
# Clone the repo
git clone https://github.com/iknowkungfubar/billiam-os.git
cd billiam-os

# Run the installer (auto-detects your hardware)
bash scripts/install.sh
```

### 2. Start an LLM Backend

You need a local LLM server running. The easiest options:

**Option A: llama.cpp (recommended)**
```bash
bash scripts/setup_inference.sh    # Builds llama.cpp + downloads model
./llama.cpp/build/bin/llama-server \
  -m models/qwen2.5-coder-3b.gguf \
  --host 0.0.0.0 --port 8080 -ngl 0 -c 4096
```

**Option B: Ollama** (if already installed)
```bash
ollama run qwen2.5-coder:3b
# Then: export BILLIAM_API_BASE=http://localhost:11434/v1
```

### 3. Start Billiam

```bash
# Interactive text mode
python -m core.ai_core

# With British butler voice
python -m core.ai_core --voice

# Full daemon (voice + listening + auto-start)
python -m core.ai_core --daemon
```

### 4. Try It

```
👤  You: "What's my current RAM usage?"
👤  You: "Create a todo list file on my desktop"
👤  You: "List the files in my Downloads folder"
👤  You: "How much disk space do I have left?"
```

Say **"exit"** or press **Ctrl+C** to quit.

---

## 🎭 The Billiam Persona

Billiam is an **impeccably polite British butler**. Key personality traits:

- Calls you "sir" or "madam"
- Speaks with quiet authority and understated elegance
- Uses phrases like "Very good, sir", "One moment, please", "I do apologise, sir"
- Always courteous, efficient, and safety-conscious
- Jeeves meets a senior systems engineer

**Voice:** British male (en-GB-RyanNeural) via Edge TTS  
**Fallback:** espeak-ng with MBROLA British voice (offline)  
**Wake word:** "Billiam", "Hey Billiam", "Okay Billiam"

---

## 📁 Project Structure

```
billiam-os/
├── core/
│   ├── ai_core.py       # Main orchestrator — LLM loop, tool parsing
│   ├── billiam.py       # British butler personality profile
│   ├── tts.py           # Text-to-Speech (Edge TTS + espeak-ng)
│   ├── stt.py           # Speech-to-Text (faster-whisper + wake word)
│   ├── audio.py         # Audio daemon (capture/playback coordination)
│   ├── sandbox.py       # 3-Layer Guardrail (L1 regex, L2 intent, L3 HITL)
│   ├── memory.py        # JSON-persistent memory layer
│   └── config.py        # YAML + env var configuration
├── scripts/
│   ├── install.sh       # Installation & uninstallation
│   ├── setup_inference.sh  # llama.cpp + OpenVINO build
│   ├── hotkey.sh        # Window manager hotkey trigger
│   └── billiam-voice.sh # Voice command trigger
├── config/
│   └── aios.service     # systemd user service
├── tests/               # 225 tests, 81% coverage
├── docs/
│   └── architecture.md  # Full architecture documentation
├── Dockerfile           # Container build
├── Makefile             # Build, test, install automation
└── .env.example         # Environment variable reference
```

---

## 🛡️ Safety: 3-Layer Guardrail System

Billiam OS uses a **three-layer safety system** to prevent destructive commands:

| Layer | Mechanism | What It Blocks |
|-------|-----------|----------------|
| **L1** | Regex pattern matching | `rm -rf /`, `mkfs`, `dd if=`, fork bombs, etc. |
| **L2** | Intent classification | Dangerous keywords (wipe/destroy/format), risky targets (/boot,/etc,/dev) |
| **L3** | Human-in-the-loop | `sudo`, `pacman`, `reboot`, `systemctl` — user must confirm |

```
Example: "Delete everything in /boot"
  L1: No regex match (not "rm -rf /")
  L2: ⚠ DANGEROUS (score=1.5) — contains "delete", targets "/boot"
  L3: Would require confirmation due to "delete"
  → BLOCKED by Layer 2 with informative message
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BILLIAM_API_BASE` | `http://localhost:8080/v1` | LLM backend URL |
| `BILLIAM_MODEL` | `qwen-2.5-coder-3b-instruct` | Model name |
| `BILLIAM_TEMPERATURE` | `0.2` | LLM temperature |
| `BILLIAM_TTS_VOICE` | `en-GB-RyanNeural` | TTS voice |
| `BILLIAM_STT_MODEL` | `base` | Whisper model size |
| `BILLIAM_LOG_LEVEL` | `INFO` | Logging level |
| `BILLIAM_MEMORY_PATH` | `~/.config/billiam-os/memory.json` | Memory file |

### YAML Config File

Edit `~/.config/billiam-os/config.yaml`:

```yaml
billiam:
  name: Billiam
  wake_word: billiam
  polite_mode: true

llm:
  api_base: http://localhost:8080/v1
  model: qwen-2.5-coder-3b-instruct
  temperature: 0.2
  max_tokens: 512
```

---

## 🐳 Docker

```bash
docker build -t billiam-os .
docker run -it --rm \
  -v ~/.config/billiam-os:/home/user/.config/billiam-os \
  billiam-os
```

For voice support, add `--device /dev/snd`.

---

## 🧪 Testing

```bash
make test              # Run tests with coverage
make lint              # Lint with ruff
make test-quick        # Quick test run
```

Tests: **225 passing, 81% coverage**

---

## 📊 Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| LLM Inference | >15 tok/s | CPU-only, Qwen-3B Q4 |
| STT Latency | <600ms | faster-whisper base |
| Guardrail Overhead | <10ms | Per command |
| Memory (idle) | <1 GB | With LLM server running |
| Memory (active) | <6 GB | During voice conversation |

---

## 🔄 Systemd Service

```bash
# Enable auto-start
systemctl --user enable billiam-os.service
systemctl --user start billiam-os.service

# Check status
systemctl --user status billiam-os.service

# View logs
journalctl --user -u billiam-os.service -f
```

---

## ⌨️ Window Manager Integration

### i3wm
```bash
bindsym $mod+space exec ~/.config/billiam-os/scripts/hotkey.sh
bindsym $mod+v     exec ~/.config/billiam-os/scripts/billiam-voice.sh
```

### Hyprland
```bash
bind = SUPER, SPACE, exec, ~/.config/billiam-os/scripts/hotkey.sh
bind = SUPER, V, exec, ~/.config/billiam-os/scripts/billiam-voice.sh
```

---

## ❓ Troubleshooting

| Problem | Solution |
|---------|----------|
| `LLM inference failed` | Is llama-server running? Check `BILLIAM_API_BASE` |
| `No module named 'edge_tts'` | Run `pip install -r requirements.txt` |
| Voice sounds robotic | Install espeak-ng: `sudo pacman -S espeak-ng` |
| Microphone not working | Test with: `arecord test.wav` (install alsa-utils) |
| Low coverage on ai_core.py | Normal — LLM-dependent paths need a running server |
| Docker build fails | Ensure Docker is running and you have internet |

---

## 📜 License

**GNU General Public License v3.0** — 100% Free and Open Source Software.

Built with ❤️ for the FOSS community. No proprietary AI services required.

---

## 🏗️ Architecture

See [docs/architecture.md](docs/architecture.md) for the full system architecture,
component specifications, data flow diagrams, and performance budgets.
