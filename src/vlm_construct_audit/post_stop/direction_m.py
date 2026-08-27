"""Direction M real-checkpoint answer-contract decomposition."""

from __future__ import annotations

import gc
import json
import math
import re
import time
import traceback
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np
import torch
from PIL import Image, ImageDraw

from ..measurement.strict_parser import parse_declared_contract
from ..triage.vlm_smoke_worker import (
    InternVLWorker,
    StandardWorker,
    _score_rows,
)
from .common import ROOT, canonical_hash, dump_yaml, load_yaml, sha256_file, utc_now, write_jsonl

CONTRACTS = ["M-C1", "M-C2", "M-C3", "M-C4"]
COLORS = {
    "red": (220, 45, 45),
    "green": (40, 170, 75),
    "blue": (45, 90, 220),
    "yellow": (230, 195, 35),
}
MULTI_COLORS = {
    "deep red": (170, 25, 35),
    "forest green": (25, 120, 60),
    "ocean blue": (30, 95, 175),
    "golden yellow": (220, 165, 25),
}
SHAPES = ["circle", "square", "triangle", "star"]


def _polygon_star(cx: int, cy: int, radius: int) -> list[tuple[int, int]]:
    points = []
    for index in range(10):
        angle = -math.pi / 2 + index * math.pi / 5
        length = radius if index % 2 == 0 else radius * 0.45
        points.append((int(cx + math.cos(angle) * length), int(cy + math.sin(angle) * length)))
    return points


def _draw_shape(draw: ImageDraw.ImageDraw, shape: str, center: tuple[int, int], color: tuple[int, int, int]) -> None:
    x, y = center
    box = (x - 35, y - 35, x + 35, y + 35)
    if shape == "circle":
        draw.ellipse(box, fill=color, outline=(0, 0, 0), width=3)
    elif shape == "square":
        draw.rectangle(box, fill=color, outline=(0, 0, 0), width=3)
    elif shape == "triangle":
        draw.polygon([(x, y - 40), (x - 40, y + 35), (x + 40, y + 35)], fill=color, outline=(0, 0, 0))
    else:
        draw.polygon(_polygon_star(x, y, 42), fill=color, outline=(0, 0, 0))


def _scene_question(task: str, shapes: list[str], colors: list[str], relation: str) -> tuple[str, list[str], str]:
    if task == "object_identity":
        return "Which object is leftmost?", SHAPES, shapes[0]
    if task == "color":
        return "What color is the leftmost object?", list(COLORS), colors[0]
    if task == "shape":
        return "What shape is the rightmost object?", SHAPES, shapes[1]
    if task == "direct_relation_direction":
        return f"Where is the {shapes[0]} relative to the {shapes[1]}?", ["left of", "right of", "above", "below"], relation
    if task == "entity_attribute_binding":
        return f"What color is the {shapes[1]}?", list(COLORS), colors[1]
    if task == "option_mapping":
        mapping = {"red": "option alpha", "green": "option beta", "blue": "option gamma", "yellow": "option delta"}
        question = "Use red=option alpha, green=option beta, blue=option gamma, yellow=option delta. Which option maps to the leftmost object's color?"
        return question, list(mapping.values()), mapping[colors[0]]
    multi = list(MULTI_COLORS)
    return "Which multi-word color best describes the leftmost object?", multi, colors[0]


