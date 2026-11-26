# syntax=docker/dockerfile:1.7
#
# FitShot in one image: the app (FastAPI + React), FASHN VTON 1.5, CatVTON and ComfyUI,
# with every model downloaded while the image builds. Nothing is fetched when it runs.
#
#   docker compose up --build        (see DOCKER.md)
#
# Needs an NVIDIA GPU (8 GB tested) and the NVIDIA Container Toolkit to run, and about
# 30 GB of free disk to build. Skip ComfyUI (about 14 GB, only used to make built-in
# people's photos) with:  docker compose build --build-arg WITH_COMFYUI=0

# ---------- 1. Frontend ----------
FROM node:20-bookworm-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2. Everything else ----------
FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_PYTHON_DOWNLOADS=never \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git curl ca-certificates build-essential libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# The setup scripts are the same ones used on Windows. Strip Windows line endings in case
# the repository was cloned with core.autocrlf.
COPY scripts/ scripts/
RUN sed -i 's/\r$//' scripts/*.sh

# Model layers come before the app code, so changing the code never downloads them again.

# ComfyUI, the InstantID node and its models (RealVisXL, InstantID, OpenPose, antelopev2).
ARG WITH_COMFYUI=1
RUN if [ "$WITH_COMFYUI" = "1" ]; then bash scripts/setup_comfyui.sh; \
    else echo "Skipping ComfyUI (WITH_COMFYUI=$WITH_COMFYUI)"; fi \
 && rm -rf "$UV_CACHE_DIR" /root/.cache

# CatVTON: its Python environment (CUDA PyTorch) and weights.
RUN bash scripts/setup_catvton.sh && rm -rf "$UV_CACHE_DIR"

# FASHN VTON 1.5: reuses CatVTON's environment, weights go under fashn/.
RUN bash scripts/setup_fashn.sh && rm -rf "$UV_CACHE_DIR"

# The app's Python environment, from the lockfile.
COPY backend/pyproject.toml backend/uv.lock backend/
RUN cd backend && uv sync --frozen --no-dev && rm -rf "$UV_CACHE_DIR"

# The inspection models: face (InsightFace buffalo_l), pose and hands (MediaPipe),
# clothing and object segmentation (rembg). Same folders the app reads from models/.
RUN mkdir -p models/mediapipe \
 && curl -fL --retry 10 --retry-all-errors -sS -o models/mediapipe/pose_landmarker_full.task \
      https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task \
 && curl -fL --retry 10 --retry-all-errors -sS -o models/mediapipe/hand_landmarker.task \
      https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task \
 && U2NET_HOME=/app/models/rembg backend/.venv/bin/python -c "\
from rembg import new_session; \
[new_session(n, providers=['CPUExecutionProvider']) for n in ('u2net_cloth_seg', 'isnet-general-use')]; \
from insightface.app import FaceAnalysis; \
FaceAnalysis(name='buffalo_l', root='/app/models/insightface', allowed_modules=['detection', 'recognition'], providers=['CPUExecutionProvider']); \
print('inspection models ready')" \
 && rm -f models/insightface/models/*.zip

# App code, the GPU services and the built frontend.
COPY backend/ backend/
COPY services/ services/
COPY .env.example ./
COPY --from=frontend /app/frontend/dist frontend/dist
COPY docker/start.sh /usr/local/bin/fitshot-start
RUN sed -i 's/\r$//' /usr/local/bin/fitshot-start services/*.py && chmod +x /usr/local/bin/fitshot-start

# Photos, results and the database live here; mount a volume to keep them.
VOLUME ["/app/data"]
EXPOSE 8000
CMD ["fitshot-start"]
