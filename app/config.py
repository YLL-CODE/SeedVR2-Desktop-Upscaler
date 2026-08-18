from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from .i18n import tr

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = Path(os.environ.get("SEEDVR2_MODEL_DIR", PROJECT_ROOT / "models" / "SEEDVR2")).resolve()
DIT_FILENAME = "seedvr2_ema_7b_sharp-Q4_K_M.gguf"
VAE_FILENAME = "ema_vae_fp16.safetensors"
DIT_SIZE = 4_758_306_592
VAE_SIZE = 501_324_814
SCALE = 4
SUPPORTED_SCALES = (2, 4, 6, 8)
SUPPORTED_GRIDS = (3, 4, 5)
BLEND_PADDING = 64
SEED = 2_794_489_657


def memory_profile(vram_bytes: int) -> dict[str, int | str | bool]:
    gib = vram_bytes / 1024**3 if vram_bytes > 0 else 16
    if gib < 10:
        return {"label": "8GB", "tileInput": 512, "vaeTile": 512, "vaeOverlap": 64, "swapIo": True}
    if gib < 14:
        return {"label": "12GB", "tileInput": 768, "vaeTile": 768, "vaeOverlap": 96, "swapIo": False}
    return {"label": "16GB", "tileInput": 1024, "vaeTile": 1024, "vaeOverlap": 128, "swapIo": False}


def runtime_python() -> Path:
    candidate = PROJECT_ROOT / "runtime" / "python" / "python.exe"
    if candidate.exists():
        return candidate
    if os.environ.get("SEEDVR2_ALLOW_SYSTEM_PYTHON") == "1":
        return Path(sys.executable)
    raise FileNotFoundError(tr("error.runtime_missing"))


def ascii_temp_root() -> Path:
    configured = os.environ.get("SEEDVR2_TEMP_ROOT")
    candidates = [Path(configured)] if configured else []
    candidates.extend([Path(tempfile.gettempdir()) / "seedvr2_upscaler", Path("C:/SeedVR2Temp")])
    for candidate in candidates:
        if not str(candidate).isascii():
            continue
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue
    raise RuntimeError(tr("error.temp_root"))


def log_root() -> Path:
    root = ascii_temp_root().parent / "seedvr2_upscaler_logs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_models() -> dict[str, int]:
    expected = {DIT_FILENAME: DIT_SIZE, VAE_FILENAME: VAE_SIZE}
    found: dict[str, int] = {}
    for filename, expected_size in expected.items():
        path = MODEL_DIR / filename
        if not path.is_file():
            raise FileNotFoundError(tr("error.model_missing", path=path))
        size = path.stat().st_size
        if size != expected_size:
            raise RuntimeError(tr("error.model_size", filename=filename, size=size, expected=expected_size))
        found[filename] = size
    return found
