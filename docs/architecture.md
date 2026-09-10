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

Phase 1 implements media inspection, normalized temporary audio, ASR and export. Its concrete flow is:

```text
source -> MediaInspection/MediaInfo -> temporary 16 kHz mono PCM
       -> ASRBackend/ASRResult -> Transcript schema v1 -> exporters
```

`FasterWhisperBackend` is the only ASR implementation in Phase 1. It immediately converts third-party segments into typed immutable IHateMeetings models. Exporters only consume the canonical `Transcript`, never backend output. FFprobe and ASR evidence are stored separately under `raw/`; normalized audio is temporary until cache/resume arrives in Phase 5.

CPU INT8 is a required and tested selection path. CUDA FP16 is selected only when CTranslate2 reports an accessible CUDA device. Manual device and compute-type overrides remain available.

External ML libraries must be wrapped behind internal interfaces before use, so third-party response shapes do not leak through the application.
