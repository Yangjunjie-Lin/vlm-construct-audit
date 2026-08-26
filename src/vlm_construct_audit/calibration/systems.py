"""Six deliberately distinct systems with trusted pre-output traces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def rotate(answer: str, options: list[str]) -> str:
    return options[(options.index(answer) + 1) % len(options)]


def solve_supplied_facts(scene: dict[str, Any], facts: list[dict[str, str]]) -> tuple[str | None, list[str]]:
    question = scene["question"]
    trace: list[str] = []
    if question["question_type"] == "direct_uptake":
        target = question["target_entity"]
    else:
        current = question["anchor_entity"]
        predicate = question["predicate"]
        for _ in range(int(question["reasoning_depth"])):
            candidates = [
                fact["subject"]
                for fact in facts
                if fact["kind"] == "relation"
                and fact["predicate"] == predicate
                and fact["object"] == current
            ]
            if len(candidates) != 1:
                return None, trace + [f"relation_lookup_failed:{predicate}:{current}"]
            current = candidates[0]
            trace.append(f"relation:{current}:{predicate}")
        target = current
    colors = [
        fact["object"]
        for fact in facts
        if fact["kind"] == "attribute"
        and fact["predicate"] == "color"
        and fact["subject"] == target
    ]
    if len(colors) != 1:
        return None, trace + [f"color_lookup_failed:{target}"]
    return colors[0], trace + [f"color:{target}:{colors[0]}"]


@dataclass(frozen=True)
class SystemOutput:
    pre_mapping_answer: str | None
    selected_answer: str
    canonical_trace: list[str]
    measurement_probe_pass: bool
    diagnostic_subtype: str
    constrained_schema_valid: bool = True


class CalibrationSystem:
    name = "CalibrationSystem"
    revision = "known-state-v1"

    def infer(
        self,
        scene: dict[str, Any],
        facts: list[dict[str, str]],
        condition: str,
        serialization: str,
        contract: str,
    ) -> SystemOutput:
        raise NotImplementedError

    @staticmethod
    def _fallback(scene: dict[str, Any]) -> str:
        return rotate(scene["answer"], scene["question"]["options"])


class OracleEvidenceReasoner(CalibrationSystem):
    name = "OracleEvidenceReasoner"

    def infer(self, scene, facts, condition, serialization, contract):
        answer, trace = solve_supplied_facts(scene, facts)
        return SystemOutput(answer, answer or self._fallback(scene), trace, True, "valid_reasoning")


class EvidenceBlindSystem(CalibrationSystem):
    name = "EvidenceBlindSystem"

    def infer(self, scene, facts, condition, serialization, contract):
        return SystemOutput(None, self._fallback(scene), ["evidence_not_read"], True, "evidence_blind")


class ParserCorruptedSystem(CalibrationSystem):
    name = "ParserCorruptedSystem"

    def infer(self, scene, facts, condition, serialization, contract):
        answer, trace = solve_supplied_facts(scene, facts)
        source = answer or self._fallback(scene)
        return SystemOutput(
            answer,
            rotate(source, scene["question"]["options"]),
            trace + ["option_mapping_corrupted"],
            False,
            "parser_option_mapping",
            constrained_schema_valid=contract != "constrained_generation",
        )


class FormatShortcutSystem(CalibrationSystem):
    name = "FormatShortcutSystem"

    def infer(self, scene, facts, condition, serialization, contract):
        shortcut_success = serialization == "natural_language" and condition == "correct_evidence"
        answer = scene["answer"] if shortcut_success else self._fallback(scene)
        return SystemOutput(
            None,
            answer,
            [f"format_marker:{serialization}:{condition}"],
            True,
            "format_position_shortcut",
        )


class UptakeOnlySystem(CalibrationSystem):
    name = "UptakeOnlySystem"

    def infer(self, scene, facts, condition, serialization, contract):
        if scene["split"] == "uptake_validation":
            answer, trace = solve_supplied_facts(scene, facts)
            return SystemOutput(answer, answer or self._fallback(scene), trace, True, "direct_uptake_only")
        return SystemOutput(
            None,
            self._fallback(scene),
            ["composition_not_executed"],
            True,
            "direct_uptake_only",
        )


class ReasonerWithOutputCorruption(CalibrationSystem):
    name = "ReasonerWithOutputCorruption"

    def infer(self, scene, facts, condition, serialization, contract):
        answer, trace = solve_supplied_facts(scene, facts)
        source = answer or self._fallback(scene)
        return SystemOutput(
            answer,
            rotate(source, scene["question"]["options"]),
            trace + ["final_output_mapping_corrupted"],
            False,
            "final_output_mapping",
        )


SYSTEMS = {
    cls.name: cls
    for cls in (
        OracleEvidenceReasoner,
        EvidenceBlindSystem,
        ParserCorruptedSystem,
        FormatShortcutSystem,
        UptakeOnlySystem,
        ReasonerWithOutputCorruption,
    )
}


def get_system(name: str) -> CalibrationSystem:
    try:
        return SYSTEMS[name]()
    except KeyError as exc:
        raise KeyError(f"Unknown calibration system: {name}") from exc

