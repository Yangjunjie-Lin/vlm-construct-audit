"""Adapters for known-state systems and non-scientific engineering smoke."""

from __future__ import annotations

import platform
import sys
from typing import Any

from ..calibration.systems import CalibrationSystem, get_system
from ..measurement.contracts import generate_constrained_raw, score_conditional_likelihood
from ..utils import canonical_hash
from .base import VLMAdapter


class CalibrationVLMAdapter(VLMAdapter):
    def __init__(self, system_name: str) -> None:
        self.system: CalibrationSystem = get_system(system_name)

    def prepare_input(self, scene, evidence, **kwargs):
        return {
            "scene": scene,
            "facts": evidence["facts"],
            "condition": evidence["condition"],
            "serialization": evidence["serialization"],
        }

    def _decision(self, prepared_input, contract):
        return self.system.infer(
            prepared_input["scene"],
            prepared_input["facts"],
            prepared_input["condition"],
            prepared_input["serialization"],
            contract,
        )

    def score_candidates(self, prepared_input, candidates, **kwargs):
        decision = self._decision(prepared_input, "conditional_likelihood")
        result = score_conditional_likelihood(decision.selected_answer, candidates)
        result["system_output"] = decision
        return result

    def generate_constrained(self, prepared_input, allowed_answers, **kwargs):
        decision = self._decision(prepared_input, "constrained_generation")
        return generate_constrained_raw(decision.selected_answer, decision.constrained_schema_valid)

    def constrained_decision(self, prepared_input):
        return self._decision(prepared_input, "constrained_generation")

    def get_revision_metadata(self):
        return {
            "model_repository": f"builtin://{self.system.name}",
            "model_revision": self.system.revision,
            "checkpoint_hash": canonical_hash({"system": self.system.name, "revision": self.system.revision}),
            "processor_revision": "deterministic-fact-parser-v1",
            "tokenizer_revision": "explicit-regex-tokenizer-v1",
            "dtype": "symbolic",
            "quantization": "none",
            "device_mapping": "cpu",
            "generation_parameters": {"temperature": 0, "do_sample": False},
            "software_versions": {"python": sys.version.split()[0], "platform": platform.platform()},
            "scientific_vlm": False,
        }


class FakeSmokeAdapter(CalibrationVLMAdapter):
    """Explicitly non-scientific adapter used to test model plumbing without weights."""

    def __init__(self) -> None:
        super().__init__("OracleEvidenceReasoner")

    def get_revision_metadata(self):
        metadata = super().get_revision_metadata()
        metadata["model_repository"] = "builtin://fake-smoke-adapter"
        metadata["engineering_smoke_only"] = True
        return metadata

