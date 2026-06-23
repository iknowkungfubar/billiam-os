"""
core/ai_core.py
Billiam OS — AI Core Orchestrator Daemon

The central brain of Billiam OS. It orchestrates the voice-controlled,
agent-driven personal digital assistant loop:

    1. Accept user input (text or speech-to-text transcript)
    2. Inject memory context into system prompt
    3. Send to local LLM (llama.cpp / OpenVINO) via OpenAI-compatible API
    4. Parse TOOL: commands from the LLM response
    5. Execute commands through the Guardrail Sandbox
    6. Feed results back to LLM for natural language summarization
    7. Deliver response (text, or route to TTS)

Architecture:
    - Runs as a systemd user service for autostart on boot
    - Stateless LLM calls with stateful memory layer
    - Three-layer guardrail system for command safety
    - Hotkey integration with window manager (i3/Hyprland)
"""

import os
import sys
import json
import logging
from typing import Optional

from openai import OpenAI

from .memory import AssistantMemoryLayer
from .sandbox import SecureExecutionSandbox, GuardrailException

# ── Configuration ────────────────────────────────────────────────────────────
DEFAULT_LLM_API_BASE = os.environ.get(
    "BILLIAM_API_BASE", "http://localhost:8080/v1"
)
DEFAULT_LLM_MODEL = os.environ.get(
    "BILLIAM_MODEL", "qwen-2.5-coder-3b-instruct"
)
DEFAULT_SYSTEM_MEMORY_PATH = os.environ.get(
    "BILLIAM_MEMORY_PATH", "~/.config/aios/memory.json"
)
DEFAULT_LLM_TEMPERATURE = float(os.environ.get("BILLIAM_TEMPERATURE", "0.2"))
DEFAULT_LLM_MAX_TOKENS = int(
    os.environ.get("BILLIAM_MAX_TOKENS", "512")
)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("billiam")


class AICore:
    """The central orchestration engine for Billiam OS.

    Manages the complete interaction loop:
    memory → LLM inference → tool parsing → guardrail execution → response.

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
    ):
        """Initialize the AI Core with all subsystems.

        Args:
            api_base: Base URL for the OpenAI-compatible LLM API.
            model: Model name to use for inference.
            memory_path: Path to the persistent memory JSON file.
            temperature: LLM temperature for response generation.
            max_tokens: Maximum tokens in LLM response.
        """
        self.api_base = api_base
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Initialize subsystems
        self.memory = AssistantMemoryLayer(storage_path=memory_path)
        self.sandbox = SecureExecutionSandbox()

        # Initialize LLM client
        self.client = OpenAI(
            base_url=api_base,
            api_key="billiam-local-no-key-needed",
        )

        # Conversation history for current session
        self.conversation_history = []

        logger.info(
            "AICore initialized (model=%s, api=%s, user=%s)",
            self.model,
            self.api_base,
            self.memory.get_user_name(),
        )

    def _build_system_prompt(self) -> str:
        """Build the system prompt with dynamic memory context injection.

        Returns:
            The compiled system prompt string.
        """
        user_name = self.memory.get_user_name()
        context = self.memory.get_context_summary()

        return f"""You are {self.memory.memory['assistant_profile']['name']}, a Personalized Digital Assistant running directly on the user's Linux machine.

SYSTEM CONTEXT:
{context}

CAPABILITIES:
You can interact with the Linux operating system directly using system tools.
If the user asks you to perform an action (e.g., check system stats, create files, list files, run commands), output a system tool call exactly like this:

TOOL: [your bash command here]

Only output ONE tool call at a time. After you receive the tool output, formulate your final spoken response.

SAFETY RULES:
- Never execute rm -rf or destructive commands
- Never modify system files outside /home
- Ask for confirmation before installing packages
- If you're unsure about a command, ask the user to clarify