def build_scenes(split: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    spec = config["scenes"]["development" if split == "development" else "sealed_holdout"]
    root = ROOT / "artifacts/post_stop/direction_m" / split / "images"
    root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(spec["seed"]))
    tasks = list(config["scenes"]["tasks"])
    scenes = []
    for index in range(int(spec["count"])):
        task = tasks[index % len(tasks)]
        shapes = list(rng.choice(SHAPES, size=2, replace=False))
        palette = list(MULTI_COLORS) if task == "multi_token_answer" else list(COLORS)
        colors = list(rng.choice(palette, size=2, replace=False))
        vertical = task == "direct_relation_direction" and index % 4 in {2, 3}
        if vertical:
            centers = [(168, 65), (168, 170)] if index % 4 == 2 else [(168, 170), (168, 65)]
            relation = "above" if centers[0][1] < centers[1][1] else "below"
        else:
            centers = [(85, 112), (250, 112)]
            relation = "left of" if centers[0][0] < centers[1][0] else "right of"
        image = Image.new("RGB", (336, 224), (246, 246, 246))
        draw = ImageDraw.Draw(image)
        palette_values = MULTI_COLORS if task == "multi_token_answer" else COLORS
        _draw_shape(draw, shapes[0], centers[0], palette_values[colors[0]])
        _draw_shape(draw, shapes[1], centers[1], palette_values[colors[1]])
        question, candidates, truth = _scene_question(task, shapes, colors, relation)
        path = root / f"{spec['namespace']}_{index:03d}.png"
        image.save(path)
        scenes.append({
            "scene_id": f"{spec['namespace']}_{index:03d}",
            "split": split,
            "task": task,
            "image_path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "image_sha256": sha256_file(path.relative_to(ROOT)),
            "shapes": shapes,
            "colors": colors,
            "relation": relation,
            "question": question,
            "candidates": candidates,
            "truth": truth,
        })
    write_jsonl(Path("artifacts/post_stop/direction_m") / split / "scenes.jsonl", scenes)
    return scenes


def _prompt(scene: dict[str, Any], serialization: str, contract: str) -> str:
    candidates = ", ".join(scene["candidates"])
    if serialization == "natural_language":
        question = scene["question"]
    else:
        question = f"FUNCTIONAL_QUERY[task={scene['task']}; query={scene['question']}]"
    base = f"Inspect the image and answer the direct question.\n{question}\nAllowed semantic answers: {candidates}.\n"
    if contract == "M-C1":
        return base + "Return exactly one allowed semantic answer. Answer: "
    if contract in {"M-C2", "M-C3"}:
        return base + 'Return exactly one JSON object with no other text: {"answer":"<allowed semantic answer>"}.'
    return base + "Return only the semantic answer, with no explanation."


def canonicalize_response(raw: str, allowed_answers: list[str]) -> dict[str, Any]:
    allowed = {answer.casefold(): answer for answer in allowed_answers}
    value = raw.strip()
    terminal = re.sub(r"[.!?]+$", "", value).strip()
    if terminal.casefold() in allowed:
        return {"parsed_response": allowed[terminal.casefold()], "status": "ok_semantic_token"}
    fence = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", value, flags=re.IGNORECASE | re.DOTALL)
    json_values = []
    if fence:
        json_values = [fence.group(1)]
    else:
        json_values = re.findall(r"\{[^{}]*\}", value, flags=re.DOTALL)
        if len(json_values) != 1:
            return {"parsed_response": None, "status": "rejected_invalid_or_ambiguous"}
    try:
        obj = json.loads(json_values[0])
    except json.JSONDecodeError:
        return {"parsed_response": None, "status": "rejected_invalid_or_ambiguous"}
    if not isinstance(obj, dict) or set(obj) != {"answer"} or not isinstance(obj["answer"], str):
        return {"parsed_response": None, "status": "rejected_invalid_or_ambiguous"}
    answer = obj["answer"].strip().casefold()
    if answer not in allowed:
        return {"parsed_response": None, "status": "rejected_invalid_or_ambiguous"}
    return {"parsed_response": allowed[answer], "status": "ok_single_json_object"}


def canonicalizer_validation() -> dict[str, Any]:
    allowed = ["deep red", "forest green", "ocean blue"]
    valid = [
        ("deep red", "deep red"), ("DEEP RED", "deep red"), ("forest green.", "forest green"),
        ('```json\n{"answer":"ocean blue"}\n```', "ocean blue"),
        ('Answer record: {"answer":"deep red"}', "deep red"),
    ]
    invalid = [
        "reddish", '{"answer":"red"}', '{"answer":"deep red","extra":1}',
        '{"answer":"deep red"} {"answer":"forest green"}', "deep red or forest green",
    ]
    valid_recall = sum(canonicalize_response(raw, allowed)["parsed_response"] == truth for raw, truth in valid) / len(valid)
    invalid_rejection = sum(canonicalize_response(raw, allowed)["parsed_response"] is None for raw in invalid) / len(invalid)
    return {"valid_form_recall": valid_recall, "invalid_ambiguous_rejection": invalid_rejection, "valid_cases": len(valid), "invalid_cases": len(invalid)}


