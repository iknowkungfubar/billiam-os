# Copyright (C) 2025 Billiam OS Contributors
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
core/cli - Billiam OS CLI Package

Provides the argparse interface and main() entry point.
Split from core/cli.py for maintainability:
  - main.py:     setup_logging(), build_parser(), main()
  - handlers.py: _handle_* subcommand dispatch functions
  - daemon.py:   _daemonize, _cleanup_daemon, _run_daemon_event_loop, _check_llm_port
"""

# Re-export sub-module symbols for backward compat (tests, core/__init__.py)
from .daemon import _check_llm_port, _cleanup_daemon, _daemonize, _run_daemon_event_loop
from .handlers import _handle_check, _handle_config, _handle_docs, _handle_setup, _handle_smoke_test
from .main import build_parser, main, setup_logging

__all__ = [
    "_check_llm_port",
    "_cleanup_daemon",
    "_daemonize",
    "_handle_check",
    "_handle_config",
    "_handle_docs",
    "_handle_setup",
    "_handle_smoke_test",
    "_run_daemon_event_loop",
    "build_parser",
    "main",
    "setup_logging",
]
