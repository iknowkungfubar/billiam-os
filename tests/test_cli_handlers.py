"""Tests for the 'config' subcommand handler in core/cli/handlers.py.

Covers _handle_config (the `billiam config validate` command): it loads a
YAML config file, validates it against the LLM schema, and returns the
correct exit code (0 when valid, 1 on a missing or invalid config).
"""

import argparse
import os
import tempfile

import yaml

from core.cli.handlers import _handle_config


class TestHandleConfig:
    """Test the 'config' subcommand handler (_handle_config)."""

    def test_handle_config_valid_file_returns_0(self):
        """_handle_config must return 0 for a config that passes validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.yaml")
            with open(path, "w") as f:
                yaml.safe_dump({"llm": {"model": "test-model"}}, f)

            args = argparse.Namespace(file=path)

            assert _handle_config(args) == 0

    def test_handle_config_missing_file_returns_1(self):
        """_handle_config must return 1 when the config path cannot be loaded."""
        args = argparse.Namespace(file="/nonexistent/path/config.yaml")

        assert _handle_config(args) == 1

    def test_handle_config_invalid_config_returns_1(self):
        """_handle_config must return 1 for a config that fails schema validation.

        A temperature outside the allowed 0-2 range is rejected by LLMConfig,
        so validation produces errors and the handler exits with code 1.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.yaml")
            with open(path, "w") as f:
                yaml.safe_dump({"llm": {"model": "x", "temperature": 5.0}}, f)

            args = argparse.Namespace(file=path)

            assert _handle_config(args) == 1
