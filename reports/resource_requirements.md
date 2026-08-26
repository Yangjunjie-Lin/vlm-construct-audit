# Resource Requirements

Current Python runtime: Torch CUDA availability is `False`.
The host exposes an RTX 3060 Laptop GPU with 6 GiB through `nvidia-smi`, but the active Torch
build is CPU-only. The offline tiny-random BLIP forward passed; it is not a checkpoint smoke.

A three-family pilot needs model-specific frozen revisions, one-model-at-a-time VRAM feasibility,
checkpoint storage, image preprocessing caches, and approximately 28,800 synthetic evaluations
plus 120 separately analysed transport samples. No resource estimate is treated as execution.
