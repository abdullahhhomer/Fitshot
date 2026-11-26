#!/usr/bin/env bash
# Installs FASHN VTON 1.5 (Apache-2.0) for the local try-on service, about 2.6 GB of model files.
# It reuses the CatVTON Python environment (CUDA PyTorch), so run scripts/setup_catvton.sh first.
# Run from Git Bash in the FitShot folder. Everything stays under fashn/ on this drive.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/catvton/.venv/Scripts/python.exe"
[ -x "$PY" ] || PY="$ROOT/catvton/.venv/bin/python"   # Linux and Docker
DIR="$ROOT/fashn"
COMMIT=7c0f10af3f91ad4048fe9729c470a13ef905d25a   # tested with FitShot on 2026-11-25

[ -x "$PY" ] || { echo "Run scripts/setup_catvton.sh first (FASHN reuses its Python environment)."; exit 1; }
mkdir -p "$DIR"
if [ ! -d "$DIR/fashn-vton-1.5" ]; then
  git clone https://github.com/fashn-AI/fashn-vton-1.5.git "$DIR/fashn-vton-1.5"
fi
git -C "$DIR/fashn-vton-1.5" checkout --quiet "$COMMIT"

# Adds packages only; none of CatVTON's packages change (checked with --dry-run).
UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT/../.uv-cache}" uv pip install --python "$PY" -e "$DIR/fashn-vton-1.5"

# Model (1.9 GB), DWPose (0.3 GB) and the human parser (0.25 GB), all kept under fashn/.
export HF_HOME="$DIR/hf-cache" PYTHONIOENCODING=utf-8
"$PY" "$DIR/fashn-vton-1.5/scripts/download_weights.py" --weights-dir "$DIR/weights"
echo "FASHN is ready. Start it with run-fashn.cmd (or start-all.cmd)."
