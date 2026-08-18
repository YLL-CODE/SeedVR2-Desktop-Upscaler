# 第三方软件、模型与许可证说明

SeedVR2 Upscaler GUI 的第一方代码采用 Apache License 2.0。项目同时包含或分发下列第三方组件；它们仍分别遵循自己的许可证。

## SeedVR2

- 项目：[IceClear/SeedVR2](https://github.com/IceClear/SeedVR2)
- 本地快照：SeedVR2 2.5.24，commit `4490bd1f482e026674543386bb2a4d176da245b9`
- 许可证：Apache License 2.0
- 本仓库保留的许可证：[vendor/seedvr2/LICENSE](./vendor/seedvr2/LICENSE)

## 模型文件

### SeedVR2 7B Sharp Q4 GGUF

- 文件：`seedvr2_ema_7b_sharp-Q4_K_M.gguf`
- 来源：[cmeka/SeedVR2-GGUF](https://huggingface.co/cmeka/SeedVR2-GGUF/blob/main/seedvr2_ema_7b_sharp-Q4_K_M.gguf)
- 许可证：Apache License 2.0
- SHA256：`7AED800AC4EB8E0D18569A954C0FF35F5A1CAA3ED5D920E66CC31405F75B6E69`

### SeedVR2 VAE fp16

- 文件：`ema_vae_fp16.safetensors`
- 来源：[Comfy-Org/SeedVR2](https://huggingface.co/Comfy-Org/SeedVR2/blob/main/vae/ema_vae_fp16.safetensors)
- 许可证：Apache License 2.0
- SHA256：`20678548F420D98D26F11442D3528F8B8C94E57EE046EF93DBB7633DA8612CA1`

## tkinterdnd2 / TkDND

- Python 包：[pmgagne/tkinterdnd2](https://github.com/pmgagne/tkinterdnd2)
- 许可证：MIT
- 本仓库保留的许可证：[app/_vendor/tkinterdnd2/LICENSE](./app/_vendor/tkinterdnd2/LICENSE)

## Qt for Python / PySide6

- 项目：[Qt for Python](https://doc.qt.io/qtforpython-6/)
- 组件：PySide6-Essentials 6.11.1、Shiboken6 6.11.1 与其随附 Qt 6 动态库和平台插件
- 许可证：LGPL-3.0-only / GPL-2.0-only / GPL-3.0-only（按上游组件提供的可选许可）
- 用途：Qt Core、Gui 与 Widgets 桌面界面、高 DPI、原生文件拖放和抗锯齿绘制

## Python Runtime 与 Python 包

Windows 完整安装包内含 CPython、PyTorch、TorchVision、CUDA 运行依赖及 [requirements-lock.txt](./requirements-lock.txt) 列出的 Python 包。安装包保留各包随 wheel 或发行物提供的许可证文件；这些组件不因本项目采用 Apache-2.0 而改变其原许可证。

本项目及其维护者不隶属于 SeedVR2、Hugging Face、Python、PyTorch 或 NVIDIA。
