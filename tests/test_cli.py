from pathlib import Path

import pytest

from ihatemeetings.cli.main import main


def test_help_runs(capsys):
    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "IHateMeetings" in output
    assert "doctor" in output


def test_models_list(capsys):
    assert main(["models", "list"]) == 0
    output = capsys.readouterr().out
    assert "No model weights" in output


def test_missing_input_fails(capsys):
    assert main(["transcribe", "missing.mp3"]) == 2
    output = capsys.readouterr().out
    assert "Input file not found" in output


def test_file_argument_is_transcribe_alias(capsys):
    assert main(["missing.mp3"]) == 2
    output = capsys.readouterr().out
    assert "Input file not found" in output


@pytest.mark.parametrize("language", ("it", "en"))
def test_explicit_and_short_forms_invoke_same_pipeline(monkeypatch, tmp_path, language):
    source = tmp_path / "meeting.mp3"
    source.touch()
    calls = []

    def fake_pipeline(input_path, config):
        calls.append((input_path, config.language, config.model, config.align))
        return Path("output/meeting")

    monkeypatch.setattr("ihatemeetings.cli.main.run_transcription", fake_pipeline)

    assert main([str(source), "--language", language, "--model", "tiny", "--align"]) == 0
    assert main(
        ["transcribe", str(source), "--language", language, "--model", "tiny", "--align"]
    ) == 0
    assert calls == [(source, language, "tiny", True), (source, language, "tiny", True)]


def test_explicit_unsupported_language_is_rejected(tmp_path, capsys):
    source = tmp_path / "meeting.mp3"
    source.touch()

    assert main([str(source), "--language", "fr"]) == 2
    assert "invalid choice" in capsys.readouterr().err
