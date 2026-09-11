from pathlib import Path


def test_platform_installers_sync_project_environment():
    root = Path(__file__).resolve().parents[1]
    assert (root / ".python-version").read_text(encoding="utf-8").strip() == "3.13"
    for name in ("arch.sh", "ubuntu.sh", "fedora.sh"):
        text = (root / "install" / name).read_text(encoding="utf-8")
        assert "uv python install 3.13" in text
        assert (
            "uv sync --python 3.13 --extra dev --extra alignment --extra diarization" in text
        )
        assert "models download small" in text
        assert "models download-alignment it" in text
        assert "models download-diarization" in text


def test_uninstall_script_is_documented_and_conservative():
    root = Path(__file__).resolve().parents[1]
    script = root / "install" / "uninstall.sh"
    text = script.read_text(encoding="utf-8")

    assert script.exists()
    assert "--yes" in text
    assert "does not uninstall shared system packages" in text
    assert "rm -rf --" in text
