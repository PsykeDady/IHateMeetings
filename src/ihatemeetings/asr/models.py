from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ihatemeetings.errors import IHMError


@dataclass(frozen=True)
class ModelSpec:
    name: str
    repository: str
    approximate_size: str


MODELS = {
    "tiny": ModelSpec("tiny", "Systran/faster-whisper-tiny", "about 80 MB"),
    "small": ModelSpec("small", "Systran/faster-whisper-small", "about 490 MB"),
    "medium": ModelSpec("medium", "Systran/faster-whisper-medium", "about 1.6 GB"),
    "large-v3-turbo": ModelSpec(
        "large-v3-turbo", "dropbox-dash/faster-whisper-large-v3-turbo", "about 1.6 GB"
    ),
    "large-v3": ModelSpec("large-v3", "Systran/faster-whisper-large-v3", "about 3.1 GB"),
}

PROFILE_MODELS = {"fast": "small", "balanced": "large-v3-turbo", "accurate": "large-v3"}


def model_cache_dir() -> Path:
    cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache_root / "ihatemeetings" / "models"


def resolve_local_model(model: str) -> Path:
    spec = MODELS.get(model)
    if spec is None:
        local_path = Path(model).expanduser()
        if local_path.is_dir():
            return local_path.resolve()
        raise IHMError(
            f"Unknown model '{model}'.",
            "Use a local model directory or one of: " + ", ".join(MODELS),
        )
    try:
        from huggingface_hub import snapshot_download
        from huggingface_hub.errors import LocalEntryNotFoundError
    except ImportError as exc:
        raise IHMError(
            "huggingface-hub is unavailable.", "Run 'uv sync --extra dev' and retry."
        ) from exc
    try:
        path = snapshot_download(
            repo_id=spec.repository,
            cache_dir=model_cache_dir(),
            local_files_only=True,
        )
    except LocalEntryNotFoundError as exc:
        raise IHMError(
            f"Model '{model}' is not available locally ({spec.approximate_size}).",
            f"Download it explicitly with: uv run ihm models download {model}",
        ) from exc
    return Path(path)


def download_model(model: str) -> Path:
    spec = MODELS.get(model)
    if spec is None:
        raise IHMError(f"Unknown model '{model}'. Choose one of: {', '.join(MODELS)}")
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise IHMError("huggingface-hub is unavailable. Run 'uv sync --extra dev'.") from exc
    try:
        path = snapshot_download(repo_id=spec.repository, cache_dir=model_cache_dir())
    except Exception as exc:
        raise IHMError(
            f"Model download failed: {exc}",
            "Check Internet access and free disk space, then retry the explicit download command.",
        ) from exc
    return Path(path)


def is_model_cached(model: str) -> bool:
    try:
        resolve_local_model(model)
    except IHMError:
        return False
    return True
