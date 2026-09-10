from __future__ import annotations

from dataclasses import dataclass

from ihatemeetings.errors import IHMError


@dataclass(frozen=True)
class ComputeSelection:
    device: str
    compute_type: str
    cuda_devices: int


def cuda_device_count() -> int:
    try:
        import ctranslate2

        return int(ctranslate2.get_cuda_device_count())
    except (ImportError, OSError, RuntimeError):
        return 0


def select_compute(device: str = "auto", compute_type: str | None = None) -> ComputeSelection:
    cuda_devices = cuda_device_count()
    selected = (
        "cuda" if device == "auto" and cuda_devices > 0 else "cpu" if device == "auto" else device
    )
    if selected == "cuda" and cuda_devices == 0:
        raise IHMError(
            "CUDA was requested but CTranslate2 cannot access a CUDA device.",
            "Use '--device cpu --compute-type int8' or fix the CUDA runtime.",
        )
    selected_type = compute_type or ("float16" if selected == "cuda" else "int8")
    return ComputeSelection(selected, selected_type, cuda_devices)
