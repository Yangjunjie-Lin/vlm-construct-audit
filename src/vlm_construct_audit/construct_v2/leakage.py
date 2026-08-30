"""Deterministic and cross-validated shortcut audits for v2."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Callable, Hashable
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from scipy.stats import beta
from sklearn.base import BaseEstimator
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.tree import DecisionTreeClassifier

from .generator import ROOT


def _condition_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand each paired scene so identifiers repeat across two answer targets."""

    expanded = []
    for row in rows:
        for condition, answer in (
            ("correct", row["answer"]["semantic"]),
            ("corrupted", row["answer"]["corrupted_semantic"]),
        ):
            expanded.append({"base": row, "condition": condition, "target": answer})
    return expanded


def _exact_upper(successes: int, n: int, alpha: float = 0.05) -> float:
    return 1.0 if successes == n else float(beta.ppf(1 - alpha, successes + 1, n - successes))


def _contingency(
    expanded: list[dict[str, Any]], extractor: Callable[[dict[str, Any]], Hashable]
) -> dict[str, Any]:
    table: dict[Hashable, Counter[str]] = defaultdict(Counter)
    for item in expanded:
        table[extractor(item)][item["target"]] += 1
    correct = sum(max(counts.values()) for counts in table.values())
    deterministic = all(len(counts) == 1 for counts in table.values())
    return {
        "levels": len(table),
        "bayes_accuracy": correct / len(expanded),
        "deterministic_mapping": deterministic,
        "pass": not deterministic,
    }


def deterministic_contingency_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    expanded = _condition_rows(rows)

    def base(item: dict[str, Any]) -> dict[str, Any]:
        return item["base"]

    fields: dict[str, Callable[[dict[str, Any]], Hashable]] = {
        "scene_index_mod_16": lambda item: base(item)["scene_index"] % 16,
        "scene_id_hash_bucket": lambda item: hashlib.sha256(
            base(item)["internal_scene_id"].encode()
        ).hexdigest()[0],
        "scene_id": lambda item: base(item)["internal_scene_id"],
        "entity_aliases": lambda item: tuple(
            entity["model_visible_identifier"] for entity in base(item)["entities"]
        ),
        "template_id": lambda item: base(item)["template_id"],
        "option_position": lambda item: base(item)["answer"]["correct_option_position"],
        "option_order": lambda item: tuple(base(item)["answer"]["semantic_candidates"]),
        "entity_count": lambda item: base(item)["entity_count"],
        "color_shape_pattern": lambda item: tuple(
            (entity["color"], entity["shape"]) for entity in base(item)["entities"]
        ),
        "corruption_seed_mod_16": lambda item: base(item)["seeds"]["corruption_seed"] % 16,
        "rendering_seed_mod_16": lambda item: base(item)["seeds"]["rendering_seed"] % 16,
        "template_x_entity_count": lambda item: (
            base(item)["template_id"], base(item)["entity_count"]
        ),
        "template_x_option_position": lambda item: (
            base(item)["template_id"], base(item)["answer"]["correct_option_position"]
        ),
    }
    results = {name: _contingency(expanded, extractor) for name, extractor in fields.items()}
    return {
        "target": "condition-specific semantic answer over paired correct/corrupted rows",
        "rows": len(expanded),
        "fields": results,
        "unique_row_key_note": (
            "scene_id plus condition is an observational row key and is necessarily unique; "
            "neither component is model-visible, and scene_id alone is explicitly audited"
        ),
        "status": "PASS" if all(result["pass"] for result in results.values()) else "FAIL",
    }


def _dict_views(item: dict[str, Any], view: str) -> dict[str, float | str]:
    row = item["base"]
    if view == "question_only":
        return {"question": row["question"]["text"]}
    if view == "entity_labels_only":
        return {
            f"entity_{index}": entity["model_visible_identifier"]
            for index, entity in enumerate(row["entities"])
        }
    if view == "scene_metadata_only":
        return {
            "scene_index": float(row["scene_index"]),
            "scene_id": row["internal_scene_id"],
            "entity_count": float(row["entity_count"]),
            "template": row["template_id"],
            "condition": item["condition"],
            "corruption_seed": float(row["seeds"]["corruption_seed"]),
            "rendering_seed": float(row["seeds"]["rendering_seed"]),
        }
    if view == "option_order_only":
        return {"order": "|".join(row["answer"]["semantic_candidates"])}
    if view == "option_position_only":
        return {"position": float(row["answer"]["correct_option_position"])}
    if view == "template_only":
        return {"template": row["template_id"]}
    raise ValueError(view)


