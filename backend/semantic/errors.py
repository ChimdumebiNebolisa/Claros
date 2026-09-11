"""Stable internal failures for closed-world semantic processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, NoReturn

SemanticFailureCode = Literal[
    "semantic_unknown_id",
    "semantic_duplicate_id",
    "semantic_reordered",
    "semantic_overlapping",
    "semantic_incomplete",
    "semantic_unsupported",
    "semantic_ambiguous",
    "semantic_refused",
    "semantic_timeout",
    "semantic_malformed",
    "semantic_forbidden_geometry",
    "semantic_provider_unavailable",
    "semantic_input_invalid",
    "semantic_unsafe_rephrase",
    "semantic_model_gate_failed",
]


@dataclass(frozen=True, slots=True)
class SemanticFailure(Exception):
    """A provider-safe failure whose detail is intentionally not student-facing."""

    code: SemanticFailureCode
    recoverable: bool = True

    def __str__(self) -> str:
        return self.code


def semantic_failure(code: SemanticFailureCode, *, recoverable: bool = True) -> NoReturn:
    raise SemanticFailure(code=code, recoverable=recoverable)
