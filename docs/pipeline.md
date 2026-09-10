# Pipeline

The Phase 1 pipeline is:

```text
input media -> ffprobe -> FFmpeg PCM mono/16 kHz/16-bit -> faster-whisper
            -> transcript.json schema v1 -> Markdown/TXT/SRT/VTT
```

Output is written to `output/<input-stem>/` unless `--output-dir` is supplied. `raw/media.json` preserves FFprobe data, `raw/asr.json` preserves backend observations, and `metadata.json` records versions and execution choices. The temporary normalized WAV is removed after the ASR stage.

Phase 1 has no VAD, word alignment, diarization, speaker resolution, confidence aggregation or resume. Those remain future stages.

Raw inference outputs are immutable. Later processing layers must write separate artifacts so final transcript decisions remain auditable.
