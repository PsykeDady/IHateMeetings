# Phase 2 pipeline

The Phase 2 pipeline is:

```text
input media -> ffprobe -> FFmpeg PCM mono/16 kHz/16-bit -> faster-whisper
            -> immutable raw ASR -> optional CTC word alignment
            -> transcript.json schema v2 -> Markdown/TXT/SRT/VTT
```

Output is written to `output/<input-stem>/` unless `--output-dir` is supplied. `raw/media.json` preserves FFprobe data, `raw/asr.json` preserves backend observations, and `raw/alignment.json` records aligned or explicitly unaligned words without modifying ASR evidence. `metadata.json` records versions and execution choices. The temporary normalized WAV is removed after alignment.

Alignment is fault-aware. Automatic mode runs only when dependencies and the detected-language model are cached. Explicit `--align` reports failure in `raw/alignment.json` and still exports a usable unaligned transcript. `--no-align` records alignment as disabled. Unsupported words have null timing and confidence rather than invented values.

Official v1 languages are Italian (`it`) and English (`en`). Automatic detection routes those codes to their respective alignment models. Any other detected language produces a visible warning, `officially_supported_language: false` in metadata and `unsupported_language` alignment status; raw ASR and canonical text remain available. An explicitly requested unsupported code is rejected before inference.

Phase 2 has no separate VAD stage, diarization, speaker resolution, confidence aggregation or resume. Those remain future stages.

Raw inference outputs are immutable. Later processing layers must write separate artifacts so final transcript decisions remain auditable.
