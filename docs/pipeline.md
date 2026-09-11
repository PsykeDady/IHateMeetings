# Phase 4 pipeline

The current pipeline is:

```text
input media -> ffprobe -> FFmpeg PCM mono/16 kHz/16-bit -> faster-whisper
            -> immutable raw ASR -> optional CTC word alignment
            -> optional local Community-1 diarization -> word/cluster merge
            -> optional manual/anchor evidence -> SpeakerResolver
            -> transcript.json schema v4 -> Markdown/TXT/SRT/VTT
```

Output is written to `output/<input-stem>/` unless `--output-dir` is supplied. `raw/media.json`, `raw/asr.json`, `raw/alignment.json`, `raw/diarization.json` and `raw/diarization.rttm` preserve each stage independently. `metadata.json` records versions and execution choices. The temporary normalized WAV is removed after inference.

Alignment is fault-aware. Automatic mode runs only when dependencies and the detected-language model are cached. Explicit `--align` reports failure in `raw/alignment.json` and still exports a usable unaligned transcript. `--no-align` records alignment as disabled. Unsupported words have null timing and confidence rather than invented values.

Official v1 languages are Italian (`it`) and English (`en`). Automatic detection routes those codes to their respective alignment models. Any other detected language produces a visible warning, `officially_supported_language: false` in metadata and `unsupported_language` alignment status; raw ASR and canonical text remain available. An explicitly requested unsupported code is rejected before inference.

Phase 4 runs `ConservativeSpeakerResolver` after temporal attribution. Inputs are explicit `--speaker` mappings, an optional `--speaker-map` YAML file, normalized textual anchors, and an optional participant context. Manual mappings win for their exact cluster. Strong anchors require at least five normalized words and 24 characters; matching first tries exact normalized containment, then a conservative sliding fuzzy comparison. Weak/common phrases are ignored. Multiple strong identities produce `conflicting`; close subthreshold candidates produce `ambiguous`; neither receives a display name.

Fuzzy matches below `0.85` are discarded. A single identity needs at least `0.92` to resolve. If two subthreshold candidates above `0.85` differ by less than `0.05`, the cluster is `ambiguous`. If more than one identity reaches `0.92`, the cluster is `conflicting` regardless of ranking. If the same anchor matches more than one cluster, it is discarded globally rather than used twice.

The participant list only constrains anchor candidates. It never resolves a cluster by itself, and matching cluster count to participant count is forbidden. A configured anchor that is absent from the participant context is ignored with an audit warning.

Manual map schema:

```yaml
speakers:
  SPEAKER_00:
    id: partecipante-a
    name: Partecipante A
  SPEAKER_01: Partecipante B
```

Anchor schema:

```yaml
speakers:
  - id: partecipante-a
    name: Partecipante A
    anchors:
      - "la migrazione del database inizierà dopo il controllo finale"
```

Context may be YAML with a `participants` list or Markdown with a `Participants:` list. Structured entries may provide both `id` and `name`; otherwise a deterministic lowercase slug is derived from the display name. CLI `--speaker` entries override the same cluster from `--speaker-map`.

Every cluster decision is written to `debug/speaker_mapping.json`; raw diarization remains unchanged. Unresolved clusters remain `SPEAKER_NN`, while Phase 3 null attribution remains `UNKNOWN [?]`. Separate VAD, transcript-confidence aggregation and resume remain future work.

Raw inference outputs are immutable. Later processing layers must write separate artifacts so final transcript decisions remain auditable.
