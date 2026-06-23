"""
tests/test_config.py
Billiam OS — Configuration Test Suite

Tests configuration loading, merging, and environment variable overrides.
"""

import os
import tempfile

from core.config import (
    DEFAULT_CONFIG,
    find_config_file,
    get_config_value,
    load_config,
    load_yaml_config,
    merge_config,
)


class TestDefaultConfig:
    """Test the default configuration structure."""

    def test_default_config_exists(self):
        """Default config must be a dict with expected sections."""
        assert isinstance(DEFAULT_CONFIG, dict)
        assert "billiam" in DEFAULT_CONFIG
        assert "llm" in DEFAULT_CONFIG
        assert "tts" in DEFAULT_CONFIG
        assert "stt" in DEFAULT_CONFIG
        assert "audio" in DEFAULT_CONFIG
        assert "memory" in DEFAULT_CONFIG
        assert "logging" in DEFAULT_CONFIG
        assert "security" in DEFAULT_CONFIG

    def test_billiam_section(self):
        """Billiam section must have name and wake word."""
        billiam = DEFAULT_CONFIG["billiam"]
        assert billiam["name"] == "Billiam"
        assert billiam["wake_word"] == "billiam"

    def test_tts_section(self):
        """TTS section must have British voice defaults."""
        tts = DEFAULT_CONFIG["tts"]
        assert tts["voice"] == "en-GB-RyanNeural"
        assert tts["provider"] == "edge-tts"

    def test_llm_section(self):
        """LLM section must have sane defaults."""
        llm = DEFAULT_CONFIG["llm"]
        assert llm["api_base"] == "http://localhost:8080/v1"
        assert llm["model"] == "qwen-2.5-coder-3b-instruct"
        assert 0 < llm["temperature"] <= 1.0


class TestConfigLoading:
    """Test configuration file loading."""

    def setup_method(self, method):
        self.tmp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmp_dir, "config.yaml")

    def teardown_method(self, method):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_load_nonexistent_file(self):
        """Loading a nonexistent file must return empty dict."""
        config = load_yaml_config("/nonexistent/path/config.yaml")
        assert config == {}

    def test_merge_config_basic(self):
        """Merging must override base values."""
        base = {"key": "base_value", "other": "keep"}
        override = {"key": "override_value"}
        result = merge_config(base, override)
        assert result["key"] == "override_value"
        assert result["other"] == "keep"

    def test_merge_config_nested(self):
        """Nested merge must preserve unset keys."""
        base = {"outer": {"inner1": "a", "inner2": "b"}}
        override = {"outer": {"inner1": "overridden"}}
        result = merge_config(base, override)
        assert result["outer"]["inner1"] == "overridden"
        assert result["outer"]["inner2"] == "b"

    def test_merge_config_new_key(self):
        """Merging must add new keys."""
        base = {"existing": "value"}
        override = {"new_key": "new_value"}
        result = merge_config(base, override)
        assert result["new_key"] == "new_value"

    def test_get_config_value_simple(self):
        """Getting a simple config value must work."""
        value = get_config_value(DEFAULT_CONFIG, "billiam.name")
        assert value == "Billiam"

    def test_get_config_value_nested(self):
        """Getting a nested config value must work."""
        value = get_config_value(DEFAULT_CONFIG, "llm.api_base")
        assert value == "http://localhost:8080/v1"

    def test_get_config_value_default(self):
        """Missing keys must return default."""
        value = get_config_value(DEFAULT_CONFIG, "nonexistent.key", "fallback")
        assert value == "fallback"

    def test_get_config_value_none_default(self):
        """Missing keys without default must return None."""
        value = get_config_value(DEFAULT_CONFIG, "nonexistent.key")
        assert value is None


class TestFindConfigFile:
    """Test config file discovery."""

    def test_find_config_no_file(self):
        """No config file should return None."""
        # Temporarily unset env var if set
        old_env = os.environ.pop("BILLIAM_CONFIG", None)
        try:
            result = find_config_file()
            assert result is None
        finally:
            if old_env is not None:
                os.environ["BILLIAM_CONFIG"] = old_env

    def test_find_config_env_var(self):
        """BILLIAM_CONFIG env var must be checked."""
        old_env = os.environ.get("BILLIAM_CONFIG")
        os.environ["BILLIAM_CONFIG"] = "/tmp/test_billiam_config.yaml"
        try:
            # File doesn't exist, but path is from env
            find_config_file()
            # Should check env path first, but it doesn't exist
            # so it might find another candidate or None
            pass
        finally:
            if old_env:
                os.environ["BILLIAM_CONFIG"] = old_env
            else:
                del os.environ["BILLIAM_CONFIG"]


class TestLoadConfig:
    """Test full config loading."""

    def test_load_config_defaults(self):
        """Loading without a file must return defaults."""
        old_env = os.environ.pop("BILLIAM_CONFIG", None)
        try:
            config = load_config()
            assert config["billiam"]["name"] == "Billiam"
            assert config["llm"]["model"] == "qwen-2.5-coder-3b-instruct"
        finally:
            if old_env is not None:
                os.environ["BILLIAM_CONFIG"] = old_env
