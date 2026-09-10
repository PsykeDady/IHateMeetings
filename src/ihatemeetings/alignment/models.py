from __future__ import annotations

import importlib
import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path

from ihatemeetings.errors import IHMError


@dataclass(frozen=True)
class AlignmentModelSpec:
    language: str
    repository: str
    approximate_size: str
    license: str
    weight_file: str


ALIGNMENT_MODELS = {
    "en": AlignmentModelSpec(
        "en",
        "facebook/wav2vec2-base-960h",
        "about 380 MB",
        "Apache-2.0",
        "model.safetensors",
    ),
    "it": AlignmentModelSpec(
        "it",
        "jonatasgrosman/wav2vec2-large-xlsr-53-italian",
        "about 1.3 GB",
        "Apache-2.0",
        "pytorch_model.bin",
    ),
}

MODEL_METADATA_FILES = (
    "config.json",
    "preprocessor_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
)


def alignment_cache_dir() -> Path:
    cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache_root / "ihatemeetings" / "alignment"


def _model_files(spec: AlignmentModelSpec) -> tuple[str, ...]:
    return (*MODEL_METADATA_FILES, spec.weight_file)


def resolve_alignment_model(language: str, override: str | None = None) -> tuple[Path, str]:
    if override:
        local_path = Path(override).expanduser()
        if local_path.is_dir():
            return local_path.resolve(), local_path.name
        raise IHMError("Alignment model overrides must be local model directories.")
    spec = ALIGNMENT_MODELS.get(language)
    if spec is None:
        raise IHMError(
            f"No default alignment model is configured for language '{language}'.",
            "Disable alignment or provide a tested local model with --alignment-model.",
        )
    try:
        from huggingface_hub import snapshot_download
        from huggingface_hub.errors import LocalEntryNotFoundError

        path = snapshot_download(
            repo_id=spec.repository,
            cache_dir=alignment_cache_dir(),
            local_files_only=True,
            allow_patterns=_model_files(spec),
        )
    except ImportError as exc:
        raise IHMError(
            "huggingface-hub is unavailable. Run 'uv sync --python 3.13'."
        ) from exc
    except LocalEntryNotFoundError as exc:
        raise IHMError(
            f"Alignment model for '{language}' is not cached ({spec.approximate_size}).",
            f"Download it explicitly with: uv run ihm models download-alignment {language}",
        ) from exc
    return Path(path), spec.repository


def download_alignment_model(language: str) -> Path:
    spec = ALIGNMENT_MODELS[language]
    try:
        from huggingface_hub import snapshot_download

        path = snapshot_download(
            repo_id=spec.repository,
            cache_dir=alignment_cache_dir(),
            allow_patterns=_model_files(spec),
        )
    except Exception as exc:
        raise IHMError(
            f"Alignment model download failed: {exc}",
            "Check Internet access and free disk space, then retry.",
        ) from exc
    return Path(path)


def is_alignment_model_cached(language: str) -> bool:
    try:
        resolve_alignment_model(language)
    except IHMError:
        return False
    return True


def alignment_runtime_available(*, verify_imports: bool = False) -> bool:
    if any(importlib.util.find_spec(module) is None for module in ("torch", "transformers")):
        return False
    if not verify_imports:
        return True
    try:
        importlib.import_module("torch")
        importlib.import_module("transformers")
    except (ImportError, OSError, RuntimeError):
        return False
    return True
