from __future__ import annotations

from ihatemeetings.errors import IHMError

SUPPORTED_LANGUAGES = ("it", "en")
LANGUAGE_NAMES = {
    "it": "Italian",
    "en": "English",
}


def normalize_language_code(language: str | None) -> str | None:
    if language is None:
        return None
    return language.strip().casefold().replace("_", "-").split("-", 1)[0] or None


def require_supported_language(language: str) -> str:
    normalized = normalize_language_code(language)
    if normalized not in SUPPORTED_LANGUAGES:
        supported = ", ".join(SUPPORTED_LANGUAGES)
        raise IHMError(
            f"Language '{language}' is not officially supported in v1.",
            f"Choose one of: {supported}, or omit --language for automatic detection.",
        )
    return normalized


def unsupported_detection_warning(language: str | None) -> str | None:
    normalized = normalize_language_code(language)
    if normalized in SUPPORTED_LANGUAGES:
        return None
    detected = normalized or "unknown"
    return (
        f"Detected language '{detected}' is not officially supported in v1 "
        "(supported: it, en). The raw ASR transcript will be exported without alignment."
    )
