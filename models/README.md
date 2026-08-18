# Models

Place these two Apache-2.0 model files in `models/SEEDVR2/`:

| File | Bytes | SHA256 | Source |
|---|---:|---|---|
| `seedvr2_ema_7b_sharp-Q4_K_M.gguf` | 4,758,306,592 | `7AED800AC4EB8E0D18569A954C0FF35F5A1CAA3ED5D920E66CC31405F75B6E69` | [cmeka/SeedVR2-GGUF](https://huggingface.co/cmeka/SeedVR2-GGUF/blob/main/seedvr2_ema_7b_sharp-Q4_K_M.gguf) |
| `ema_vae_fp16.safetensors` | 501,324,814 | `20678548F420D98D26F11442D3528F8B8C94E57EE046EF93DBB7633DA8612CA1` | [Comfy-Org/SeedVR2](https://huggingface.co/Comfy-Org/SeedVR2/blob/main/vae/ema_vae_fp16.safetensors) |

The application checks the exact filenames and byte sizes before inference. See [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) for attribution and licensing details.
