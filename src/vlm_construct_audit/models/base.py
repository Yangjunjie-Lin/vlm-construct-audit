"""Model adapter interface frozen before scientific model selection."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class VLMAdapter(ABC):
    @abstractmethod
    def prepare_input(self, scene: dict[str, Any], evidence: dict[str, Any], **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def score_candidates(self, prepared_input: Any, candidates: list[str], **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def generate_constrained(self, prepared_input: Any, allowed_answers: list[str], **kwargs: Any) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_revision_metadata(self) -> dict[str, Any]:
        raise NotImplementedError