def _generic_score(worker: Any, prompt: str, image: Image.Image, candidates: list[str]) -> dict[str, Any]:
    if isinstance(worker, InternVLWorker):
        pixels = worker.pixels(image)
        base = worker._base_query(prompt)

        def build(text: str) -> dict[str, Any]:
            values = worker.tokenizer(text, return_tensors="pt")
            return {
                "pixel_values": pixels,
                "input_ids": values["input_ids"].to(worker.device),
                "attention_mask": values["attention_mask"].to(worker.device),
                "image_flags": torch.ones((1, 1), dtype=torch.long, device=worker.device),
            }
        return _score_rows(worker.model, build, base, candidates)
    base = worker.base_text(prompt)
    return _score_rows(worker.model, lambda text: worker.build_inputs(text, image), base, candidates)


def _finite_json_sequences(worker: Any, base: str, image: Image.Image, answers: list[str]) -> tuple[dict[str, Any], list[list[int]], Any]:
    strings = [json.dumps({"answer": answer}, separators=(",", ":")) for answer in answers]
    if isinstance(worker, InternVLWorker):
        pixels = worker.pixels(image)
        values = worker.tokenizer(base, return_tensors="pt")
        inputs = {
            "pixel_values": pixels,
            "input_ids": values["input_ids"].to(worker.device),
            "attention_mask": values["attention_mask"].to(worker.device),
            "image_flags": torch.ones((1, 1), dtype=torch.long, device=worker.device),
        }
        tokenizer = worker.tokenizer
        full_ids = [worker.tokenizer(base + value, return_tensors="pt")["input_ids"][0].tolist() for value in strings]
    else:
        inputs = worker.build_inputs(base, image)
        tokenizer = worker.processor.tokenizer
        full_ids = [worker.build_inputs(base + value, image)["input_ids"][0].tolist() for value in strings]
    prefix = inputs["input_ids"][0].tolist()
    sequences = []
    for ids in full_ids:
        if ids[:len(prefix)] != prefix:
            raise RuntimeError("grammar candidate is not token-prefix compatible")
        sequences.append(ids[len(prefix):])
    return inputs, sequences, tokenizer


def _constrained_generate(worker: Any, prompt: str, image: Image.Image, answers: list[str]) -> tuple[str, dict[str, Any]]:
    base = worker._base_query(prompt) if isinstance(worker, InternVLWorker) else worker.base_text(prompt)
    inputs, sequences, tokenizer = _finite_json_sequences(worker, base, image, answers)
    input_length = int(inputs["input_ids"].shape[1])
    eos = tokenizer.eos_token_id

    def allowed(_batch: int, ids: torch.Tensor) -> list[int]:
        suffix = ids.tolist()[input_length:]
        next_tokens = {sequence[len(suffix)] for sequence in sequences if len(suffix) < len(sequence) and sequence[:len(suffix)] == suffix}
        if any(sequence == suffix for sequence in sequences):
            next_tokens.add(eos)
        if not next_tokens:
            return [eos]
        return sorted(next_tokens)

    with torch.inference_mode():
        output = worker.model.generate(
            **inputs,
            max_new_tokens=max(map(len, sequences)) + 1,
            do_sample=False,
            num_beams=1,
            use_cache=True,
            prefix_allowed_tokens_fn=allowed,
            eos_token_id=eos,
            pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else eos,
        )
    suffix = output[0, input_length:]
    raw = tokenizer.decode(suffix, skip_special_tokens=True).strip()
    return raw, {"automaton_language_size": len(sequences), "allowed_token_sequences": sequences, "token_level_mask_applied": True}


