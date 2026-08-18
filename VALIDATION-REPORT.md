# SeedVR2 独立放大工具技术验证报告

验证日期：2026-08-19

验证结论：独立工具已完成，基准图真实 4× 推理通过；当前作为独立桌面应用发布。

## 1. 交付结果

- 运行目录只包含本工具、项目内 CPython Runtime、精确依赖、SeedVR2 独立 CLI 源码快照和两个模型，不携带 ComfyUI。
- Worker 使用 JSON Lines 标准输入输出，模型在进程内缓存，推理日志与协议输出隔离。
- PySide6/Qt Widgets 桌面界面支持简体中文/英文即时切换与持久化，以及选择图片与目录、单任务开始、完成当前块后停止、进度、错误提示和打开输出目录；窗口缩放基准持续验证实时重排性能。
- 图片管线复现 TTP 4× 画布、3×3 分块、25% SeedVR2 输入和 64 px 渐变融合；透明通道独立放大后保留。
- 输入会复制到 ASCII 临时目录；最终 PNG 和 JSON 报告使用唯一文件名并在完成前原子发布，不覆盖输入或旧结果。
- 没有修改其他应用，也没有删除、移动或覆盖原 ComfyUI、模型和旧验证产物。

## 2. 独立目录

```text
seedvr2-upscaler/
├─ app/                         # UI、Worker、图片管线、SeedVR2 适配
├─ models/seedvr2/              # 固定 GGUF 与 VAE（不纳入 Git）
├─ runtime/python/              # CPython 3.13.6 与独立 site-packages
├─ scripts/                     # Runtime 安装、基准和连续任务脚本
├─ tests/                       # 34 项确定性测试
├─ vendor/seedvr2/              # SeedVR2 2.5.24 CLI 最小源码快照
├─ requirements-lock.txt        # 54 distribution 精确锁定
└─ 启动 SeedVR2 放大工具.bat
```

Runtime 安装器会校验 CPython 安装器固定 SHA256 和 Python Software Foundation 数字签名；运行时设置 `PYTHONNOUSERSITE=1`，并拒绝包含 `ComfyUI` 的导入路径。

## 3. 验证环境

| 项目 | 实测值 |
|---|---|
| 操作系统 | Windows x64 |
| Python | CPython 3.13.6（项目内 Runtime） |
| PyTorch | 2.10.0+cu130 |
| CUDA wheel runtime | 13.0 |
| GPU | NVIDIA GeForce RTX 4070 Ti SUPER |
| 驱动 | 591.86 |
| 显存 | 17,170,956,288 bytes（nvidia-smi 显示 16,376 MiB） |
| SeedVR2 | 2.5.24，commit `4490bd1f482e026674543386bb2a4d176da245b9` |
| 分块参数 | 4×、3×3、64 px 渐变、SeedVR2 输入为块的 25% |
| 推理参数 | 7B Sharp Q4、resolution 1024、batch 1、blocks_to_swap 36、SDPA、wavelet、DiT/VAE cache、CPU offload、seed 2794489657 |

CUDA 自检确认 `comfyPaths` 为空，临时目录为纯 ASCII：

```text
%TEMP%\seedvr2_upscaler
```

## 4. 模型校验

| 文件 | 字节数 | SHA256 |
|---|---:|---|
| `seedvr2_ema_7b_sharp-Q4_K_M.gguf` | 4,758,306,592 | `7AED800AC4EB8E0D18569A954C0FF35F5A1CAA3ED5D920E66CC31405F75B6E69` |
| `ema_vae_fp16.safetensors` | 501,324,814 | `20678548F420D98D26F11442D3528F8B8C94E57EE046EF93DBB7633DA8612CA1` |

模型合计 5,259,631,406 bytes（约 4.90 GiB）。SeedVR2 程序源码、GGUF 与 VAE 模型均按其来源页标注的 Apache-2.0 许可证分发；来源和哈希见 `THIRD_PARTY_NOTICES.md`。

## 5. 基准图端到端结果

输入：原验证环境中的 `image (1).png`

输入 SHA256：`DA428481DB3156A334205450F93E7B64EB2DB3A1ADC0C27312534B6A44FE10C3`

| 指标 | 新独立工具实测 |
|---|---:|
| 输入尺寸 | 2048×1536 |
| 输出尺寸 | 8192×6144 |
| 分块 | 3×3，共九块 |
| 原始块尺寸 | 3032×2272 |
| SeedVR2 输入 | 758×568 |
| prepare | 0.91 s |
| SeedVR2 九块推理 | 46.70 s |
| 渐变拼接 | 3.22 s |
| Worker 完整墙钟 | 54.41 s |
| 外部命令墙钟 | 56.08 s |
| PyTorch 峰值 allocated | 6,297,630,038 bytes（5.86 GiB） |
| PyTorch 峰值 reserved | 7,818,182,656 bytes（7.28 GiB） |
| 输出文件 | 23,879,908 bytes |
| 输出 SHA256 | `01B88F8093AD31FDC18025BEBCB25BE214D61F82CAD412C900BEF6D3CB1C70EC` |
| 接缝最大平均相邻像素变化 | 1.8915/255 |

