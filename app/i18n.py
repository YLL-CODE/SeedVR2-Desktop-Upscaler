from __future__ import annotations

import ctypes
import json
import locale
import os
import sys
from pathlib import Path
from typing import Any

LANG_ZH = "zh_CN"
LANG_EN = "en"
SUPPORTED_LANGUAGES = (LANG_ZH, LANG_EN)

_MESSAGES: dict[str, dict[str, str]] = {
    LANG_ZH: {
        "app.title": "SeedVR2 独立图片放大工具",
        "app.heading": "图片放大",
        "cli.description": "SeedVR2 独立图片放大工具命令行入口",
        "task.new": "新建放大任务",
        "task.single": "单图 · 保留原图",
        "task.subtitle": "配置输入与输出位置，Worker 就绪后即可开始。",
        "task.warning": "AI 放大可能重绘图片细节，\n请保留原图并检查输出结果。",
        "preset.scale": "放大倍率",
        "preset.grid": "分块方式",
        "preset.auto": "自动",
        "action.start": "开始 {scale}× 放大",
        "action.stop": "停止等待",
        "action.open_output": "打开输出目录",
        "action.open_output_short": "打开目录",
        "action.choose_image": "⊞  选择图片",
        "action.change": "▱  更改",
        "action.view_log": "查看日志",
        "action.hide_log": "隐藏日志",
        "input.label": "输入图片",
        "input.none": "尚未选择图片",
        "input.formats": "支持 PNG / JPG / WEBP / BMP / TIFF",
        "input.loading_info": "正在读取图片信息…",
        "input.read_failed": "无法读取图片信息",
        "input.only_one": "一次只能处理一张图片，请只拖入一个文件。",
        "input.not_found": "未找到有效的图片文件。",
        "input.unsupported": "仅支持 PNG / JPG / WEBP / BMP / TIFF 图片。",
        "input.image_type": "图片",
        "output.label": "输出目录",
        "status.worker_starting": "Worker 正在启动…",
        "status.checking_cuda": "正在检查 CUDA…",
        "status.worker_ready": "Worker 已就绪",
        "status.stopping": "正在停止…",
        "status.completed": "放大完成",
        "status.cancelled": "任务已停止",
        "status.failed": "处理失败",
        "status.scale": "倍率  {scale}×",
        "status.grid": "分块  {grid}",
        "status.gpu_detecting": "GPU 检测中",
        "status.gpu_ready": "GPU 就绪 · {gpu}",
        "status.gpu_unavailable": "GPU 未就绪",
        "detail.choose_image": "请选择一张图片。",
        "detail.ready": "已按 {profile} 显存档适配 · 可开始单图放大",
        "detail.current_tile": "当前块：{current}/{total}",
        "detail.stopping": "当前块完成后会停止，请稍候。",
        "detail.completed": "{scale}× · {columns}×{rows} 分块 · {width}×{height} · {seconds:.2f} 秒 · {mebibytes:.1f} MiB\n{profile} 档 · 峰值保留显存 {gibibytes:.2f} GiB",
        "size.default": "建议输入 ≤ 2560 × 1440；自动分块适配 {profile}",
        "size.high": "高倍率建议输入 ≤ 1920 × 1080；开始前会显示风险提醒",
        "size.manual": "；手动分块请留意显存",
        "view.input": "原图",
        "view.compare": "对比",
        "view.output": "结果",
        "preview.input_title": "原图",
        "preview.output_title": "放大结果",
        "preview.input_empty": "选择图片后显示原图",
        "preview.output_empty": "完成后显示放大结果",
        "preview.compare_empty": "放大完成后，可拖动分隔线查看前后差异",
        "preview.loading_input": "正在加载原图…",
        "preview.loading_output": "正在加载放大结果…",
        "preview.processing": "正在放大，完成后显示结果…",
        "preview.no_result": "本次任务未生成结果",
        "preview.unavailable": "无法预览这张图片",
        "preview.error": "无法预览：{error}",
        "preview.fit": "完整适配",
        "preview.compare_help": "滚轮缩放 · 右键拖动画面",
        "preview.output_help": "滚轮缩放 · 拖动查看",
        "preview.zoom_reset": "{percent}% · 双击复位",
        "log.title": "运行日志",
        "log.live": "实时",
        "log.path": "日志：{path}",
        "footer.output_size": "输出尺寸",
        "footer.elapsed": "耗时",
        "dialog.choose_image": "选择图片",
        "dialog.image_files": "图片",
        "dialog.all_files": "所有文件",
        "dialog.choose_output": "选择输出目录",
        "dialog.change_blocked_title": "暂时无法更换图片",
        "dialog.change_blocked": "当前任务正在处理，请停止或等待完成后再更换。",
        "dialog.add_failed": "无法添加图片",
        "dialog.start_failed": "无法开始",
        "dialog.select_valid": "请选择一张有效图片。",
        "dialog.high_scale_title": "高倍率放大提醒",
        "dialog.high_scale_output": "预计输出约 {width} × {height}。\n",
        "dialog.high_scale": "{scale}× 会明显增加内存、处理时间和文件体积。\n\nSeedVR2 原生输出为 4×；6×/8× 会在 4× 结果上继续重采样，不会按倍率同比增加真实细节。\n\n{output_size}仍要继续吗？",
        "dialog.processing_failed": "SeedVR2 处理失败",
        "dialog.settings_failed": "无法保存语言设置",
        "dialog.settings_failed_message": "界面已切换，但无法保存选择：{error}",
        "worker.protocol_broken": "Worker 协议输出损坏。",
        "worker.exited": "Worker 意外退出（代码 {code}）。",
        "worker.not_running": "Worker 已退出，请重新启动工具。",
        "worker.starting": "SeedVR2 Worker 正在启动。",
        "worker.ready": "Worker 已就绪。",
        "worker.shutdown": "Worker 已退出。",
        "worker.cancel_requested": "已请求停止，将在当前块完成后结束。",
        "worker.invalid_json": "Worker 收到无效 JSON 指令。",
        "worker.environment": "正在检查模型和 CUDA 环境…",
        "worker.system_ready": "运行环境已就绪：{gpu}",
        "worker.cancelled": "任务已停止，未生成最终图片。",
        "worker.prepared": "已准备 {scale}× 画布和 {columns}×{rows} 分块。",
        "worker.model_loading": "首次加载模型并处理第 1/{total} 块…",
        "worker.processing": "正在处理第 {current}/{total} 块…",
        "worker.model_ready": "模型已缓存，后续块将复用。",
        "worker.tile_completed": "已完成第 {current}/{total} 块。",
        "worker.assembling": "正在渐变拼接并写入 PNG…",
        "worker.completed": "{scale}× 放大完成。",
        "worker.unknown_command": "未知 Worker 指令：{name}",
        "worker.unsupported_language": "不支持的显示语言：{language}",
        "error.vram": "显存不足。请关闭占用显存的程序，或改用自动/更多分块后重试。",
        "error.permission": "没有读取输入或写入输出目录的权限，请更换目录。",
        "error.image_read": "无法读取图片，请确认文件未损坏且格式受支持。",
        "error.cuda": "CUDA 运行失败：{error}",
        "error.cuda_unavailable": "CUDA 不可用，请检查 NVIDIA 驱动和 PyTorch CUDA Runtime。",
        "error.processing": "处理失败：{error}",
        "error.runtime_missing": "独立 Python Runtime 不存在，请先运行 scripts\\install-runtime.ps1。",
        "error.temp_root": "无法创建纯英文临时目录，请设置 SEEDVR2_TEMP_ROOT。",
        "error.model_missing": "缺少模型文件：{path}",
        "error.model_size": "模型文件大小不符：{filename}（{size}，预期 {expected}）",
        "error.comfy_path": "检测到 ComfyUI 路径污染：{path}",
        "error.scale_required": "放大倍率必须是 2、4、6 或 8。",
        "error.scale_unsupported": "不支持的放大倍率：{scale}×。",
        "error.grid_required": "分块必须是自动、3×3、4×4 或 5×5。",
        "error.grid_unsupported": "不支持的分块预设：{grid}×{grid}。",
        "error.source_missing": "输入图片不存在：{path}",
        "error.image_too_small": "图片尺寸过小，无法执行分块处理。",
        "error.assembled_size": "拼接尺寸异常：{actual_width}×{actual_height}，预期 {expected_width}×{expected_height}",
        "error.output_names": "输出目录中的同名文件过多，请更换输出目录。",
        "error.output_reserve": "无法预留输出文件名，请关闭其他放大工具实例后重试。",
        "error.preview_mode": "未知预览模式：{mode}",
        "error.segment_option": "未知分段选项：{value}",
    },
    LANG_EN: {
        "app.title": "SeedVR2 Standalone Image Upscaler",
        "app.heading": "Image Upscaler",
        "cli.description": "Command-line entry point for the SeedVR2 standalone image upscaler",
        "task.new": "New Upscale Task",
        "task.single": "1 file · Safe",
        "task.subtitle": "Choose input/output, then start when ready.",
        "task.warning": "AI may redraw details.\nKeep originals and review results.",
        "preset.scale": "Upscale Factor",
        "preset.grid": "Tile Grid",
        "preset.auto": "Auto",
        "action.start": "Start {scale}× Upscale",
        "action.stop": "Stop",
        "action.open_output": "Open Folder",
        "action.open_output_short": "Open",
        "action.choose_image": "⊞  Choose Image",
        "action.change": "▱  Change",
        "action.view_log": "View Log",
        "action.hide_log": "Hide Log",
        "input.label": "Input Image",
        "input.none": "No image selected",
        "input.formats": "PNG · JPG · WEBP · BMP · TIFF",
        "input.loading_info": "Reading image information…",
        "input.read_failed": "Could not read image information",
        "input.only_one": "Only one image can be processed at a time. Drop a single file.",
        "input.not_found": "No valid image file was found.",
        "input.unsupported": "Only PNG / JPG / WEBP / BMP / TIFF images are supported.",
        "input.image_type": "Image",
        "output.label": "Output Folder",
        "status.worker_starting": "Worker is starting…",
        "status.checking_cuda": "Checking CUDA…",
        "status.worker_ready": "Worker Ready",
        "status.stopping": "Stopping…",
        "status.completed": "Upscale Complete",
        "status.cancelled": "Task Stopped",
        "status.failed": "Processing Failed",
        "status.scale": "Scale  {scale}×",
        "status.grid": "Tiles  {grid}",
        "status.gpu_detecting": "Detecting GPU",
        "status.gpu_ready": "GPU Ready · {gpu}",
        "status.gpu_unavailable": "GPU Not Ready",
        "detail.choose_image": "Choose an image to begin.",
        "detail.ready": "Tuned for the {profile} VRAM profile · Ready for one image",
        "detail.current_tile": "Current tile: {current}/{total}",
        "detail.stopping": "The task will stop after the current tile. Please wait.",
        "detail.completed": "{scale}× · {columns}×{rows} tiles · {width}×{height} · {seconds:.2f} sec · {mebibytes:.1f} MiB\n{profile} profile · Peak reserved VRAM {gibibytes:.2f} GiB",
        "size.default": "Recommended input ≤ 2560 × 1440 · Auto tiles support {profile}",
        "size.high": "For high scales, use ≤ 1920 × 1080 · A warning appears before starting",
        "size.manual": " · Watch VRAM usage with manual tiles",
        "view.input": "Original",
        "view.compare": "Compare",
        "view.output": "Result",
        "preview.input_title": "Original",
        "preview.output_title": "Upscaled Result",
        "preview.input_empty": "The original appears after you choose an image",
        "preview.output_empty": "The upscaled result appears when processing finishes",
        "preview.compare_empty": "Finish an upscale, then drag the divider to compare",
        "preview.loading_input": "Loading original…",
        "preview.loading_output": "Loading upscaled result…",
        "preview.processing": "Upscaling… The result will appear when complete",
        "preview.no_result": "This task did not produce a result",
        "preview.unavailable": "This image cannot be previewed",
        "preview.error": "Preview unavailable: {error}",
        "preview.fit": "Fit to view",
        "preview.compare_help": "Mouse wheel to zoom · Right-drag to pan",
        "preview.output_help": "Mouse wheel to zoom · Drag to pan",
        "preview.zoom_reset": "{percent}% · Double-click to reset",
        "log.title": "Run Log",
        "log.live": "Live",
        "log.path": "Log: {path}",
        "footer.output_size": "Output Size",
        "footer.elapsed": "Elapsed",
        "dialog.choose_image": "Choose an Image",
        "dialog.image_files": "Images",
        "dialog.all_files": "All Files",
        "dialog.choose_output": "Choose an Output Folder",
        "dialog.change_blocked_title": "Image Cannot Be Changed Yet",
        "dialog.change_blocked": "A task is running. Stop it or wait for it to finish before changing the image.",
        "dialog.add_failed": "Could Not Add Image",
        "dialog.start_failed": "Could Not Start",
        "dialog.select_valid": "Choose a valid image first.",
        "dialog.high_scale_title": "High Upscale Factor",
        "dialog.high_scale_output": "Estimated output: about {width} × {height}.\n",
        "dialog.high_scale": "{scale}× greatly increases memory use, processing time, and file size.\n\nSeedVR2 natively outputs 4×. The 6×/8× modes resample the 4× result and do not add real detail in proportion to the selected factor.\n\n{output_size}Continue?",
        "dialog.processing_failed": "SeedVR2 Processing Failed",
        "dialog.settings_failed": "Language Setting Could Not Be Saved",
        "dialog.settings_failed_message": "The interface changed, but the preference could not be saved: {error}",
        "worker.protocol_broken": "The Worker returned invalid protocol output.",
        "worker.exited": "The Worker exited unexpectedly (code {code}).",
        "worker.not_running": "The Worker has exited. Restart the app.",
        "worker.starting": "The SeedVR2 Worker is starting.",
        "worker.ready": "The Worker is ready.",
        "worker.shutdown": "The Worker has exited.",
        "worker.cancel_requested": "Stop requested. The task will end after the current tile.",
        "worker.invalid_json": "The Worker received an invalid JSON command.",
        "worker.environment": "Checking the models and CUDA environment…",
        "worker.system_ready": "The runtime is ready: {gpu}",
        "worker.cancelled": "The task was stopped and no final image was created.",
        "worker.prepared": "Prepared a {scale}× canvas with a {columns}×{rows} tile grid.",
        "worker.model_loading": "Loading the model for the first time and processing tile 1/{total}…",
        "worker.processing": "Processing tile {current}/{total}…",
        "worker.model_ready": "The model is cached and will be reused for later tiles.",
        "worker.tile_completed": "Completed tile {current}/{total}.",
        "worker.assembling": "Blending the tiles and writing the PNG…",
        "worker.completed": "{scale}× upscale complete.",
        "worker.unknown_command": "Unknown Worker command: {name}",
        "worker.unsupported_language": "Unsupported display language: {language}",
        "error.vram": "Not enough VRAM. Close GPU-heavy apps or retry with Auto/more tiles.",
        "error.permission": "The app cannot read the input or write to the output folder. Choose another location.",
        "error.image_read": "The image could not be read. Check that it is not damaged and uses a supported format.",
        "error.cuda": "CUDA failed: {error}",
        "error.cuda_unavailable": "CUDA is unavailable. Check the NVIDIA driver and PyTorch CUDA Runtime.",
        "error.processing": "Processing failed: {error}",
        "error.runtime_missing": "The standalone Python runtime is missing. Run scripts\\install-runtime.ps1 first.",
        "error.temp_root": "An ASCII-only temporary folder could not be created. Set SEEDVR2_TEMP_ROOT.",
        "error.model_missing": "Model file is missing: {path}",
        "error.model_size": "Model file size is invalid: {filename} ({size}; expected {expected})",
        "error.comfy_path": "ComfyUI path contamination detected: {path}",
        "error.scale_required": "The upscale factor must be 2, 4, 6, or 8.",
        "error.scale_unsupported": "Unsupported upscale factor: {scale}×.",
        "error.grid_required": "The tile grid must be Auto, 3×3, 4×4, or 5×5.",
        "error.grid_unsupported": "Unsupported tile preset: {grid}×{grid}.",
        "error.source_missing": "Input image does not exist: {path}",
        "error.image_too_small": "The image is too small for tiled processing.",
        "error.assembled_size": "Invalid assembled size: {actual_width}×{actual_height}; expected {expected_width}×{expected_height}",
        "error.output_names": "The output folder has too many files with the same name. Choose another output folder.",
        "error.output_reserve": "An output filename could not be reserved. Close other upscaler instances and retry.",
        "error.preview_mode": "Unknown preview mode: {mode}",
        "error.segment_option": "Unknown segmented-control option: {value}",
    },
}


