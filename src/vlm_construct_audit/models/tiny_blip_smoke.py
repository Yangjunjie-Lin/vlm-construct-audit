"""Offline tiny-random BLIP forward smoke; never a scientific checkpoint."""

from __future__ import annotations

import hashlib
from typing import Any


def run_tiny_random_blip_forward() -> dict[str, Any]:
    try:
        import torch
        import transformers
        from transformers import BlipConfig, BlipForQuestionAnswering
    except ImportError as exc:
        return {"status": "SKIPPED_DEPENDENCY_MISSING", "reason": str(exc)}

    torch.manual_seed(20260826)
    text_config = {
        "vocab_size": 128,
        "hidden_size": 16,
        "intermediate_size": 32,
        "num_hidden_layers": 1,
        "num_attention_heads": 2,
        "encoder_hidden_size": 16,
        "bos_token_id": 1,
        "eos_token_id": 2,
        "pad_token_id": 0,
    }
    vision_config = {
        "hidden_size": 16,
        "intermediate_size": 32,
        "num_hidden_layers": 1,
        "num_attention_heads": 2,
        "image_size": 16,
        "patch_size": 8,
    }
    config = BlipConfig(
        text_config=text_config,
        vision_config=vision_config,
        projection_dim=16,
        image_text_hidden_size=16,
    )
    model = BlipForQuestionAnswering(config).eval()
    with torch.no_grad():
        output = model(
            input_ids=torch.tensor([[1, 17, 23, 2]]),
            attention_mask=torch.ones(1, 4, dtype=torch.long),
            pixel_values=torch.zeros(1, 3, 16, 16),
            decoder_input_ids=torch.tensor([[1, 2]]),
        )
    tensor = output.last_hidden_state
    digest = hashlib.sha256(tensor.detach().cpu().numpy().tobytes()).hexdigest()
    return {
        "status": "PASS",
        "architecture": "BlipForQuestionAnswering",
        "weights": "random_seeded_not_a_checkpoint",
        "scientific_evidence": False,
        "device": str(tensor.device),
        "output_shape": list(tensor.shape),
        "output_sha256": digest,
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
        "cuda_available_to_torch": torch.cuda.is_available(),
    }
