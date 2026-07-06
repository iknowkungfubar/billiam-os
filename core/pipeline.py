"""Pipeline protocols and orchestration for billiam-os.

Extracted from AICore to create testable seams between pipeline stages.
Each stage is a protocol — inject different implementations for testing
or to add new capabilities.
"""
from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger("billiam.pipeline")


# ── Protocols (interfaces for each pipeline stage) ──


@runtime_checkable
class LLMBackend(Protocol):
    """LLM inference protocol. Implementations: OpenAI, llama.cpp, mock."""

    def inference(self, messages: list[dict], temperature: float | None = None) -> str:
        """Send messages to LLM and return response text."""
        ...


@runtime_checkable
class ToolExecutor(Protocol):
    """Tool/command execution protocol with safety guardrails."""

    def execute(self, command: str) -> str:
        """Execute a command string and return result output."""
        ...


@runtime_checkable
class MemoryProvider(Protocol):
    """Memory/persistence protocol. Implementations: JSON file, SQLite, in-memory."""

    def get_context_summary(self) -> str:
        """Return a summary of relevant context for the LLM prompt."""
        ...

    def record_interaction(self, user_input: str, assistant_output: str) -> None:
        """Record a user-assistant interaction."""
        ...


@runtime_checkable
class OutputDriver(Protocol):
    """Output delivery protocol. Implementations: TTS, text, GUI notification."""

    def deliver(self, text: str) -> None:
        """Deliver output text to the user."""
        ...

    def name(self) -> str:
        """Human-readable name of this output driver."""
        ...


# ── Core Pipeline ──


class CorePipeline:
    """Pluggable pipeline for the billiam interaction loop.

    Stages:
        input → memory_inject → llm_call → parse → execute → output

    Each stage is a protocol, so implementations are swappable.
    """

    def __init__(
        self,
        llm: LLMBackend,
        executor: ToolExecutor,
        memory: MemoryProvider,
        outputs: list[OutputDriver] | None = None,
        system_prompt: str = "",
    ):
        self.llm = llm
        self.executor = executor
        self.memory = memory
        self.outputs = outputs or []
        self.system_prompt = system_prompt
        self.conversation_history: list[dict] = []

    def process(self, user_input: str) -> str:
        """Run the full pipeline for a single user input.

        Returns the assistant's text response.
        """
        # 1. Build messages with memory context
        context = self.memory.get_context_summary()
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": f"Context: {context}"},
            *self.conversation_history[-10:],  # last 10 turns
            {"role": "user", "content": user_input},
        ]

        # 2. LLM inference
        response = self.llm.inference(messages)

        # 3. Parse and execute tool calls if present
        tool_result = self._try_extract_tool(response)
        if tool_result is not None:
            # Feed tool result back to LLM for summarization
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"Tool output: {tool_result}\nSummarize naturally."})
            final_response = self.llm.inference(messages)
        else:
            final_response = response

        # 4. Record interaction in memory
        self.memory.record_interaction(user_input, final_response)
        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": final_response})

        # 5. Deliver output through all drivers
        for driver in self.outputs:
            try:
                driver.deliver(final_response)
            except Exception as e:
                logger.warning("Output driver %s failed: %s", driver.name(), e)

        return final_response

    def _try_extract_tool(self, text: str) -> str | None:
        """Extract and execute a tool command from LLM output.

        Returns tool output string if found, None otherwise.
        """
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("TOOL:"):
                command = line[5:].strip()
                try:
                    return self.executor.execute(command)
                except Exception as e:
                    return f"[Tool error: {e}]"
        return None
