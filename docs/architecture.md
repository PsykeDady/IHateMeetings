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

Phase 2 implements media inspection, normalized temporary audio, ASR, optional word alignment and export. Its concrete flow is:

```text
source -> MediaInspection/MediaInfo -> temporary 16 kHz mono PCM
       -> ASRBackend/ASRResult -> AlignmentBackend/AlignmentResult
       -> Transcript schema v2 -> exporters
```

`FasterWhisperBackend` is the ASR implementation. `CTCAlignmentBackend` is the first alignment implementation and uses a language-specific Transformers CTC model. Both immediately convert third-party values into typed immutable IHateMeetings models. Exporters only consume the canonical `Transcript`, never backend output. FFprobe, ASR and alignment evidence are stored separately under `raw/`; normalized audio is temporary until cache/resume arrives in Phase 5.

CPU INT8 is a required and tested selection path. CUDA FP16 is selected only when CTranslate2 reports an accessible CUDA device. Manual device and compute-type overrides remain available.

The project runtime is CPython 3.13 managed by `uv`, independently of the host distribution's Python. Language policy is centralized: `it` and `en` route to their configured CTC models, while unsupported automatically detected languages retain ASR output but skip alignment explicitly.

`ASROptions.glossary_terms` provides a typed, non-mutating route for future glossary hints. Faster-whisper is always invoked with `task="transcribe"`; no translation or technical-term rewriting is performed.

External ML libraries must be wrapped behind internal interfaces before use, so third-party response shapes do not leak through the application.
