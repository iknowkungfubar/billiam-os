# Billiam OS — Makefile
#
# Build, test, install, and manage Billiam OS.
#
# Targets:
#   install      Install Python dependencies
#   test         Run test suite with coverage
#   lint         Run ruff linter
#   format       Format code with ruff
#   typecheck    Run pyright type checking
#   clean        Remove build artifacts
#   setup-llm    Build llama.cpp with OpenVINO
#

.PHONY: install test lint format typecheck clean setup-llm run run-voice hotkey

# ── Install ──────────────────────────────────────────────────────────────────

install:
	@echo "Installing Billiam OS dependencies..."
	pip install --quiet --upgrade pip 2>/dev/null || true
	pip install --quiet -r requirements.txt
	@echo "Done. Run 'make test' to verify."

install-dev:
	@echo "Installing dev dependencies..."
	pip install --quiet ruff pyright pytest pytest-cov pyyaml
	pip install --quiet -r requirements.txt
	@echo "Dev environment ready."

# ── Testing ──────────────────────────────────────────────────────────────────

test:
	@echo "Running Billiam OS test suite..."
	python -m pytest tests/ -v --cov=core --cov-report=term-missing | tail -30

test-quick:
	@echo "Running quick tests..."
	python -m pytest tests/ -q

test-coverage:
	@echo "Running tests with coverage..."
	python -m pytest tests/ --cov=core --cov-report=term --cov-report=xml --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

coverage: test-coverage

# ── Linting ──────────────────────────────────────────────────────────────────

lint:
	@echo "Linting core modules..."
	ruff check core/ tests/ scripts/

lint-fix:
	@echo "Auto-fixing lint issues..."
	ruff check core/ tests/ scripts/ --fix
	ruff format core/ tests/ scripts/

format:
	ruff format core/ tests/ scripts/

typecheck:
	@echo "Running type checker..."
	pyright core/ 2>/dev/null || echo "pyright not available"

# ── Running ──────────────────────────────────────────────────────────────────

run:
	@echo "Starting Billiam OS (interactive mode)..."
	python -m core.ai_core

run-voice:
	@echo "Starting Billiam OS with voice (British butler)..."
	python -m core.ai_core --voice

run-daemon:
	@echo "Starting Billiam OS daemon..."
	python -m core.ai_core --daemon

# ── Setup ────────────────────────────────────────────────────────────────────

setup-llm:
	@echo "Setting up inference engine..."
	bash scripts/setup_inference.sh

setup-all: install setup-llm
	@echo "Full setup complete."

install-system:
	@echo "Running system installation..."
	bash scripts/install.sh

# ── Cleanup ──────────────────────────────────────────────────────────────────

clean:
	@echo "Cleaning build artifacts..."
	rm -rf __pycache__ core/__pycache__ tests/__pycache__
	rm -rf .pytest_cache .ruff_cache
	rm -rf htmlcov coverage.xml .coverage
	rm -rf build/ dist/ *.egg-info
	rm -rf *.gguf models/*.gguf
	@echo "Clean."

clean-all: clean
	@echo "Removing llama.cpp build..."
	rm -rf llama.cpp/

# ── Systemd Service ──────────────────────────────────────────────────────────

service-install:
	@echo "Installing systemd user service..."
	mkdir -p ~/.config/systemd/user
	cp config/aios.service ~/.config/systemd/user/billiam-os.service
	systemctl --user daemon-reload
	@echo "Service installed."
	@echo "  Enable: systemctl --user enable billiam-os.service"
	@echo "  Start:  systemctl --user start billiam-os.service"
	@echo "  Status: systemctl --user status billiam-os.service"

service-enable:
	systemctl --user enable --now billiam-os.service
	@echo "Service enabled and started."

service-status:
	systemctl --user status billiam-os.service

# ── Help ─────────────────────────────────────────────────────────────────────

help:
	@echo "Billiam OS — Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  install       Install Python dependencies"
	@echo "  install-dev   Install dev dependencies (lint, typecheck)"
	@echo "  test          Run test suite with coverage"
	@echo "  lint          Run ruff linter"
	@echo "  format        Format code with ruff"
	@echo "  run           Start Billiam OS interactively"
	@echo "  run-voice     Start with British butler voice"
	@echo "  setup-llm     Build llama.cpp with OpenVINO"
	@echo "  clean         Remove build artifacts"
	@echo ""
