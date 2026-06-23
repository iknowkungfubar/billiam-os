"""
core/ai_core.py
Billiam OS — AI Core Orchestrator Daemon

The central brain of Billiam OS. Orchestrates the voice-controlled,
agent-driven personal digital assistant loop:

    1. Accept user input (text or speech-to-text transcript)
    2. Inject memory context + Billiam persona into system prompt
    3. Send to local LLM (llama.cpp / OpenVINO) via OpenAI-compatible API
    4. Parse TOOL: commands from the LLM response
    5. Execute commands through the Guardrail Sandbox
    6. Feed results back to LLM for natural language summarization
    7. Deliver response (text or TTS via British butler voice)

Architecture:
    - Runs as a systemd user service for autostart on boot
    - Stateless LLM calls with stateful memory layer
    - Three-layer guardrail system for command safety
    - Voice input via STT (faster-whisper) + wake word
    - Voice output via TTS (edge-tts British voice)
    - Hotkey integration with window manager
"""

import logging

from openai import OpenAI

from .billiam import (
    BILLIAM_PROFILE,
    get_catchphrase,
    system_prompt_injection,
)
from .config import get_config_value, load_config
from .memory import AssistantMemoryLayer
from .sandbox import GuardrailError, SecureExecutionSandbox

# ── Configuration ────────────────────────────────────────────────────────────
_CONF = load_config()
DEFAULT_LLM_API_BASE = get_config_value(_CONF, "llm.api_base")
DEFAULT_LLM_MODEL = get_config_value(_CONF, "llm.model")
DEFAULT_SYSTEM_MEMORY_PATH = get_config_value(_CONF, "memory.storage_path")
DEFAULT_LLM_TEMPERATURE = float(get_config_value(_CONF, "llm.temperature"))
DEFAULT_LLM_MAX_TOKENS = int(get_config_value(_CONF, "llm.max_tokens"))

logger = logging.getLogger("billiam.core")


