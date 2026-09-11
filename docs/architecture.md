# Architecture

IHateMeetings is designed as a staged local-first pipeline:

1. Media inspection.
2. Audio extraction and normalization.
3. Voice activity detection.
4. Speech recognition.
5. Word alignment.
6. Speaker diarization.
7. Speaker resolution.
8. Confidence analysis.
9. Optional reasoning over uncertain regions.
10. Transcript reconstruction and export.

Phases 0–4 implement media inspection, normalized temporary audio, ASR, optional word alignment, optional speaker diarization, temporal word attribution, conservative identity resolution and export. Phase 4.1 adds post-hoc review from an existing output directory. The concrete flow is:

```text
source -> MediaInspection/MediaInfo -> temporary 16 kHz mono PCM
       -> ASRBackend/ASRResult -> AlignmentBackend/AlignmentResult
       -> DiarizationBackend/DiarizationResult -> temporal attribution
       -> SpeakerResolver/ResolutionReport -> Transcript schema v5 -> exporters

existing output -> ReviewSession (no media/ML stages) -> explicit review overrides
                -> atomic canonical/audit persistence -> reviewed exporters
```

`FasterWhisperBackend` is the ASR implementation, `CTCAlignmentBackend` is the alignment implementation, and `PyannoteDiarizationBackend` wraps local Community-1 inference. `SpeakerResolver` is a separate interface; `ConservativeSpeakerResolver` combines explicit manual mappings and local textual-anchor evidence. Third-party values are immediately converted into typed immutable IHateMeetings models. Exporters only consume the canonical `Transcript`. FFprobe, ASR, alignment and diarization evidence are stored separately under `raw/`; speaker decisions live under `debug/`; normalized audio is temporary until cache/resume arrives in Phase 5.

The post-hoc review package loads schema v4/v5 without invoking media, ASR, alignment or
diarization backends. `ReviewSession` records immutable-style state transitions;
the effective transcript is derived from original segments plus cluster and segment overrides.
`review/revisions.json` is the durable operation log. Transactional persistence prepares all
canonical and human-readable outputs before replacement and restores prior files if replacement
fails. Interactive sessions stay in memory until explicit save.

Speaker identity models are explicit: `SpeakerIdentity`, `IdentityEvidence`, `IdentityCandidate`, `Speaker`, and `ResolutionReport`. A `Speaker` always retains its diarization cluster and a resolution status. Only `resolved` speakers may contain a selected identity. Segment speaker nullability is not changed by identity resolution.

Manual mappings are authoritative per cluster. Anchor matching uses deterministic Unicode/case/punctuation/whitespace normalization and conservative fuzzy matching, with minimum anchor-strength and decision thresholds documented in the pipeline guide. Participant context constrains anchors but supplies no evidence. Conflict and ambiguity remain data rather than being collapsed to a guessed name.

Word attribution aggregates temporal overlap per speaker. A unique winner must cover at least half the word and at least 60% of all candidate overlap. Exact overlap ties stay unassigned. A gap of at most 250 ms is bridged only when the nearest turns on both sides belong to the same cluster. Candidate overlaps and the selected method remain in canonical word provenance. Regular pyannote diarization, rather than its exclusive view, preserves overlapping speech.

CPU INT8 is a required and tested selection path. CUDA FP16 is selected only when CTranslate2 reports an accessible CUDA device. Manual device and compute-type overrides remain available.

The project runtime is CPython 3.13 managed by `uv`, independently of the host distribution's Python. Language policy is centralized: `it` and `en` route to their configured CTC models, while unsupported automatically detected languages retain ASR output but skip alignment explicitly.

`ASROptions.glossary_terms` provides a typed, non-mutating route for future glossary hints. Faster-whisper is always invoked with `task="transcribe"`; no translation or technical-term rewriting is performed.

External ML libraries must be wrapped behind internal interfaces before use, so third-party response shapes do not leak through the application.
