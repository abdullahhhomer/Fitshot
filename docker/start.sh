#!/usr/bin/env bash
# Starts FitShot inside the container, like start-all.cmd does on Windows:
# ComfyUI, CatVTON and FASHN on 127.0.0.1 inside the container, then the app on port 8000.
# If any of them stops, the container stops too, so Docker's restart policy can bring it back.
set -uo pipefail
cd /app
mkdir -p data

# Run a command in the background with its name in front of each log line.
run() {
  local name="$1"; shift
  "$@" > >(sed -u "s/^/[$name] /") 2>&1 &
}

if [ -f comfyui/main.py ]; then
  run comfyui bash -c 'cd comfyui && exec .venv/bin/python main.py --listen 127.0.0.1 --port 8188 --lowvram --disable-auto-launch'
else
  echo "[fitshot] ComfyUI was not built into this image (WITH_COMFYUI=0). Built-in people's photos can't be made."
fi
run catvton catvton/.venv/bin/python services/catvton_server.py
run fashn catvton/.venv/bin/python services/fashn_server.py

# The app listens on every interface inside the container; docker-compose.yml publishes it
# on 127.0.0.1 of the host only.
run app bash -c 'cd backend && exec .venv/bin/python -m uvicorn fitshot.api:app --host 0.0.0.0 --port 8000'

# docker stop: pass the signal on to every service.
trap 'echo "[fitshot] Stopping."; kill $(jobs -p) 2>/dev/null; wait; exit 0' TERM INT

echo "[fitshot] Starting. Open http://127.0.0.1:8000 once the app reports it is running. The GPU models load on first use."
wait -n
status=$?
echo "[fitshot] A service stopped (exit $status). Stopping the container."
exit "$status"
