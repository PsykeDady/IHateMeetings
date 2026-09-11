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
    assert (
        main(["transcribe", str(source), "--language", language, "--model", "tiny", "--align"]) == 0
    )
    assert calls == [(source, language, "tiny", True), (source, language, "tiny", True)]


def test_explicit_unsupported_language_is_rejected(tmp_path, capsys):
    source = tmp_path / "meeting.mp3"
    source.touch()

    assert main([str(source), "--language", "fr"]) == 2
    assert "invalid choice" in capsys.readouterr().err


@pytest.mark.parametrize(
    "arguments,message",
    (
        (["--num-speakers", "2", "--min-speakers", "1"], "cannot be combined"),
        (["--min-speakers", "3", "--max-speakers", "2"], "cannot be greater"),
        (["--no-diarize", "--num-speakers", "2"], "cannot be used"),
    ),
)
def test_invalid_diarization_options_are_rejected(tmp_path, capsys, arguments, message):
    source = tmp_path / "meeting.wav"
    source.touch()

    assert main([str(source), *arguments]) == 2
    assert message in capsys.readouterr().out


def test_manual_speaker_mapping_enables_diarization_and_reaches_pipeline(monkeypatch, tmp_path):
    source = tmp_path / "meeting.wav"
    source.touch()
    calls = []

    def fake_pipeline(_input_path, config):
        calls.append(config)
        return Path("output/meeting")

    monkeypatch.setattr("ihatemeetings.cli.main.run_transcription", fake_pipeline)

    assert main([str(source), "--speaker", "SPEAKER_00=Partecipante A"]) == 0
    assert calls[0].diarize is True
    mapping = calls[0].speaker_resolution.manual_mappings[0]
    assert mapping.cluster == "SPEAKER_00"
    assert mapping.identity.display_name == "Partecipante A"


@pytest.mark.parametrize(
    "arguments,message",
    (
        (["--speaker", "Nome"], "Invalid --speaker mapping"),
        (
            ["--speaker", "SPEAKER_00=Partecipante A", "--speaker", "SPEAKER_00=Partecipante B"],
            "may be mapped only once",
        ),
        (
            ["--no-diarize", "--speaker", "SPEAKER_00=Partecipante A"],
            "cannot be used with --no-diarize",
        ),
    ),
)
def test_invalid_manual_speaker_cli_options_are_rejected(tmp_path, capsys, arguments, message):
    source = tmp_path / "meeting.wav"
    source.touch()

    assert main([str(source), *arguments]) == 2
    assert message in capsys.readouterr().out


def test_anchor_and_context_files_enable_resolution(monkeypatch, tmp_path):
    source = tmp_path / "meeting.wav"
    source.touch()
    anchors = tmp_path / "anchors.yaml"
    anchors.write_text(
        "speakers:\n"
        "  - name: Partecipante A\n"
        "    anchors:\n"
        "      - questa frase tecnica identifica il parlante senza ambiguità\n",
        encoding="utf-8",
    )
    context = tmp_path / "context.yaml"
    context.write_text("participants:\n  - Partecipante A\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(
        "ihatemeetings.cli.main.run_transcription",
        lambda _input_path, config: calls.append(config) or Path("output/meeting"),
    )

    assert main([str(source), "--anchors", str(anchors), "--context", str(context)]) == 0
    assert calls[0].diarize is True
    assert calls[0].speaker_resolution.anchors
    assert calls[0].speaker_resolution.participants


def test_missing_resolution_file_fails_before_pipeline(monkeypatch, tmp_path, capsys):
    source = tmp_path / "meeting.wav"
    source.touch()
    called = False

    def fake_pipeline(_input_path, _config):
        nonlocal called
        called = True

    monkeypatch.setattr("ihatemeetings.cli.main.run_transcription", fake_pipeline)

    assert main([str(source), "--anchors", str(tmp_path / "missing.yaml")]) == 1
    assert "Configuration file not found" in capsys.readouterr().err
    assert called is False
