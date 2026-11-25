"""Turn the demo recording and screenshots into two captioned H.264 MP4 videos.

Usage: python demo/scripts/make_videos.py demo
Needs opencv-python, numpy, Pillow and an ffmpeg with libx264: set FFMPEG to its path,
or install imageio-ffmpeg, which ships one.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

demo = Path(sys.argv[1])
steps = json.loads((demo / "steps.json").read_text(encoding="utf-8"))
W, H = 1440, 900
FONT = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 26)
BOLD = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 26)
TITLE = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 64)
INK, VOLT, COBALT = (14, 14, 16), (200, 255, 46), (43, 53, 245)


def caption(frame_bgr: np.ndarray, number: str, text: str) -> np.ndarray:
    """An ink bar at the bottom with a volt step number and the caption, wrapped to two lines."""
    image = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=FONT) > W - 200:
            lines.append(line)
            line = word
        else:
            line = trial
    lines.append(line)
    bar = 30 + 38 * len(lines)
    draw.rectangle([0, H - bar, W, H], fill=INK)
    if number:
        draw.rectangle([28, H - bar + 18, 28 + 64, H - bar + 18 + 40], fill=VOLT)
        draw.text((60, H - bar + 38), number, font=BOLD, fill=INK, anchor="mm")
    for i, text_line in enumerate(lines):
        draw.text((116, H - bar + 16 + 38 * i), text_line, font=FONT, fill=(255, 255, 255))
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def fit(image_bgr: np.ndarray) -> np.ndarray:
    """Place any screenshot (the phone one is narrow) centred on a W x H canvas."""
    h, w = image_bgr.shape[:2]
    scale = min(W / w, H / h)
    resized = cv2.resize(image_bgr, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    canvas = np.full((H, W, 3), (240, 241, 241), np.uint8)
    y, x = (H - resized.shape[0]) // 2, (W - resized.shape[1]) // 2
    canvas[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
    return canvas


def find_ffmpeg() -> str:
    if os.environ.get("FFMPEG"):
        return os.environ["FFMPEG"]
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        found = shutil.which("ffmpeg")
        assert found, "No ffmpeg: set FFMPEG or pip install imageio-ffmpeg"
        return found


class writer:
    """Pipe BGR frames into ffmpeg's libx264: small files that play everywhere."""

    def __init__(self, path: Path, fps: float):
        self.process = subprocess.Popen(
            [find_ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
             "-r", str(fps), "-i", "pipe:0", "-c:v", "libx264", "-preset", "slow", "-crf", "22",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)],
            stdin=subprocess.PIPE,
        )

    def write(self, frame: np.ndarray) -> None:
        self.process.stdin.write(np.ascontiguousarray(frame).tobytes())

    def release(self) -> None:
        self.process.stdin.close()
        assert self.process.wait() == 0, "ffmpeg failed"


def title_card(subtitle: str) -> np.ndarray:
    image = Image.new("RGB", (W, H), COBALT)
    draw = ImageDraw.Draw(image)
    draw.text((W // 2, H // 2 - 40), "FITSHOT", font=TITLE, fill=(255, 255, 255), anchor="mm")
    draw.rectangle([W // 2 - 260, H // 2 + 20, W // 2 + 260, H // 2 + 70], fill=VOLT)
    draw.text((W // 2, H // 2 + 45), subtitle, font=BOLD, fill=INK, anchor="mm")
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


# ---------- 1. Captioned screen recording ----------
shots = [s for s in steps if s["file"]]
wait = {s["caption"]: s["at"] for s in steps if not s["file"]}
source = cv2.VideoCapture(str(demo / "raw-video" / "walkthrough.webm"))
fps = source.get(cv2.CAP_PROP_FPS) or 25
out = writer(demo / "fitshot-walkthrough.mp4", fps)
for _ in range(int(fps * 2.5)):
    out.write(title_card("Walkthrough: try a garment on, end to end"))
index, kept = 0, 0
while True:
    ok, frame = source.read()
    if not ok:
        break
    t = index / fps
    index += 1
    if wait.get("wait-start", 1e9) < t < wait.get("wait-end", -1) and index % 10:
        continue  # the generation wait plays at 10x
    frame = cv2.resize(frame, (W, H)) if frame.shape[1::-1] != (W, H) else frame
    current = [s for s in shots if s["at"] - 1.6 <= t]
    if current:
        s = current[-1]
        speed = " (sped up)" if wait.get("wait-start", 1e9) < t < wait.get("wait-end", -1) else ""
        frame = caption(frame, str(s["n"]), s["caption"] + speed)
    out.write(frame)
    kept += 1
out.release()
print(f"walkthrough: {kept / fps:.0f} s")

# ---------- 2. Captioned slideshow ----------
out = writer(demo / "fitshot-slideshow.mp4", 25)
slides = [title_card("The complete workflow in 23 steps")] + [
    caption(fit(cv2.imread(str(demo / "screenshots" / s["file"]))), str(s["n"]), s["caption"]) for s in shots
]
hold, fade = 25 * 4, 12
for i, slide in enumerate(slides):
    for _ in range(hold):
        out.write(slide)
    if i + 1 < len(slides):
        for k in range(1, fade + 1):
            out.write(cv2.addWeighted(slide, 1 - k / fade, slides[i + 1], k / fade, 0))
out.release()
print(f"slideshow: {len(slides) * (hold + fade) / 25:.0f} s")
