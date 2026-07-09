"""
main.py - CLI entry point setup and dispatch

Provides setup_logging(), build_parser(), and main().
"""

import argparse
import logging
import sys

from ..ai_core import AICore
from ..billiam import BILLIAM_PROFILE
from ..config import get_config_value, load_config
from .daemon import _daemonize, _run_daemon_event_loop
from .handlers import _handle_check, _handle_config, _handle_docs, _handle_setup, _handle_smoke_test

logger = logging.getLogger("billiam.cli")


def setup_logging() -> None:
    """Configure root logger from config."""
    config = load_config()
    level = get_config_value(config, "logging.level", "INFO")
    fmt = get_config_value(
        config,
        "logging.format",
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logging.basicConfig(level=level, format=fmt)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description=f"{BILLIAM_PROFILE['name']} OS - AI Core Orchestrator",
    )
    parser.add_argument(
        "--once",
        type=str,
        help="Process a single request and exit",
        default=None,
    )
    parser.add_argument(
        "--voice",
        "--tts",
        action="store_true",
        help="Enable voice output (British butler TTS)",
    )
    parser.add_argument(
        "--stt",
        action="store_true",
        help="Enable speech-to-text (wake word + voice commands)",
    )
    parser.add_argument(
        "--api-base",
        type=str,
        default=None,
        help="LLM API base URL (overrides config)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM model name (overrides config)",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as a persistent system daemon (forks, writes PID file, handles signals)",
    )
    parser.add_argument(
        "--no-fork",
        action="store_true",
        help="With --daemon, run in foreground (do not fork)",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command")

    # Config subcommand
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_parser.add_argument(
        "action",
        nargs="?",
        choices=["validate"],
        default="validate",
        help="Config action (default: validate)",
    )
    config_parser.add_argument(
        "--file",
        "-f",
        type=str,
        default=None,
        help="Path to config file to validate",
    )

    # Smoke-test subcommand
    subparsers.add_parser("smoke-test", help="Run smoke tests to verify the system works")

    # Docs subcommand
    subparsers.add_parser("docs", help="Open documentation in browser or show in terminal")

    # Check subcommand
    subparsers.add_parser("check", help="Validate all system dependencies")

    # Setup wizard subcommand
    subparsers.add_parser("setup", help="First-run wizard: checks LLM, tests voice, saves config")

    return parser


def main() -> int:
    """CLI entry point for Billiam OS.

    Returns:
        Exit code (0 for success).
    """
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        try:
            import importlib.metadata

            ver = importlib.metadata.version("billiam-os")
        except Exception:
            from .. import __version__  # noqa: F811

            ver = __version__
        print(f"Billiam OS v{ver}")
        return 0

    # Handle subcommands
    if args.command == "config":
        return _handle_config(args)
    elif args.command == "smoke-test":
        return _handle_smoke_test(args)
    elif args.command == "docs":
        return _handle_docs(args)
    elif args.command == "check":
        return _handle_check(args)
    elif args.command == "setup":
        return _handle_setup(args)

    # Deprecation warning for --daemon when used without actual daemon intent
    # (old behavior was just interactive with voice - now it truly daemonizes)
    if args.daemon:
        logger.info(
            "--daemon now performs true daemonization (fork+PID+signals). "
            "For interactive mode with voice use: billiam --voice --stt"
        )

    # Allow CLI args to override config defaults
    config = load_config()
    api_base = args.api_base or get_config_value(config, "llm.api_base", "http://localhost:8080/v1")
    model = args.model or get_config_value(config, "llm.model", "qwen-2.5-coder-3b-instruct")

    core = AICore(
        api_base=api_base,
        model=model,
        enable_tts=args.voice or args.daemon,
        enable_stt=args.stt or args.daemon,
    )

    if args.once:
        response = core.run_once(args.once)
        print(response)
        return 0

    if args.daemon:
        print(f"{core.assistant_name} OS Daemon starting...")
        _daemonize(foreground=args.no_fork)
        _run_daemon_event_loop(core)
    else:
        core.run_interactive()

    return 0


if __name__ == "__main__":
    sys.exit(main())
