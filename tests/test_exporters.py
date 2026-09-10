import json

from ihatemeetings.exporters.transcript import export_all
from ihatemeetings.models import Transcript, TranscriptSegment, Word


def sample_transcript() -> Transcript:
    return Transcript(
        duration=65.25,
        language="it",
        language_probability=0.99,
        source="sample.wav",
        segments=(
            TranscriptSegment(
                "segment-000001",
                1.25,
                3.5,
                "Ciao a tutti.",
                words=(
                    Word("Ciao", 1.25, 1.7, 0.95),
                    Word("a", 1.8, 1.9, 0.9),
                    Word("tutti.", 2.0, 2.5, 0.92),
                ),
            ),
        ),
    )


def test_all_exporters_consume_canonical_transcript(tmp_path):
    paths = export_all(sample_transcript(), tmp_path)

    assert {path.name for path in paths} == {
        "transcript.json",
        "transcript.md",
        "transcript.txt",
        "transcript.srt",
        "transcript.vtt",
    }
    payload = json.loads((tmp_path / "transcript.json").read_text())
    assert payload["schema_version"] == 2
    assert payload["segments"][0]["words"][0]["text"] == "Ciao"
    assert "UNKNOWN [?]" in (tmp_path / "transcript.md").read_text()
    assert "00:00:01,250 --> 00:00:03,500" in (tmp_path / "transcript.srt").read_text()
    assert (tmp_path / "transcript.vtt").read_text().startswith("WEBVTT\n")
