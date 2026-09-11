# Canonical transcript schema v3

`transcript.json` is the canonical final Phase 3 representation. All text and subtitle exporters consume the same typed `Transcript` object.

```json
{
  "schema_version": 3,
  "meeting": {
    "source": "meeting.mp3",
    "duration": 42.5,
    "language": "it",
    "language_probability": 0.98
  },
  "speakers": [
    {"cluster": "SPEAKER_00", "name": null, "confidence": null}
  ],
  "segments": [
    {
      "id": "segment-000001",
      "start": 0.5,
      "end": 3.2,
      "text": "Buongiorno a tutti.",
      "speaker": {"cluster": "SPEAKER_00", "name": null, "confidence": null},
      "confidence": null,
      "words": [
        {
          "text": "Buongiorno",
          "start": 0.52,
          "end": 1.18,
          "confidence": 0.91,
          "speaker": {
            "speaker_id": "SPEAKER_00",
            "method": "temporal_overlap",
            "overlap": 0.66,
            "word_coverage": 1.0,
            "candidates": [
              {"speaker_id": "SPEAKER_00", "overlap": 0.66}
            ]
          }
        },
        {
          "text": "a",
          "start": null,
          "end": null,
          "confidence": null,
          "speaker": {
            "speaker_id": null,
            "method": "missing_word_timestamps",
            "overlap": 0.0,
            "word_coverage": 0.0,
            "candidates": []
          }
        }
      ]
    }
  ]
}
```

Schema v3 is additive relative to v2 at word and meeting level: words gain nullable speaker-attribution provenance, and `speakers` lists anonymous diarization clusters. Diarization can also split one ASR segment into multiple human-readable speaker turns. Existing meeting and segment fields retain their meanings. Consumers must branch on `schema_version`; v1/v2 documents remain readable by clients that do not require Phase 3 fields.

Times are seconds from the start of the prepared meeting audio. A word's start and end are either both available or both null; confidence may independently be null when a backend cannot supply it. Null speaker assignment means the temporal evidence was absent or ambiguous, not that a hidden identity was inferred. Cluster `name` and cluster confidence remain null because Phase 3 does not implement speaker identification or a transcript confidence engine.

`raw/asr.json`, `raw/alignment.json`, `raw/diarization.json` and `raw/diarization.rttm` are independent immutable stage artifacts. Attribution provenance exists only in canonical v3 output and never mutates ASR/alignment evidence. If diarization is disabled or unavailable, Phase 2 segment structure and text remain intact, speakers stay empty/null, and the raw diarization status explains why.
