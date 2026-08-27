from __future__ import annotations

from vlm_construct_audit.measurement.strict_parser import parse_declared_contract


def test_duplicate_keys_and_cross_schema_fail_closed() -> None:
    kwargs = {
        "allowed_answers": ["red", "blue"],
        "option_id_mapping": {"A": "red", "B": "blue"},
    }
    duplicate = parse_declared_contract(
        '{"answer":"red","answer":"blue"}', schema="semantic_answer", **kwargs
    )
    cross_schema = parse_declared_contract('{"answer":"red"}', schema="option_id", **kwargs)
    assert duplicate["parser_status"] == "failed_duplicate_key"
    assert cross_schema["parser_status"] == "failed_schema"


def test_registered_alias_is_explicit_not_silent_repair() -> None:
    common = {
        "schema": "semantic_answer",
        "allowed_answers": ["red", "blue"],
        "option_id_mapping": {"A": "red", "B": "blue"},
    }
    rejected = parse_declared_contract('{"answer":"azure"}', **common)
    accepted = parse_declared_contract(
        '{"answer":"azure"}', registered_aliases={"azure": "blue"}, **common
    )
    assert rejected["parser_status"] == "failed_disallowed_answer"
    assert accepted == {"parsed_response": "blue", "parser_status": "ok"}

