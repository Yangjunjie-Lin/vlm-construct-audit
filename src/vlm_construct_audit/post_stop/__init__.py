"""Post-STOP isolated screening directions."""

from typing import Any

from .common import freeze_post_stop
from .human_review import import_human_review
from .reporting import adjudicate_post_stop, seal_direction, verify_post_stop_artifacts


def run_direction_m(split: str) -> dict[str, Any]:
    """Load the optional real-checkpoint stack only for an explicit Direction M run."""
    from .direction_m import run_direction_m as implementation

    return implementation(split)


def run_direction_p(split: str) -> dict[str, Any]:
    from .direction_p import run_direction_p as implementation

    return implementation(split)


def run_direction_u(split: str) -> dict[str, Any]:
    from .direction_u import run_direction_u as implementation

    return implementation(split)


__all__ = [
    "adjudicate_post_stop",
    "freeze_post_stop",
    "import_human_review",
    "run_direction_m",
    "run_direction_p",
    "run_direction_u",
    "seal_direction",
    "verify_post_stop_artifacts",
]