Keep responses concise, helpful, and assistant-centric.
"""

    def _run_llm_inference(
        self, messages: list, temperature: Optional[float] = None
    ) -> str:
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
            return f"Error: Failed to reach LLM backend at {self.api_base}. Is llama-server running?"

    def _parse_tool_call(self, ai_output: str) -> Optional[str]:
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
            print(f"\n⚠️  PRIVILEGED ACTION: The assistant wants to run:")
            print(f"    `{command}`")
            print(f"    Type 'y' to allow, anything else to block: ", end="")
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
        except GuardrailException as e:
            return str(e)

    def process_input(self, user_input: str) -> str:
        """Process a single user input through the full AI orchestration loop.

        The flow:
        1. Build system prompt with memory context
        2. Run LLM inference
        3. Parse and execute any tool calls through the sandbox
        4. If tool was called, run a second LLM inference for response synthesis
        5. Record interaction in memory
        6. Return the final response

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
        messages.extend(self.conversation_history[-6:])  # Last 3 turns

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

            # Feed tool result back for response synthesis
            messages.append({"role": "assistant", "content": ai_output})
            messages.append(
                {"role": "user", "content": f"TOOL RESULT:\n{tool_result}"}
            )

            logger.info("Running response synthesis...")
            final_response = self._run_llm_inference(
                messages, temperature=0.5
            )

            # ── Step 4: Record interaction ──
            self.memory.record_interaction(
                user_input, f"{ai_output}\n→ {final_response}"
            )

            # Update conversation history
            self.conversation_history.append(
                {"role": "user", "content": user_input}
            )
            self.conversation_history.append(
                {"role": "assistant", "content": final_response}
            )

            return final_response
        else:
            # Standard chat response (no tool execution)
            self.memory.record_interaction(user_input, ai_output)
            self.conversation_history.append(
                {"role": "user", "content": user_input}
            )
            self.conversation_history.append(
                {"role": "assistant", "content": ai_output}
            )
            return ai_output

    def run_interactive(self) -> None:
        """Run the AI core in interactive CLI mode.

        This is the primary entry point for testing and daily use.
        Type 'exit' or 'quit' to stop. Ctrl+C also works.
        """
        assistant_name = self.memory.memory["assistant_profile"]["name"]

        print(f"\n{'='*60}")
        print(f"  {assistant_name} — Billiam OS AI Assistant")
        print(f"  Model: {self.model}")
        print(f"  Backend: {self.api_base}")
        print(f"  User: {self.memory.get_user_name()}")
        print(f"{'='*60}")
        print(f"  Type your request below.")
        print(f"  Examples:")
        print(f"    • 'What is my current RAM usage?'")
        print(f"    • 'Create a todo list file on my desktop'")
        print(f"    • 'How much disk space do I have left?'")
        print(f"  Type 'exit' or 'quit' to stop.")
        print(f"{'='*60}\n")

        while True:
            try:
                user_in = input("👤  You: ").strip()
                if not user_in:
                    continue
                if user_in.lower() in ("exit", "quit", "/exit", "/quit"):
                    print(f"\n{assistant_name}: Goodbye!")
                    break

                print(f"\n🧠  {assistant_name} is thinking...")
                response = self.process_input(user_in)
                print(f"\n🗣️  {assistant_name}: {response}\n")

            except KeyboardInterrupt:
                print(f"\n\n{assistant_name}: Goodbye!")
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


# ── CLI Entry Point ──────────────────────────────────────────────────────────

def main():
    """CLI entry point for the Billiam OS AI Core.

    Usage:
        python -m core.ai_core              # Interactive mode
        python -m core.ai_core --once "..."  # Single request
        python -m core.ai_core --daemon      # Daemon mode (future)
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Billiam OS — AI Core Orchestrator Daemon"
    )
    parser.add_argument(
        "--once",
        type=str,
        help="Process a single request and exit",
        default=None,
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as a persistent daemon (future)",
    )
    parser.add_argument(
        "--api-base",
        type=str,
        default=DEFAULT_LLM_API_BASE,
        help="LLM API base URL",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_LLM_MODEL,
        help="LLM model name",
    )

    args = parser.parse_args()

    # Initialize core
    core = AICore(
        api_base=args.api_base,
        model=args.model,
    )

    if args.once:
        # Single-shot mode
        response = core.run_once(args.once)
        print(response)
    elif args.daemon:
        # Daemon mode (future: add audio capture, wake word, etc.)
        print("Daemon mode not yet implemented. Starting interactive mode...")
        core.run_interactive()
    else:
        # Interactive mode
        core.run_interactive()


if __name__ == "__main__":
    main()