def _models() -> dict[str, BaseEstimator]:
    return {
        "majority_baseline": make_pipeline(DictVectorizer(), DummyClassifier(strategy="most_frequent")),
        "decision_tree": make_pipeline(
            DictVectorizer(), DecisionTreeClassifier(max_depth=6, min_samples_leaf=20, random_state=863001)
        ),
        "logistic_regression": make_pipeline(
            DictVectorizer(), LogisticRegression(C=0.1, max_iter=1000, random_state=863002)
        ),
        "random_forest": make_pipeline(
            DictVectorizer(),
            RandomForestClassifier(
                n_estimators=100,
                max_depth=6,
                min_samples_leaf=10,
                max_features="sqrt",
                random_state=863003,
                n_jobs=1,
            ),
        ),
    }


def _cross_validated_predictions(
    estimator: BaseEstimator,
    x: list[Any],
    y: np.ndarray,
    groups: np.ndarray,
    folds: int,
) -> np.ndarray:
    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=863101)
    predictions = np.empty(len(y), dtype=object)
    for train, test in splitter.split(np.zeros(len(y)), y, groups):
        estimator.fit([x[index] for index in train], y[train])
        predictions[test] = estimator.predict([x[index] for index in test])
    return predictions


def _metric(y: np.ndarray, predictions: np.ndarray) -> dict[str, Any]:
    correct = int(np.sum(y == predictions))
    accuracy = float(accuracy_score(y, predictions))
    upper = _exact_upper(correct, len(y))
    return {
        "correct": correct,
        "n": len(y),
        "cross_validated_accuracy": accuracy,
        "one_sided_95_exact_upper": upper,
        "accuracy_gate_le_0_30": accuracy <= 0.30,
        "upper_gate_le_0_35": upper <= 0.35,
        "pass": accuracy <= 0.30 and upper <= 0.35,
    }


def cross_validated_shortcut_audit(
    rows: list[dict[str, Any]], *, folds: int = 5
) -> dict[str, Any]:
    expanded = _condition_rows(rows)
    y = np.asarray([item["target"] for item in expanded])
    groups = np.asarray([item["base"]["scene_uuid"] for item in expanded])
    views = (
        "question_only", "entity_labels_only", "scene_metadata_only",
        "option_order_only", "option_position_only", "template_only",
    )
    results: dict[str, dict[str, Any]] = {}
    for view in views:
        x = [_dict_views(item, view) for item in expanded]
        results[view] = {}
        for name, estimator in _models().items():
            predictions = _cross_validated_predictions(estimator, x, y, groups, folds)
            results[view][name] = _metric(y, predictions)

    text_views = {
        "question_text_char_ngrams": [item["base"]["question"]["text"] for item in expanded],
        "scene_id_char_ngrams": [item["base"]["internal_scene_id"] for item in expanded],
    }
    for view, x in text_views.items():
        estimator = make_pipeline(
            TfidfVectorizer(analyzer="char", ngram_range=(2, 5), min_df=2),
            LogisticRegression(C=0.1, max_iter=1000, random_state=863102),
        )
        predictions = _cross_validated_predictions(estimator, x, y, groups, folds)
        results[view] = {"character_ngram_logistic": _metric(y, predictions)}

    flat = [metric for models in results.values() for metric in models.values()]
    return {
        "folds": folds,
        "splitter": "stratified group CV; both conditions from a scene remain in one fold",
        "classification_target": "four-class condition-specific semantic answer",
        "views": results,
        "maximum_accuracy": max(metric["cross_validated_accuracy"] for metric in flat),
        "maximum_one_sided_95_exact_upper": max(
            metric["one_sided_95_exact_upper"] for metric in flat
        ),
        "status": "PASS" if all(metric["pass"] for metric in flat) else "FAIL",
    }


def audit_leakage(rows: list[dict[str, Any]], *, folds: int = 5) -> dict[str, Any]:
    deterministic = deterministic_contingency_audit(rows)
    shortcut = cross_validated_shortcut_audit(rows, folds=folds)
    passed = deterministic["status"] == shortcut["status"] == "PASS"
    return {
        "schema_version": 1,
        "protocol_id": rows[0]["protocol_id"] if rows else None,
        "base_scene_count": len(rows),
        "deterministic_contingency": deterministic,
        "cross_validated_shortcuts": shortcut,
        "status": "PASS" if passed else "CONSTRUCT_V2_LEAKAGE_NO_GO",
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def audit_construct_v2_leakage() -> dict[str, Any]:
    rows = _read_jsonl(ROOT / "data/construct_v2/reasoning_test.jsonl")
    result = audit_leakage(rows)
    target = ROOT / "artifacts/construct_v2/leakage_metrics.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(result, sort_keys=False), encoding="utf-8")
    return result
