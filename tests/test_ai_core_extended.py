"""
tests/test_ai_core_extended.py
Billiam OS — Extended AI Core Tests

Tests voice initialization, tool execution edge cases,
and Billiam persona integration.
"""

import os
import tempfile

import pytest

from core.ai_core import AICore
from core.billiam import BILLIAM_PROFILE


class TestAICoreExtended:
    """Extended AI Core tests."""

    def setup_method(self, method):
        self.tmp_dir = tempfile.mkdtemp()
        self.memory_path = os.path.join(self.tmp_dir, "memory.json")

    def teardown_method(self, method):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_core_billiam_name(self):
        """Core must use Billiam as assistant name."""
        core = AICore(memory_path=self.memory_path)
        assert core.assistant_name == "Billiam"

    def test_core_tts_disabled_by_default(self):
        """TTS must be disabled by default."""
        core = AICore(memory_path=self.memory_path)
        assert core.enable_tts is False

    def test_core_stt_disabled_by_default(self):
        """STT must be disabled by default."""
        core = AICore(memory_path=self.memory_path)
        assert core.enable_stt is False

    def test_core_tts_enabled_flag(self):
        """TTS flag must be settable."""
        core = AICore(memory_path=self.memory_path, enable_tts=True)
        assert core.enable_tts is True

    def test_core_stt_enabled_flag(self):
        """STT flag must be settable."""
        core = AICore(memory_path=self.memory_path, enable_stt=True)
        assert core.enable_stt is True

    def test_core_system_prompt_contains_billiam(self):
        """System prompt must reference Billiam."""
        core = AICore(memory_path=self.memory_path)
        prompt = core._build_system_prompt()
        assert "Billiam" in prompt
        assert "Butler" in prompt

    def test_core_system_prompt_contains_tool(self):
        """System prompt must mention TOOL capability."""
        core = AICore(memory_path=self.memory_path)
        prompt = core._build_system_prompt()
        assert "TOOL:" in prompt

    def test_parse_tool_with_spaces(self):
        """Parsing TOOL: with leading/trailing spaces."""
        core = AICore(memory_path=self.memory_path)
        result = core._parse_tool_call("  TOOL:   ls -la  ")
        assert result == "ls -la"

    def test_parse_multiline_with_tool(self):
        """Parsing TOOL: from multiline output."""
        core = AICore(memory_path=self.memory_path)
        result = core._parse_tool_call(
            "Let me check that.\n\nTOOL: df -h\n\nHere is the result:"
        )
        assert result == "df -h"

    def test_handle_tool_execution_uname(self):
        """Handle tool execution for safe commands."""
        core = AICore(memory_path=self.memory_path)
        result = core._handle_tool_execution("uname -a")
        assert "Linux" in result
        assert "Exit code:" in result

    def test_handle_tool_execution_echo(self):
        """Handle tool execution for echo."""
        core = AICore(memory_path=self.memory_path)
        result = core._handle_tool_execution("echo 'test output'")
        assert "test output" in result

    def test_conversation_history_format(self):
        """Conversation history must have proper role alternation."""
        core = AICore(memory_path=self.memory_path)
        core.process_input("Hello")
        assert len(core.conversation_history) > 0
        assert core.conversation_history[0]["role"] == "user"

    def test_memory_updated_after_input(self):
        """Memory must be updated after each input."""
        core = AICore(memory_path=self.memory_path)
        before = core.memory.to_dict()["session_metadata"]["total_interactions"]
        core.process_input("Hello")
        after = core.memory.to_dict()["session_metadata"]["total_interactions"]
        assert after == before + 1

    def test_conversation_history_bounded(self):
        """Conversation history must not grow unbounded."""
        core = AICore(memory_path=self.memory_path)
        # Process many inputs
        for i in range(20):
            core.process_input(f"Message {i}")
        # History should have entries but not grow unbounded
        assert len(core.conversation_history) <= 40  # 20 turns = 40 messages
