from __future__ import annotations

import importlib
import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path

from ihatemeetings.errors import IHMError


@dataclass(frozen=True)
class DiarizationModelSpec:
    name: str
    repository: str
    revision: str
    approximate_size: str
    license: str
    gated: bool


COMMUNITY_1 = DiarizationModelSpec(
    "community-1",
    "pyannote/speaker-diarization-community-1",
    "3533c8cf8e369892e6b79ff1bf80f7b0286a54ee",
    "about 34 MB (runtime dependencies are separate)",
    "CC-BY-4.0",
    True,
)


def diarization_cache_dir() -> Path:
    cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache_root / "ihatemeetings" / "diarization"


def diarization_runtime_available(*, verify_imports: bool = False) -> bool:
    modules = ("pyannote.audio", "torch", "torchaudio", "torchcodec")
    if any(importlib.util.find_spec(module) is None for module in modules):
        return False
    if not verify_imports:
        return True
    os.environ["PYANNOTE_METRICS_ENABLED"] = "0"
    try:
        for module in modules:
            importlib.import_module(module)
    except (ImportError, OSError, RuntimeError):
        return False
    return True


def resolve_diarization_model(override: str | None = None) -> tuple[Path, str]:
    if override:
        path = Path(override).expanduser()
        if path.is_dir():
            return path.resolve(), path.name
        raise IHMError("Diarization model overrides must be local model directories.")
    marker = diarization_cache_dir() / "community-1.ready"
    try:
        path = Path(marker.read_text(encoding="utf-8").strip())
    except OSError as exc:
        raise _model_missing() from exc
    if not path.is_dir() or not (path / "config.yaml").is_file():
        raise _model_missing()
    return path, f"{COMMUNITY_1.repository}@{COMMUNITY_1.revision}"


def is_diarization_model_cached() -> bool:
    try:
        resolve_diarization_model()
    except IHMError:
        return False
    return True


def download_diarization_model(token: str | None = None) -> Path:
    token = token or os.environ.get("HF_TOKEN")
    if not token:
        raise IHMError(
            "HF_TOKEN is required to acquire the gated Community-1 model.",
            "Accept the model conditions at Hugging Face, create a read token, then run: "
            "HF_TOKEN=... uv run ihm models download-diarization",
        )
    if not diarization_runtime_available():
        raise IHMError(
            "Diarization runtime dependencies are not installed.",
            "Run: uv sync --python 3.13 --extra diarization",
        )
    os.environ["PYANNOTE_METRICS_ENABLED"] = "0"
    try:
        from huggingface_hub import snapshot_download
        from pyannote.audio import Pipeline

        cache = diarization_cache_dir()
        path = Path(
            snapshot_download(
                repo_id=COMMUNITY_1.repository,
                revision=COMMUNITY_1.revision,
                cache_dir=cache,
                token=token,
            )
        )
        # Loading once is deliberate: Community-1 references additional gated model assets.
        pipeline = Pipeline.from_pretrained(path, token=token, cache_dir=cache)
        if pipeline is None:
            raise IHMError("pyannote could not load the acquired Community-1 pipeline.")
        cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        marker = cache / "community-1.ready"
        marker.write_text(str(path.resolve()) + "\n", encoding="utf-8")
        marker.chmod(0o600)
        return path
    except Exception as exc:
        raise IHMError(
            f"Community-1 acquisition failed: {exc}",
            "Confirm that both Community-1 model conditions are accepted, the token has read "
            "access, Internet access is available, and sufficient disk space remains.",
        ) from exc


def _model_missing() -> IHMError:
    return IHMError(
        f"Community-1 is not prepared locally ({COMMUNITY_1.approximate_size}).",
        "Acquire it explicitly with: HF_TOKEN=... uv run ihm models download-diarization",
    )