class AICore:
    """The central orchestration engine for Billiam OS.

    Manages the complete interaction loop:
    memory → Billiam persona → LLM inference → tool parsing
    → guardrail execution → response (text or TTS).

    Usage:
        core = AICore()
        core.run_interactive()     # Interactive CLI mode
        core.process_input(text)   # Programmatic single-request mode
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
        client: OpenAI | None = None,
    ):
        """Initialize the AI Core with all subsystems.

        Args:
            api_base: Base URL for the OpenAI-compatible LLM API.
            model: Model name to use for inference.
            memory_path: Path to the persistent memory JSON file.
            temperature: LLM temperature for response generation.
            max_tokens: Maximum tokens in LLM response.
            enable_tts: Enable Text-to-Speech (British butler voice).
            enable_stt: Enable Speech-to-Text (wake word + voice commands).
            client: Injected OpenAI client (for testing). Creates one if None.
        """
        self.api_base = api_base
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.enable_tts = enable_tts
        self.enable_stt = enable_stt

        self.assistant_name = BILLIAM_PROFILE["name"]

        # Initialize subsystems
        self.memory = AssistantMemoryLayer(storage_path=memory_path)
        self.sandbox = SecureExecutionSandbox()

        # Initialize TTS/STT (lazy, only if enabled)
        self._tts = None
        self._stt = None
        self._audio_daemon = None
        if enable_tts or enable_stt:
            self._init_voice()

        # Initialize LLM client (accept injected for testing)
        self.client = client or OpenAI(
            base_url=api_base,
            api_key="billiam-local-no-key-needed",
        )

        # Conversation history for current session
        self.conversation_history = []

        logger.info(
            "%s initialized (model=%s, api=%s, tts=%s, stt=%s)",
            self.assistant_name,
            self.model,
            self.api_base,
            enable_tts,
            enable_stt,
        )

    def _init_voice(self) -> None:
        """Initialize voice subsystems (TTS/STT/audio)."""
        try:
            from .audio import AudioDaemon
            from .stt import STTModule
            from .tts import TTSModule

            if self.enable_tts:
                self._tts = TTSModule(
                    voice=BILLIAM_PROFILE["voice"]["voice_id"],
                )
                if not self._tts.is_available:
                    logger.warning("TTS module initialized but no backend available.")

            if self.enable_stt:
                self._stt = STTModule(
                    model_size="base",
                    wake_words=[BILLIAM_PROFILE["wake_word"]],
                )

            if self.enable_tts or self.enable_stt:
                self._audio_daemon = AudioDaemon(
                    stt_model_size="base" if self.enable_stt else None,
                    tts_voice=BILLIAM_PROFILE["voice"]["voice_id"] if self.enable_tts else None,
                    wake_word_required=True,
                )

        except ImportError as e:
            logger.warning("Voice modules not available: %s", e)

    def _build_system_prompt(self) -> str:
        """Build the system prompt with Billiam persona + memory context.

        Returns:
            The compiled system prompt string.
        """
        context = self.memory.get_context_summary()
        return system_prompt_injection(memory_summary=context)

    def _run_llm_inference(self, messages: list, temperature: float | None = None) -> str:
        """Run a single LLM inference call.

        Args:
            messages: The message list (system + history + user).
            temperature: Override temperature for this call.

        Returns:
            The LLM response text.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=self.max_tokens,
            )
            content = response.choices[0].message.content or ""
            return content.strip()
        except Exception as e:
            logger.error("LLM inference failed: %s", e)
            return (
                f"I do apologise, sir, but I seem unable to reach my "
                f"inference engine at {self.api_base}. "
                f"Would you kindly ensure llama-server is running?"
            )

    def _parse_tool_call(self, ai_output: str) -> str | None:
        """Extract a TOOL: command from the LLM output.

        Args:
            ai_output: The raw LLM response text.

        Returns:
            The extracted command string, or None if no tool call.
        """
        for line in ai_output.split("\n"):
            stripped = line.strip()
            # Handle backtick-wrapped TOOL:`command` variants first
            if stripped.upper().startswith("TOOL:`"):
                command = stripped[6:].strip("`").strip()
                if command:
                    return command
            # Handle TOOL: command variant
            if stripped.upper().startswith("TOOL:"):
                command = stripped[5:].strip()
                if command:
                    return command
        return None

    def _handle_tool_execution(self, command: str) -> str:
        """Execute a tool command through the guardrail sandbox.

        Includes Layer 3 human-in-the-loop confirmation for privileged
        operations like sudo, pacman, reboot, etc.

        Args:
            command: The bash command to execute.

        Returns:
            The command output or status message.
        """
        # Layer 3: Check for privileged operations requiring confirmation
        if self.sandbox.check_privileged(command):
            print(f"\n⚠️  {self.assistant_name} wants to execute a privileged command:")
            print(f"    `{command}`")
            print("    Type 'y' to allow, anything else to block: ", end="")
            try:
                choice = input().strip().lower()
                if choice != "y":
                    return "Action aborted by user — privileged command denied."
            except (EOFError, KeyboardInterrupt):
                return "Action aborted — input interrupted."

        # Execute through sandbox
        try:
            returncode, stdout, stderr = self.sandbox.execute_safely(command)
            if returncode == 0:
                output = stdout.strip() if stdout else "Success (no output)."
                return f"Exit code: {returncode}\nOutput:\n{output}"
            else:
                return (
                    f"Exit code: {returncode}\n"
                    f"Stderr: {stderr.strip() if stderr else 'None'}\n"
                    f"Stdout: {stdout.strip() if stdout else 'None'}"
                )
        except GuardrailError as e:
            return str(e)

    def _speak_response(self, text: str) -> None:
        """Speak the response via TTS if enabled.

        Args:
            text: Text to speak.
        """
        if self._tts and self.enable_tts:
            self._tts.speak_async(text)

    def process_input(self, user_input: str) -> str:
        """Process a single user input through the full AI orchestration loop.

        The flow:
        1. Acknowledge receipt
        2. Build system prompt with Billiam persona + memory context
        3. Run LLM inference
        4. Parse and execute any tool calls through the sandbox
        5. If tool was called, run a second LLM inference for response synthesis
        6. Record interaction in memory
        7. Speak response via TTS if enabled
        8. Return the final response

        Args:
            user_input: The user's text input.

        Returns:
            The assistant's text response.
        """
        logger.info("Processing: %s", user_input[:80])

        # ── Step 1: Build messages with system prompt ──
        system_prompt = self._build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]

        # Include recent conversation history for context
        messages.extend(self.conversation_history[-6:])

        # Add current user input
        messages.append({"role": "user", "content": user_input})

        # ── Step 2: Initial LLM Inference ──
        logger.info("Running LLM inference...")
        ai_output = self._run_llm_inference(messages)

        # ── Step 3: Parse and Execute Tool Calls ──
        tool_command = self._parse_tool_call(ai_output)
        if tool_command:
            logger.info("Tool call detected: %s", tool_command)
            tool_result = self._handle_tool_execution(tool_command)

            # Feed tool result back to LLM for response synthesis
            messages.append({"role": "assistant", "content": ai_output})
            messages.append({"role": "user", "content": f"TOOL RESULT:\n{tool_result}"})

            logger.info("Running response synthesis...")
            final_response = self._run_llm_inference(messages, temperature=0.5)

            # Record interaction
            self.memory.record_interaction(user_input, f"{ai_output}\n→ {final_response}")

            # Update conversation history
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": final_response})

            # Speak response if TTS enabled
            self._speak_response(final_response)

            return final_response
        else:
            # Standard chat response (no tool execution)
            self.memory.record_interaction(user_input, ai_output)
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": ai_output})

            # Speak response if TTS enabled
            self._speak_response(ai_output)

            return ai_output

    def run_interactive(self) -> None:
        """Run the AI core in interactive CLI mode.

        This is the primary entry point for testing and daily use.
        Type 'exit' or 'quit' to stop. Ctrl+C also works.
        """
        print(f"\n{'=' * 60}")
        print(f"  {self.assistant_name} — Your Personal Digital Butler")
        print(f"  Model: {self.model}")
        print(f"  Backend: {self.api_base}")
        print(f"  User: {self.memory.get_user_name()}")
        print(f"  TTS: {'Enabled (British voice)' if self.enable_tts else 'Disabled'}")
        print(f"  STT: {'Enabled (wake word)' if self.enable_stt else 'Disabled'}")
        print(f"{'=' * 60}")
        print("  Type your request below, or speak to me if voice is enabled.")
        print("  Examples:")
        print("    • 'What is my current RAM usage?'")
        print("    • 'Create a todo list file on my desktop'")
        print("    • 'How much disk space do I have left?'")
        print("  Type 'exit' or 'quit' to stop.")
        print(f"{'=' * 60}\n")

        print(f"{self.assistant_name}: {get_catchphrase('welcome')}\n")

        while True:
            try:
                user_in = input("👤  You: ").strip()
                if not user_in:
                    continue
                if user_in.lower() in ("exit", "quit", "/exit", "/quit"):
                    farewell = get_catchphrase("farewell")
                    print(f"\n{self.assistant_name}: {farewell}")
                    self._speak_response(farewell)
                    break

                print(f"\n🧠  {self.assistant_name} is thinking...")
                response = self.process_input(user_in)
                print(f"\n🗣️  {self.assistant_name}: {response}\n")

            except KeyboardInterrupt:
                print(f"\n\n{self.assistant_name}: {get_catchphrase('farewell')}")
                break
            except EOFError:
                break

    def run_once(self, prompt: str) -> str:
        """Process a single prompt and return the response (non-interactive).

        Useful for hotkey-triggered invocations from the window manager.

        Args:
            prompt: The user's input text.

        Returns:
            The assistant's response text.
        """
        return self.process_input(prompt)
