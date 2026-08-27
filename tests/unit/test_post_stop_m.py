from __future__ import annotations

from vlm_construct_audit.post_stop.direction_m import (
    canonicalize_response,
    canonicalizer_validation,
)


def test_canonicalizer_registered_valid_forms() -> None:
    metrics = canonicalizer_validation()
    assert metrics["valid_form_recall"] >= 0.99


def test_canonicalizer_rejects_ambiguity_and_disallowed_answers() -> None:
    allowed = ["red", "green"]
    assert canonicalize_response('{"answer":"red"} {"answer":"green"}', allowed)["parsed_response"] is None
    assert canonicalize_response('{"answer":"blue"}', allowed)["parsed_response"] is None
    assert canonicalize_response("red or green", allowed)["parsed_response"] is None


def test_canonicalizer_does_not_silently_repair_schema() -> None:
    allowed = ["red", "green"]
    assert canonicalize_response('{"Answer":"red"}', allowed)["parsed_response"] is None
    assert canonicalize_response('{"answer":"red","extra":true}', allowed)["parsed_response"] is None
