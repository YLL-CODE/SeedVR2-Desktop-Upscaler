from __future__ import annotations

import contextlib
import importlib
import os
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

from .config import DIT_FILENAME, MODEL_DIR, PROJECT_ROOT, SEED, memory_profile, validate_models
from .i18n import tr


class SeedVR2Backend:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.runner_cache: dict[str, Any] = {}
        self.cli: Any = None
        self.torch: Any = None
        self.models_loaded = False

    def set_log_path(self, log_path: Path) -> None:
        self.log_path = log_path

    def load(self) -> None:
        if self.cli is not None:
            return
        validate_models()
        vendor = PROJECT_ROOT / "vendor" / "seedvr2"
        if not vendor.is_dir():
            raise FileNotFoundError(tr("error.model_missing", path=vendor))
        sys.path.append(str(vendor))
        with self.log_path.open("a", encoding="utf-8") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            self.cli = importlib.import_module("inference_cli")
            self.torch = importlib.import_module("torch")
        if not self.torch.cuda.is_available():
            raise RuntimeError(tr("error.cuda_unavailable"))

    def system_info(self) -> dict[str, Any]:
        self.load()
        total_memory = self.torch.cuda.get_device_properties(0).total_memory
        return {
            "torch": self.torch.__version__,
            "cudaRuntime": self.torch.version.cuda,
            "gpu": self.torch.cuda.get_device_name(0),
            "vramBytes": total_memory,
            "memoryProfile": memory_profile(total_memory)["label"],
        }

    def reset_peak_memory(self) -> None:
        self.load()
        self.torch.cuda.reset_peak_memory_stats(0)

    def memory_metrics(self) -> dict[str, int]:
        return {
            "peakAllocatedBytes": int(self.torch.cuda.max_memory_allocated(0)),
            "peakReservedBytes": int(self.torch.cuda.max_memory_reserved(0)),
        }

    def upscale(self, input_path: Path, output_path: Path) -> None:
        self.load()
        profile = memory_profile(self.torch.cuda.get_device_properties(0).total_memory)
        args = Namespace(
            input=str(input_path),
            output=str(output_path),
            output_format="png",
            video_backend="opencv",
            use_10bit=False,
            model_dir=str(MODEL_DIR),
            dit_model=DIT_FILENAME,
            resolution=1024,
            max_resolution=0,
            batch_size=1,
            uniform_batch_size=False,
            seed=SEED,
            skip_first_frames=0,
            load_cap=0,
            chunk_size=0,
            prepend_frames=0,
            temporal_overlap=0,
            color_correction="wavelet",
            input_noise_scale=0.0,
            latent_noise_scale=0.0,
            cuda_device="0",
            dit_offload_device="cpu",
            vae_offload_device="cpu",
            tensor_offload_device="cpu",
            blocks_to_swap=36,
            swap_io_components=profile["swapIo"],
            vae_encode_tiled=True,
            vae_encode_tile_size=profile["vaeTile"],
            vae_encode_tile_overlap=profile["vaeOverlap"],
            vae_decode_tiled=True,
            vae_decode_tile_size=profile["vaeTile"],
            vae_decode_tile_overlap=profile["vaeOverlap"],
            tile_debug="false",
            attention_mode="sdpa",
            compile_dit=False,
            compile_vae=False,
            compile_backend="inductor",
            compile_mode="default",
            compile_fullgraph=False,
            compile_dynamic=False,
            compile_dynamo_cache_size_limit=64,
            compile_dynamo_recompile_limit=128,
            cache_dit=True,
            cache_vae=True,
            debug=False,
        )
        with self.log_path.open("a", encoding="utf-8") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            self.cli.process_single_file(
                str(input_path), args, ["0"], str(output_path), runner_cache=self.runner_cache
            )
        self.models_loaded = True


class PassthroughBackend:
    """Small deterministic backend used only when SEEDVR2_FAKE=1 in tests."""

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.peak = 0
        self.models_loaded = False

    def set_log_path(self, log_path: Path) -> None:
        self.log_path = log_path

    def system_info(self) -> dict[str, Any]:
        return {
            "torch": "fake",
            "cudaRuntime": None,
            "gpu": "fake",
            "vramBytes": 0,
            "memoryProfile": memory_profile(0)["label"],
        }

    def reset_peak_memory(self) -> None:
        return None

    def memory_metrics(self) -> dict[str, int]:
        return {"peakAllocatedBytes": 0, "peakReservedBytes": 0}

    def upscale(self, input_path: Path, output_path: Path) -> None:
        import time
        from PIL import Image

        time.sleep(float(os.environ.get("SEEDVR2_FAKE_DELAY", "0")))
        with Image.open(input_path) as image:
            image.convert("RGB").resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS).save(output_path)
        with self.log_path.open("a", encoding="utf-8") as log:
            log.write(f"{input_path} -> {output_path}\n")
        self.models_loaded = True
