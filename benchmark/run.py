"""Try-on benchmark: the same synthetic people and garments through FASHN VTON 1.5 and CatVTON.

Run from the backend folder (so FitShot's packages are importable):

    cd backend
    uv run python ../benchmark/run.py                  # both generators, every scenario
    uv run python ../benchmark/run.py --only fashn     # one generator
    uv run python ../benchmark/run.py --force          # redo outputs that already exist

FASHN runs on Hugging Face and uses the daily GPU quota of HF_TOKEN's account (about 15 s
per image), so existing outputs are reused unless --force is given. CatVTON needs
run-catvton.cmd and run-comfyui.cmd running. Each output is scored with FitShot's own QA
checks (no Gemini judge), and a contact sheet and REPORT.md are written to results/.
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from fitshot.config import settings  # noqa: E402
from fitshot.generators import get_generator  # noqa: E402
from fitshot.generators.base import DressRequest  # noqa: E402
from fitshot.imaging import load_rgb, save_rgb  # noqa: E402
from fitshot.qa.gate import QAInput, run_qa  # noqa: E402
from fitshot.qa.judge import read_sleeves  # noqa: E402
from fitshot.qa.perception import detect_faces  # noqa: E402

INPUTS, RESULTS = HERE / "inputs", HERE / "results"
SEED = 42

# name: (person, garment, FitShot category, what it tests)
SCENARIOS = {
    "1_full_flatlay_tee": ("person_full_hoodie", "garment_stripe_tee_flatlay", "top", "Full body + flat-lay striped tee"),
    "2_half_flatlay_tee": ("person_half_hoodie", "garment_navy_tee_flatlay", "top", "Half body + flat-lay tee"),
    "3_full_modelworn_tee": ("person_full_hoodie", "garment_navy_tee_model_worn", "top", "Full body + model-worn tee"),
    "4_half_modelworn_tee": ("person_half_hoodie", "garment_navy_tee_model_worn", "top", "Half body + model-worn tee"),
    "5_full_trousers": ("person_full_hoodie", "garment_beige_chinos_flatlay", "bottom", "Full body + flat-lay trousers"),
    "6_full_dress": ("person_full_hoodie", "garment_red_polka_dress_flatlay", "dress", "Full body + flat-lay patterned dress"),
    "7_pose_jacket": ("person_pose_hand_on_hip", "garment_olive_jacket_flatlay", "outerwear", "Hand-on-hip pose + flat-lay jacket"),
}
GATES = ("garment_color", "garment_pattern", "identity", "skin_tone", "body_pose")


class GpuPeak:
    """Highest GPU memory in use (MiB, whole GPU) while a call runs, read from nvidia-smi."""

    def __init__(self) -> None:
        self.peak, self._stop = 0, threading.Event()

    def _read(self) -> int:
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            ).stdout
            return int(out.split()[0])
        except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
            return 0

    def _poll(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, self._read())
            self._stop.wait(0.5)

    def __enter__(self):
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join()


def sleeves_for(garment_name: str, garment: np.ndarray, cache: dict) -> str | None:
    if garment_name not in cache and settings.gemini_api_key:
        try:
            cache[garment_name] = read_sleeves(settings.gemini_api_key, settings.gemini_judge_model, garment)
        except Exception as exc:  # CatVTON still runs without it.
            print(f"  (sleeve reading failed: {exc})")
            cache[garment_name] = None
    return cache.get(garment_name)


def score(person: np.ndarray, garment: np.ndarray, output: np.ndarray, category: str) -> dict:
    faces = detect_faces(person)
    centroid = faces[0].embedding.astype(np.float32) if faces else np.zeros(512, np.float32)
    report = run_qa(QAInput(garment, output, person, person, centroid, category, "studio"), None)
    return {g.name: {"status": g.status, "score": g.score} for g in report.gates if g.name in GATES}


def run(names: list[str], generators: list[str], force: bool) -> dict:
    metrics_path = RESULTS / "metrics.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    sleeves_cache = metrics.setdefault("_sleeves", {})
    for gen_name in generators:
        generator = get_generator(gen_name)
        ready, reason = generator.status()
        if not ready:
            print(f"{gen_name}: not ready ({reason}), skipped")
            continue
        for name in names:
            person_name, garment_name, category, _ = SCENARIOS[name]
            out_path = RESULTS / gen_name / f"{name}.png"
            entry = metrics.setdefault(name, {}).setdefault(gen_name, {})
            if out_path.exists() and not force and entry.get("ok"):
                print(f"{gen_name} {name}: kept existing output")
                continue
            person, garment = load_rgb(INPUTS / f"{person_name}.png"), load_rgb(INPUTS / f"{garment_name}.png")
            sleeves = sleeves_for(garment_name, garment, sleeves_cache) if category != "bottom" else None
            request = DressRequest(person, garment, category, "studio", person, None, [], keep_body=True, sleeves=sleeves)
            random.seed(SEED)
            started = time.perf_counter()
            try:
                with GpuPeak() as gpu:
                    result = generator.dress(request)
            except Exception as exc:
                entry.clear()
                entry.update(ok=False, error=f"{type(exc).__name__}: {exc}"[:400])
                print(f"{gen_name} {name}: FAILED {entry['error']}")
                continue
            seconds = time.perf_counter() - started
            save_rgb(result.image, out_path)
            entry.clear()
            entry.update(
                ok=True, seconds=round(seconds, 1), gpu_peak_mib=gpu.peak, model=result.model,
                output_size=list(result.image.shape[1::-1]), checks=score(person, garment, result.image, category),
            )
            print(f"{gen_name} {name}: {seconds:.0f}s, GPU peak {gpu.peak} MiB, {entry['checks']}")
            metrics_path.parent.mkdir(parents=True, exist_ok=True)
            metrics_path.write_text(json.dumps(metrics, indent=2))
    metrics_path.write_text(json.dumps(metrics, indent=2))
    return metrics


def contact_sheet(metrics: dict, generators: list[str]) -> None:
    height = 360
    rows = []
    for name, (person_name, garment_name, _, title) in SCENARIOS.items():
        tiles = [load_rgb(INPUTS / f"{person_name}.png"), load_rgb(INPUTS / f"{garment_name}.png")]
        for gen_name in generators:
            path = RESULTS / gen_name / f"{name}.png"
            tiles.append(load_rgb(path) if path.exists() else np.full((height, 270, 3), 235, np.uint8))
        tiles = [cv2.resize(t, (round(t.shape[1] * height / t.shape[0]), height)) for t in tiles]
        widths = [270] * len(tiles)
        padded = []
        for tile, w in zip(tiles, widths):
            canvas = np.full((height, w, 3), 255, np.uint8)
            tile = tile[:, : w] if tile.shape[1] > w else tile
            x = (w - tile.shape[1]) // 2
            canvas[:, x : x + tile.shape[1]] = tile
            padded.append(canvas)
        label = np.full((34, sum(widths), 3), 255, np.uint8)
        cv2.putText(label, f"{title}   |   person, garment, {', '.join(generators)}", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 1)
        rows.append(np.vstack([label, np.hstack(padded)]))
    save_rgb(np.vstack(rows), RESULTS / "sheet.jpg")


def report(metrics: dict, generators: list[str]) -> None:
    lines = ["# Try-on benchmark", "", f"Seed {SEED}. Synthetic people only. Checks are FitShot's QA gates (no Gemini judge).", "",
             "| Scenario | Generator | Time (s) | GPU peak (MiB) | Output | Color | Pattern | Face | Skin | Body |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for name, (_, _, _, title) in SCENARIOS.items():
        for gen_name in generators:
            e = metrics.get(name, {}).get(gen_name)
            if not e:
                continue
            if not e.get("ok"):
                lines.append(f"| {title} | {gen_name} | failed: {e.get('error', '')[:80]} |||||||| ")
                continue
            c = e["checks"]
            cell = lambda g: f"{c[g]['status']} ({c[g]['score']:.2f})" if g in c and c[g]["score"] is not None else c.get(g, {}).get("status", "-")
            lines.append(
                f"| {title} | {gen_name} | {e['seconds']} | {e['gpu_peak_mib']} | {e['output_size'][0]}x{e['output_size'][1]} | "
                + " | ".join(cell(g) for g in GATES) + " |"
            )
    lines += ["", "Color is a Delta E distance (lower is closer). Pattern and Face are similarities (higher is closer). "
              "Body is limb-length drift (lower is closer). GPU peak is the whole GPU, read with nvidia-smi; for FASHN the "
              "work runs on Hugging Face, so the local figure is what other programs already held.", "",
              "See sheet.jpg for the images side by side."]
    (RESULTS / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", choices=("fashn", "catvton"), help="run one generator")
    parser.add_argument("--scenarios", nargs="*", choices=list(SCENARIOS), default=list(SCENARIOS))
    parser.add_argument("--force", action="store_true", help="redo outputs that already exist")
    args = parser.parse_args()
    generators = [args.only] if args.only else ["fashn", "catvton"]
    metrics = run(args.scenarios, generators, args.force)
    shown = ["fashn", "catvton"]
    contact_sheet(metrics, shown)
    report(metrics, shown)
    print(f"Wrote {RESULTS / 'REPORT.md'} and {RESULTS / 'sheet.jpg'}")


if __name__ == "__main__":
    main()
