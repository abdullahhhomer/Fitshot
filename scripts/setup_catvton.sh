#!/usr/bin/env bash
# Sets up the local CatVTON try-on service (about 2 GB of weights).
# CatVTON is licensed CC BY-NC-SA 4.0: non-commercial use only.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODE="$ROOT/catvton"
WEIGHTS="$CODE/weights"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT/../.cache/uv}"
export HF_HOME="${HF_HOME:-$ROOT/../.cache/huggingface}"
export HF_HUB_DISABLE_XET=1 HF_HUB_DISABLE_PROGRESS_BARS=1

echo "== Code from the authors' Hugging Face Space"
[ -d "$CODE/.venv" ] || uv venv --python 3.12 "$CODE/.venv"
PY="$CODE/.venv/Scripts/python.exe"
[ -x "$PY" ] || PY="$CODE/.venv/bin/python"   # Linux and Docker
uv pip install --python "$PY" torch torchvision --index-url https://download.pytorch.org/whl/cu128
uv pip install --python "$PY" diffusers accelerate transformers huggingface_hub safetensors \
  fastapi "uvicorn[standard]" python-multipart pillow numpy packaging

"$PY" - "$CODE" "$WEIGHTS" <<'EOF'
import os, shutil, sys
from huggingface_hub import hf_hub_download

code, weights = sys.argv[1:]
for name in ("model/pipeline.py", "model/attn_processor.py", "model/utils.py", "model/__init__.py", "utils.py", "README.md"):
    target = os.path.join(code, name)
    if not os.path.exists(target):
        try:
            hf_hub_download("zhengchong/CatVTON", name, repo_type="space", local_dir=code)
        except Exception as exc:
            if name != "model/__init__.py":
                raise
            open(target, "w").close()

def fetch(repo, name, dest):
    if os.path.exists(dest):
        print("have:", os.path.relpath(dest, weights))
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print("downloading:", repo, name, flush=True)
    os.replace(hf_hub_download(repo, name, local_dir=os.path.join(weights, ".downloads")), dest)

base = "stable-diffusion-v1-5/stable-diffusion-inpainting"
fetch(base, "scheduler/scheduler_config.json", os.path.join(weights, "base/scheduler/scheduler_config.json"))
fetch(base, "unet/config.json", os.path.join(weights, "base/unet/config.json"))
# Safetensors cannot execute code when loaded, unlike the pickle .bin file.
fetch(base, "unet/diffusion_pytorch_model.fp16.safetensors", os.path.join(weights, "base/unet/diffusion_pytorch_model.safetensors"))
fetch("zhengchong/CatVTON", "mix-48k-1024/attention/model.safetensors", os.path.join(weights, "catvton/mix-48k-1024/attention/model.safetensors"))
for name in ("config.json", "diffusion_pytorch_model.safetensors"):
    hf_hub_download("stabilityai/sd-vae-ft-mse", name)
print("weights ready")
EOF

"$PY" -c "import torch, diffusers; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), 'diffusers', diffusers.__version__)"
echo "== CatVTON setup complete"
