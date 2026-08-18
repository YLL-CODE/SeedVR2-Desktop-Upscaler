from __future__ import annotations

import json
import os
import queue
import shutil
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT, SCALE, SUPPORTED_GRIDS, SUPPORTED_SCALES, ascii_temp_root, log_root, validate_models
from .i18n import set_language, tr
from .pipeline import assemble, copy_source_to_ascii, prepare, reserve_output_path, seam_metric, sha256
from .seedvr2_backend import PassthroughBackend, SeedVR2Backend

COMMANDS: queue.Queue[dict[str, Any]] = queue.Queue()
CANCEL = threading.Event()
OUTPUT_LOCK = threading.Lock()
PROTOCOL_OUTPUT = sys.stdout


def emit(event: str, **payload: Any) -> None:
    message = {"event": event, "timestamp": time.time(), **payload}
    with OUTPUT_LOCK:
        print(json.dumps(message, ensure_ascii=False), file=PROTOCOL_OUTPUT, flush=True)


def emit_message(event: str, key: str, *, values: dict[str, Any] | None = None, **payload: Any) -> None:
    values = values or {}
    emit(event, message=tr(key, **values), messageKey=key, messageArgs=values, **payload)


def localized_error(error: BaseException) -> str:
    text = str(error)
    lowered = text.lower()
    if "out of memory" in lowered:
        return tr("error.vram")
    if isinstance(error, PermissionError):
        return tr("error.permission")
    if isinstance(error, FileNotFoundError):
        return text
    if "cannot identify image" in lowered or "cannot open" in lowered:
        return tr("error.image_read")
    if "cuda" in lowered:
        return tr("error.cuda", error=text)
    return tr("error.processing", error=text)


def command_reader() -> None:
    for line in sys.stdin:
        try:
            command = json.loads(line)
            if command.get("command") == "cancel":
                CANCEL.set()
                emit_message("cancel_requested", "worker.cancel_requested")
            elif command.get("command") == "set_language":
                language = str(command.get("language", ""))
                try:
                    set_language(language, persist=False)
                except ValueError:
                    emit_message("error", "worker.unsupported_language", values={"language": language})
            else:
                COMMANDS.put(command)
        except json.JSONDecodeError:
            emit_message("error", "worker.invalid_json")
    COMMANDS.put({"command": "shutdown"})


def self_check() -> dict[str, Any]:
    models = validate_models()
    comfy_paths = [path for path in sys.path if "comfyui" in path.lower()]
    if comfy_paths:
        raise RuntimeError(tr("error.comfy_path", path=comfy_paths[0]))
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "projectRoot": str(PROJECT_ROOT),
        "models": models,
        "comfyPaths": comfy_paths,
        "tempRoot": str(ascii_temp_root()),
    }


def write_report(output: Path, report: dict[str, Any]) -> Path:
    report_path = output.with_suffix(".json")
    temporary = report_path.parent / f".{report_path.stem}-{os.getpid()}.tmp.json"
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, report_path)
    return report_path


def task_options(command: dict[str, Any]) -> tuple[int, int | None]:
    try:
        scale = int(command.get("scale", SCALE))
    except (TypeError, ValueError) as error:
        raise ValueError(tr("error.scale_required")) from error
    if scale not in SUPPORTED_SCALES:
        raise ValueError(tr("error.scale_unsupported", scale=scale))

    grid_value = command.get("grid", 3)
    if grid_value is None or str(grid_value).lower() == "auto":
        return scale, None
    try:
        grid = int(str(grid_value).split("x", 1)[0].split("×", 1)[0])
    except (TypeError, ValueError) as error:
        raise ValueError(tr("error.grid_required")) from error
    if grid not in SUPPORTED_GRIDS:
        raise ValueError(tr("error.grid_unsupported", grid=grid))
    return scale, grid


def publish_result(staged_output: Path, output: Path, report: dict[str, Any], started: float) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.stem}-{os.getpid()}.tmp.png"
    shutil.copy2(staged_output, temporary)
    report["timings"]["wallSeconds"] = time.perf_counter() - started
    report_path: Path | None = None
    try:
        report_path = write_report(output, report)
        os.replace(temporary, output)
    except Exception:
        if report_path:
            report_path.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)
        raise
    return report_path


