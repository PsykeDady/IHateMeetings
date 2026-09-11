import hashlib
import json
from datetime import UTC, datetime

import pytest

from ihatemeetings.cli.main import main
from ihatemeetings.errors import IHMError
from ihatemeetings.exporters import export_all
from ihatemeetings.models import Speaker, SpeakerIdentity, Transcript, TranscriptSegment, Word
from ihatemeetings.review.effective import effective_segments
from ihatemeetings.review.interactive import run_interactive
from ihatemeetings.review.io import load_review
from ihatemeetings.review.service import ReviewSession


def _clock():
    return datetime(2026, 9, 11, 10, 0, tzinfo=UTC)


def _make_job(tmp_path):
    job = tmp_path / "meeting"
    sonia = Speaker(
        "SPEAKER_00",
        SpeakerIdentity("sonia-greco", "Sonia Greco"),
        "resolved",
        0.99,
        "conservative-v1",
    )
    davide = Speaker("SPEAKER_01")
    transcript = Transcript(
        5.0,
        "it",
        0.99,
        "meeting.wav",
        (
            TranscriptSegment(
                "SEG_000001",
                0.0,
                1.0,
                "Prima frase.",
                (Word("Prima", 0.0, 0.4, 0.9), Word("frase.", 0.5, 1.0, 0.8)),
                sonia,
            ),
            TranscriptSegment("SEG_000002", 1.0, 2.0, "solo una", unknown_id="UNK_000001"),
            TranscriptSegment("SEG_000003", 2.0, 3.0, "cosa.", speaker=sonia),
            TranscriptSegment("SEG_000004", 3.0, 4.0, "Ultima.", speaker=davide),
        ),
        (sonia, davide),
    )
    export_all(transcript, job)
    raw = job / "raw"
    raw.mkdir()
    (raw / "diarization.json").write_text('{"immutable": true}\n', encoding="utf-8")
    debug = job / "debug"
    debug.mkdir()
    (debug / "speaker_mapping.json").write_text('{"phase": 4}\n', encoding="utf-8")
    return job


def _session(job):
    return ReviewSession.open(job, clock=_clock)


