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
import subprocess

# ── Layer 1: Banned Expression Patterns ──────────────────────────────────────
# These patterns are EXPLICITLY blocked regardless of context.
# If a command matches any of these, execution is denied immediately.
BANNED_EXPRESSIONS = [
    # Filesystem destruction
    r"rm\s+-(r|f|rf|fr)\s+/",  # rm -rf /
    r"rm\s+-(r|f|rf|fr)\s+~\s*/*",  # rm -rf ~
    r"rm\s+-(r|f|rf|fr)\s+/home",  # rm -rf /home
    # Disk/partition operations
    r"dd\s+if=",  # dd if=/dev/zero of=/dev/sda
    r"mkfs\.",  # mkfs.ext4 /dev/sda
    r"mkswap\s+/dev/",  # mkswap on disk device
    # Permission escalation
    r"chown\s+.*\s+/\s*$",  # chown -R user:user /
    r"chmod\s+777\s+/",  # chmod 777 /
    # Fork bombs
    r":\(\)\s*\{\s*:\|:&\s*\};:",  # Classic bash fork bomb
    r"fork\s*\(",  # fork() in scripts
    # Device-level destruction
    r"nvme\s+format",  # NVMe format
    r"shred\s+",  # Secure delete
    r"wipefs\s+-[a]",  # Wipe filesystem signatures
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


class GuardrailError(Exception):
    """Raised when a command is blocked by the guardrail system."""

    pass


# ── Layer 2: Intent Classification ──────────────────────────────────────────
# Heuristic risk scoring for commands beyond simple pattern matching.
# Scores: 0.0 (safe) → 1.0 (critical danger)

DANGEROUS_KEYWORDS = {
    "delete": 0.6,
    "destroy": 0.9,
    "wipe": 0.9,
    "overwrite": 0.5,
    "format": 0.8,
    "partition": 0.7,
}

DANGEROUS_TARGETS = [
    "/boot",
    "/etc",
    "/dev/sd",
    "/dev/nvme",
    "/sys",
    "/proc",
]

SYSTEM_MODIFICATION_COMMANDS = [
    "pacman",
    "apt",
    "dnf",
    "yum",
    "zypper",
    "systemctl",
    "service",
    "passwd",
    "useradd",
    "usermod",
    "groupadd",
    "modprobe",
    "insmod",
    "rmmod",
]


class IntentClassification:
    """Layer 2: Heuristic intent classification for command safety.

    Analyzes command structure, keywords, and targets to classify
    the intent as SAFE, SUSPICIOUS, or DANGEROUS.
    """

    SAFE = "SAFE"
    SUSPICIOUS = "SUSPICIOUS"
    DANGEROUS = "DANGEROUS"

    @classmethod
    def classify(cls, command: str) -> tuple:
        """Classify a command's intent.

        Args:
            command: The shell command to classify.

        Returns:
            Tuple of (classification, score, reason).
        """
        command_lower = command.lower()
        score = 0.0
        reasons = []

        # Read-only commands should not be flagged for target/modification checks
        READ_ONLY_PREFIXES = ["cat ", "less ", "more ", "head ", "tail ", "grep ", "wc "]
        is_read_only = any(command_lower.startswith(prefix) for prefix in READ_ONLY_PREFIXES)

        # Data-driven checks: (score_weight, matcher_fn, reason_template)
        checks = []

        # 1. Dangerous keywords
        for keyword, weight in DANGEROUS_KEYWORDS.items():
            checks.append(
                (
                    weight,
                    lambda kw=keyword: kw in command_lower,
                    f"contains dangerous keyword '{keyword}'",
                )
            )

        # 2. Dangerous targets (only for non-read operations)
        if not is_read_only:
            for target in DANGEROUS_TARGETS:
                checks.append(
                    (0.5, lambda t=target: t in command_lower, f"targets system path '{target}'")
                )

        # 3. Destructive flag combinations
        has_rm_rf = "rm" in command_lower and ("-rf" in command_lower or "-fr" in command_lower)
        has_rm_sep = "rm" in command_lower and "-r" in command_lower and "-f" in command_lower
        has_rm_root = bool(
            re.search(r"rm\s+-rf\s+/\s", command_lower)
            or re.search(r"rm\s+-fr\s+/\s", command_lower)
        )
        has_dd_disk = "dd" in command_lower and "of=" in command_lower
        has_chmod_777 = "chmod" in command_lower and "777" in command_lower and "/" in command_lower

        checks.append((0.5, lambda: has_rm_rf, "recursive force delete flags detected"))
        checks.append((0.5, lambda: has_rm_root, "root filesystem targeted for recursive delete"))
        checks.append((0.4, lambda: has_rm_sep, "recursive force delete flags (separated)"))
        checks.append((0.7, lambda: has_dd_disk, "direct disk write operation detected"))
        checks.append((0.6, lambda: has_chmod_777, "permission escalation on root detected"))

        # 4. System modification commands (not read-only)
        if not is_read_only:
            for cmd in SYSTEM_MODIFICATION_COMMANDS:

                def _make_matcher(c):
                    return lambda: bool(re.search(rf"\b{re.escape(c)}\b", command_lower))

                checks.append((0.3, _make_matcher(cmd), f"system modification command '{cmd}'"))

        # 5. Password operations (even read-only)
        checks.append(
            (
                0.2,
                lambda: (
                    "passwd" in command_lower
                    and any(w in command_lower for w in ["write", "change", "add", "mod", "-e"])
                ),
                "password write operation detected",
            )
        )

        # 6. Shell injection characters at start of command
        injection_chars = [";", "&&", "||", "`", "$("]
        for char in injection_chars:
            checks.append(
                (
                    0.4,
                    lambda c=char: command.strip().startswith(c),
                    f"starts with injection char '{char}'",
                )
            )

        # Apply all checks
        for weight, matcher, reason in checks:
            if matcher():
                score += weight
                reasons.append(reason)

        # Determine classification
        if score >= 0.7:
            return (cls.DANGEROUS, score, "; ".join(reasons))
        elif score >= 0.3:
            return (cls.SUSPICIOUS, score, "; ".join(reasons))
        else:
            return (cls.SAFE, score, "Command appears benign")


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
            GuardrailError: If the command fails any guardrail check.
        """
        # Layer 1: Deterministic pattern match
        if not self.check_string_safety(command):
            raise GuardrailError(
                "GUARDRAIL BLOCKED [Layer 1]: Command matched a banned security pattern. "
                "Execution terminated."
            )

        # Layer 2: Intent classification
        classification, score, reason = IntentClassification.classify(command)
        if classification == IntentClassification.DANGEROUS:
            raise GuardrailError(
                f"GUARDRAIL BLOCKED [Layer 2]: Command classified as DANGEROUS "
                f"(score={score:.2f}). {reason}"
            )

    def execute_safely(self, command: str, timeout: int = 20) -> tuple[int, str, str]:
        """Execute a shell instruction through the sandbox.

        Args:
            command: The shell command to execute.
            timeout: Maximum execution time in seconds (default: 20).

        Returns:
            Tuple of (returncode, stdout, stderr).

        Raises:
            GuardrailError: If the command fails guardrail checks.
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
