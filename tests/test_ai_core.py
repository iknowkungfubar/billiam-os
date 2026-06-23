"""
tests/test_ai_core.py
Billiam OS — AI Core Test Suite

Tests the main orchestration layer:
- System prompt construction with memory context
- TOOL: command parsing
- Conversation history management
- Error handling when LLM backend is unreachable
"""

import json
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from core.ai_core import AICore
from core.sandbox import GuardrailException


class TestAICoreInit:
    """Test AI Core initialization."""

    def setup_method(self, method):
        self.tmp_dir = tempfile.mkdtemp()
        self.memory_path = os.path.join(self.tmp_dir, "memory.json")

    def teardown_method(self, method):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_init_creates_memory(self):
        """Initializing AI Core must create memory file."""
        core = AICore(memory_path=self.memory_path)
        assert os.path.exists(self.memory_path)

    def test_init_sets_defaults(self):
        """AI Core must use defaults."""
        core = AICore(memory_path=self.memory_path)
        assert core.model == "qwen-2.5-coder-3b-instruct"
        assert core.api_base == "http://localhost:8080/v1"
        assert core.temperature == 0.2


class TestSystemPrompt:
    """Test system prompt construction."""

    def setup_method(self, method):
        self.tmp_dir = tempfile.mkdtemp()
        self.memory_path = os.path.join(self.tmp_dir, "memory.json")
        self.core = AICore(memory_path=self.memory_path)

    def teardown_method(self, method):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    
    def test_system_prompt_contains_user_name(self):
        """System prompt must include user name from memory."""
        self.core.memory.set_user_info(name="Alice")
        prompt = self.core._build_system_prompt()
        assert "Alice" in prompt

    def test_system_prompt_contains_assistant_name(self):
        """System prompt must include assistant profile name."""
        prompt = self.core._build_system_prompt()
        assert "Aura" in prompt

    def test_system_prompt_contains_tool_instructions(self):
        """System prompt must include TOOL: format instruction."""
        prompt = self.core._build_system_prompt()
        assert "TOOL:" in prompt

    def test_system_prompt_contains_safety_rules(self):
        """System prompt must include safety rules."""
        prompt = self.core._build_system_prompt()
        assert "safety" in prompt.lower() or "never" in prompt.lower()


class TestToolParsing:
    """Test TOOL: command extraction from LLM output."""

    def setup_method(self, method):
        self.tmp_dir = tempfile.mkdtemp()
        self.memory_path = os.path.join(self.tmp_dir, "memory.json")
        self.core = AICore(memory_path=self.memory_path)

    def teardown_method(self, method):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    
    def test_parse_simple_tool_call(self):
        """Parse a standard TOOL: command."""
        result = self.core._parse_tool_call("TOOL: df -h")
        assert result == "df -h"

    def test_parse_tool_call_with_output(self):
        """Parse TOOL: when there's surrounding text."""
        result = self.core._parse_tool_call(
            "I'll check that for you.\nTOOL: df -h\nLet me see..."
        )
        assert result == "df -h"

    def test_parse_no_tool_call(self):
        """No TOOL: prefix must return None."""
        result = self.core._parse_tool_call(
            "Hello! How can I help you today?"
        )
        assert result is None

    def test_parse_multiple_tool_calls(self):
        """Only the first TOOL: command must be returned."""
        result = self.core._parse_tool_call(
            "TOOL: echo first\nTOOL: echo second"
        )
        assert result == "echo first"

    def test_parse_backtick_wrapped(self):
        """TOOL:`command` syntax must work."""
        result = self.core._parse_tool_call("TOOL:`ls -la`")
        assert result == "ls -la"

    def test_parse_empty_tool(self):
        """TOOL: with nothing after it must return None (no command)."""
        result = self.core._parse_tool_call("TOOL:")
        assert result is None


class TestProcessInput:
    """Test the main process_input flow with mocked LLM."""

    def setup_method(self, method):
        self.tmp_dir = tempfile.mkdtemp()
        self.memory_path = os.path.join(self.tmp_dir, "memory.json")
        self.core = AICore(memory_path=self.memory_path)

    def teardown_method(self, method):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    
    def test_llm_unreachable_returns_error(self):
        """When the LLM backend is unreachable, return a helpful error."""
        result = self.core.process_input("Hello")
        # The process_input should handle the connection error gracefully
        assert "Failed to reach LLM backend" in result
        assert "Is llama-server running?" in result

    def test_conversation_history_grows(self):
        """Each process_input must add to conversation history."""
        # With no real LLM, this records an error response
        self.core.process_input("Hello")
        assert len(self.core.conversation_history) > 0

    def test_memory_records_interaction(self):
        """Each process_input must record in memory."""
        before = self.core.memory.to_dict()["session_metadata"][
            "total_interactions"
        ]
        self.core.process_input("Hello")
        after = self.core.memory.to_dict()["session_metadata"][
            "total_interactions"
        ]
        assert after == before + 1


class TestHandleToolExecution:
    """Test tool execution through the sandbox."""

    def setup_method(self, method):
        self.tmp_dir = tempfile.mkdtemp()
        self.memory_path = os.path.join(self.tmp_dir, "memory.json")
        self.core = AICore(memory_path=self.memory_path)

    def teardown_method(self, method):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    
    def test_execute_safe_command(self):
        """Safe commands must execute and return output."""
        result = self.core._handle_tool_execution("echo 'hello world'")
        assert "hello world" in result

    def test_execute_destructive_blocked(self):
        """Destructive commands must be blocked by guardrail."""
        result = self.core._handle_tool_execution("rm -rf /")
        assert "GUARDRAIL BLOCKED" in result
        assert "banned security pattern" in result
