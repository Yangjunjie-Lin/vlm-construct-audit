from __future__ import annotations

from collections import Counter, defaultdict

from vlm_construct_audit.construct_v2.generator import (
    ANSWERS,
    CARDINALS,
    build_reasoning_rows,
    build_uptake_rows,
)


def _reasoning() -> list[dict]:
    return build_reasoning_rows(768)


def test_no_model_visible_identifier_contains_scene_index() -> None:
    for row in _reasoning():
        visible = " ".join(
            [
                row["question"]["text"],
                row["evidence"]["correct"]["natural_language"],
                row["evidence"]["correct"]["triples"],
                *row["answer"]["semantic_candidates"],
            ]
        )
        assert str(row["scene_index"]) not in visible.split()
        assert row["scene_uuid"] not in visible
        assert "ANS_REL" not in visible
        assert row["model_visible"] == {
            "scene_id_included": False,
            "entity_uuid_included": False,
            "relation_coded_candidate_id_included": False,
        }


def test_answer_is_balanced_over_template_entity_count_and_option_position() -> None:
    rows = _reasoning()
    for field in ("template_id", "entity_count"):
        strata: dict[object, Counter] = defaultdict(Counter)
        for row in rows:
            strata[row[field]][row["answer"]["semantic"]] += 1
        assert all(set(counts) == set(ANSWERS) for counts in strata.values())
        assert all(max(counts.values()) == min(counts.values()) for counts in strata.values())

    table = Counter(
        (row["answer"]["semantic"], row["answer"]["correct_option_position"])
        for row in rows
    )
    assert len(set(table.values())) == 1


def test_question_and_entity_labels_repeat_over_all_answers() -> None:
    by_question: dict[str, set[str]] = defaultdict(set)
    by_labels: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for row in _reasoning():
        answer = row["answer"]["semantic"]
        by_question[row["question"]["text"]].add(answer)
        labels = tuple(entity["model_visible_identifier"] for entity in row["entities"])
        by_labels[labels].add(answer)
    assert all(answers == set(ANSWERS) for answers in by_question.values())
    assert all(answers == set(ANSWERS) for answers in by_labels.values())


def test_corruption_changes_exactly_one_unobserved_bridge_fact() -> None:
    for row in _reasoning():
        correct = row["evidence"]["correct"]["canonical_facts"]
        corrupted = row["evidence"]["corrupted"]["canonical_facts"]
        assert len(correct) == len(corrupted) == 1
        assert correct[0]["head_role"] == corrupted[0]["head_role"] == "B"
        assert correct[0]["tail_role"] == corrupted[0]["tail_role"] == "C"
        assert correct[0]["relation"] != corrupted[0]["relation"]
        assert row["evidence"]["changed_fact_count"] == 1
        assert row["evidence"]["direct_image_text_conflict"] is False
        assert all("C" not in fact.values() for fact in row["image"]["canonical_facts"])
        assert row["modality_allocation"]["c_spatially_rendered"] is False


def test_every_uptake_task_is_independently_relation_balanced() -> None:
    rows = build_uptake_rows()
    counts = Counter((row["uptake_task"], row["answer"]["semantic"]) for row in rows)
    for task in {row["uptake_task"] for row in rows}:
        assert {counts[(task, answer)] for answer in CARDINALS} == {16}
        positions = Counter(
            row["answer"]["correct_option_position"]
            for row in rows
            if row["uptake_task"] == task
        )
        assert positions == Counter({0: 16, 1: 16, 2: 16, 3: 16})

