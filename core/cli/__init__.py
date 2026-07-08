"""
core/cli - Billiam OS CLI Package

Provides the argparse interface and main() entry point.
Split from core/cli.py for maintainability:
  - main.py:     setup_logging(), build_parser(), main()
  - handlers.py: _handle_* subcommand dispatch functions
  - daemon.py:   _daemonize, _cleanup_daemon, _run_daemon_event_loop, _check_llm_port
"""

from .main import build_parser, main, setup_logging

# Re-export sub-module symbols for backward compat (tests, core/__init__.py)
from .daemon import _check_llm_port, _cleanup_daemon, _daemonize, _run_daemon_event_loop
from .handlers import _handle_check, _handle_config, _handle_docs, _handle_setup, _handle_smoke_test

__all__ = [
    "build_parser",
    "main",
    "setup_logging",
    "_check_llm_port",
    "_cleanup_daemon",
    "_daemonize",
    "_run_daemon_event_loop",
    "_handle_check",
    "_handle_config",
    "_handle_docs",
    "_handle_setup",
    "_handle_smoke_test",
]
