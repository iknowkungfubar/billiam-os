"""
tests/test_config_extended.py
Billiam OS — Extended Configuration Tests

Covers config saving, environment variable overrides,
and file-based loading edge cases.
"""

import os
import tempfile

from core.config import (
    DEFAULT_CONFIG,
    load_config,
    load_yaml_config,
    merge_config,
    save_config,
)


class TestConfigSave:
    """Test saving configuration to YAML files."""

    def setup_method(self, method):
        self.tmp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmp_dir, "config.yaml")

    def teardown_method(self, method):
        import shutil

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_save_and_reload(self):
        """Saving config and reloading must preserve values."""
        config = DEFAULT_CONFIG.copy()
        config["billiam"]["name"] = "TestName"
        result = save_config(config, self.config_path)
        assert result is True
        assert os.path.exists(self.config_path)

        reloaded = load_yaml_config(self.config_path)
        assert reloaded["billiam"]["name"] == "TestName"

    def test_save_creates_directory(self):
        """Save must create parent directories."""
        deep_path = os.path.join(self.tmp_dir, "subdir", "nested", "config.yaml")
        config = DEFAULT_CONFIG.copy()
        result = save_config(config, deep_path)
        assert result is True
        assert os.path.exists(deep_path)

    def test_load_config_with_explicit_path(self):
        """Load with explicit path must use that file."""
        config = DEFAULT_CONFIG.copy()
        config["llm"]["model"] = "test-model"
        save_config(config, self.config_path)

        loaded = load_config(path=self.config_path)
        assert loaded["llm"]["model"] == "test-model"

    def test_load_config_preserves_defaults(self):
        """Load with partial config must preserve default values."""
        partial = {"billiam": {"name": "CustomBilliam"}}
        save_config(partial, self.config_path)

        loaded = load_config(path=self.config_path)
        assert loaded["billiam"]["name"] == "CustomBilliam"
        assert loaded["llm"]["model"] == DEFAULT_CONFIG["llm"]["model"]


class TestConfigEnvOverride:
    """Test environment variable overrides."""

    def setup_method(self, method):
        self.env_vars = {}

    def teardown_method(self, method):
        for var in self.env_vars:
            os.environ.pop(var, None)

    def _set_env(self, key, value):
        self.env_vars[key] = value
        os.environ[key] = value

    def test_env_api_base_override(self):
        """BILLIAM_API_BASE env var must override config."""
        self._set_env("BILLIAM_API_BASE", "http://custom:9090/v1")
        config = load_config()
        assert config["llm"]["api_base"] == "http://custom:9090/v1"

    def test_env_model_override(self):
        """BILLIAM_MODEL env var must override config."""
        self._set_env("BILLIAM_MODEL", "custom-model")
        config = load_config()
        assert config["llm"]["model"] == "custom-model"

    def test_env_temperature_override(self):
        """BILLIAM_TEMPERATURE env var must override as float."""
        self._set_env("BILLIAM_TEMPERATURE", "0.8")
        config = load_config()
        assert config["llm"]["temperature"] == 0.8

    def test_env_log_level_override(self):
        """BILLIAM_LOG_LEVEL env var must override."""
        self._set_env("BILLIAM_LOG_LEVEL", "DEBUG")
        config = load_config()
        assert config["logging"]["level"] == "DEBUG"

    def test_env_invalid_temperature(self):
        """Invalid temperature env var must not crash."""
        self._set_env("BILLIAM_TEMPERATURE", "not-a-number")
        config = load_config()
        assert config["llm"]["temperature"] == float(DEFAULT_CONFIG["llm"]["temperature"])


class TestMergeConfigExtended:
    """Extended merge tests."""

    def test_merge_empty_override(self):
        """Empty override must return base unchanged."""
        result = merge_config({"a": 1}, {})
        assert result == {"a": 1}

    def test_merge_deep_nested(self):
        """Deep nesting must merge correctly."""
        base = {"level1": {"level2": {"level3": "old"}}}
        override = {"level1": {"level2": {"level3": "new"}}}
        result = merge_config(base, override)
        assert result["level1"]["level2"]["level3"] == "new"

    def test_merge_new_nested_key(self):
        """New nested keys must be added."""
        base = {"level1": {"existing": "value"}}
        override = {"level1": {"new": "added"}}
        result = merge_config(base, override)
        assert result["level1"]["existing"] == "value"
        assert result["level1"]["new"] == "added"


class TestLoadYamlConfig:
    """Test YAML loading edge cases."""

    def setup_method(self, method):
        self.tmp_dir = tempfile.mkdtemp()

    def teardown_method(self, method):
        import shutil

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_load_empty_yaml(self):
        """Empty file must return empty dict."""
        path = os.path.join(self.tmp_dir, "empty.yaml")
        with open(path, "w") as f:
            f.write("")
        config = load_yaml_config(path)
        assert config == {}

    def test_load_invalid_yaml(self):
        """Invalid YAML must not crash, return empty dict."""
        path = os.path.join(self.tmp_dir, "bad.yaml")
        with open(path, "w") as f:
            f.write("{{invalid: yaml: :broken")
        config = load_yaml_config(path)
        assert config == {}
