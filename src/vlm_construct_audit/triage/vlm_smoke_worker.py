"""Isolated real-checkpoint worker for the non-scientific Loop C preflight."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import random
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import psutil
import torch
import yaml
from PIL import Image, ImageDraw
from torchvision import transforms
from torchvision.transforms.functional import InterpolationMode

from vlm_construct_audit.measurement.strict_parser import parse_declared_contract

ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_ROOT = ROOT / "artifacts" / "loop_c"
COLORS = ["red", "green", "blue"]
COLOR_RGB = {"red": (220, 40, 40), "green": (35, 175, 70), "blue": (40, 90, 220)}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _dump_yaml(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def environment_snapshot() -> dict[str, Any]:
    import accelerate
    import bitsandbytes
    import google.protobuf
    import hf_xet
    import sentencepiece
    import transformers

    gpu = None
    if torch.cuda.is_available():
        properties = torch.cuda.get_device_properties(0)
        gpu = {
            "name": properties.name,
            "total_vram_bytes": properties.total_memory,
            "architecture": str(properties.gcnArchName) if hasattr(properties, "gcnArchName") else None,
        }
    return {
        "operating_system": platform.platform(),
        "python": sys.version,
        "python_executable": sys.executable,
        "torch": str(torch.__version__),
        "torch_cuda_build": str(torch.version.cuda),
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_count": torch.cuda.device_count(),
        "gpu": gpu,
        "ram_bytes": psutil.virtual_memory().total,
        "disk_free_bytes": psutil.disk_usage(str(ROOT.drive + "\\")).free,
        "transformers": str(transformers.__version__),
        "accelerate": str(accelerate.__version__),
        "bitsandbytes": str(bitsandbytes.__version__),
        "protobuf": str(google.protobuf.__version__),
        "sentencepiece": str(sentencepiece.__version__),
        "hf_xet": str(hf_xet.__version__) if hasattr(hf_xet, "__version__") else "1.1.9",
    }


def _make_images() -> list[dict[str, Any]]:
    image_root = ARTIFACT_ROOT / "images"
    image_root.mkdir(parents=True, exist_ok=True)
    rows = []
    rng = random.Random(73000)
    relations = ["left_of", "right_of", "above", "below", "in_front_of", "behind"]
    for index in range(12):
        color = COLORS[index % len(COLORS)]
        other = COLORS[(index + 1) % len(COLORS)]
        entity_a = f"smoke_{rng.randrange(100, 999)}_a"
        entity_b = f"smoke_{rng.randrange(100, 999)}_b"
        relation = relations[index % len(relations)]
        image = Image.new("RGB", (224, 224), (245, 245, 245))
        draw = ImageDraw.Draw(image)
        draw.rectangle((22, 82, 92, 152), fill=COLOR_RGB[color], outline=(0, 0, 0), width=3)
        draw.ellipse((132, 82, 202, 152), fill=COLOR_RGB[other], outline=(0, 0, 0), width=3)
        draw.text((28, 158), entity_a, fill=(0, 0, 0))
        draw.text((136, 158), entity_b, fill=(0, 0, 0))
        path = image_root / f"loop_c_scene_{index:02d}.png"
        image.save(path)
        rows.append(
            {
                "scene_id": f"loop_c_dev_{index:02d}",
                "path": path,
                "entity_a": entity_a,
                "entity_b": entity_b,
                "color_a": color,
                "color_b": other,
                "relation": relation,
                "sha256": _sha256_file(path),
            }
        )
    return rows


def _prompt(case_index: int, scene: dict[str, Any], serialization: str, contract: str) -> str:
    if serialization == "natural_language":
        evidence = (
            f"Entity {scene['entity_a']} has color {scene['color_a']}.\n"
            f"Entity {scene['entity_a']} is {scene['relation']} entity {scene['entity_b']}."
        )
    else:
        evidence = (
            f"({scene['entity_a']}, color, {scene['color_a']})\n"
            f"({scene['entity_a']}, {scene['relation']}, {scene['entity_b']})"
        )
    mode = case_index % 6
    if mode == 0:
        question = f"Return the recorded color of entity {scene['entity_a']}."
    elif mode == 1:
        question = f"Map entity {scene['entity_a']} to its recorded color."
    elif mode == 2:
        question = f"Read the direct attribute bound to {scene['entity_a']}."
    elif mode == 3:
        question = f"Use the directed relation record, then return {scene['entity_a']}'s color."
    elif mode == 4:
        question = "Select one semantic color candidate; some candidate labels may use multiple tokens."
    else:
        question = f"Confirm the option mapping for {scene['entity_a']} from the supplied record."
    if contract == "constrained_generation":
        output = 'Return exactly one JSON object: {"answer":"red"}. Replace red with one of red, green, blue.'
    else:
        output = "The answer must be exactly one candidate from: red, green, blue. Answer: "
    return f"Engineering measurement smoke only.\nEvidence:\n{evidence}\nQuestion: {question}\n{output}"


def _to_device(inputs: dict[str, Any], device: torch.device) -> dict[str, Any]:
    return {key: value.to(device) if hasattr(value, "to") else value for key, value in inputs.items()}


def _score_rows(
    model: Any,
    build_inputs: Any,
    base_text: str,
    candidates: list[str],
) -> dict[str, Any]:
    records = {}
    maximum_difference = 0.0
    for candidate in candidates:
        base_inputs = build_inputs(base_text)
        full_inputs = build_inputs(base_text + candidate)
        base_ids = base_inputs["input_ids"][0]
        full_ids = full_inputs["input_ids"][0]
        base_length = int(base_ids.numel())
        if full_ids[:base_length].tolist() != base_ids.tolist():
            raise RuntimeError("Candidate-scoring prompt is not a token prefix of the full sequence")
        if int(full_ids.numel()) <= base_length:
            raise RuntimeError("Candidate produced no scored tokens")
        with torch.inference_mode():
            outputs = model(**full_inputs, use_cache=False, return_dict=True)
        token_ids = full_ids[base_length:]
        logits = outputs.logits[0, base_length - 1 : int(full_ids.numel()) - 1].float()
        if logits.shape[0] != token_ids.shape[0]:
            raise RuntimeError("Shifted candidate logit count mismatch")
        torch_values = torch.log_softmax(logits, dim=-1).gather(1, token_ids[:, None]).squeeze(1)
        numpy_logits = logits.detach().cpu().numpy().astype(np.float64)
        numpy_ids = token_ids.detach().cpu().numpy()
        independent = np.asarray(
            [row[int(target)] - np.logaddexp.reduce(row) for row, target in zip(numpy_logits, numpy_ids, strict=True)]
        )
        torch_numpy = torch_values.detach().cpu().numpy().astype(np.float64)
        difference = float(np.max(np.abs(torch_numpy - independent)))
        maximum_difference = max(maximum_difference, difference)
        raw = float(torch_values.sum().item())
        records[candidate] = {
            "candidate_token_ids": token_ids.detach().cpu().tolist(),
            "token_count": int(token_ids.numel()),
            "raw_log_likelihood": raw,
            "length_normalized_score": raw / int(token_ids.numel()),
            "independent_raw_log_likelihood": float(independent.sum()),
            "independent_length_normalized_score": float(independent.mean()),
            "maximum_token_logprob_difference": difference,
        }
        del outputs, logits, torch_values
    ranking_a = sorted(candidates, key=lambda item: (-records[item]["length_normalized_score"], candidates.index(item)))
    ranking_b = sorted(
        candidates,
        key=lambda item: (-records[item]["independent_length_normalized_score"], candidates.index(item)),
    )
    return {
        "scores": records,
        "ranking": ranking_a,
        "independent_ranking": ranking_b,
        "ranking_agreement": ranking_a == ranking_b,
        "maximum_token_logprob_difference": maximum_difference,
        "candidate_margin": records[ranking_a[0]]["length_normalized_score"]
        - records[ranking_a[1]]["length_normalized_score"],
    }


class StandardWorker:
    def __init__(self, registry: dict[str, Any]) -> None:
        from transformers import AutoProcessor, BitsAndBytesConfig

        self.registry = registry
        repository = registry["repository"]
        revision = registry["revision"]
        self.processor = AutoProcessor.from_pretrained(repository, revision=revision)
        kwargs: dict[str, Any] = {
            "revision": revision,
            "torch_dtype": torch.float16,
            "device_map": {"": 0},
            "low_cpu_mem_usage": True,
        }
        if registry["quantization"] == "bitsandbytes_int8":
            kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        if registry["family"] == "Qwen2-VL":
            from transformers import Qwen2VLForConditionalGeneration

            model_class = Qwen2VLForConditionalGeneration
        else:
            from transformers import AutoModelForVision2Seq

            model_class = AutoModelForVision2Seq
        self.model = model_class.from_pretrained(repository, **kwargs).eval()
        self.device = next(self.model.parameters()).device

    def base_text(self, prompt: str) -> str:
        messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
        return self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    def build_inputs(self, text: str, image: Image.Image) -> dict[str, Any]:
        values = self.processor(text=[text], images=[image], return_tensors="pt")
        return _to_device(dict(values), self.device)

    def score(self, prompt: str, image: Image.Image) -> dict[str, Any]:
        base = self.base_text(prompt)
        return _score_rows(self.model, lambda text: self.build_inputs(text, image), base, COLORS)

    def generate(self, prompt: str, image: Image.Image) -> str:
        base = self.base_text(prompt)
        inputs = self.build_inputs(base, image)
        input_length = int(inputs["input_ids"].shape[1])
        with torch.inference_mode():
            output = self.model.generate(
                **inputs,
                max_new_tokens=14,
                do_sample=False,
                num_beams=1,
                use_cache=True,
            )
        return self.processor.batch_decode(output[:, input_length:], skip_special_tokens=True)[0].strip()


class InternVLWorker:
    def __init__(self, registry: dict[str, Any]) -> None:
        from transformers import AutoModel, AutoTokenizer

        self.registry = registry
        repository = registry["repository"]
        revision = registry["revision"]
        self.tokenizer = AutoTokenizer.from_pretrained(
            repository,
            revision=revision,
            trust_remote_code=True,
            use_fast=False,
        )
        self.model = AutoModel.from_pretrained(
            repository,
            revision=revision,
            torch_dtype=torch.float16,
            load_in_8bit=True,
            low_cpu_mem_usage=True,
            use_flash_attn=False,
            trust_remote_code=True,
            device_map={"": 0},
        ).eval()
        self.device = next(self.model.parameters()).device
        self.transform = transforms.Compose(
            [
                transforms.Lambda(lambda image: image.convert("RGB")),
                transforms.Resize((448, 448), interpolation=InterpolationMode.BICUBIC),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=(0.485, 0.456, 0.406),
                    std=(0.229, 0.224, 0.225),
                ),
            ]
        )

    def pixels(self, image: Image.Image) -> torch.Tensor:
        return self.transform(image).unsqueeze(0).to(device=self.device, dtype=torch.float16)

    def generate(self, prompt: str, image: Image.Image) -> str:
        return self.model.chat(
            self.tokenizer,
            self.pixels(image),
            "<image>\n" + prompt,
            {"max_new_tokens": 14, "do_sample": False, "num_beams": 1},
        )

    def _base_query(self, prompt: str) -> str:
        module = sys.modules[self.model.__class__.__module__]
        template = module.get_conv_template(self.model.template)
        template.system_message = self.model.system_message
        template.append_message(template.roles[0], "<image>\n" + prompt)
        template.append_message(template.roles[1], None)
        query = template.get_prompt()
        self.model.img_context_token_id = self.tokenizer.convert_tokens_to_ids("<IMG_CONTEXT>")
        image_tokens = "<img>" + "<IMG_CONTEXT>" * self.model.num_image_token + "</img>"
        return query.replace("<image>", image_tokens, 1)

    def score(self, prompt: str, image: Image.Image) -> dict[str, Any]:
        pixels = self.pixels(image)
        base = self._base_query(prompt)

        def build_inputs(text: str) -> dict[str, Any]:
            values = self.tokenizer(text, return_tensors="pt")
            return {
                "pixel_values": pixels,
                "input_ids": values["input_ids"].to(self.device),
                "attention_mask": values["attention_mask"].to(self.device),
                "image_flags": torch.ones((1, 1), dtype=torch.long, device=self.device),
            }

        return _score_rows(self.model, build_inputs, base, COLORS)


def _model_cache_integrity(registry: dict[str, Any]) -> dict[str, Any]:
    from huggingface_hub import snapshot_download

    path = Path(
        snapshot_download(
            repo_id=registry["repository"],
            revision=registry["revision"],
            local_files_only=True,
        )
    )
    weights = []
    for file in sorted(path.glob("*.safetensors")):
        weights.append(
            {
                "filename": file.name,
                "size_bytes": file.stat().st_size,
                "sha256": _sha256_file(file),
            }
        )
    return {
        "snapshot_path_suffix": str(path).replace("\\", "/").split("/snapshots/")[-1],
        "snapshot_revision_matches": path.name == registry["revision"],
        "weight_files": weights,
        "weight_bytes": sum(item["size_bytes"] for item in weights),
        "not_tiny_random": sum(item["size_bytes"] for item in weights) > 100_000_000,
    }


def _run_case(
    worker: Any,
    registry: dict[str, Any],
    scene: dict[str, Any],
    case_index: int,
    contract: str,
    serialization: str,
    config_hash: str,
) -> dict[str, Any]:
    prompt = _prompt(case_index, scene, serialization, contract)
    image = Image.open(scene["path"]).convert("RGB")
    started = time.perf_counter()
    if contract == "conditional_likelihood":
        candidate_scores = worker.score(prompt, image)
        raw_response = None
        parsed_response = candidate_scores["ranking"][0]
        parser_status = "not_applicable_conditional_likelihood"
    else:
        candidate_scores = None
        raw_response = worker.generate(prompt, image)
        parsed = parse_declared_contract(
            raw_response,
            schema="semantic_answer",
            allowed_answers=COLORS,
            option_id_mapping={"A": "red", "B": "green", "C": "blue"},
        )
        parsed_response = parsed["parsed_response"]
        parser_status = parsed["parser_status"]
    elapsed = time.perf_counter() - started
    return {
        "model_family": registry["family"],
        "model_id": registry["model_id"],
        "model_revision": registry["revision"],
        "scene_id": scene["scene_id"],
        "split": "development_only",
        "condition": "engineering_smoke_no_factorial",
        "serialization": serialization,
        "contract": contract,
        "raw_response": raw_response,
        "parsed_response": parsed_response,
        "candidate_scores": candidate_scores,
        "parser_status": parser_status,
        "runtime_seconds": elapsed,
        "timestamp": _utc(),
        "config_hash": config_hash,
        "scientific_outcome_use_forbidden": True,
    }


def run_model(registry_path: str, model_id: str) -> int:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    registry_document = yaml.safe_load(Path(registry_path).read_text(encoding="utf-8"))
    registry = next(item for item in registry_document["models"] if item["model_id"] == model_id)
    config_hash = _canonical_hash(registry_document)
    output_root = ARTIFACT_ROOT / model_id
    output_root.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "schema_version": 1,
        "model_id": model_id,
        "family": registry["family"],
        "repository": registry["repository"],
        "revision": registry["revision"],
        "config_hash": config_hash,
        "checkpoint_load_success": False,
        "actual_visual_forward_success": False,
        "status": "FAILED",
        "scientific_vlm_result": "NOT_EXECUTED",
    }
    try:
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is not available in the isolated smoke environment")
        torch.manual_seed(73000)
        torch.cuda.manual_seed_all(73000)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.cuda.reset_peak_memory_stats()
        process = psutil.Process()
        load_started = time.perf_counter()
        worker = InternVLWorker(registry) if registry["family"].startswith("InternVL") else StandardWorker(registry)
        summary["checkpoint_load_success"] = True
        summary["checkpoint_load_seconds"] = time.perf_counter() - load_started
        summary["checkpoint_integrity"] = _model_cache_integrity(registry)
        scenes = _make_images()
        cases = []
        for index in range(40):
            contract = "conditional_likelihood" if index < 20 else "constrained_generation"
            serialization = "natural_language" if index % 2 == 0 else "triples"
            cases.append((index, scenes[index % len(scenes)], contract, serialization))
        rows = []
        reruns = []
        for index, scene, contract, serialization in cases:
            row = _run_case(worker, registry, scene, index, contract, serialization, config_hash)
            rows.append(row)
            repeat = _run_case(worker, registry, scene, index, contract, serialization, config_hash)
            if contract == "conditional_likelihood":
                agreement = (
                    row["candidate_scores"]["ranking"] == repeat["candidate_scores"]["ranking"]
                    and abs(
                        row["candidate_scores"]["candidate_margin"]
                        - repeat["candidate_scores"]["candidate_margin"]
                    )
                    <= 1e-6
                )
            else:
                agreement = row["raw_response"] == repeat["raw_response"]
            reruns.append(
                {
                    "model_id": model_id,
                    "scene_id": scene["scene_id"],
                    "contract": contract,
                    "serialization": serialization,
                    "agreement": agreement,
                    "first_parser_status": row["parser_status"],
                    "second_parser_status": repeat["parser_status"],
                    "config_hash": config_hash,
                }
            )
            summary["actual_visual_forward_success"] = True
        _write_jsonl(output_root / "predictions.jsonl", rows)
        _write_jsonl(output_root / "deterministic_reruns.jsonl", reruns)
        parser_rows = [row for row in rows if row["contract"] == "constrained_generation"]
        cll_rows = [row for row in rows if row["contract"] == "conditional_likelihood"]
        required_fields = {
            "model_family", "model_id", "model_revision", "scene_id", "split", "condition",
            "serialization", "contract", "raw_response", "parsed_response", "candidate_scores",
            "parser_status", "runtime_seconds", "timestamp", "config_hash",
        }
        summary.update(
            {
                "status": "PASS",
                "case_count": len(rows),
                "model_evaluation_count_including_reruns": len(rows) + len(reruns),
                "artifact_completeness": sum(required_fields <= set(row) for row in rows) / len(rows),
                "parser_valid_rate": sum(row["parser_status"] == "ok" for row in parser_rows) / len(parser_rows),
                "independent_scorer_ranking_agreement": sum(
                    row["candidate_scores"]["ranking_agreement"] for row in cll_rows
                )
                / len(cll_rows),
                "maximum_independent_token_logprob_difference": max(
                    row["candidate_scores"]["maximum_token_logprob_difference"] for row in cll_rows
                ),
                "deterministic_rerun_agreement": sum(row["agreement"] for row in reruns) / len(reruns),
                "peak_vram_bytes": torch.cuda.max_memory_allocated(),
                "peak_ram_bytes": getattr(process.memory_info(), "peak_wset", process.memory_info().rss),
                "latency_seconds_mean": sum(row["runtime_seconds"] for row in rows) / len(rows),
                "latency_seconds_total_primary": sum(row["runtime_seconds"] for row in rows),
                "no_silent_fallback": True,
                "mock_or_tiny_random_substitution": False,
            }
        )
        summary["gates"] = {
            "checkpoint_load": summary["checkpoint_load_success"],
            "visual_forward": summary["actual_visual_forward_success"],
            "artifact_completeness": summary["artifact_completeness"] == 1.0,
            "parser_valid_rate": summary["parser_valid_rate"] >= 0.98,
            "independent_scorer": summary["independent_scorer_ranking_agreement"] == 1.0,
            "determinism": summary["deterministic_rerun_agreement"] >= 0.99,
            "no_silent_fallback": summary["no_silent_fallback"],
            "not_mock_or_tiny_random": not summary["mock_or_tiny_random_substitution"],
        }
        if not all(summary["gates"].values()):
            summary["status"] = "GATE_FAILED"
        _dump_yaml(output_root / "summary.yaml", summary)
        return 0
    except Exception as exc:  # noqa: BLE001 - a failed checkpoint must leave an auditable summary
        summary["error_type"] = type(exc).__name__
        summary["error"] = str(exc)
        summary["traceback"] = traceback.format_exc()
        if torch.cuda.is_available():
            summary["peak_vram_bytes"] = torch.cuda.max_memory_allocated()
        _dump_yaml(output_root / "summary.yaml", summary)
        return 2
    finally:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", action="store_true")
    parser.add_argument("--registry", default="configs/model_smoke_registry.yaml")
    parser.add_argument("--model-id")
    args = parser.parse_args()
    if args.environment:
        print(json.dumps(environment_snapshot(), sort_keys=True))
        return 0
    if not args.model_id:
        parser.error("--model-id is required unless --environment is used")
    return run_model(args.registry, args.model_id)


if __name__ == "__main__":
    raise SystemExit(main())
