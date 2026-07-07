"""
core/ai_core.py
Billiam OS -- AI Core Orchestrator Daemon

Refactored to use CorePipeline from core/pipeline.py. The pipeline
extracts the orchestration loop into composable protocol interfaces:
LLMBackend, ToolExecutor, MemoryProvider, OutputDriver.

AICore now delegates to CorePipeline for the interaction loop while
maintaining backward-compatible constructor and public API.
"""

from __future__ import annotations

import logging

from .billiam import (
    BILLIAM_PROFILE,
    get_catchphrase,
)
from .adapters import build_pipeline
from .config import get_config_value, load_config

# -- Configuration --
_CONF = load_config()
DEFAULT_LLM_API_BASE = get_config_value(_CONF, "llm.api_base")
DEFAULT_LLM_MODEL = get_config_value(_CONF, "llm.model")
DEFAULT_SYSTEM_MEMORY_PATH = get_config_value(_CONF, "memory.storage_path")
DEFAULT_LLM_TEMPERATURE = float(get_config_value(_CONF, "llm.temperature"))
DEFAULT_LLM_MAX_TOKENS = int(get_config_value(_CONF, "llm.max_tokens"))

logger = logging.getLogger("billiam.core")


class AICore:
    """The central orchestration engine for Billiam OS.

    Delegates to CorePipeline for the interaction loop.
    Backward-compatible constructor and public API.
    """

    def __init__(
        self,
        api_base: str = DEFAULT_LLM_API_BASE,
        model: str = DEFAULT_LLM_MODEL,
        memory_path: str = DEFAULT_SYSTEM_MEMORY_PATH,
        temperature: float = DEFAULT_LLM_TEMPERATURE,
        max_tokens: int = DEFAULT_LLM_MAX_TOKENS,
        enable_tts: bool = False,
        enable_stt: bool = False,
        client=None,
    ):
        self.api_base = api_base
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.enable_tts = enable_tts
        self.enable_stt = enable_stt
        self.assistant_name = BILLIAM_PROFILE["name"]

        # Build the pipeline (replaces inline subsystem init)
        self.pipeline = build_pipeline(
            api_base=api_base,
            model=model,
            memory_path=memory_path,
            temperature=temperature,
            max_tokens=max_tokens,
            enable_tts=enable_tts,
            enable_stt=enable_stt,
            client=client,
        )

        # Keep references for backward compatibility
        self._memory_layer = getattr(self.pipeline.memory, "memory", None)
        self.client = getattr(self.pipeline.llm, "client", None)

        # STT for interactive mode (not part of pipeline -- input side)
        self._stt = None
        self._audio_daemon = None
        if enable_stt:
            self._init_stt()

        logger.info(
            "%s initialized (model=%s, api=%s, tts=%s, stt=%s)",
            self.assistant_name,
            self.model,
            self.api_base,
            enable_tts,
            enable_stt,
        )

    def _init_stt(self) -> None:
        """Initialize speech-to-text subsystem."""
        try:
            from .audio import AudioDaemon
            from .stt import STTModule

            self._stt = STTModule(
                model_size="base",
                wake_words=[BILLIAM_PROFILE["wake_word"]],
            )
            self._audio_daemon = AudioDaemon(
                stt_model_size="base" if self.enable_stt else None,
                tts_voice=BILLIAM_PROFILE["voice"]["voice_id"] if self.enable_tts else None,
                wake_word_required=True,
            )
        except ImportError as e:
            logger.warning("STT modules not available: %s", e)

    def _speak_response(self, text: str) -> None:
        """Speak response via TTS if any output driver handles it."""
        for driver in self.pipeline.outputs:
            if "tts" in driver.name().lower():
                try:
                    driver.deliver(text)
                except Exception as e:
                    logger.warning("TTS output failed: %s", e)

    def process_input(self, user_input: str) -> str:
        """Process a single user input through the full AI orchestration loop.

        Delegates to CorePipeline.process() which handles:
        memory injection -> LLM inference -> tool parsing -> execution -> output delivery
        """
        logger.info("Processing: %s", user_input[:80])
        return self.pipeline.process(user_input)

    def run_interactive(self) -> None:
        """Run the AI core in interactive CLI mode."""
        import queue
        import threading

        print(f"\n{'=' * 60}")
        print(f"  {self.assistant_name} -- Your Personal Digital Butler")
        print(f"  Model: {self.model}")
        print(f"  Backend: {self.api_base}")
        print(f"  User: {self.memory.get_user_name()}")
        print(f"  TTS: {'Enabled (British voice)' if self.enable_tts else 'Disabled'}")
        print(f"  STT: {'Enabled (wake word)' if self.enable_stt else 'Disabled'}")
        print(f"{'=' * 60}")
        print("  Type your request below, or speak to me if voice is enabled.")
        print("  Type 'exit' or 'quit' to stop.")
        print(f"{'=' * 60}\n")

        print(f"{self.assistant_name}: {get_catchphrase('welcome')}\n")

        voice_queue: queue.Queue = queue.Queue()

        if self.enable_stt and self._stt:
            def _voice_listener() -> None:
                while True:
                    try:
                        text = self._stt.listen(duration=3)
                        if text and text.strip():
                            voice_queue.put(text)
                    except Exception:
                        import time
                        time.sleep(0.5)

            threading.Thread(target=_voice_listener, daemon=True).start()
            print("  Voice input active -- speak after the prompt\n")

        while True:
            try:
                user_in: str | None = None
                if self.enable_stt:
                    try:
                        user_in = voice_queue.get_nowait()
                    except queue.Empty:
                        pass

                if user_in is not None:
                    print(f"You (voice): {user_in}")
                else:
                    user_in = input("You: ").strip()
                    if not user_in:
                        continue

                if user_in.lower() in ("exit", "quit", "/exit", "/quit"):
                    farewell = get_catchphrase("farewell")
                    print(f"\n{self.assistant_name}: {farewell}")
                    self._speak_response(farewell)
                    break

                print(f"\n{self.assistant_name} is thinking...")
                response = self.process_input(user_in)
                print(f"\n{self.assistant_name}: {response}\n")

            except KeyboardInterrupt:
                print(f"\n\n{self.assistant_name}: {get_catchphrase('farewell')}")
                break
            except EOFError:
                break

    def run_once(self, prompt: str) -> str:
        """Process a single prompt and return the response (non-interactive)."""
        return self.process_input(prompt)

    # -- Backward compatibility shims for existing tests --
    # These delegate to pipeline internals so existing tests pass
    # without modification.

    @property
    def memory(self):
        """Backward compat: return the underlying AssistantMemoryLayer."""
        return self._memory_layer

    @property
    def _tts(self):
        """Backward compat: return first TTS output driver if any."""
        for driver in self.pipeline.outputs:
            if "tts" in driver.name().lower():
                return driver
        return None

    def _build_system_prompt(self) -> str:
        """Backward compat: return the pipeline's system prompt."""
        return self.pipeline.system_prompt

    def _parse_tool_call(self, ai_output: str) -> str | None:
        """Backward compat: extract TOOL: command from LLM output."""
        for line in ai_output.split("\n"):
            stripped = line.strip()
            if stripped.upper().startswith("TOOL:`"):
                command = stripped[6:].strip("`").strip()
                if command:
                    return command
            if stripped.upper().startswith("TOOL:"):
                command = stripped[5:].strip()
                if command:
                    return command
        return None

    def _handle_tool_execution(self, command: str) -> str:
        """Backward compat: execute command through the pipeline's executor."""
        try:
            return self.pipeline.executor.execute(command)
        except Exception as e:
            return str(e)