def run_task(command: dict[str, Any], backend: SeedVR2Backend | PassthroughBackend | None) -> SeedVR2Backend | PassthroughBackend:
    source = Path(command.get("source", "")).expanduser().resolve()
    output_dir = Path(command.get("outputDir", "")).expanduser().resolve()
    scale, grid = task_options(command)
    if not source.is_file():
        raise FileNotFoundError(tr("error.source_missing", path=source))
    output_dir.mkdir(parents=True, exist_ok=True)
    task_id = uuid.uuid4().hex
    staging = ascii_temp_root() / task_id
    log_path: Path | None = None
    output_lock: Path | None = None
    started = time.perf_counter()
    timings: dict[str, float] = {}
    try:
        staging.mkdir(parents=True)
        log_path = log_root() / f"task-{task_id}.log"
        output, output_lock = reserve_output_path(source, output_dir, scale)
        fresh_backend = backend is None
        emit_message("status", "worker.environment", stage="environment", progress=0.01, taskId=task_id)
        if fresh_backend:
            backend_type = PassthroughBackend if os.environ.get("SEEDVR2_FAKE") == "1" else SeedVR2Backend
            backend = backend_type(log_path)
        else:
            backend.set_log_path(log_path)
        needs_model_load = not backend.models_loaded
        info = backend.system_info()
        emit_message("system_ready", "worker.system_ready", values={"gpu": info["gpu"]}, system=info, progress=0.02)
        if CANCEL.is_set():
            emit_message("cancelled", "worker.cancelled", taskId=task_id)
            return backend
        ascii_source = copy_source_to_ascii(source, staging)
        phase = time.perf_counter()
        manifest = prepare(
            ascii_source,
            staging,
            scale=scale,
            grid_size=grid,
            vram_bytes=int(info.get("vramBytes", 0)),
        )
        timings["prepareSeconds"] = time.perf_counter() - phase
        total = len(manifest["positions"])
        emit_message(
            "status",
            "worker.prepared",
            values={"scale": scale, "columns": manifest["columns"], "rows": manifest["rows"]},
            stage="prepare",
            progress=0.03,
            taskId=task_id,
        )
        backend.reset_peak_memory()
        phase = time.perf_counter()
        for index in range(total):
            if CANCEL.is_set():
                emit_message("cancelled", "worker.cancelled", taskId=task_id)
                return backend
            if needs_model_load and index == 0:
                emit_message(
                    "status",
                    "worker.model_loading",
                    values={"total": total},
                    stage="model",
                    progress=0.08,
                )
            emit_message(
                "progress",
                "worker.processing",
                values={"current": index + 1, "total": total},
                stage="inference",
                current=index + 1,
                total=total,
                progress=0.1 + index / total * 0.78,
            )
            backend.upscale(staging / "input" / f"{index:03d}.png", staging / "processed" / f"{index:03d}.png")
            if needs_model_load and index == 0:
                emit_message("model_ready", "worker.model_ready", system=info, progress=0.18)
            emit_message(
                "progress",
                "worker.tile_completed",
                values={"current": index + 1, "total": total},
                stage="inference",
                current=index + 1,
                total=total,
                progress=0.1 + (index + 1) / total * 0.78,
            )
        timings["inferenceSeconds"] = time.perf_counter() - phase
        if CANCEL.is_set():
            emit_message("cancelled", "worker.cancelled", taskId=task_id)
            return backend
        emit_message("status", "worker.assembling", stage="assemble", progress=0.9)
        if CANCEL.is_set():
            emit_message("cancelled", "worker.cancelled", taskId=task_id)
            return backend
        time.sleep(float(os.environ.get("SEEDVR2_FAKE_ASSEMBLE_DELAY", "0")))
        phase = time.perf_counter()
        staged_output = staging / "final.png"
        result = assemble(staging, staged_output)
        timings["assembleSeconds"] = time.perf_counter() - phase
        if CANCEL.is_set():
            emit_message("cancelled", "worker.cancelled", taskId=task_id)
            return backend
        report = {
            "status": "completed",
            "taskId": task_id,
            "source": str(source),
            "output": str(output),
            "sourceSize": [manifest["sourceWidth"], manifest["sourceHeight"]],
            "outputSize": [result["width"], result["height"]],
            "scale": scale,
            "gridPreset": manifest["gridPreset"],
            "tiles": [manifest["columns"], manifest["rows"]],
            "tileSize": [manifest["tileWidth"], manifest["tileHeight"]],
            "seedInputSize": [manifest["seedInputWidth"], manifest["seedInputHeight"]],
            "memoryProfile": manifest["memoryProfile"],
            "timings": timings,
            "memory": backend.memory_metrics(),
            "outputBytes": staged_output.stat().st_size,
            "sha256": sha256(staged_output),
            "seam": seam_metric(staged_output, manifest),
            "log": str(log_path),
        }
        if CANCEL.is_set():
            emit_message("cancelled", "worker.cancelled", taskId=task_id)
            return backend
        report_path = publish_result(staged_output, output, report, started)
        emit_message(
            "completed",
            "worker.completed",
            values={"scale": scale},
            output=str(output),
            report=str(report_path),
            metrics=report,
            progress=1.0,
        )
        return backend
    except Exception as error:
        if log_path:
            setattr(error, "seedvr2_log_path", str(log_path))
        raise
    finally:
        CANCEL.clear()
        if output_lock:
            output_lock.unlink(missing_ok=True)
        if os.environ.get("SEEDVR2_KEEP_TEMP") != "1":
            shutil.rmtree(staging, ignore_errors=True)


def main() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONNOUSERSITE", "1")
    emit_message("starting", "worker.starting")
    threading.Thread(target=command_reader, daemon=True).start()
    backend: SeedVR2Backend | PassthroughBackend | None = None
    try:
        check = self_check()
    except Exception as error:
        emit("error", message=localized_error(error), detail=traceback.format_exc())
        raise SystemExit(1)
    emit_message("ready", "worker.ready", check=check)
    while True:
        command = COMMANDS.get()
        name = command.get("command")
        if name == "shutdown":
            emit_message("shutdown", "worker.shutdown")
            break
        if name == "self_check":
            try:
                result = self_check()
                if command.get("withCuda"):
                    backend_type = PassthroughBackend if os.environ.get("SEEDVR2_FAKE") == "1" else SeedVR2Backend
                    backend = backend or backend_type(log_root() / "self-check.log")
                    result["system"] = backend.system_info()
                emit("self_check", result=result)
            except Exception as error:
                emit(
                    "error",
                    message=localized_error(error),
                    detail=traceback.format_exc(),
                    log=getattr(error, "seedvr2_log_path", str(getattr(backend, "log_path", ""))),
                )
        elif name == "run":
            try:
                backend = run_task(command, backend)
            except Exception as error:
                emit(
                    "error",
                    message=localized_error(error),
                    detail=traceback.format_exc(),
                    log=getattr(error, "seedvr2_log_path", str(getattr(backend, "log_path", ""))),
                )
        else:
            emit_message("error", "worker.unknown_command", values={"name": name})


if __name__ == "__main__":
    main()