def normalize_language(value: object) -> str | None:
    text = str(value or "").strip().replace("-", "_").lower()
    if text.startswith("zh"):
        return LANG_ZH
    if text in {"en", "english"} or text.startswith("en_"):
        return LANG_EN
    return None


def system_language() -> str:
    override = normalize_language(os.environ.get("SEEDVR2_LANGUAGE"))
    if override:
        return override
    if sys.platform == "win32":
        try:
            language_id = int(ctypes.windll.kernel32.GetUserDefaultUILanguage())
            return LANG_ZH if language_id & 0x3FF == 0x04 else LANG_EN
        except (AttributeError, OSError, ValueError):
            pass
    language, _encoding = locale.getlocale()
    return LANG_ZH if str(language or "").lower().startswith("zh") else LANG_EN


def settings_path() -> Path:
    override = os.environ.get("SEEDVR2_SETTINGS_PATH")
    if override:
        return Path(override).expanduser()
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "SeedVR2 Upscaler" / "settings.json"


def load_language() -> str:
    override = normalize_language(os.environ.get("SEEDVR2_LANGUAGE"))
    if override:
        return override
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8-sig"))
        saved = normalize_language(data.get("language") if isinstance(data, dict) else None)
        if saved:
            return saved
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, AttributeError):
        pass
    return system_language()


_language = load_language()


def get_language() -> str:
    return _language


def set_language(language: str, *, persist: bool = True) -> str:
    normalized = normalize_language(language)
    if normalized is None:
        raise ValueError(f"Unsupported language: {language}")
    global _language
    _language = normalized
    if persist:
        save_language(normalized)
    return normalized


def save_language(language: str) -> None:
    target = settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = json.loads(target.read_text(encoding="utf-8-sig")) if target.exists() else {}
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        existing = {}
    data = existing if isinstance(existing, dict) else {}
    data["language"] = language
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)


def tr(key: str, **values: Any) -> str:
    template = _MESSAGES.get(_language, _MESSAGES[LANG_EN]).get(key)
    if template is None:
        template = _MESSAGES[LANG_EN].get(key, key)
    try:
        return template.format(**values)
    except (KeyError, ValueError):
        return template


def translated_values(key: str) -> set[str]:
    return {messages[key] for messages in _MESSAGES.values() if key in messages}
