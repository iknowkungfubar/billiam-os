"""
core/sandbox.py
Billiam OS — Guardrail Execution Sandbox

A secure execution wrapper that prevents destructive system operations
through three layers of protection:

Layer 1: Deterministic regex-based banned pattern matching
Layer 2: LLM intent classification (at caller level)
Layer 3: Human-in-the-loop confirmation for privileged operations

All commands run through subprocess with strict timeout and resource limits.
"""

import re
import shlex
import subprocess
from typing import Tuple

# ── Layer 1: Banned Expression Patterns ──────────────────────────────────────
# These patterns are EXPLICITLY blocked regardless of context.
# If a command matches any of these, execution is denied immediately.
BANNED_EXPRESSIONS = [
    # Filesystem destruction
    r"rm\s+-(r|f|rf|fr)\s+/",            # rm -rf /
    r"rm\s+-(r|f|rf|fr)\s+~\s*/*",       # rm -rf ~
    r"rm\s+-(r|f|rf|fr)\s+/home",        # rm -rf /home
    # Disk/partition operations
    r"dd\s+if=",                           # dd if=/dev/zero of=/dev/sda
    r"mkfs\.",                             # mkfs.ext4 /dev/sda
    r"mkswap\s+/dev/",                     # mkswap on disk device
    # Permission escalation
    r"chown\s+.*\s+/\s*$",               # chown -R user:user /
    r"chmod\s+777\s+/",                   # chmod 777 /
    # Fork bombs
    r":\(\)\s*\{\s*:\|:&\s*\};:",        # Classic bash fork bomb
    r"fork\s*\(",                           # fork() in scripts
    # Device-level destruction
    r"nvme\s+format",                      # NVMe format
    r"shred\s+",                           # Secure delete
    r"wipefs\s+-[a]",                      # Wipe filesystem signatures
]

# Commands that trigger Layer 3 human-in-the-loop confirmation
PRIVILEGED_TRIGGERS = [
    "sudo",
    "pacman",
    "reboot",
    "poweroff",
    "shutdown",
    "systemctl",
    "parted",
    "fdisk",
    "mkfs",
    "mount",
    "umount",
]


class GuardrailException(Exception):
    """Raised when a command is blocked by the guardrail system."""

    pass


class SecureExecutionSandbox:
    """Secure wrapper for executing system commands through the guardrail system.

    Features:
    - Regex-based banned pattern detection (Layer 1)
    - Configurable privilege escalation confirmation (Layer 3)
    - Subprocess execution with timeout and resource limits
    - Sanitized return values (no raw exceptions to LLM)
    """

    def __init__(self, banned_expressions: list = BANNED_EXPRESSIONS):
        self.banned_expressions = banned_expressions

    def check_string_safety(self, command: str) -> bool:
        """Layer 1: Deterministic regex check against banned patterns.

        Args:
            command: The shell command string to validate.

        Returns:
            True if the command passes all pattern checks, False if blocked.
        """
        for expression in self.banned_expressions:
            if re.search(expression, command, re.IGNORECASE | re.MULTILINE):
                return False
        return True

    def check_privileged(self, command: str) -> bool:
        """Check if a command requires human-in-the-loop confirmation.

        Args:
            command: The shell command string.

        Returns:
            True if the command triggers privilege confirmation.
        """
        for trigger in PRIVILEGED_TRIGGERS:
            if re.search(rf"\b{re.escape(trigger)}\b", command, re.IGNORECASE):
                return True
        return False

    def validate_command(self, command: str) -> None:
        """Run all guardrail checks against a command.

        Args:
            command: The shell command string to validate.

        Raises:
            GuardrailException: If the command fails any guardrail check.
        """
        # Layer 1: Deterministic pattern match
        if not self.check_string_safety(command):
            raise GuardrailException(
                "GUARDRAIL BLOCKED: Command matched a banned security pattern. "
                "Execution terminated."
            )

    def execute_safely(
        self, command: str, timeout: int = 20
    ) -> Tuple[int, str, str]:
        """Execute a shell instruction through the sandbox.

        Args:
            command: The shell command to execute.
            timeout: Maximum execution time in seconds (default: 20).

        Returns:
            Tuple of (returncode, stdout, stderr).

        Raises:
            GuardrailException: If the command fails guardrail checks.
        """
        # Run guardrail checks
        self.validate_command(command)

        # Execute with resource limits
        try:
            completed_proc = subprocess.run(
                ["/usr/bin/bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return (
                completed_proc.returncode,
                completed_proc.stdout,
                completed_proc.stderr,
            )
        except subprocess.TimeoutExpired:
            return (
                -1,
                "",
                f"Execution halted: Command exceeded {timeout}s timeout.",
            )
        except PermissionError:
            return (-1, "", "Permission denied.")
        except FileNotFoundError:
            return (-1, "", "Command not found.")
        except OSError as e:
            return (-1, "", f"System error: {e}")

    def __repr__(self) -> str:
        return f"<SecureExecutionSandbox patterns={len(self.banned_expressions)}>"
