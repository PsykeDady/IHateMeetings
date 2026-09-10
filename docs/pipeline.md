# Pipeline

The target MVP pipeline is:

```text
input media -> ffprobe -> ffmpeg audio -> ASR -> canonical transcript -> exporters
```

Future phases will insert VAD, alignment, diarization, speaker resolution, confidence analysis and cache-aware resume between those steps.

Raw inference outputs are immutable. Later processing layers must write separate artifacts so final transcript decisions remain auditable.

