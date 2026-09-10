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