def _hash_tree(job):
    return {
        str(path.relative_to(job)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in job.rglob("*")
        if path.is_file()
    }


def test_cluster_assignment_changes_effective_identity_and_keeps_machine_evidence(tmp_path):
    job = _make_job(tmp_path)
    raw_before = (job / "raw" / "diarization.json").read_bytes()
    session = _session(job)
    session.assign_cluster("SPEAKER_00", "Federica Orsini")
    session.save()

    loaded = load_review(job).transcript
    labels = [item.attribution.label for item in effective_segments(loaded)]
    assert labels[:3] == ["Federica Orsini", "UNKNOWN [?]", "Federica Orsini"]
    assert loaded.segments[0].speaker.name == "Sonia Greco"
    assert (job / "raw" / "diarization.json").read_bytes() == raw_before


def test_segment_override_beats_cluster_assignment(tmp_path):
    session = _session(_make_job(tmp_path))
    session.assign_cluster("SPEAKER_00", "Federica Orsini")
    session.assign_segment("SEG_000003", display_name="Davide Galati")

    labels = [item.attribution.label for item in effective_segments(session.transcript)]
    assert labels == ["Federica Orsini", "UNKNOWN [?]", "Davide Galati", "SPEAKER_01"]


@pytest.mark.parametrize("reference", ("SEG_000002", "UNK_000001"))
def test_unknown_assignment_by_both_stable_ids_preserves_unknown_provenance(tmp_path, reference):
    session = _session(_make_job(tmp_path))
    session.assign_unknown(reference, display_name="Sonia Greco")
    session.save()

    segment = load_review(session.output_dir).transcript.segments[1]
    assert segment.unknown_id == "UNK_000001"
    assert segment.speaker is None
    assert effective_segments(load_review(session.output_dir).transcript)[1].attribution.label == (
        "Sonia Greco"
    )


@pytest.mark.parametrize("reference", ("SEG_999999", "UNK_999999"))
def test_invalid_stable_id_fails_without_writing(tmp_path, reference):
    job = _make_job(tmp_path)
    before = _hash_tree(job)
    session = _session(job)
    with pytest.raises(IHMError, match="Unknown"):
        session.assign_unknown(reference, display_name="Sonia Greco")
    assert _hash_tree(job) == before


def test_non_unknown_cannot_be_resolved_as_unknown(tmp_path):
    session = _session(_make_job(tmp_path))
    with pytest.raises(IHMError, match="not originally UNKNOWN"):
        session.assign_unknown("SEG_000001", display_name="Davide")


def test_assignment_can_explicitly_target_an_existing_anonymous_cluster(tmp_path):
    session = _session(_make_job(tmp_path))
    session.assign_segment("UNK_000001", cluster="SPEAKER_01")
    item = effective_segments(session.transcript)[1]
    assert item.attribution.label == "SPEAKER_01"
    assert item.attribution.target_cluster == "SPEAKER_01"


def test_adjacent_merge_preserves_order_words_ids_and_provenance(tmp_path):
    session = _session(_make_job(tmp_path))
    session.merge("SEG_000001", "SEG_000002", display_name="Sonia Greco")
    session.save()

    transcript = load_review(session.output_dir).transcript
    merged = effective_segments(transcript)[0]
    assert merged.id == "SEG_000001"
    assert merged.source_segment_ids == ("SEG_000001", "SEG_000002")
    assert merged.text == "Prima frase. solo una"
    assert merged.start == 0.0 and merged.end == 2.0
    assert [word.text for word in merged.words] == ["Prima", "frase."]
    assert transcript.segments[1].unknown_id == "UNK_000001"
    assert transcript.segments[1].review.merged_into == "SEG_000001"
    assert transcript.segments[2].id == "SEG_000003"
    audit = json.loads((session.output_dir / "review" / "revisions.json").read_text())
    assert audit["revisions"][-1]["operation"] == "merge_segments"
    assert audit["revisions"][-1]["targets"] == ["SEG_000001", "SEG_000002"]


def test_merge_rejects_non_adjacent_and_speaker_mismatch_without_resolution(tmp_path):
    session = _session(_make_job(tmp_path))
    with pytest.raises(IHMError, match="adjacent"):
        session.merge("SEG_000001", "SEG_000003")
    with pytest.raises(IHMError, match="different effective speakers"):
        session.merge("SEG_000001", "SEG_000002")


def test_delete_is_tombstoned_omitted_and_does_not_renumber(tmp_path):
    session = _session(_make_job(tmp_path))
    session.delete("SEG_000002")
    session.save()

    transcript = load_review(session.output_dir).transcript
    assert [segment.id for segment in transcript.segments] == [
        "SEG_000001",
        "SEG_000002",
        "SEG_000003",
        "SEG_000004",
    ]
    assert transcript.segments[1].review.status == "deleted"
    assert "solo una" not in (session.output_dir / "transcript.md").read_text()
    assert transcript.segments[1].unknown_id == "UNK_000001"


def test_review_list_show_and_speakers_expose_copyable_ids(tmp_path, capsys):
    job = _make_job(tmp_path)
    assert main(["review", "list", str(job), "--unknown-only"]) == 0
    assert "SEG_000002 · UNK_000001" in capsys.readouterr().out
    assert main(["review", "show", str(job), "UNK_000001"]) == 0
    assert "Original: UNKNOWN [?]" in capsys.readouterr().out
    assert main(["review", "speakers", str(job)]) == 0
    assert "SPEAKER_00 · Sonia Greco" in capsys.readouterr().out


def test_static_review_cli_does_not_invoke_transcription_pipeline(monkeypatch, tmp_path):
    job = _make_job(tmp_path)
    monkeypatch.setattr(
        "ihatemeetings.cli.main.run_transcription",
        lambda *_args, **_kwargs: pytest.fail("ML pipeline was invoked"),
    )
    assert (
        main(
            [
                "review",
                "assign-speaker",
                str(job),
                "SPEAKER_00",
                "--name",
                "Federica Orsini",
            ]
        )
        == 0
    )


def test_static_assign_unknown_by_cli_preserves_id(tmp_path):
    job = _make_job(tmp_path)
    assert (
        main(
            [
                "review",
                "assign-unknown",
                str(job),
                "UNK_000001",
                "--name",
                "Sonia Greco",
            ]
        )
        == 0
    )
    payload = json.loads((job / "transcript.json").read_text())
    assert payload["segments"][1]["unknown_id"] == "UNK_000001"
    assert payload["segments"][1]["effective"]["speaker"]["label"] == "Sonia Greco"


def test_interactive_ok_skip_assignment_merge_delete_and_save(tmp_path):
    job = _make_job(tmp_path)
    session = _session(job)
    answers = iter(
        [
            "",  # accept first
            "a",
            "n",
            "Sonia Greco",  # assign UNKNOWN
            "m",  # merge third with fourth, speakers differ
            "n",
            "Davide Galati",
            "q",
        ]
    )
    assert run_interactive(session, input_fn=lambda _prompt: next(answers), emit=lambda _: None)
    loaded = load_review(job)
    operations = [item["operation"] for item in loaded.revisions]
    assert operations == [
        "accept_segment",
        "assign_segment_identity",
        "merge_segments",
    ]
    assert loaded.transcript.segments[0].review.accepted is True
    assert loaded.transcript.segments[1].review.accepted is False
    assert loaded.transcript.segments[3].review.status == "merged"


def test_interactive_skip_and_discard_write_nothing(tmp_path):
    job = _make_job(tmp_path)
    before = _hash_tree(job)
    answers = iter(["s", "d", "Q"])
    saved = run_interactive(
        _session(job), input_fn=lambda _prompt: next(answers), emit=lambda _: None
    )
    assert saved is False
    assert _hash_tree(job) == before


def test_interactive_cluster_rename_and_delete_persist_on_save(tmp_path):
    job = _make_job(tmp_path)
    answers = iter(["r", "Federica Orsini", "d", "q"])
    assert run_interactive(
        _session(job), input_fn=lambda _prompt: next(answers), emit=lambda _: None
    )
    loaded = load_review(job)
    assert loaded.transcript.review.cluster_assignments[0].assignment.identity.display_name == (
        "Federica Orsini"
    )
    assert loaded.transcript.segments[1].review.status == "deleted"


def test_interactive_unknown_only_enumerates_only_original_unknown(tmp_path):
    session = _session(_make_job(tmp_path))
    shown = []
    answers = iter(["Q"])
    run_interactive(
        session,
        unknown_only=True,
        input_fn=lambda _prompt: next(answers),
        emit=shown.append,
    )
    output = "\n".join(shown)
    assert "SEG_000002" in output
    assert "SEG_000001" not in output


def test_failed_transaction_restores_existing_outputs(monkeypatch, tmp_path):
    job = _make_job(tmp_path)
    before = _hash_tree(job)
    session = _session(job)
    session.assign_segment("SEG_000003", display_name="Davide Galati")
    import ihatemeetings.review.io as review_io

    real_replace = review_io.os.replace
    failed = False

    def fail_once(source, destination):
        nonlocal failed
        if not failed and str(destination).endswith("transcript.md"):
            failed = True
            raise OSError("simulated persistence failure")
        return real_replace(source, destination)

    monkeypatch.setattr(review_io.os, "replace", fail_once)
    with pytest.raises(OSError, match="simulated"):
        session.save()
    assert _hash_tree(job) == before


def test_v4_migration_is_explicit_audited_and_assigns_stable_ids(tmp_path):
    job = _make_job(tmp_path)
    payload = json.loads((job / "transcript.json").read_text())
    payload["schema_version"] = 4
    payload.pop("review")
    for index, segment in enumerate(payload["segments"], 1):
        segment["id"] = f"segment-{index:06d}"
        segment.pop("unknown_id")
        segment.pop("original")
        segment.pop("review")
        segment.pop("effective")
    (job / "transcript.json").write_text(json.dumps(payload), encoding="utf-8")

    session = _session(job)
    assert [item.id for item in session.transcript.segments] == [
        "SEG_000001",
        "SEG_000002",
        "SEG_000003",
        "SEG_000004",
    ]
    assert session.transcript.segments[1].unknown_id == "UNK_000001"
    session.assign_unknown("UNK_000001", display_name="Sonia Greco")
    session.save()
    audit = json.loads((job / "review" / "revisions.json").read_text())
    assert audit["revisions"][0]["operation"] == "schema_migration"
    assert audit["revisions"][0]["before"]["segment_ids"]["segment-000001"] == ("SEG_000001")


def test_unsupported_old_schema_is_rejected_conservatively(tmp_path):
    job = _make_job(tmp_path)
    payload = json.loads((job / "transcript.json").read_text())
    payload["schema_version"] = 3
    (job / "transcript.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(IHMError, match="v4 or v5"):
        ReviewSession.open(job)
