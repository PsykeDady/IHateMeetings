# Canonical transcript schema v4

`transcript.json` is the canonical final Phase 4 representation. All text and subtitle exporters consume the same typed `Transcript` object.

```json
{
  "schema_version": 4,
  "meeting": {
    "source": "meeting.mp3",
    "duration": 42.5,
    "language": "it",
    "language_probability": 0.98
  },
  "speakers": [
    {
      "cluster": "SPEAKER_00",
      "identity": {
        "id": "partecipante-a",
        "display_name": "Partecipante A"
      },
      "resolution": {
        "status": "resolved",
        "confidence": 1.0,
        "resolver": "conservative-v1",
        "evidence": [
          {
            "type": "manual_mapping",
            "value": "SPEAKER_00",
            "confidence": 1.0,
            "method": "explicit_user_input",
            "segment_id": null
          }
        ],
        "candidates": [],
        "warnings": []
      }
    }
  ],
  "segments": [
    {
      "id": "segment-000001",
      "start": 0.5,
      "end": 3.2,
      "text": "Testo della trascrizione.",
      "speaker": {
        "cluster": "SPEAKER_00",
        "identity": {
          "id": "partecipante-a",
          "display_name": "Partecipante A"
        },
        "resolution": {
          "status": "resolved",
          "confidence": 1.0,
          "resolver": "conservative-v1",
          "evidence": [
            {
              "type": "manual_mapping",
              "value": "SPEAKER_00",
              "confidence": 1.0,
              "method": "explicit_user_input",
              "segment_id": null
            }
          ],
          "candidates": [],
          "warnings": []
        }
      },
      "confidence": null,
      "words": []
    }
  ]
}
```

Schema v4 replaces the flat Phase 3 speaker summary with an explicit identity-resolution object. The immutable anonymous `cluster` is always retained. `identity` is populated only for `status: resolved`; otherwise it is null. Resolution status is one of `resolved`, `unresolved`, `ambiguous` or `conflicting`. Candidates, evidence, confidence, resolver and warnings explain the decision without changing raw inference.

Manual evidence has confidence `1.0` because it represents authoritative user input, not model certainty. Exact anchor confidence is `0.99`; fuzzy confidence is the deterministic normalized string-similarity score. Candidate confidence from multiple anchors is `1 - product(1 - evidence confidence)`, capped at `0.999`. These are resolution-policy scores, not biometric probabilities.

An anonymous `SPEAKER_02` has a reliable Phase 3 cluster but no selected real identity. A null segment `speaker` is different: Phase 3 could not assign that speech to any cluster, so exporters show `UNKNOWN [?]`. Phase 4 never fills that null value from neighboring text.

`raw/asr.json`, `raw/alignment.json`, `raw/diarization.json` and `raw/diarization.rttm` remain independent immutable stage artifacts. Full Phase 4 decisions are duplicated in `debug/speaker_mapping.json` for audit. Consumers must branch on `schema_version`; schema v3 artifacts remain valid historical outputs.
