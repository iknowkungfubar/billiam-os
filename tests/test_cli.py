"""
tests/test_cli.py
Billiam OS — CLI Entry Point Tests

Tests the extracted CLI module (argparse parsing, main function).
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

    @patch("core.cli.AICore")
    def test_main_once(self, mock_core):
        """main() with --once must call run_once."""
        from core.cli import main
        mock_core.return_value.run_once.return_value = "test response"
        sys.argv = ["billiam", "--once", "hello"]
        result = main()
        assert result == 0
        mock_core.return_value.run_once.assert_called_once_with("hello")

    @patch("core.cli.AICore")
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
