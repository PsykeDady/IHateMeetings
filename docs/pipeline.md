# Phase 4 and 4.1 pipeline

The current pipeline is:

```text
input media -> ffprobe -> FFmpeg PCM mono/16 kHz/16-bit -> faster-whisper
            -> immutable raw ASR -> optional CTC word alignment
            -> optional local Community-1 diarization -> word/cluster merge
            -> optional manual/anchor evidence -> SpeakerResolver
            -> transcript.json schema v5 -> Markdown/TXT/SRT/VTT
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

## Post-hoc review (Phase 4.1)

Review consumes only an existing output directory. It never inspects media or invokes FFmpeg,
ASR, alignment, diarization or speaker-resolution ML:

```text
ihm review list OUTPUT [--unknown-only]
ihm review show OUTPUT SEG_000019
ihm review show OUTPUT UNK_000004
ihm review speakers OUTPUT
ihm review assign-speaker OUTPUT SPEAKER_02 --name "Sonia Greco"
ihm review assign-segment OUTPUT SEG_000042 --name "Davide Galati"
ihm review assign-segment OUTPUT SEG_000042 --cluster SPEAKER_01
ihm review assign-unknown OUTPUT UNK_000004 --name "Sonia Greco"
ihm review merge OUTPUT SEG_000019 SEG_000020 --name "Sonia Greco"
ihm review delete OUTPUT SEG_000031
ihm review interactive OUTPUT [--unknown-only]
```

Name and cluster targets use separate mutually exclusive flags, so arbitrary names are never
guessed to be cluster IDs. Segment assignments override cluster assignments. Cluster assignments
override the Phase 4 resolver. The remaining fallbacks are anonymous cluster and UNKNOWN.

Merge accepts adjacent active segments in original order only. The earlier ID survives; the
later segment is retained as a merged tombstone. Text and words are combined in order and the
effective time range spans both. A speaker mismatch requires `--name` or `--cluster`. Delete is
a tombstone operation: normal Markdown/TXT/SRT/VTT omit it, canonical JSON and audit retain it.

Interactive `OK` marks a segment accepted; `Skip` advances without recording acceptance.
Previous and jump navigation are available. Lowercase `q` atomically saves all accumulated
operations and re-exports; uppercase `Q` discards the in-memory session and performs no writes.
