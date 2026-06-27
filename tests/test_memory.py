"""
tests/test_memory.py
Billiam OS — Memory Layer Test Suite

Tests the JSON-persistent memory system for:
- First-run initialization with defaults
- Loading and saving user identity
- Fact storage and retrieval
- Interaction history recording
- Memory reset
"""

import json
import os
import tempfile

from core.memory import (
    AssistantMemoryLayer,
)


class TestAssistantMemoryLayer:
    """Test memory layer initialization and persistence."""

    def setup_method(self, method):
        """Create a temporary directory for each test."""
        self.tmp_dir = tempfile.mkdtemp()
        self.memory_path = os.path.join(self.tmp_dir, "memory.json")

    def teardown_method(self, method):
        """Clean up temporary files."""
        import shutil

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # ── Initialization ────────────────────────────────────────────────────

    def test_first_run_creates_defaults(self):
        """First initialization must create memory file with defaults."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        assert os.path.exists(self.memory_path)
        assert memory.get_user_name() == "Developer"

    def test_load_existing_memory(self):
        """Loading existing memory must preserve data."""
        # Create initial memory
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        memory.set_user_info(name="TestUser", role="Tester")

        # Create a new instance loading the same file
        memory2 = AssistantMemoryLayer(storage_path=self.memory_path)
        assert memory2.get_user_name() == "TestUser"

    def test_default_schema_structure(self):
        """The loaded memory must match expected schema."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        data = memory.to_dict()
        assert "user_identity" in data
        assert "assistant_profile" in data
        assert "cached_system_facts" in data
        assert "interaction_history_tokens" in data
        assert "session_metadata" in data

    # ── User Identity ─────────────────────────────────────────────────────

    def test_set_user_name(self):
        """Setting user name must persist."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        memory.set_user_info(name="Alice")
        assert memory.get_user_name() == "Alice"

        # Verify on disk
        with open(self.memory_path) as f:
            data = json.load(f)
        assert data["user_identity"]["name"] == "Alice"

    def test_set_user_role(self):
        """Setting user role must persist."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        memory.set_user_info(role="System Administrator")
        assert memory.to_dict()["user_identity"]["role"] == "System Administrator"

    def test_set_user_name_and_role(self):
        """Setting both name and role must persist both."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        memory.set_user_info(name="Bob", role="DevOps")
        data = memory.to_dict()
        assert data["user_identity"]["name"] == "Bob"
        assert data["user_identity"]["role"] == "DevOps"

    # ── Facts ─────────────────────────────────────────────────────────────

    def test_store_and_retrieve_fact(self):
        """Storing and retrieving facts must work."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        memory.update_fact("architecture", "x86_64")
        assert memory.get_fact("architecture") == "x86_64"

    def test_fact_default_value(self):
        """Missing facts must return default."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        assert memory.get_fact("nonexistent", "fallback") == "fallback"

    def test_fact_none_default_on_missing(self):
        """Missing facts without default must return None."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        assert memory.get_fact("nonexistent") is None

    def test_multiple_facts(self):
        """Multiple facts must be stored and retrievable."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        memory.update_fact("arch", "x86_64")
        memory.update_fact("kernel", "Linux")
        memory.update_fact("shell", "bash")

        assert memory.get_fact("arch") == "x86_64"
        assert memory.get_fact("kernel") == "Linux"
        assert memory.get_fact("shell") == "bash"

    def test_overwrite_fact(self):
        """Overwriting a fact must update the value."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        memory.update_fact("theme", "dark")
        memory.update_fact("theme", "light")
        assert memory.get_fact("theme") == "light"

    def test_facts_persist_across_reload(self):
        """Facts must survive a reload."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        memory.update_fact("language", "Python")

        memory2 = AssistantMemoryLayer(storage_path=self.memory_path)
        assert memory2.get_fact("language") == "Python"

    # ── Interaction History ───────────────────────────────────────────────

    def test_record_interaction(self):
        """Recording an interaction must store it."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        memory.record_interaction("hello", "hi there")
        assert memory.to_dict()["session_metadata"]["total_interactions"] == 1

    def test_interaction_history_length(self):
        """Getting recent interactions must return the right count."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        for i in range(10):
            memory.record_interaction(f"input_{i}", f"output_{i}")

        recent = memory.get_recent_interactions(count=3)
        assert len(recent) == 3

    def test_interaction_history_order(self):
        """Recent interactions must be newest-first."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        memory.record_interaction("first", "first_out")
        memory.record_interaction("second", "second_out")
        memory.record_interaction("third", "third_out")

        recent = memory.get_recent_interactions(count=3)
        assert recent[0]["user"] == "third"
        assert recent[2]["user"] == "first"

    def test_interaction_history_bounded(self):
        """Interaction history must not exceed 100 entries."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        for i in range(150):
            memory.record_interaction(f"input_{i}", f"output_{i}")

        assert len(memory.to_dict()["interaction_history_tokens"]) == 100

    def test_interaction_truncation(self):
        """Long interactions must be truncated to 500 chars."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        long_input = "a" * 1000
        memory.record_interaction(long_input, "ok")
        stored = memory.get_recent_interactions(1)[0]
        assert len(stored["user"]) == 500

    # ── Context Summary ───────────────────────────────────────────────────

    def test_context_summary_contains_user_name(self):
        """Context summary must include user name."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        memory.set_user_info(name="Charlie")
        summary = memory.get_context_summary()
        assert "Charlie" in summary

    def test_context_summary_contains_assistant_name(self):
        """Context summary must include assistant name."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        summary = memory.get_context_summary()
        assert "Billiam" in summary

    # ── Reset ─────────────────────────────────────────────────────────────

    def test_reset_clears_data(self):
        """Reset must clear all stored data."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        memory.set_user_info(name="TestUser")
        memory.update_fact("key", "value")
        memory.record_interaction("test", "response")

        memory.reset()

        assert memory.get_user_name() == "Developer"
        assert memory.get_fact("key") is None
        assert memory.to_dict()["session_metadata"]["total_interactions"] == 0

    # ── Edge Cases ────────────────────────────────────────────────────────

    def test_corrupted_json_reinitializes(self):
        """Corrupted JSON file must reinitialize with defaults."""
        # Write invalid JSON
        with open(self.memory_path, "w") as f:
            f.write("not valid json {{{")

        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        assert memory.get_user_name() == "Developer"  # Reinitialized

    def test_empty_file_reinitializes(self):
        """Empty file must reinitialize."""
        with open(self.memory_path, "w") as f:
            f.write("")

        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        assert memory.get_user_name() == "Developer"

    def test_repr_contains_info(self):
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        rep = repr(memory)
        assert "AssistantMemoryLayer" in rep
        assert "Developer" in rep

    def test_session_metadata_timestamps(self):
        """Session timestamps must be set on first run."""
        memory = AssistantMemoryLayer(storage_path=self.memory_path)
        data = memory.to_dict()
        assert data["session_metadata"]["first_seen"] is not None
        assert data["session_metadata"]["last_seen"] is not None