def _run_once(worker: Any, scene: dict[str, Any], serialization: str, contract: str) -> dict[str, Any]:
    prompt = _prompt(scene, serialization, contract)
    image = Image.open(ROOT / scene["image_path"]).convert("RGB")
    started = time.perf_counter()
    scorer = None
    automaton = None
    if contract == "M-C1":
        scorer = _generic_score(worker, prompt, image, scene["candidates"])
        raw = None
        semantic = scorer["ranking"][0]
        parser_status = "not_applicable_conditional_likelihood"
        syntactic_valid = None
    elif contract == "M-C2":
        raw, automaton = _constrained_generate(worker, prompt, image, scene["candidates"])
        parsed = parse_declared_contract(raw, schema="semantic_answer", allowed_answers=scene["candidates"], option_id_mapping={})
        semantic = parsed["parsed_response"]
        parser_status = parsed["parser_status"]
        syntactic_valid = parser_status == "ok"
    elif contract == "M-C3":
        raw = worker.generate(prompt, image)
        parsed = parse_declared_contract(raw, schema="semantic_answer", allowed_answers=scene["candidates"], option_id_mapping={})
        semantic = parsed["parsed_response"]
        parser_status = parsed["parser_status"]
        syntactic_valid = parser_status == "ok"
    else:
        raw = worker.generate(prompt, image)
        parsed = canonicalize_response(raw, scene["candidates"])
        semantic = parsed["parsed_response"]
        parser_status = parsed["status"]
        syntactic_valid = None
    return {
        "contract": contract,
        "elicitation_prompt": prompt,
        "decoding_constraint": "finite_language_token_prefix_automaton" if contract == "M-C2" else None,
        "raw_response": raw,
        "semantic_answer": semantic,
        "parser_status": parser_status,
        "syntactic_valid": syntactic_valid,
        "task_correct": semantic == scene["truth"] if semantic is not None else False,
        "candidate_scores": scorer,
        "automaton": automaton,
        "runtime_seconds": time.perf_counter() - started,
    }


