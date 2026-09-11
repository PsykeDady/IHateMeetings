import shutil
import subprocess
from pathlib import Path

import pytest

from ihatemeetings.errors import IHMError
from ihatemeetings.models import Speaker, SpeakerIdentity, Transcript, TranscriptSegment
from ihatemeetings.speakers import (
    ManualSpeakerMapping,
    ResolutionConfig,
    SpeakerAnchor,
    load_resolution_config,
    parse_speaker_mapping,
)
from ihatemeetings.speakers.resolution import (
    ConservativeSpeakerResolver,
    apply_resolution,
    normalize_anchor_text,
)
from ihatemeetings.speakers.voice import ensure_private_speaker_data_dir, speaker_data_dir

IDENTITY_A = SpeakerIdentity("partecipante-a", "Partecipante A")
IDENTITY_B = SpeakerIdentity("partecipante-b", "Partecipante B")
STRONG_PHRASE = "La migrazione del database inizierà dopo il controllo finale"


def _anonymous_transcript() -> Transcript:
    return Transcript(
        4.0,
        "it",
        0.99,
        "meeting.wav",
        (
            TranscriptSegment(
                "SEG_000001",
                0.0,
                1.0,
                f"{STRONG_PHRASE}.",
                speaker=Speaker("SPEAKER_00"),
            ),
            TranscriptSegment(
                "SEG_000002",
                1.2,
                2.0,
                "Confermo la seconda attività pianificata.",
                speaker=Speaker("SPEAKER_01"),
            ),
            TranscriptSegment("SEG_000003", 2.1, 2.3, "Sì.", unknown_id="UNK_000001"),
        ),
        (Speaker("SPEAKER_00"), Speaker("SPEAKER_01")),
    )


def _resolve(config: ResolutionConfig):
    transcript = _anonymous_transcript()
    report = ConservativeSpeakerResolver().resolve(transcript, config)
    return apply_resolution(transcript, report), report


def test_parse_manual_speaker_mapping_preserves_display_name():
    mapping = parse_speaker_mapping(" SPEAKER_02 = Partecipante A ")
    assert mapping.cluster == "SPEAKER_02"
    assert mapping.identity == IDENTITY_A


@pytest.mark.parametrize("value", ("SPEAKER_00", "speaker_00=Nome", "SPEAKER_00="))
def test_invalid_manual_speaker_mapping_is_rejected(value):
    with pytest.raises(ValueError, match="SPEAKER_NN=Name"):
        parse_speaker_mapping(value)


def test_manual_mapping_is_authoritative_and_retains_provenance():
    config = ResolutionConfig(
        manual_mappings=(ManualSpeakerMapping("SPEAKER_00", IDENTITY_A),),
        anchors=(SpeakerAnchor(IDENTITY_B, STRONG_PHRASE),),
    )
    resolved, report = _resolve(config)

    speaker = resolved.speakers[0]
    assert speaker.identity == IDENTITY_A
    assert speaker.confidence == 1.0
    assert speaker.evidence[0].type == "manual_mapping"
    assert speaker.evidence[0].method == "explicit_user_input"
    assert resolved.segments[0].speaker == speaker
    assert report.resolver == "conservative-v1"


def test_manual_mapping_never_creates_a_missing_cluster():
    config = ResolutionConfig(manual_mappings=(ManualSpeakerMapping("SPEAKER_09", IDENTITY_A),))
    with pytest.raises(IHMError, match="unknown cluster"):
        _resolve(config)


def test_anchor_normalization_handles_unicode_case_punctuation_and_whitespace():
    assert normalize_anchor_text("  LA migrazione—del DATABASE!\ninizierà  ") == (
        "la migrazione del database inizierà"
    )


def test_strong_exact_normalized_anchor_resolves_expected_cluster():
    config = ResolutionConfig(
        anchors=(SpeakerAnchor(IDENTITY_A, f"  {STRONG_PHRASE.upper()}!!!  "),)
    )
    resolved, _report = _resolve(config)

    assert resolved.speakers[0].status == "resolved"
    assert resolved.speakers[0].identity == IDENTITY_A
    assert resolved.speakers[0].evidence[0].method == "exact_normalized"
    assert resolved.speakers[1].status == "unresolved"


def test_conservative_fuzzy_anchor_tolerates_one_small_asr_error():
    anchor = "La migrazione del database iniziera dopo il controllo finali"
    resolved, _report = _resolve(ResolutionConfig(anchors=(SpeakerAnchor(IDENTITY_A, anchor),)))

    assert resolved.speakers[0].status == "resolved"
    assert resolved.speakers[0].evidence[0].method == "fuzzy_normalized"


