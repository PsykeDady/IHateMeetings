from __future__ import annotations

import unicodedata
from collections.abc import Sequence


def normalize_reference_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(
        "".join(character if character.isalnum() else " " for character in normalized).split()
    )


def word_error_rate(reference: str, hypothesis: str) -> float:
    expected = normalize_reference_text(reference).split()
    actual = normalize_reference_text(hypothesis).split()
    return _error_rate(expected, actual)


def character_error_rate(reference: str, hypothesis: str) -> float:
    expected = list(normalize_reference_text(reference))
    actual = list(normalize_reference_text(hypothesis))
    return _error_rate(expected, actual)


def _error_rate(reference: Sequence[str], hypothesis: Sequence[str]) -> float:
    if not reference:
        raise ValueError("reference text must not be empty")
    previous = list(range(len(hypothesis) + 1))
    for row, expected in enumerate(reference, 1):
        current = [row]
        for column, actual in enumerate(hypothesis, 1):
            current.append(
                min(
                    current[column - 1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (expected != actual),
                )
            )
        previous = current
    return previous[-1] / len(reference)
