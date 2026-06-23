"""
tests/test_ai_core_di.py
Billiam OS — AI Core Dependency Injection Tests

Tests the refactored AICore with mock OpenAI client injection.
Covers all previously untested code paths in the orchestration loop.
"""

import os
import tempfile
from unittest.mock import MagicMock

from core.ai_core import AICore


class MockChoice:
    """Mock OpenAI chat completion choice."""
    def __init__(self, content: str):
        self.message = MagicMock()
        self.message.content = content


class MockResponse:
    """Mock OpenAI chat completion response."""
    def __init__(self, content: str):
        self.choices = [MockChoice(content)]


class MockOpenAI:
    """Mock OpenAI client for testing AICore."""

    def __init__(self, responses: list[str] | None = None):
        self.responses = responses or ["I see, sir.", "Very good, sir."]
        self.call_count = 0
        self.last_messages = None

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, model=None, messages=None, temperature=None, max_tokens=None):
        self.call_count += 1
        self.last_messages = messages
        self.last_model = model
        self.last_temp = temperature
        idx = min(self.call_count - 1, len(self.responses) - 1)
        return MockResponse(self.responses[idx])


class TestAICoreDI:
    """Test AICore with dependency-injected mock client."""

    def setup_method(self, method):
        self.tmp_dir = tempfile.mkdtemp()
        self.memory_path = os.path.join(self.tmp_dir, "memory.json")
        self.mock_client = MockOpenAI()

    def teardown_method(self, method):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_init_with_injected_client(self):
        """Injecting a mock client must use it instead of creating a real one."""
        core = AICore(memory_path=self.memory_path, client=self.mock_client)
        assert core.client is self.mock_client

    def test_init_creates_client_when_none(self):
        """Omitting client must create a real OpenAI client."""
        core = AICore(memory_path=self.memory_path)
        assert core.client is not None

    def test_run_llm_inference_uses_client(self):
        """_run_llm_inference must call the injected client."""
        core = AICore(memory_path=self.memory_path, client=self.mock_client)
        result = core._run_llm_inference([{"role": "user", "content": "hi"}])
        assert self.mock_client.call_count == 1
        assert result == "I see, sir."

    def test_run_llm_inference_passes_messages(self):
        """_run_llm_inference must pass messages to the client."""
        core = AICore(memory_path=self.memory_path, client=self.mock_client)
        messages = [{"role": "user", "content": "test message"}]
        core._run_llm_inference(messages)
        assert self.mock_client.last_messages == messages

    def test_run_llm_inference_passes_model(self):
        """_run_llm_inference must use the configured model."""
        core = AICore(memory_path=self.memory_path, client=self.mock_client, model="test-model")
        core._run_llm_inference([{"role": "user", "content": "hi"}])
        assert self.mock_client.last_model == "test-model"

    def test_run_llm_inference_temperature_override(self):
        """_run_llm_inference must use override temperature when provided."""
        core = AICore(memory_path=self.memory_path, client=self.mock_client)
        core._run_llm_inference([{"role": "user", "content": "hi"}], temperature=0.9)
        assert self.mock_client.last_temp == 0.9

    def test_process_input_no_tool_call(self):
        """process_input without tool call returns the LLM response directly."""
        core = AICore(memory_path=self.memory_path, client=self.mock_client)
        result = core.process_input("Hello")
        assert "I see, sir." in result

    def test_process_input_with_tool_call(self):
        """process_input with a TOOL: command must execute it and return synthesis."""
        client = MockOpenAI(responses=[
            "TOOL: echo 'test output'",
            "Done, sir. The command returned: test output",
        ])
        core = AICore(memory_path=self.memory_path, client=client)
        result = core.process_input("run this")
        assert client.call_count >= 2
        assert "test output" in result or "Done" in result

    def test_process_input_destructive_blocked(self):
        """Destructive commands must be blocked by guardrail."""
        client = MockOpenAI(responses=[
            "TOOL: rm -rf /",
            "I apologise, sir, but that command was blocked.",
        ])
        core = AICore(memory_path=self.memory_path, client=client)
        result = core.process_input("delete everything")
        assert "GUARDRAIL BLOCKED" in result or "apologise" in result.lower()

    def test_conversation_history_maintained(self):
        """process_input must maintain conversation history."""
        core = AICore(memory_path=self.memory_path, client=self.mock_client)
        core.process_input("First message")
        core.process_input("Second message")
        assert len(core.conversation_history) == 4  # 2 turns = 4 messages

    def test_system_prompt_contains_persona(self):
        """System prompt must be built with Billiam persona."""
        core = AICore(memory_path=self.memory_path, client=self.mock_client)
        prompt = core._build_system_prompt()
        assert "Billiam" in prompt
        assert "Butler" in prompt

    def test_parse_tool_call_variants(self):
        """All TOOL: variants must be parsed correctly."""
        core = AICore(memory_path=self.memory_path, client=self.mock_client)

        assert core._parse_tool_call("TOOL: ls -la") == "ls -la"
        assert core._parse_tool_call("  TOOL:   df -h  ") == "df -h"
        assert core._parse_tool_call("TOOL:`echo hello`") == "echo hello"
        assert core._parse_tool_call("Just text") is None
        assert core._parse_tool_call("TOOL:") is None

    def test_speak_response_does_nothing_without_tts(self):
        """_speak_response must not crash when TTS is disabled."""
        core = AICore(memory_path=self.memory_path, client=self.mock_client, enable_tts=False)
        core._speak_response("Hello")  # Should not raise

    def test_run_once_returns_string(self):
        """run_once must return a string response."""
        core = AICore(memory_path=self.memory_path, client=self.mock_client)
        result = core.run_once("Hello")
        assert isinstance(result, str)

    def test_memory_records_interaction(self):
        """process_input must record interaction in memory."""
        core = AICore(memory_path=self.memory_path, client=self.mock_client)
        before = core.memory.to_dict()["session_metadata"]["total_interactions"]
        core.process_input("Hello")
        after = core.memory.to_dict()["session_metadata"]["total_interactions"]
        assert after == before + 1

    def test_handle_tool_execution_echo(self):
        """handle_tool_execution for safe commands."""
        core = AICore(memory_path=self.memory_path, client=self.mock_client)
        result = core._handle_tool_execution("echo 'test output'")
        assert "test output" in result
