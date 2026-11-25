#!/usr/bin/env bash
# Installs ComfyUI, the FitShot custom nodes and the required models (about 14 GB).
# Safe to re-run: finished downloads are skipped and partial ones resume.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMFY="$ROOT/comfyui"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT/../.cache/uv}"
HF="https://huggingface.co"

fetch() {
  local url="$1" dest="$2"
  if [ -s "$dest" ]; then echo "have: $(basename "$dest")"; return; fi
  mkdir -p "$(dirname "$dest")"
  echo "downloading: $(basename "$dest")"
  # Large Hugging Face downloads can drop mid-transfer, so retry and resume on any error.
  curl -fL --retry 30 --retry-all-errors --retry-delay 5 -C - -sS -o "$dest.part" "$url"
  mv "$dest.part" "$dest"
}

# Uses Hugging Face's resumable downloader. Files stay on this drive with no second copy.
hf_fetch() {
  local repo="$1" file="$2" dest="$3"
  if [ -s "$dest" ]; then echo "have: $(basename "$dest")"; return; fi
  mkdir -p "$(dirname "$dest")" "$COMFY/models/.downloads"
  echo "downloading: $repo/$file"
  # Plain HTTP resumes reliably here; the Xet transfer stalled on a resumed partial file.
  HF_HUB_DISABLE_XET=1 HF_HUB_DISABLE_PROGRESS_BARS=1 "$PY" -c "
import os, sys
from huggingface_hub import hf_hub_download
repo, name, dest, area = sys.argv[1:]
os.replace(hf_hub_download(repo, name, local_dir=area), dest)
" "$repo" "$file" "$dest" "$COMFY/models/.downloads"
}

clone() {
  local url="$1" dest="$2"
  if [ -d "$dest/.git" ]; then echo "have: $(basename "$dest")"; return; fi
  git clone --depth 1 "$url" "$dest"
}

echo "== ComfyUI"
clone https://github.com/comfyanonymous/ComfyUI.git "$COMFY"
clone https://github.com/cubiq/ComfyUI_InstantID.git "$COMFY/custom_nodes/ComfyUI_InstantID"

echo "== Python environment"
[ -d "$COMFY/.venv" ] || uv venv --python 3.12 "$COMFY/.venv"
PY="$COMFY/.venv/Scripts/python.exe"
# RTX 50-series GPUs need a CUDA 12.8 or newer PyTorch build.
uv pip install --python "$PY" torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
uv pip install --python "$PY" -r "$COMFY/requirements.txt"
uv pip install --python "$PY" insightface onnxruntime

echo "== Models"
# ComfyUI makes brand model photos only (InstantID + OpenPose). Try-ons use FASHN VTON 1.5
# on Hugging Face or CatVTON, so the IP-Adapter dressing models are no longer downloaded.
M="$COMFY/models"
hf_fetch SG161222/RealVisXL_V5.0_Lightning RealVisXL_V5.0_Lightning_fp16.safetensors \
  "$M/checkpoints/RealVisXL_V5.0_Lightning_fp16.safetensors"
hf_fetch InstantX/InstantID ip-adapter.bin \
  "$M/instantid/ip-adapter.bin"
hf_fetch InstantX/InstantID ControlNetModel/diffusion_pytorch_model.safetensors \
  "$M/controlnet/instantid_controlnet.safetensors"
hf_fetch xinsir/controlnet-openpose-sdxl-1.0 diffusion_pytorch_model.safetensors \
  "$M/controlnet/openpose_sdxl.safetensors"

ANTELOPE="$M/insightface/models"
if [ ! -s "$ANTELOPE/antelopev2/glintr100.onnx" ]; then
  mkdir -p "$ANTELOPE"
  fetch "https://github.com/deepinsight/insightface/releases/download/v0.7/antelopev2.zip" "$ANTELOPE/antelopev2.zip"
  "$PY" -m zipfile -e "$ANTELOPE/antelopev2.zip" "$ANTELOPE"
  rm -f "$ANTELOPE/antelopev2.zip"
fi

echo "== Verify"
"$PY" -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
ls -la "$ANTELOPE/antelopev2"
du -sh "$M"
echo "== ComfyUI setup complete"