输出文件：`output/baseline/image (1)-seedvr2-4x.png`

JSON 报告：`output/baseline/image (1)-seedvr2-4x.json`

预览图：`output/baseline/image (1)-seedvr2-4x-preview.png`

接缝检查图：`output/baseline/image (1)-seedvr2-4x-seams.png`

肉眼检查：九块边界没有明显断层；瓶身轮廓、中心标识、金属高光和背景纹理在接缝处连续。新旧输出均为 RGB；由于这是在独立 Runtime 中重新执行生成式推理并重新实现拼接，两者不会字节一致。RGB 逐通道平均绝对差为 1.3571/255，最大局部差为 154/255；预览未见明显整体偏色或拼接断层，因此不能只用文件哈希判断视觉质量。

旧验证产物 SHA256 复核仍为：

```text
D0861D6CB46D38D985BC33D72BDF61572052BF47025E7923D9A28F7223490661
```

## 6. 常驻 Worker 复用结果

同一个 Worker 连续执行两次相同任务：

| 指标 | 首次任务 | 连续任务 |
|---|---:|---:|
| 外部墙钟 | 53.35 s | 46.98 s |
| Worker 墙钟 | 53.27 s | 46.97 s |
| 推理 | 45.25 s | 41.67 s |
| 峰值 reserved | 6.97 GiB | 7.28 GiB |
| 输出 SHA256 | `01B88F…1C70EC` | `01B88F…1C70EC` |

第二个任务没有再次发送 `model_ready`，证明复用了 Worker 内的模型缓存；完整墙钟减少约 6.37 秒（11.9%）。两次输出哈希一致，固定参数下结果可重复。

详细数据：`output/continuous/continuous-benchmark.json`。

## 7. 安装体积

| 构成 | 实测字节数 | 约 GiB |
|---|---:|---:|
| Python Runtime + site-packages | 3,469,437,578 | 3.23 |
| 两个模型（目录含说明文件） | 5,259,632,156 | 4.90 |
| SeedVR2 vendored 源码 | 3,217,177 | 0.003 |
| 第一方代码、脚本、测试与文档 | < 0.25 MiB | < 0.001 |
| 已安装核心目录（不含下载缓存和验证输出） | 约 8.73×10⁹ bytes | 约 8.13 GiB |

若发布时排除可重建的 `__pycache__`，当前文件集合约 7.87 GiB；首次运行会重新产生部分缓存。安装下载缓存 `.downloads/` 和 `output/` 不应进入交付包。

## 8. 自动验证与审查

- 独立 Runtime 下 34 项测试全部通过，覆盖 Qt 界面交互与语言切换控件替换、语言检测/持久化/运行时切换、几何、融合、透明通道、唯一输出、原子发布、协议隔离、启动异常、任务日志、模型复用和推理/拼接阶段取消。
- `python -m compileall -q app scripts tests` 通过。
- Qt GUI 冒烟测试与 100 次窗口缩放基准通过，p95 低于 33 ms 发布阈值；简体中文与英文界面均完成截图复核。
- CUDA、模型字节数、UTF-8、ASCII 临时目录和 ComfyUI 路径拒绝自检通过。
- 两阶段代码审查通过，未剩余 HIGH/MEDIUM 级问题。
- 其他项目工作树保持 clean；原输入、模型和旧验证产物未改动。

## 9. 已知限制和接入决策

SeedVR2 是生成式放大，可能重绘小文字、Logo、产品细节、人脸、纹理和边缘。工具已在界面持续显示：

> AI 放大可能重绘图片细节，请保留原图并检查输出结果。

当前决定：保持独立桌面应用。工具在 16 GiB 设备上已达到技术可用，但扩大硬件支持前仍需：

1. 在完全没有 ComfyUI 的另一台电脑进行离线安装与启动验收。
2. 实测 8 GiB 和 12 GiB 显卡，确认参数或最低显存要求。
3. 覆盖竖图、超长图、透明图片、文字、Logo、产品硬边缘和人脸测试集。
4. 验证长时间连续任务、用户关闭窗口和停止任务后的系统级显存释放。
5. 若以上通过，再以当前 JSON Lines Worker 作为其他本地前端的适配边界。

## 10. 复测命令

```powershell
# CUDA、模型和 ComfyUI 隔离检查
.\runtime\python\python.exe -m app.cli check --cuda

# 自动测试
.\runtime\python\python.exe -m unittest discover -s tests -v

# 单次真实基准
powershell -ExecutionPolicy Bypass -File .\scripts\run-benchmark.ps1 -Source "C:\path\input.png"

# 桌面界面
.\runtime\python\python.exe -m app.gui
```
