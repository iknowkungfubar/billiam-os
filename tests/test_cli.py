"""
tests/test_cli.py
Billiam OS -- CLI Entry Point Tests

Tests the extracted CLI module (argparse parsing, main function).
Regression tests for existing CLI behavior.
"""

import sys
from unittest.mock import patch

from core.cli import build_parser, setup_logging


class TestCLIParser:
    """Test CLI argument parser."""

    def test_build_parser(self):
        """Parser must be constructable."""
        parser = build_parser()
        assert parser is not None

    def test_parse_once(self):
        """--once flag must be parsed."""
        parser = build_parser()
        args = parser.parse_args(["--once", "hello"])
        assert args.once == "hello"

    def test_parse_voice(self):
        """--voice flag must be parsed."""
        parser = build_parser()
        args = parser.parse_args(["--voice"])
        assert args.voice is True

    def test_parse_stt(self):
        """--stt flag must be parsed."""
        parser = build_parser()
        args = parser.parse_args(["--stt"])
        assert args.stt is True

    def test_parse_daemon(self):
        """--daemon flag must be parsed."""
        parser = build_parser()
        args = parser.parse_args(["--daemon"])
        assert args.daemon is True

    def test_parse_api_base(self):
        """--api-base must be parsed."""
        parser = build_parser()
        args = parser.parse_args(["--api-base", "http://custom:9090/v1"])
        assert args.api_base == "http://custom:9090/v1"

    def test_parse_model(self):
        """--model must be parsed."""
        parser = build_parser()
        args = parser.parse_args(["--model", "custom-model"])
        assert args.model == "custom-model"

    def test_parse_version(self):
        """--version flag must be parsed."""
        parser = build_parser()
        args = parser.parse_args(["--version"])
        assert args.version is True

    def test_defaults(self):
        """All flags must default to None/False."""
        parser = build_parser()
        args = parser.parse_args([])
        assert args.once is None
        assert args.voice is False
        assert args.stt is False
        assert args.daemon is False
        assert args.api_base is None
        assert args.model is None
        assert args.version is False

    # --- Subcommand parsing ---

    def test_parse_subcommand_config(self):
        """'config' subcommand must be parsed."""
        parser = build_parser()
        args = parser.parse_args(["config"])
        assert args.command == "config"

    def test_parse_subcommand_smoke_test(self):
        """'smoke-test' subcommand must be parsed."""
        parser = build_parser()
        args = parser.parse_args(["smoke-test"])
        assert args.command == "smoke-test"

    def test_parse_subcommand_docs(self):
        """'docs' subcommand must be parsed."""
        parser = build_parser()
        args = parser.parse_args(["docs"])
        assert args.command == "docs"

    def test_parse_subcommand_check(self):
        """'check' subcommand must be parsed."""
        parser = build_parser()
        args = parser.parse_args(["check"])
        assert args.command == "check"

    def test_parse_subcommand_setup(self):
        """'setup' subcommand must be parsed."""
        parser = build_parser()
        args = parser.parse_args(["setup"])
        assert args.command == "setup"

    # --- _handle_docs ---

    def test_handle_docs_returns_0(self):
        """_handle_docs must return 0 (success)."""
        from core.cli import _handle_docs
        result = _handle_docs(None)
        assert result == 0

    # --- main() subcommand dispatch ---

    @patch("core.cli.main.AICore")
    @patch("core.cli.main.setup_logging")
    def test_main_docs_subcommand(self, mock_logging, mock_core):
        """main() with 'docs' must dispatch to _handle_docs and return 0."""
        from core.cli import main

        sys.argv = ["billiam", "docs"]
        result = main()
        assert result == 0
        mock_core.assert_not_called()

    @patch("core.cli.main.AICore")
    @patch("core.cli.main.setup_logging")
    @patch("core.tts.TTSModule")
    @patch("core.cli.handlers._check_llm_port")
    def test_main_check_subcommand(
        self, mock_check_port, mock_tts, mock_logging, mock_core
    ):
        """main() with 'check' must dispatch to _handle_check and return 0."""
        mock_tts_instance = mock_tts.return_value
        mock_tts_instance._edge_available = True
        mock_tts_instance._piper_available = True
        mock_tts_instance._espeak_available = True
        mock_tts_instance._piper_model_ready = True
        mock_check_port.return_value = (True, "Found Ollama on port 11434")

        from core.cli import main

        sys.argv = ["billiam", "check"]
        result = main()
        assert result == 0
        mock_core.assert_not_called()

    # --- _check_llm_port ---

    def test_check_llm_port_no_listener(self):
        """_check_llm_port must return (False, ...) when nothing listens."""
        from core.cli import _check_llm_port
        ok, detail = _check_llm_port(19999, "test-backend")
        assert ok is False
        assert "test-backend" in detail or "detected" in detail

    @patch("core.cli.main.AICore")
    def test_main_once(self, mock_core):
        """main() with --once must call run_once."""
        from core.cli import main

        mock_core.return_value.run_once.return_value = "test response"
        sys.argv = ["billiam", "--once", "hello"]
        result = main()
        assert result == 0
        mock_core.return_value.run_once.assert_called_once_with("hello")

    @patch("core.cli.main.AICore")
    def test_main_version(self, mock_core):
        """main() with --version must print version and exit."""
        from core.cli import main

        sys.argv = ["billiam", "--version"]
        result = main()
        assert result == 0
        mock_core.assert_not_called()

    def test_setup_logging(self):
        """setup_logging must not crash."""
        setup_logging()
