# Dead End Ledger — Billiam OS Red Team Audit

## 2026-06-23 - Bandit JSON output parsing
- **Attempted:** `bandit -r core/ -f json | python3 -c "import sys,json;..."` 
- **Why it failed:** Bandit produced no stdout output when piped; JSON decode failed on empty input
- **Evidence:** `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`
- **Lesson:** Run Bandit with `-f txt` (default) and parse text output, or install bandit in the active venv

## 2026-06-23 - Lambdas capturing loop variables
- **Attempted:** `lambda: has_rm_rf` style capture of local booleans in classify()
- **Why it worked:** Boolean values computed before lambda creation, so late binding is irrelevant
- **Evidence:** All 50 classification tests pass
- **Lesson:** Simple booleans can be safely captured by reference. Only loop variables need `c=cmd` default-arg binding.

## 2026-06-23 - Ruff E731 (lambda assignment)
- **Attempted:** Named lambda `matcher = lambda ...`
- **Why it failed:** Ruff E731 forbids assigning lambdas to names
- **Evidence:** Lint check failed
- **Lesson:** Use `def _make_matcher(c): return lambda: ...` factory pattern instead of assigning lambda to variable

## 2026-06-23 - Hermes hardline blocked `rm -rf /boot` in test
- **Attempted:** `python3 -c "from core.sandbox import IntentClassification; IntentClassification.classify('rm -rf /boot')"`
- **Why it failed:** Hermes terminal tool blocks `rm -rf` strings unconditionally, even in Python test strings
- **Evidence:** `BLOCKED (hardline): recursive delete of system directory`
- **Lesson:** Use `format /dev/sda1` or `dd if=/dev/zero of=/dev/sda` (also blocked) for Layer 2 testing. Safer: `wipe` keyword which is classified DANGEROUS without matching hardline patterns.
