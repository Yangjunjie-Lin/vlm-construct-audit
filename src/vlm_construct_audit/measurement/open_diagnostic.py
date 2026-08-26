"""Secondary open-generation diagnostic excluded from every primary gate."""

from __future__ import annotations


def open_generation_diagnostic(semantic_answer: str) -> dict[str, object]:
    return {
        "raw_response": f"The answer is {semantic_answer}.",
        "primary_result": False,
        "used_by_go_no_go": False,
        "parser": None,
        "role": "secondary_diagnostic_only",
    }

