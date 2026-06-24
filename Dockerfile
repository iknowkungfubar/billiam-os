# Billiam OS — Docker Development Image
#
# Build:  docker build -t billiam-os .
# Run:    docker run -it --rm \
#           -v ~/.config/billiam-os:/home/user/.config/billiam-os \
#           billiam-os
#
# For full voice integration, you need actual audio hardware.
# Run with --device /dev/snd for ALSA or --device /dev/dri for GPU.

# hadolint global ignore: DL3008 (pin versions in apt-get) is intentional
# for maximum distro compatibility in development images.
FROM python:3.11-slim

LABEL org.opencontainers.image.title="Billiam OS"
LABEL org.opencontainers.image.description="FOSS AI-Powered Linux Desktop Assistant"
LABEL org.opencontainers.image.licenses="GPL-3.0"

# ── Stage 1: Dependencies ──────────────────────────────────
# Install system packages and create non-root user in one layer.
# hadolint ignore=DL3008,DL3013
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    ffmpeg \
    alsa-utils \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 user

WORKDIR /home/user/billiam-os

# Copy only requirements first (layer caching — rebuilds only when deps change)
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && rm -rf /root/.cache/pip

# ── Stage 2: Application ───────────────────────────────────
COPY --chown=user:user . .

RUN mkdir -p /home/user/.config/billiam-os

USER user

# Verify critical imports
RUN python -c "\
from core.billiam import BILLIAM_PROFILE; \
from core.memory import AssistantMemoryLayer; \
from core.sandbox import SecureExecutionSandbox; \
from core.config import load_config; \
import tempfile, os; \
d = tempfile.mkdtemp(); \
mp = os.path.join(d, 'mem.json'); \
from core.ai_core import AICore; \
c = AICore(memory_path=mp); \
assert c.assistant_name == 'Billiam'; \
import shutil; shutil.rmtree(d); \
print('Docker build verification: All modules import correctly')"

ENTRYPOINT ["python", "-m", "core.ai_core"]
CMD []
