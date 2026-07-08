"""Tests for setup_steps.py -- Billiam OS setup wizard steps.

Tests the SetupReporter, check_llm_port, and create_config modules
which handle the first-run setup wizard output and checks.
"""

import os
import socket
import threading
import tempfile

from core.setup_steps import (
    SetupReporter,
    SetupResult,
    check_llm_port,
    create_config,
)


class TestSetupReporter:
    """Test the SetupReporter accumulation and summary logic."""

    def test_record_adds_result(self):
        """record() must append a SetupResult to the results list."""
        reporter = SetupReporter()
        reporter.record("test check", True, "all good")
        assert len(reporter.results) == 1
        result = reporter.results[0]
        assert result.name == "test check"
        assert result.ok is True
        assert result.detail == "all good"

    def test_record_failure(self):
        """record() must append a failed result correctly."""
        reporter = SetupReporter()
        reporter.record("failing check", False, "something broke")
        assert len(reporter.results) == 1
        result = reporter.results[0]
        assert result.name == "failing check"
        assert result.ok is False
        assert result.detail == "something broke"

    def test_record_multiple_results(self):
        """record() must accumulate multiple results in order."""
        reporter = SetupReporter()
        reporter.record("check A", True)
        reporter.record("check B", False, "failed")
        reporter.record("check C", True)
        assert len(reporter.results) == 3
        assert reporter.results[0].name == "check A"
        assert reporter.results[1].name == "check B"
        assert reporter.results[2].name == "check C"

    def test_summary_all_pass_returns_zero(self):
        """summary() must return 0 when all results pass."""
        reporter = SetupReporter()
        reporter.record("pass1", True)
        reporter.record("pass2", True)
        assert reporter.summary() == 0

    def test_summary_any_fail_returns_one(self):
        """summary() must return 1 when any result fails."""
        reporter = SetupReporter()
        reporter.record("pass", True)
        reporter.record("fail", False, "broken")
        assert reporter.summary() == 1

    def test_summary_all_fail_returns_one(self):
        """summary() must return 1 when all results fail."""
        reporter = SetupReporter()
        reporter.record("fail1", False, "err1")
        reporter.record("fail2", False, "err2")
        reporter.record("fail3", False, "err3")
        assert reporter.summary() == 1

    def test_summary_empty_results(self):
        """summary() must return 0 when there are no results."""
        reporter = SetupReporter()
        assert reporter.summary() == 0


class TestCheckLlmPort:
    """Test the check_llm_port function with a real socket server."""

    def test_port_open_returns_true(self):
        """check_llm_port must return (True, _) when port is open."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", 0))
            srv.listen(1)
            port = srv.getsockname()[1]

            ok, detail = check_llm_port(port, "test-backend")
            assert ok is True
            assert "open" in detail.lower() or "Port" in detail

    def test_port_closed_returns_false(self):
        """check_llm_port must return (False, _) when port is closed."""
        # Pick a very high port that's almost certainly not in use
        ok, detail = check_llm_port(19999, "absent-backend")
        assert ok is False


class TestCreateConfig:
    """Test the create_config function."""

    def test_create_config_creates_file(self):
        """create_config must create the config file when path doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.yaml")
            reporter = SetupReporter()
            result = create_config(reporter, config_path)
            assert result is True
            assert os.path.exists(config_path)
            assert len(reporter.results) == 1
            assert reporter.results[0].ok is True

    def test_create_config_existing_file(self):
        """create_config must return True when config already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.yaml")
            # Create the file first
            with open(config_path, "w") as f:
                f.write("existing: true\n")
            reporter = SetupReporter()
            result = create_config(reporter, config_path)
            assert result is True
            assert reporter.results[0].ok is True
            assert "exists" in reporter.results[0].name.lower()
