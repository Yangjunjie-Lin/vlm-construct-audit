from __future__ import annotations

import pytest

from vlm_construct_audit.calibration.runner import run_smoke


def test_offline_tiny_random_vlm_forward_is_explicitly_non_scientific() -> None:
    report = run_smoke()
    assert report["fake_adapter_status"] == "PASS"
    if report["offline_tiny_random_vlm_forward"]["status"].startswith("SKIPPED"):
        pytest.skip("Torch/Transformers absent; dependency skip is explicit")
    assert report["offline_tiny_random_vlm_forward"]["status"] == "PASS"
    assert report["offline_tiny_random_vlm_forward"]["scientific_evidence"] is False
    assert report["open_weight_checkpoint_smoke"] == "NOT_EXECUTED"


def test_revision_metadata_contains_frozen_fields() -> None:
    metadata = run_smoke()["fake_adapter_metadata"]
    for field in (
        "model_repository", "model_revision", "checkpoint_hash", "processor_revision",
        "tokenizer_revision", "dtype", "quantization", "device_mapping",
        "generation_parameters", "software_versions",
    ):
        assert field in metadata
