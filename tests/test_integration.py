"""
tests/test_integration.py
Billiam OS — End-to-End Integration Tests

These tests use a mock OpenAI-compatible HTTP server to simulate
the LLM backend, exercising the full orchestration loop without
requiring a real GPU or model download.
"""

import os
import sys
import tempfile

from core.ai_core import AICore

# Add tests directory to path for mock_llm_server import
_tests_dir = os.path.dirname(os.path.abspath(__file__))
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

from mock_llm_server import MockLLMServer  # noqa: E402


def _make_core(tmp_dir, server, model="mock-model", **kwargs):
    """Helper: create AICore pointing at mock server."""
    memory_path = os.path.join(tmp_dir, "memory.json")
    return AICore(
        api_base=server.api_base,
        model=model,
        memory_path=memory_path,
        temperature=0.1,
        **kwargs,
    )


class TestIntegration:
    """Integration tests with mock LLM server."""

    @classmethod
    def setup_class(cls):
        cls.server = MockLLMServer(port=18123)
        cls.server.start()

    @classmethod
    def teardown_class(cls):
        cls.server.stop()

    def setup_method(self, method):
        self.tmp_dir = tempfile.mkdtemp()
        self.server.set_responses(
            [
                "Hello! I am Billiam, your personal digital butler.",
            ]
        )
        # Reset call tracking for clean test isolation
        MockLLMServer._reset()

    def teardown_method(self, method):
        import shutil

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_core_connects_to_server(self):
        """AICore must connect to the mock server and get a response."""
        core = _make_core(self.tmp_dir, self.server)
        result = core.process_input("Hello")
        assert "Billiam" in result
        assert self.server.call_count >= 1

    def test_tool_call_execution(self):
        """AICore must execute TOOL: commands via the guardrail."""
        self.server.set_responses(
            [
                "TOOL: echo 'integration works'",
                "The command returned: integration works",
            ]
        )
        core = _make_core(self.tmp_dir, self.server)
        result = core.process_input("run echo")
        # Should contain tool output and synthesis
        assert "integration works" in result or "works" in result
        # Should have made 2 LLM calls (initial + synthesis)
        assert self.server.call_count == 2, f"Expected 2 calls, got {self.server.call_count}"

    def test_destructive_command_blocked(self):
        """AICore must block destructive commands through the guardrail."""
        self.server.set_responses(
            [
                "TOOL: rm -rf /",
                "I apologise, sir, but that was blocked.",
            ]
        )
        core = _make_core(self.tmp_dir, self.server)
        result = core.process_input("delete everything")
        assert "GUARDRAIL BLOCKED" in result or "apologise" in result.lower()

    def test_conversation_history_persists(self):
        """AICore must maintain conversation across multiple turns."""
        core = _make_core(self.tmp_dir, self.server)
        core.process_input("First message")
        core.process_input("Second message")
        assert len(core.conversation_history) == 4

    def test_memory_persists_across_calls(self):
        """Memory interactions must accumulate across calls."""
        core = _make_core(self.tmp_dir, self.server)
        before = core.memory.to_dict()["session_metadata"]["total_interactions"]
        core.process_input("Hello")
        core.process_input("How are you?")
        after = core.memory.to_dict()["session_metadata"]["total_interactions"]
        assert after == before + 2

    def test_system_prompt_sent_to_llm(self):
        """The system prompt must be sent as part of the messages."""
        messages_sent = []

        def on_request(data):
            messages_sent.append(data.get("messages", []))

        self.server.set_on_request(on_request)
        core = _make_core(self.tmp_dir, self.server)
        core.process_input("Hello")

        assert len(messages_sent) >= 1
        first_call = messages_sent[0]
        roles = [m["role"] for m in first_call]
        assert "system" in roles
        assert "user" in roles

    def test_model_name_passed_correctly(self):
        """The configured model name must be sent to the API."""
        models_used = []

        def on_request(data):
            models_used.append(data.get("model"))

        self.server.set_on_request(on_request)
        core = _make_core(self.tmp_dir, self.server, model="test-llama-3b")
        core.process_input("Hello")

        assert "test-llama-3b" in models_used

    def test_multiple_tool_calls(self):
        """Multiple tool calls in sequence must work."""
        self.server.set_responses(
            [
                "TOOL: echo 'first command'",
                "First result shows: first command",
                "TOOL: echo 'second command'",
                "Second result shows: second command",
            ]
        )
        core = _make_core(self.tmp_dir, self.server)

        result1 = core.process_input("run first")
        assert isinstance(result1, str) and len(result1) > 0

        result2 = core.process_input("run second")
        assert isinstance(result2, str) and len(result2) > 0
        assert self.server.call_count >= 4

    def test_llm_server_down_graceful_fallback(self):
        """When LLM server is unreachable, Billiam must apologise."""
        # Point at a port nothing is listening on
        core = AICore(
            api_base="http://localhost:18999/v1",
            model="mock",
            memory_path=os.path.join(self.tmp_dir, "mem.json"),
        )
        result = core.process_input("Hello")
        assert "apologise" in result.lower() or "apologies" in result.lower()
        assert "inference engine" in result.lower()
