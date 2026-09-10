# Canonical transcript schema v2

`transcript.json` is the canonical final Phase 2 representation. All text and subtitle exporters consume the same typed `Transcript` object.

```json
{
  "schema_version": 2,
  "meeting": {
    "source": "meeting.mp3",
    "duration": 42.5,
    "language": "it",
    "language_probability": 0.98
  },
  "speakers": [],
  "segments": [
    {
      "id": "segment-000001",
      "start": 0.5,
      "end": 3.2,
      "text": "Buongiorno a tutti.",
      "speaker": null,
      "confidence": null,
      "words": [
        {
          "text": "Buongiorno",
          "start": 0.52,
          "end": 1.18,
          "confidence": 0.91
        },
        {
          "text": "a",
          "start": null,
          "end": null,
          "confidence": null
        }
      ]
    }
  ]
}
```

Schema v2 is additive relative to v1: every segment gains a `words` array, while existing meeting and segment fields retain their meaning. Consumers should branch on `schema_version`; v1 documents remain readable by clients that do not require words.

Times are seconds from the start of the prepared meeting audio. A word's start and end are either both available or both null; confidence may independently be null when a backend cannot supply it. Null timing means that the word could not be aligned, not that its position was estimated. Segment `speaker` and `confidence` remain null because Phase 2 does not implement diarization or a transcript confidence engine. Backend evidence stays immutable in `raw/asr.json`; alignment evidence is stored separately in `raw/alignment.json`.
