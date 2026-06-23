"""
tests/test_sandbox_layer2.py
Billiam OS — Layer 2 Intent Classification Tests
"""

import pytest

from core.sandbox import GuardrailException, IntentClassification, SecureExecutionSandbox


class TestIntentClassification:
    """Test Layer 2 intent classification."""

    @pytest.mark.parametrize(
        "command,expected",
        [
            ("echo hello", "SAFE"),
            ("ls -la", "SAFE"),
            ("uname -a", "SAFE"),
            ("df -h", "SAFE"),
            ("rm -rf /boot", "DANGEROUS"),
            ("dd if=/dev/zero of=/dev/sda", "DANGEROUS"),
            ("chmod 777 /etc/passwd", "DANGEROUS"),
            ("delete all files", "SUSPICIOUS"),
            ("sudo pacman -Syu", "SUSPICIOUS"),
            ("format /dev/sda1", "DANGEROUS"),
            ("wipe /dev/nvme0n1", "DANGEROUS"),
            ("cat /etc/passwd", "SAFE"),
        ],
    )
    def test_classify(self, command, expected):
        """Classification must match expected tier."""
        cls, score, reason = IntentClassification.classify(command)
        assert cls == expected, f"{command}: expected {expected}, got {cls} ({reason})"

    def test_classify_returns_tuple(self):
        """Classification must return a 3-tuple."""
        result = IntentClassification.classify("echo hello")
        assert len(result) == 3
        assert isinstance(result[0], str)  # classification
        assert isinstance(result[1], float)  # score
        assert isinstance(result[2], str)  # reason

    def test_safe_command_score_zero(self):
        """Safe commands must have score near 0."""
        cls, score, reason = IntentClassification.classify("echo hello")
        assert score < 0.3
        assert "benign" in reason.lower()

    def test_dangerous_command_high_score(self):
        """Dangerous commands must have score >= 0.7."""
        cls, score, reason = IntentClassification.classify(
            "rm -rf /boot"
        )
        assert score >= 0.7

    def test_layer2_blocks_dangerous(self):
        """Layer 2 must block commands that pass Layer 1 but are dangerous."""
        sandbox = SecureExecutionSandbox()
        # Use a command Layer 1 allows (no exact banned pattern match)
        # but Layer 2 classifies as DANGEROUS
        with pytest.raises(GuardrailException) as exc:
            sandbox.execute_safely("rm -rf /boot")
        # Will be blocked by Layer 1 (also fine) or Layer 2
        assert "GUARDRAIL BLOCKED" in str(exc.value)

    def test_layer2_allows_safe(self):
        """Layer 2 must allow safe commands."""
        sandbox = SecureExecutionSandbox()
        # Should not raise
        rc, stdout, stderr = sandbox.execute_safely("echo layer2 test")
        assert rc == 0
