import pytest

from ihatemeetings.config.defaults import RuntimeConfig
from ihatemeetings.errors import IHMError
from ihatemeetings.pipeline.transcribe import build_plan
from ihatemeetings.platform import compute


def test_cpu_auto_selection_uses_int8(monkeypatch):
    monkeypatch.setattr(compute, "cuda_device_count", lambda: 0)
    selected = compute.select_compute()
    assert selected.device == "cpu"
    assert selected.compute_type == "int8"


def test_unavailable_explicit_cuda_is_rejected(monkeypatch):
    monkeypatch.setattr(compute, "cuda_device_count", lambda: 0)
    with pytest.raises(IHMError, match="CUDA was requested"):
        compute.select_compute("cuda")


def test_cpu_profile_and_model_override(monkeypatch):
    monkeypatch.setattr(compute, "cuda_device_count", lambda: 0)
    plan, _ = build_plan(RuntimeConfig(profile="balanced", model="tiny", device="cpu"))
    assert plan.profile == "balanced"
    assert plan.model == "tiny"
    assert plan.compute_type == "int8"