def test_weak_common_anchor_does_not_create_false_certainty():
    resolved, report = _resolve(
        ResolutionConfig(anchors=(SpeakerAnchor(IDENTITY_A, "sì va bene"),))
    )

    assert resolved.speakers[0].status == "unresolved"
    assert resolved.speakers[0].identity is None
    assert any("Ignored weak anchor" in warning for warning in report.warnings)


def test_conflicting_strong_anchors_do_not_choose_an_identity():
    config = ResolutionConfig(
        anchors=(
            SpeakerAnchor(IDENTITY_A, STRONG_PHRASE),
            SpeakerAnchor(IDENTITY_B, STRONG_PHRASE),
        )
    )
    resolved, _report = _resolve(config)

    speaker = resolved.speakers[0]
    assert speaker.status == "conflicting"
    assert speaker.identity is None
    assert {candidate.identity.id for candidate in speaker.candidates} == {
        "partecipante-a",
        "partecipante-b",
    }


def test_similar_but_subthreshold_candidates_are_ambiguous_not_selected():
    config = ResolutionConfig(
        anchors=(
            SpeakerAnchor(
                IDENTITY_A,
                "La migrazione del database inizierà prima del controllo finale",
            ),
            SpeakerAnchor(
                IDENTITY_B,
                "La migrazione del sistema inizierà dopo il controllo finale",
            ),
        )
    )
    resolved, _report = _resolve(config)

    speaker = resolved.speakers[0]
    assert speaker.status == "ambiguous"
    assert speaker.identity is None
    assert len(speaker.candidates) == 2


def test_unresolved_cluster_and_phase3_unknown_remain_distinct():
    resolved, _report = _resolve(ResolutionConfig())

    assert resolved.speakers[0].name is None
    assert resolved.segments[0].speaker.cluster == "SPEAKER_00"
    assert resolved.segments[2].speaker is None


def test_participant_list_alone_does_not_resolve_any_cluster():
    resolved, _report = _resolve(ResolutionConfig(participants=(IDENTITY_A, IDENTITY_B)))
    assert all(speaker.status == "unresolved" for speaker in resolved.speakers)
    assert all(speaker.identity is None for speaker in resolved.speakers)


def test_context_constrains_anchor_candidates_without_becoming_evidence():
    config = ResolutionConfig(
        anchors=(SpeakerAnchor(IDENTITY_B, STRONG_PHRASE),),
        participants=(IDENTITY_A,),
    )
    resolved, report = _resolve(config)

    assert resolved.speakers[0].status == "unresolved"
    assert any("not in context" in warning for warning in report.warnings)


def test_yaml_loaders_and_cli_precedence(tmp_path):
    speaker_map = tmp_path / "speaker-map.yaml"
    speaker_map.write_text(
        "speakers:\n  SPEAKER_00: Partecipante A\n  SPEAKER_01: Partecipante B\n",
        encoding="utf-8",
    )
    anchors = tmp_path / "anchors.yaml"
    anchors.write_text(
        "speakers:\n"
        "  - id: partecipante-a\n"
        "    name: Partecipante A\n"
        "    anchors:\n"
        f"      - {STRONG_PHRASE}\n",
        encoding="utf-8",
    )
    context = tmp_path / "context.yaml"
    context.write_text("participants:\n  - Partecipante A\n", encoding="utf-8")

    config = load_resolution_config(
        cli_mappings=(parse_speaker_mapping("SPEAKER_01=Partecipante C"),),
        speaker_map_path=speaker_map,
        anchors_path=anchors,
        context_path=context,
    )

    assert [mapping.identity.display_name for mapping in config.manual_mappings] == [
        "Partecipante A",
        "Partecipante C",
    ]
    assert config.anchors[0].identity == IDENTITY_A
    assert config.participants == (IDENTITY_A,)


def test_markdown_context_is_accepted(tmp_path):
    context = tmp_path / "context.md"
    context.write_text(
        "# Meeting context\n\nParticipants:\n- Partecipante A\n- Partecipante B\n\nSubject:\nTest.\n",
        encoding="utf-8",
    )
    config = load_resolution_config(context_path=context)
    assert config.participants == (IDENTITY_A, IDENTITY_B)


def test_voice_profile_storage_is_local_and_private(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert speaker_data_dir() == tmp_path / "ihatemeetings" / "speakers"
    target = ensure_private_speaker_data_dir()
    assert target.stat().st_mode & 0o777 == 0o700


def test_privacy_sensitive_local_paths_are_ignored():
    ignore = (Path(__file__).parents[1] / ".gitignore").read_text(encoding="utf-8")
    assert "output/" in ignore
    assert "speaker-profiles/" in ignore
    assert "*.speaker-embedding" in ignore


def test_private_output_is_not_tracked_when_git_metadata_is_available():
    root = Path(__file__).parents[1]
    if not (root / ".git").exists() or shutil.which("git") is None:
        pytest.skip("Git metadata is not available in this source tree")
    result = subprocess.run(
        ["git", "ls-files", "output"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""
