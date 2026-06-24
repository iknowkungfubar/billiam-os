# Architecture

> Full system architecture documentation for Billiam OS.

## Overview

Billiam OS is a **FOSS AI-native operating system layer** for Linux. It enables
voice-controlled, agent-driven system interaction through a multi-process
architecture of specialized daemons communicating via local IPC.

## Architecture Diagram

```
                  ┌──────────────────────┐
                  │    User Microphone   │
                  └──────────┬───────────┘
                             │ Audio Stream (PipeWire/ALSA)
                             ▼
                  ┌──────────────────────┐
                  │   whisper.cpp Daemon │
                  │   (ai-audio-ingress) │
                  └──────────┬───────────┘
                             │ Text (STT Event)
                             ▼
┌──────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│ Memory Store │◄─┤   AI Core Orchestrator◄─┤  llama.cpp Server    │
│ (JSON File)  │  │   (ai-core-daemon)   │  │ (OpenVINO Backend)   │
└──────────────┘  └─────┬───────────▲────┘  └──────────────────────┘
            Bash Script │           │ Stdout/Stderr
                        ▼           │
                  ┌─────────────────┴────┐
                  │  Guardrail Sandbox   │
                  │  (Deterministic      │
                  │   + Intent Class.)   │
                  └─────────┬────────────┘
                            │ Safe Command Execution
                            ▼
                  ┌──────────────────────┐
                  │ Linux OS Subsystems  │
                  │ (Filesystem, System  │
                  │  Stats, Processes,   │
                  │  Network, etc.)      │
                  └──────────────────────┘
```

## Component Specification

### 1. AI Core Orchestrator (`core/ai_core.py`)

The central decision-making daemon. Routes user input through the full
agentic pipeline.

**Responsibilities:**
- Accept text input (from CLI or STT pipeline)
- Inject memory context into LLM system prompts
- Make LLM inference calls to the local inference engine
- Parse `TOOL:` commands from LLM output
- Route commands through the guardrail sandbox
- Feed tool results back for response synthesis
- Persist conversation history and learned facts

**IPC:** Calls `llama-server` at `localhost:8080/v1` via OpenAI-compatible API.

### 2. Guardrail Sandbox (`core/sandbox.py`)

Three-layer security system that prevents destructive operations.

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| **Layer 1** | Deterministic regex | Blocks known destructive patterns (rm -rf /, mkfs, dd, fork bombs) |
| **Layer 2** | LLM intent classification | LLM self-classifies its own command as safe/dangerous |
| **Layer 3** | Human-in-the-loop | Privileged ops (sudo, pacman, reboot) require terminal confirmation |

**Safety Philosophy:**
- Defense in depth — no single layer is trusted alone
- Layer 1 is instant and cannot be bypassed by prompt injection
- Layer 3 uses the terminal (not voice) for confirmation to prevent
  voice-command hijacking
- All guardrail violations are logged for audit

### 3. Memory Layer (`core/memory.py`)

JSON-persistent state that gives the assistant personalization memory.

**Schema:**
```json
{
  "user_identity": {
    "name": "Developer",
    "role": "System Operator",
    "preferences": {}
  },
  "assistant_profile": {
    "name": "Aura",
    "modality": "FOSS AI-OS Core"
  },
  "cached_system_facts": {},
  "interaction_history_tokens": [],
  "session_metadata": {
    "first_seen": "ISO-8601",
    "last_seen": "ISO-8601",
    "total_interactions": 0
  }
}
```

**Limits:**
- Interaction history capped at 100 most recent entries
- Individual entries truncated to 500 characters
- File location: `~/.config/aios/memory.json`

### 4. Inference Engine (`llama.cpp + OpenVINO`)

Local LLM inference server with Intel hardware acceleration.

**Build Configuration:**
```bash
cmake -B build -DGGML_OPENVINO=ON -DCMAKE_BUILD_TYPE=Release
```

**Model:** Qwen-2.5-Coder-3B-Instruct (Q4_K_M, ~1.98 GB)

**Performance Target:** >15 tokens/sec on Intel i5-8365U + UHD 620

**Server Command:**
```bash
llama-server -m qwen2.5-coder-3b.gguf --host 0.0.0.0 --port 8080 -ngl 0 -c 4096
```

### 5. Audio Pipeline (Future)

**Speech-to-Text:** `whisper.cpp` compiled with OpenVINO
- Voice Activity Detection (VAD) for wake-word detection
- Continuous listening mode with push-to-talk fallback
- Target latency: <600ms end-to-end

**Text-to-Speech:** `Kokoro-82M` via ONNX runtime
- Ultra-lightweight (82M parameters)
- CPU-friendly, runs in <100ms per utterance
- Natural prosody for conversational interaction

## Data Flow

### Voice Command Flow
```
1. [Microphone] → PipeWire audio capture
2. [whisper.cpp] → VAD detects speech → STT transcription
3. [AI Core] → Inject memory context → Call LLM
4. [LLM Response] → Parse TOOL: command or direct reply
5. [Guardrail Sandbox] → Layer 1 check → Layer 2 check → Layer 3 if needed
6. [Shell Execution] → Run command via subprocess
7. [Response Synthesis] → Feed result back to LLM
8. [TTS] → Speak response to user
```

### Text Command Flow
```
1. [User Input] → CLI input or API call
2. [AI Core] → Same as steps 3-8 above
3. [Output] → Print response to terminal
```

## System Integration

### systemd Service
- **User service** (not system-wide)
- Auto-restarts on failure (5s delay)
- Depends on `network.target` and `sound.target`
- Logs to journald

### Window Manager Integration
- **i3wm:** `bindsym $mod+space exec /path/to/billiam-os/trigger.sh`
- **Hyprland:** Similar keybind configuration
- Trigger script pipes input to `billiam --once "..."`

## Performance Budget

| Metric | Target | Measurement |
|--------|--------|-------------|
| LLM Inference | >15 tok/s | `llama-bench` |
| STT Latency | <600ms | Whisper.cpp profiling |
| Guardrail Overhead | <10ms | Python timeit |
| Memory (idle) | <1 GB | `free -h` |
| Memory (active) | <6 GB | `free -h` |
| Disk (models) | <2 GB | `du -sh models/` |
| Disk (codebase) | <1 MB | `du -sh .` |

## Known Limitations

1. **Deterministic guardrail pattern matching** cannot catch every dangerous
   variant (e.g., `rm -rf $HOME` is allowed because `$HOME` ≠ `/` or `~`).
   Layer 2 (LLM intent classification) and Layer 3 (HITL) compensate.

2. **OpenVINO on integrated GPUs** has variable performance depending on
   Intel driver versions. Test with `llama-bench` after initial setup.

3. **Single-turn tool calls** — the parser only processes one `TOOL:` per
   LLM response. Multi-step tasks require multiple iterations.

## Future Enhancements

- [ ] Voice Activity Detection (VAD) + wake word ("Hey Billiam")
- [ ] Kokoro-82M TTS integration for spoken responses
- [ ] GUI overlay (GTK/egui) showing assistant status and waveforms
- [ ] Plugin system for third-party skill integrations
- [ ] WebUI control panel for configuration
- [ ] Screen-aware mode using Vision-Language Model for visual UI control
