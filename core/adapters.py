"""Adapter classes wrapping existing billiam-os modules into pipeline protocols.

These adapters let the existing code work with CorePipeline without
modifying the original classes. Each adapter implements one protocol
from core/pipeline.py by delegating to the existing implementation.
"""
from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

from .billiam import BILLIAM_PROFILE, system_prompt_injection
from .config import get_config_value
from .memory import AssistantMemoryLayer
from .pipeline import CorePipeline, LLMBackend, MemoryProvider, OutputDriver, ToolExecutor
from .sandbox import SecureExecutionSandbox

logger = logging.getLogger("billiam.adapters")


# ── LLM Backend Adapter ──


class OpenAIBackend:
    """LLMBackend that uses OpenAI-compatible API (local or remote)."""

    def __init__(
        self,
        api_base: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        client: OpenAI | None = None,
    ):
        self.api_base = api_base
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = client or OpenAI(base_url=api_base, api_key="billiam-local-no-key-needed")

    def inference(self, messages: list[dict], temperature: float | None = None) -> str:
        """Send messages to LLM and return response text."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature if temperature is not None else self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content or ""


# ── Tool Executor Adapter ──


class SandboxExecutor:
    """ToolExecutor that uses the three-layer guardrail sandbox."""

    def __init__(self, sandbox: SecureExecutionSandbox | None = None):
        self.sandbox = sandbox or SecureExecutionSandbox()

    def execute(self, command: str) -> str:
        """Execute command through the sandbox and capture output."""
        from .sandbox import GuardrailError

        try:
            self.sandbox.validate_command(command)
            exit_code, stdout, stderr = self.sandbox.execute_safely(command)
            if exit_code != 0:
                return f"Exit {exit_code}: {stderr[:500]}" if stderr else f"Exit {exit_code}"
            return stdout[:1000] if stdout else "(completed with no output)"
        except GuardrailError as e:
            return f"[Guardrail blocked: {e}]"


# ── Memory Provider Adapter ──


class MemoryAdapter:
    """MemoryProvider wrapping AssistantMemoryLayer."""

    def __init__(self, memory: AssistantMemoryLayer):
        self.memory = memory

    def get_context_summary(self) -> str:
        return self.memory.get_context_summary()

    def record_interaction(self, user_input: str, assistant_output: str) -> None:
        self.memory.record_interaction(user_input, assistant_output)


# ── Output Driver Adapter ──


class TTSOutputDriver:
    """OutputDriver that speaks text via TTS."""

    def __init__(self, tts_module):
        self._tts = tts_module

    def deliver(self, text: str) -> None:
        self._tts.speak(text)

    def name(self) -> str:
        return "tts"


class LogOutputDriver:
    """OutputDriver that logs output (for testing/CLI mode)."""

    def __init__(self, logger_name: str = "billiam.output"):
        self._logger = logging.getLogger(logger_name)

    def deliver(self, text: str) -> None:
        self._logger.info("Response: %s", text)

    def name(self) -> str:
        return "log"


# ── Pipeline Builder ──


def build_pipeline(
    api_base: str,
    model: str,
    memory_path: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    enable_tts: bool = False,
    enable_stt: bool = False,
    client: OpenAI | None = None,
) -> CorePipeline:
    """Build a fully wired CorePipeline from configuration.

    This replaces the AICore constructor — composes the same components
    through the pipeline protocol interfaces.
    """
    llm = OpenAIBackend(
        api_base=api_base,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        client=client,
    )

    sandbox = SecureExecutionSandbox()
    executor = SandboxExecutor(sandbox=sandbox)

    memory_layer = AssistantMemoryLayer(storage_path=memory_path)
    memory = MemoryAdapter(memory=memory_layer)

    outputs: list[OutputDriver] = []
    if enable_tts:
        try:
            from .tts import TTSModule
            tts = TTSModule()
            outputs.append(TTSOutputDriver(tts))
        except Exception as e:
            logger.warning("TTS initialization failed: %s", e)

    if not outputs:
        outputs.append(LogOutputDriver())

    system_prompt = system_prompt_injection(memory_summary=memory_layer.get_context_summary())

    pipeline = CorePipeline(
        llm=llm,
        executor=executor,
        memory=memory,
        outputs=outputs,
        system_prompt=system_prompt,
    )

    return pipeline
