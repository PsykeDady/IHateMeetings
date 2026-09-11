import json

from ihatemeetings.exporters.transcript import export_all
from ihatemeetings.models import Speaker, SpeakerIdentity, Transcript, TranscriptSegment, Word


def sample_transcript() -> Transcript:
    return Transcript(
        duration=65.25,
        language="it",
        language_probability=0.99,
        source="sample.wav",
        segments=(
            TranscriptSegment(
                "SEG_000001",
                1.25,
                3.5,
                "Ciao a tutti.",
                words=(
                    Word("Ciao", 1.25, 1.7, 0.95),
                    Word("a", 1.8, 1.9, 0.9),
                    Word("tutti.", 2.0, 2.5, 0.92),
                ),
                unknown_id="UNK_000001",
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
    assert payload["schema_version"] == 5
    assert payload["segments"][0]["words"][0]["text"] == "Ciao"
    assert "UNKNOWN [?]" in (tmp_path / "transcript.md").read_text()
    assert "00:00:01,250 --> 00:00:03,500" in (tmp_path / "transcript.srt").read_text()
    assert (tmp_path / "transcript.vtt").read_text().startswith("WEBVTT\n")


def test_exporters_render_diarization_clusters_without_inventing_names(tmp_path):
    transcript = Transcript(
        2.0,
        "en",
        0.99,
        "sample.wav",
        (TranscriptSegment("SEG_000001", 0.1, 1.0, "Hello.", speaker=Speaker("SPEAKER_00")),),
        (Speaker("SPEAKER_00"),),
    )

    export_all(transcript, tmp_path)

    assert "SPEAKER_00" in (tmp_path / "transcript.md").read_text()
    assert "[SPEAKER_00] Hello." in (tmp_path / "transcript.srt").read_text()
    assert "[SPEAKER_00] Hello." in (tmp_path / "transcript.vtt").read_text()
    assert "Partecipante inventato" not in (tmp_path / "transcript.txt").read_text()


def test_all_human_exporters_render_only_a_resolved_display_name(tmp_path):
    identity = SpeakerIdentity("participant-a", "Partecipante A")
    speaker = Speaker("SPEAKER_00", identity, "resolved", 1.0, "test")
    transcript = Transcript(
        2.0,
        "it",
        0.99,
        "sample.wav",
        (TranscriptSegment("SEG_000001", 0.1, 1.0, "Salve.", speaker=speaker),),
        (speaker,),
    )

    export_all(transcript, tmp_path)

    assert "Partecipante A" in (tmp_path / "transcript.md").read_text()
    assert "[00:00:00] Partecipante A" in (tmp_path / "transcript.txt").read_text()
    assert "[Partecipante A] Salve." in (tmp_path / "transcript.srt").read_text()
    assert "[Partecipante A] Salve." in (tmp_path / "transcript.vtt").read_text()


def test_unknown_attribution_is_not_relabelled_by_resolved_neighbor(tmp_path):
    identity = SpeakerIdentity("participant-a", "Partecipante A")
    speaker = Speaker("SPEAKER_00", identity, "resolved", 1.0, "test")
    transcript = Transcript(
        2.0,
        "it",
        0.99,
        "sample.wav",
        (
            TranscriptSegment("SEG_000001", 0.0, 0.8, "Confermato.", speaker=speaker),
            TranscriptSegment("SEG_000002", 0.8, 1.0, "Sì.", unknown_id="UNK_000001"),
        ),
        (speaker,),
    )

    export_all(transcript, tmp_path)

    markdown = (tmp_path / "transcript.md").read_text()
    assert "Partecipante A" in markdown
    assert "UNKNOWN [?]" in markdown