def run_model(split: str, config: dict[str, Any], registry: dict[str, Any], scenes: list[dict[str, Any]]) -> dict[str, Any]:
    model_id = registry["model_id"]
    root = Path("artifacts/post_stop/direction_m") / split / model_id
    summary: dict[str, Any] = {"model_id": model_id, "family": registry["family"], "revision": registry["revision"], "status": "FAILED"}
    try:
        worker_registry = next(item for item in load_yaml("configs/model_smoke_registry.yaml")["models"] if item["model_id"] == model_id)
        worker = InternVLWorker(worker_registry) if registry["family"].startswith("InternVL") else StandardWorker(worker_registry)
        rows = []
        reruns = []
        for scene in scenes:
            for serialization in config["scenes"]["serializations"]:
                for contract in CONTRACTS:
                    first = _run_once(worker, scene, serialization, contract)
                    second = _run_once(worker, scene, serialization, contract)
                    row = {
                        "model_id": model_id, "family": registry["family"], "revision": registry["revision"],
                        "split": split, "scene_id": scene["scene_id"], "task": scene["task"],
                        "serialization": serialization, "truth": scene["truth"], "candidates": scene["candidates"],
                        "image_sha256": scene["image_sha256"], "config_hash": canonical_hash(config), **first,
                    }
                    rows.append(row)
                    if contract == "M-C1":
                        agreement = first["semantic_answer"] == second["semantic_answer"] and abs(first["candidate_scores"]["candidate_margin"] - second["candidate_scores"]["candidate_margin"]) <= 1e-6
                    else:
                        agreement = first["raw_response"] == second["raw_response"]
                    reruns.append({"model_id": model_id, "scene_id": scene["scene_id"], "serialization": serialization, "contract": contract, "agreement": agreement, "first_semantic": first["semantic_answer"], "second_semantic": second["semantic_answer"], "config_hash": canonical_hash(config)})
        write_jsonl(root / "predictions.jsonl", rows)
        write_jsonl(root / "deterministic_reruns.jsonl", reruns)
        required = {"model_id", "family", "revision", "split", "scene_id", "task", "serialization", "contract", "raw_response", "semantic_answer", "parser_status", "task_correct", "config_hash"}
        c1 = [row for row in rows if row["contract"] == "M-C1"]
        c2 = [row for row in rows if row["contract"] == "M-C2"]
        summary.update({
            "status": "COMPLETE",
            "primary_evaluations": len(rows),
            "rerun_evaluations": len(reruns),
            "artifact_completeness": sum(required <= set(row) for row in rows) / len(rows),
            "grammar_constrained_syntactic_validity": mean(row["syntactic_valid"] for row in c2),
            "prompt_only_JSON_syntactic_validity": mean(row["syntactic_valid"] for row in rows if row["contract"] == "M-C3"),
            "independent_scorer_ranking_agreement": mean(row["candidate_scores"]["ranking_agreement"] for row in c1),
            "maximum_independent_token_logprob_difference": max(row["candidate_scores"]["maximum_token_logprob_difference"] for row in c1),
            "deterministic_rerun_agreement": mean(row["agreement"] for row in reruns),
            "task_correctness": {contract: mean(row["task_correct"] for row in rows if row["contract"] == contract) for contract in CONTRACTS},
            "semantic_validity": {contract: mean(row["semantic_answer"] is not None for row in rows if row["contract"] == contract) for contract in CONTRACTS},
        })
        dump_yaml(root / "summary.yaml", summary)
        del worker
        return summary
    except Exception as exc:  # noqa: BLE001 - every checkpoint failure must leave an audit artifact
        summary.update({"error_type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()})
        dump_yaml(root / "summary.yaml", summary)
        return summary
    finally:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def _kappa(a: list[str | None], b: list[str | None]) -> float:
    labels = sorted({value for value in a + b if value is not None}) + [None]
    observed = mean(x == y for x, y in zip(a, b, strict=True))
    expected = sum((a.count(label) / len(a)) * (b.count(label) / len(b)) for label in labels)
    return 1.0 if expected == 1.0 and observed == 1.0 else (observed - expected) / (1 - expected)


def _model_comparison(rows: list[dict[str, Any]], model_id: str) -> dict[str, Any]:
    units = defaultdict(dict)
    for row in rows:
        if row["model_id"] == model_id:
            units[(row["scene_id"], row["serialization"])][row["contract"]] = row
    complete = [value for value in units.values() if set(value) == set(CONTRACTS)]
    a = [unit["M-C1"]["semantic_answer"] for unit in complete]
    b = [unit["M-C2"]["semantic_answer"] for unit in complete]
    kappa = _kappa(a, b)
    diffs = np.asarray([int(unit["M-C2"]["task_correct"]) - int(unit["M-C1"]["task_correct"]) for unit in complete], dtype=float)
    rng = np.random.default_rng(69317)
    boot_kappa = []
    boot_diff = []
    for _ in range(2000):
        idx = rng.integers(0, len(complete), len(complete))
        boot_kappa.append(_kappa([a[i] for i in idx], [b[i] for i in idx]))
        boot_diff.append(float(diffs[idx].mean()))
    changed = [unit for unit in complete if unit["M-C1"]["semantic_answer"] != unit["M-C2"]["semantic_answer"]]
    changed_tasks = sorted({unit["M-C1"]["task"] for unit in changed})
    changed_serializations = sorted({unit["M-C1"]["serialization"] for unit in changed})
    return {
        "model_id": model_id,
        "units": len(complete),
        "cll_vs_true_constrained_semantic_agreement": mean(x == y for x, y in zip(a, b, strict=True)),
        "cll_vs_true_constrained_kappa": kappa,
        "kappa_bootstrap_ci95": [float(np.quantile(boot_kappa, 0.025)), float(np.quantile(boot_kappa, 0.975))],
        "paired_correctness_difference_M_C2_minus_M_C1": float(diffs.mean()),
        "paired_correctness_difference_ci95": [float(np.quantile(boot_diff, 0.025)), float(np.quantile(boot_diff, 0.975))],
        "semantic_change_rate": len(changed) / len(complete),
        "changed_tasks": changed_tasks,
        "changed_serializations": changed_serializations,
        "parser_rejection_defines_change": False,
        "by_contract_correctness": {contract: mean(unit[contract]["task_correct"] for unit in complete) for contract in CONTRACTS},
        "by_contract_semantic_validity": {contract: mean(unit[contract]["semantic_answer"] is not None for unit in complete) for contract in CONTRACTS},
    }


def aggregate(split: str, config: dict[str, Any], model_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    base = ROOT / "artifacts/post_stop/direction_m" / split
    for model in config["models"]:
        path = base / model["model_id"] / "predictions.jsonl"
        if path.exists():
            rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    comparisons = [_model_comparison(rows, model["model_id"]) for model in config["models"] if any(row["model_id"] == model["model_id"] for row in rows)]
    canonical = canonicalizer_validation()
    eng = config["engineering_gates"]
    engineering = {
        "three_models_complete": len(model_summaries) == 3 and all(item["status"] == "COMPLETE" for item in model_summaries),
        "grammar_syntax": all(item.get("grammar_constrained_syntactic_validity") == eng["grammar_constrained_syntactic_validity"] for item in model_summaries),
        "artifact_completeness": all(item.get("artifact_completeness") == eng["artifact_completeness"] for item in model_summaries),
        "independent_scorer": all(item.get("independent_scorer_ranking_agreement") == eng["independent_scorer_ranking_agreement"] for item in model_summaries),
        "determinism": all(item.get("deterministic_rerun_agreement", 0) >= eng["deterministic_rerun_agreement_min"] for item in model_summaries),
        "canonicalizer_valid_recall": canonical["valid_form_recall"] >= eng["canonicalizer_valid_form_recall_min"],
        "canonicalizer_invalid_rejection": canonical["invalid_ambiguous_rejection"] >= eng["canonicalizer_invalid_ambiguous_rejection_min"],
    }
    eq = config["scientific_paths"]["equivalence"]
    equivalence_models = [item["model_id"] for item in comparisons if item["cll_vs_true_constrained_kappa"] >= eq["kappa_min"] and item["kappa_bootstrap_ci95"][0] >= eq["kappa_lower_min"] and abs(item["paired_correctness_difference_M_C2_minus_M_C1"]) <= eq["task_correctness_difference_margin"]]
    effect = config["scientific_paths"]["material_contract_effect"]
    material = [item for item in comparisons if abs(item["paired_correctness_difference_M_C2_minus_M_C1"]) >= effect["absolute_paired_task_correctness_difference_min"] and (item["paired_correctness_difference_ci95"][0] > 0 or item["paired_correctness_difference_ci95"][1] < 0) and len(item["changed_tasks"]) >= effect["changed_answers_multiple_tasks_min"] and set(item["changed_serializations"]) == set(config["scenes"]["serializations"])]
    signs = [1 if item["paired_correctness_difference_M_C2_minus_M_C1"] > 0 else -1 for item in material]
    same_direction = max(signs.count(1), signs.count(-1)) if signs else 0
    if not all(engineering.values()):
        decision = "DIRECTION_M_NO_GO" if split == "holdout" else "DEVELOPMENT_ENGINEERING_GATE_FAILED"
    elif split != "holdout":
        decision = "DEVELOPMENT_COMPLETE_NOT_A_HOLDOUT_DECISION"
    elif same_direction >= effect["families_same_direction_required"]:
        decision = "DIRECTION_M_SCIENTIFIC_GO"
    elif len(equivalence_models) >= eq["families_required"]:
        decision = "DIRECTION_M_ENGINEERING_ONLY"
    else:
        decision = "DIRECTION_M_NO_GO"
    return {
        "schema_version": 1, "direction": "M", "split": split, "config_hash": canonical_hash(config),
        "model_summaries": model_summaries, "canonicalizer_validation": canonical,
        "comparisons": comparisons, "engineering_gates": engineering,
        "equivalence_models": equivalence_models,
        "material_effect_models": [item["model_id"] for item in material],
        "material_effect_same_direction_count": same_direction,
        "decision": decision, "claim_boundary": config["claim_boundary"],
    }


def run_direction_m(split: str) -> dict[str, Any]:
    if split not in {"development", "holdout"}:
        raise ValueError(split)
    config = load_yaml("research/post_stop/direction_m/preregistration.yaml")
    root = Path("artifacts/post_stop/direction_m") / split
    marker = ROOT / root / "execution_marker.yaml"
    if split == "holdout":
        if not (ROOT / "research/post_stop/direction_m/method_freeze.yaml").exists() or not (ROOT / "research/post_stop/direction_m/holdout_authorization.yaml").exists():
            raise RuntimeError("Direction M holdout is not frozen and authorized")
        if marker.exists():
            raise RuntimeError("Direction M sealed holdout execution limit exhausted")
    dump_yaml(root / "execution_marker.yaml", {"schema_version": 1, "direction": "M", "split": split, "status": "RUNNING", "started_at": utc_now(), "execution_count": 1, "config_hash": canonical_hash(config), "historical_loop_c_outcomes_used_for_tuning": False})
    scenes = build_scenes(split, config)
    summaries = [run_model(split, config, model, scenes) for model in config["models"]]
    summary = aggregate(split, config, summaries)
    dump_yaml(root / "summary.yaml", summary)
    dump_yaml(root / "execution_marker.yaml", {"schema_version": 1, "direction": "M", "split": split, "status": "COMPLETE", "completed_at": utc_now(), "execution_count": 1, "config_hash": canonical_hash(config), "decision": summary["decision"], "historical_loop_c_outcomes_used_for_tuning": False})
    return summary
