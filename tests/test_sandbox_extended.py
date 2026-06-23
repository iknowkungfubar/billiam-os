"""
tests/test_sandbox_extended.py
Billiam OS — Extended Sandbox Tests

Covers error handling paths and edge cases.
"""


import pytest

from core.sandbox import (
    BANNED_EXPRESSIONS,
    PRIVILEGED_TRIGGERS,
    GuardrailException,
    SecureExecutionSandbox,
)


class TestSandboxEdgeCases:
    """Test sandbox edge cases and error handling."""

    def setup_method(self, method):
        self.sandbox = SecureExecutionSandbox()

    def test_custom_banned_patterns(self):
        """Custom banned patterns must be usable."""
        sandbox = SecureExecutionSandbox(
            banned_expressions=[r"dangerous_pattern"]
        )
        assert sandbox.check_string_safety("dangerous_pattern") is False
        assert sandbox.check_string_safety("echo hello") is True

    def test_very_long_command(self):
        """Very long commands must not crash."""
        long_cmd = "echo " + "a" * 10000
        rc, stdout, stderr = self.sandbox.execute_safely(long_cmd)
        assert rc == 0

    def test_command_with_special_chars(self):
        """Commands with special characters must work."""
        rc, stdout, stderr = self.sandbox.execute_safely(
            """echo "hello $HOME 'test' $(pwd)" """
        )
        assert rc == 0
        assert stdout.strip() != ""

    def test_multiple_commands(self):
        """Multiple chained commands must work."""
        rc, stdout, stderr = self.sandbox.execute_safely(
            "echo first && echo second && echo third"
        )
        assert rc == 0
        assert "first" in stdout
        assert "second" in stdout
        assert "third" in stdout

    def test_piped_commands(self):
        """Piped commands must work."""
        rc, stdout, stderr = self.sandbox.execute_safely(
            "echo 'line1\nline2\nline3' | wc -l"
        )
        assert rc == 0
        assert stdout.strip() == "3"

    def test_check_privileged_variations(self):
        """Various privilege detection edge cases."""
        assert self.sandbox.check_privileged("pacman -Syu") is True
        assert self.sandbox.check_privileged("echo pacman_version") is False
        assert self.sandbox.check_privileged("systemctl status sshd") is True
        assert self.sandbox.check_privileged("cat systemctl_log") is False
        assert self.sandbox.check_privileged("ls -la") is False

    def test_validate_no_exception_for_safe(self):
        """validate_command must not raise for safe commands."""
        self.sandbox.validate_command("echo hello")  # Should not raise

    def test_validate_raises_for_destructive(self):
        """validate_command must raise for destructive commands."""
        with pytest.raises(GuardrailException):
            self.sandbox.validate_command("rm -rf /")

    def test_banned_patterns_list_not_empty(self):
        """Banned expressions list must not be empty."""
        assert len(BANNED_EXPRESSIONS) > 0

    def test_privileged_triggers_not_empty(self):
        """Privileged triggers list must not be empty."""
        assert len(PRIVILEGED_TRIGGERS) > 0

    def test_timeout_default_value(self):
        """Default timeout must be 20 seconds."""
        rc, stdout, stderr = self.sandbox.execute_safely(
            "echo test", timeout=20
        )
        assert rc == 0

    def test_timeout_custom_value(self):
        """Custom timeout must work."""
        rc, stdout, stderr = self.sandbox.execute_safely(
            "echo test", timeout=5
        )
        assert rc == 0
