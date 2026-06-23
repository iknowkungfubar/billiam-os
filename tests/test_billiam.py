"""
tests/test_billiam.py
Billiam OS — Billiam Persona Test Suite

Tests the British butler personality profile and catchphrase system.
"""

import pytest
from core.billiam import (
    BILLIAM_PROFILE,
    CATCHPHRASES,
    system_prompt_injection,
    get_greeting,
    get_catchphrase,
)


class TestBilliamProfile:
    """Test the Billiam persona definition."""

    def test_profile_name(self):
        """Billiam's name must be Billiam."""
        assert BILLIAM_PROFILE["name"] == "Billiam"

    def test_profile_title(self):
        """Billiam must have a title."""
        assert "title" in BILLIAM_PROFILE
        assert BILLIAM_PROFILE["title"] != ""

    def test_profile_personality(self):
        """Billiam's personality must be defined."""
        assert "personality" in BILLIAM_PROFILE
        assert "British" in BILLIAM_PROFILE["personality"]

    def test_profile_voice_config(self):
        """Billiam must have voice configuration."""
        voice = BILLIAM_PROFILE["voice"]
        assert "provider" in voice
        assert "voice_id" in voice
        assert "en-GB" in voice["voice_id"]  # British voice

    def test_profile_has_wake_word(self):
        """Billiam must have a wake word."""
        assert BILLIAM_PROFILE["wake_word"] == "billiam"

    def test_profile_speech_patterns(self):
        """Billiam must have speech patterns defined."""
        patterns = BILLIAM_PROFILE["speech_patterns"]
        assert "greeting" in patterns
        assert "farewell" in patterns
        assert "acknowledgment" in patterns

    def test_profile_stt_language(self):
        """STT language must be English."""
        assert BILLIAM_PROFILE["stt_language"] == "en"


class TestCatchphrases:
    """Test Billiam's catchphrase system."""

    def test_catchphrases_exist(self):
        """Catchphrases must be defined."""
        assert len(CATCHPHRASES) > 0

    @pytest.mark.parametrize(
        "category",
        ["welcome", "affirmative", "negative", "thinking", "error", "success"],
    )
    def test_category_exists(self, category):
        """Each required category must exist."""
        assert category in CATCHPHRASES
        assert len(CATCHPHRASES[category]) > 0

    def test_get_greeting(self):
        """get_greeting must return a non-empty string."""
        greeting = get_greeting()
        assert isinstance(greeting, str)
        assert len(greeting) > 0

    def test_get_catchphrase(self):
        """get_catchphrase must return a phrase from the category."""
        phrase = get_catchphrase("welcome")
        assert phrase in CATCHPHRASES["welcome"]

    def test_get_catchphrase_unknown_category(self):
        """Unknown category returns the category name back."""
        phrase = get_catchphrase("unknown_category_xyz")
        assert phrase == "unknown_category_xyz"

    def test_all_catchphrases_are_strings(self):
        """Every catchphrase must be a non-empty string."""
        for category, phrases in CATCHPHRASES.items():
            for phrase in phrases:
                assert isinstance(phrase, str)
                assert len(phrase) > 0


class TestSystemPromptInjection:
    """Test the system prompt builder."""

    def test_system_prompt_contains_name(self):
        """System prompt must contain Billiam's name."""
        prompt = system_prompt_injection()
        assert "Billiam" in prompt

    def test_system_prompt_contains_title(self):
        """System prompt must contain Billiam's title."""
        prompt = system_prompt_injection()
        assert "Butler" in prompt or "butler" in prompt

    def test_system_prompt_contains_tool_instruction(self):
        """System prompt must mention TOOL: capability."""
        prompt = system_prompt_injection()
        assert "TOOL:" in prompt

    def test_system_prompt_contains_safety(self):
        """System prompt must mention safety."""
        prompt = system_prompt_injection()
        assert "SAFETY" in prompt.upper()

    def test_system_prompt_with_memory(self):
        """System prompt must include memory context when provided."""
        prompt = system_prompt_injection(memory_summary="Test user context")
        assert "Test user context" in prompt

    def test_system_prompt_empty_memory(self):
        """System prompt must work without memory context."""
        prompt = system_prompt_injection()
        assert "Billiam" in prompt
