"""
core/memory.py
Billiam OS — State Persistence and Personality Layer

Manages long-term memory for the AI assistant using JSON-backed persistence.
The assistant maintains its identity, user context, and learned facts across
reboots and session restarts.

The memory schema stores:
- User identity (name, role, preferences)
- Assistant profile (name, modality, personality traits)
- Cached system facts (learned information about the environment)
- Interaction history (recent conversation topics and context)
"""

import copy
import json
import os
from datetime import datetime, timezone
from typing import Any

# Default memory schema used on first initialization
DEFAULT_MEMORY_SCHEMA: dict[str, Any] = {
    "user_identity": {
        "name": "Developer",
        "role": "System Operator",
        "preferences": {},
    },
    "assistant_profile": {
        "name": "Billiam",
        "modality": "FOSS AI-OS Core — Your Personal Digital Butler",
        "personality": (
            "Impeccably polite British butler. "
            "Courteous, efficient, and safety-conscious."
        ),
    },
    "cached_system_facts": {},
    "interaction_history_tokens": [],
    "session_metadata": {
        "first_seen": None,
        "last_seen": None,
        "total_interactions": 0,
    },
}


class AssistantMemoryLayer:
    """Persistent memory layer for the AI assistant.

    Stores identity, preferences, and context in a JSON file that persists
    across system reboots. Automatically initializes with defaults on first run.

    Usage:
        memory = AssistantMemoryLayer()
        context = memory.get_context_summary()
        memory.update_fact("architecture", "x86_64")
        memory.record_interaction("user said X", "assistant replied Y")
    """

    def __init__(self, storage_path: str = "~/.config/billiam-os/memory.json"):
        """Initialize the memory layer.

        Args:
            storage_path: Path to the JSON memory file.
                          Supports ~ expansion for home directory.
        """
        self.storage_path = os.path.expanduser(storage_path)
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        # Set restrictive permissions on memory file (owner read/write only)
        if os.path.exists(self.storage_path):
            os.chmod(self.storage_path, 0o600)
        self.memory = self._load_from_disk()

    def _load_from_disk(self) -> dict[str, Any]:
        """Load memory from disk, initializing defaults if file doesn't exist.

        Returns:
            Dict containing the full memory state.
        """
        if not os.path.exists(self.storage_path):
            schema = copy.deepcopy(DEFAULT_MEMORY_SCHEMA)
            schema["session_metadata"]["first_seen"] = self._now_iso()
            schema["session_metadata"]["last_seen"] = self._now_iso()
            self._save_to_disk(schema)
            return schema

        try:
            with open(self.storage_path) as stream:
                data = json.load(stream)
            # Update last_seen timestamp
            data["session_metadata"]["last_seen"] = self._now_iso()
            self._save_to_disk(data)
            return data
        except (json.JSONDecodeError, KeyError):
            # Corrupted or invalid memory — reinitialize
            schema = copy.deepcopy(DEFAULT_MEMORY_SCHEMA)
            schema["session_metadata"]["first_seen"] = self._now_iso()
            schema["session_metadata"]["last_seen"] = self._now_iso()
            self._save_to_disk(schema)
            return schema

    def _save_to_disk(self, data: dict[str, Any] | None = None) -> None:
        """Persist memory state to disk.

        Args:
            data: Memory state to save. Uses self.memory if not provided.
        """
        with open(self.storage_path, "w") as stream:
            json.dump(data or self.memory, stream, indent=4)

    def _now_iso(self) -> str:
        """Get current ISO-8601 timestamp."""
        return datetime.now(timezone.utc).isoformat()

    # ── Public API ───────────────────────────────────────────────────────────

    def get_context_summary(self) -> str:
        """Generate a context summary string for LLM system prompt injection.

        Returns:
            A human-readable summary of the current memory state.
        """
        user = self.memory["user_identity"]
        profile = self.memory["assistant_profile"]
        return (
            f"User context: {user['name']} ({user['role']}). "
            f"Assistant Profile: {profile['name']} — {profile['modality']}. "
            f"Total interactions: {self.memory['session_metadata']['total_interactions']}."
        )

    def get_user_name(self) -> str:
        """Get the stored user name."""
        return self.memory["user_identity"]["name"]

    def set_user_info(
        self, name: str | None = None, role: str | None = None
    ) -> None:
        """Update user identity information.

        Args:
            name: New user name (optional).
            role: New user role (optional).
        """
        if name:
            self.memory["user_identity"]["name"] = name
        if role:
            self.memory["user_identity"]["role"] = role
        self._save_to_disk()

    def update_fact(self, key: str, value: Any) -> None:
        """Store a system fact in memory.

        Args:
            key: Fact identifier (e.g., 'architecture', 'default_shell').
            value: Fact value (str, int, dict, list, etc.).
        """
        self.memory["cached_system_facts"][key] = value
        self._save_to_disk()

    def get_fact(self, key: str, default: Any = None) -> Any:
        """Retrieve a stored system fact.

        Args:
            key: Fact identifier.
            default: Value to return if key is not found.

        Returns:
            The stored fact value or default.
        """
        return self.memory["cached_system_facts"].get(key, default)

    def record_interaction(
        self, user_input: str, assistant_output: str
    ) -> None:
        """Record an interaction in the history tokens.

        Args:
            user_input: The user's input text.
            assistant_output: The assistant's response text.
        """
        entry = {
            "timestamp": self._now_iso(),
            "user": user_input[:500],
            "assistant": assistant_output[:500],
        }
        self.memory["interaction_history_tokens"].append(entry)
        self.memory["session_metadata"]["total_interactions"] += 1

        # Keep history bounded at 100 entries
        if len(self.memory["interaction_history_tokens"]) > 100:
            self.memory["interaction_history_tokens"] = (
                self.memory["interaction_history_tokens"][-100:]
            )

        self._save_to_disk()

    def get_recent_interactions(self, count: int = 5) -> list[dict[str, str]]:
        """Get the most recent interaction entries.

        Args:
            count: Number of recent interactions to return.

        Returns:
            List of interaction dicts, newest first.
        """
        return self.memory["interaction_history_tokens"][-count:][::-1]

    def reset(self) -> None:
        """Reset memory to default schema (destructive)."""
        self.memory = copy.deepcopy(DEFAULT_MEMORY_SCHEMA)
        self.memory["session_metadata"]["first_seen"] = self._now_iso()
        self.memory["session_metadata"]["last_seen"] = self._now_iso()
        self._save_to_disk()

    def to_dict(self) -> dict[str, Any]:
        """Export full memory state as a dictionary."""
        return self.memory

    def __repr__(self) -> str:
        return (
            f"<AssistantMemoryLayer user={self.get_user_name()} "
            f"interactions={self.memory['session_metadata']['total_interactions']}>"
        )
