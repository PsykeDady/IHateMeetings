# Canonical transcript schema v1

`transcript.json` is the canonical final Phase 1 representation. All text and subtitle exporters consume the same typed `Transcript` object.

```json
{
  "schema_version": 1,
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
      "confidence": null
    }
  ]
}
```

Times are seconds from the start of the prepared meeting audio. `speaker` and `confidence` are explicitly null because Phase 1 does not implement diarization or a confidence engine. Backend evidence such as average log probability and no-speech probability stays in `raw/asr.json` and is not misrepresented as canonical confidence.
