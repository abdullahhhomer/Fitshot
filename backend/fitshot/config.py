"""Application settings, loaded from the project-root .env file."""
from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    gemini_api_key: str = ""
    gemini_image_model: str = "gemini-nano-banana-2.1"
    gemini_judge_model: str = "gemini-3.5-flash-lite"
    image_size: str = "2K"
    aspect_ratio: str = "3:4"

    # USD per generated image. Confirm against Google's pricing page.
    price_1k: float = 0.0336
    price_2k: float = 0.0504
    price_4k: float = 0.113
    # Estimated USD per vision-judge call.
    judge_usd_per_call: float = 0.001

    comfyui_url: str = "http://127.0.0.1:8188"
    catvton_url: str = "http://127.0.0.1:8190"
    # FASHN VTON 1.5 on this PC (run-fashn.cmd) is the "fashn" model; on Hugging Face it is "fashn_hosted".
    fashn_url: str = "http://127.0.0.1:8191"
    # Hugging Face Spaces, tried in order until one has room.
    hf_token: str = ""
    fashn_spaces: str = "merve/fashn-vton-1.5,Nymbo/fashn-vton-1.5,hmajid2301/fashn-vton-1.5,fashn-ai/fashn-vton-1.5"
    fashn_steps: int = 30
    fashn_guidance: float = 1.5
    fashn_timeout: float = 300.0
    # Set this to your rented GPU cost per image when ComfyUI is not local.
    comfyui_usd_per_image: float = 0.0

    default_generator: str = "nano_banana"
    max_attempts: int = 3
    # Looks worked on at once. Local looks still take turns on the GPU (see generators/gpu.py),
    # but while one is being checked on the CPU, the next one is already on the GPU.
    local_workers: int = 2
    cloud_workers: int = 2

    # Hosting the frontend elsewhere (for example Vercel) and reaching this server through a tunnel.
    # fitshot_access_key: when set, every /api and /media request must carry it (X-FitShot-Key header or ?key=).
    # fitshot_cors_origins: comma-separated origins allowed to call this server, e.g. https://fitshot.vercel.app
    fitshot_access_key: str = ""
    fitshot_cors_origins: str = ""

    data_dir: Path = ROOT / "data"
    models_dir: Path = ROOT / "models"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "fitshot.db"

    @property
    def image_price(self) -> float:
        return {"1K": self.price_1k, "2K": self.price_2k, "4K": self.price_4k}[self.image_size]


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
# Keep model downloads off the system drive.
os.environ.setdefault("U2NET_HOME", str(settings.models_dir / "rembg"))
