#!/usr/bin/env bash
#
# scripts/setup_inference.sh
# Billiam OS — Setup Inference Engine
#
# Compiles llama.cpp with Intel OpenVINO backend acceleration
# and downloads Qwen-2.5-Coder-3B-Instruct GGUF model.
#
# Usage: bash scripts/setup_inference.sh
#
set -euo pipefail

echo "================================================"
echo " Billiam OS — Inference Engine Setup"
echo " Compiling llama.cpp with OpenVINO acceleration"
echo "================================================"

# ── Distro Detection ────────────────────────────────────
detect_package_manager() {
    if command -v pacman &>/dev/null; then
        echo "pacman"
    elif command -v apt-get &>/dev/null; then
        echo "apt-get"
    elif command -v dnf &>/dev/null; then
        echo "dnf"
    else
        echo "unsupported"
    fi
}

PACKAGE_MANAGER="$(detect_package_manager)"

case "$PACKAGE_MANAGER" in
    pacman)
        PKG_INSTALL="sudo pacman -S --needed --noconfirm"
        DEPS=(base-devel cmake git python-pip openvino opencl-intel)
        ;;
    apt-get)
        PKG_INSTALL="sudo apt-get install -y"
        DEPS=(build-essential cmake git python3-pip openvino)
        echo ""
        echo "  ⚠ Note: OpenVINO may not be in apt. If installation fails,"
        echo "    install from: https://github.com/openvinotoolkit/openvino"
        echo ""
        ;;
    dnf)
        PKG_INSTALL="sudo dnf install -y"
        DEPS=(gcc-c++ cmake git python3-pip openvino)
        echo ""
        echo "  ⚠ Note: OpenVINO may require RPM Fusion. If installation fails,"
        echo "    see: https://github.com/openvinotoolkit/openvino"
        echo ""
        ;;
    unsupported)
        echo ""
        echo "⚠ Unsupported distribution."
        echo ""
        echo "  Please manually install the following dependencies, then re-run this script:"
        echo "    - git, cmake, gcc/g++, python3-pip"
        echo "    - Intel OpenVINO (see: https://github.com/openvinotoolkit/openvino)"
        echo "    - Intel OpenCL runtime (for GPU acceleration)"
        echo ""
        echo "  OpenVINO is optional — llama.cpp will compile without it (CPU-only fallback)."
        echo ""
        ;;
esac

# ── Step 1: System Dependencies ──────────────────────────
echo ""
echo "==> Step 1/5: Installing system dependencies..."
if [ "$PACKAGE_MANAGER" != "unsupported" ]; then
    $PKG_INSTALL "${DEPS[@]}" 2>&1 | tail -3
fi

# ── Step 2: Clone llama.cpp ──────────────────────────────
echo ""
echo "==> Step 2/5: Cloning llama.cpp..."
LLAMA_DIR="llama.cpp"
if [ ! -d "${LLAMA_DIR}" ]; then
    git clone --depth 1 https://github.com/ggml-org/llama.cpp.git "${LLAMA_DIR}"
else
    echo "    llama.cpp directory already exists, updating..."
    (cd "${LLAMA_DIR}" && git pull)
fi

# ── Step 3: Build with OpenVINO ───────────────────────────
echo ""
echo "==> Step 3/5: Configuring build with OpenVINO..."

(
cd "${LLAMA_DIR}"

cmake -B build \
    -DGGML_OPENVINO=ON \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLAMA_CURL=OFF \
    2>&1 | tail -5

echo ""
echo "==> Step 4/5: Compiling (this may take a while)..."
cmake --build build --config Release -j"$(nproc)" 2>&1 | tail -5
)

# ── Step 4: Create model directory ────────────────────────
echo ""
echo "==> Creating models directory..."
mkdir -p models

# ── Step 5: Download Qwen-2.5-Coder-3B-Instruct ──────────
MODEL_PATH="models/qwen2.5-coder-3b.gguf"
if [ ! -f "${MODEL_PATH}" ]; then
    echo ""
    echo "==> Step 5/5: Downloading Qwen-2.5-Coder-3B-Instruct (Q4_K_M)..."
    echo "    Model: 1.98 GB (Q4_K_M quantization)"
    echo "    Source: Hugging Face (GGUF format)"
    echo ""
    wget -O "${MODEL_PATH}" \
        "https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q4_k_m.gguf" \
        2>&1 | tail -5
else
    echo ""
    echo "==> Step 5/5: Model already exists at ${MODEL_PATH}, skipping download."
fi

# ── Verify ────────────────────────────────────────────────
echo ""
echo "==> Verification"
echo "    llama-server:  $(test -f ${LLAMA_DIR}/build/bin/llama-server && echo '✓' || echo '✗')"
echo "    llama-cli:     $(test -f ${LLAMA_DIR}/build/bin/llama-cli && echo '✓' || echo '✗')"
echo "    llama-bench:   $(test -f ${LLAMA_DIR}/build/bin/llama-bench && echo '✓' || echo '✗')"
echo "    Model:         $(test -f ${MODEL_PATH} && echo "✓ ($(du -h ${MODEL_PATH} | cut -f1))" || echo '✗')"

echo ""
echo "================================================"
echo " Setup Complete!"
echo ""
echo " To start the inference server:"
echo "   ${LLAMA_DIR}/build/bin/llama-server \\"
echo "     -m ${MODEL_PATH} \\"
echo "     --host 0.0.0.0 --port 8080 \\"
echo "     -ngl 0 -c 4096"
echo ""
echo " Then run the assistant:"
echo "   billiam --once \"What's my hostname?\""
echo "   billiam --voice"
echo "================================================"
