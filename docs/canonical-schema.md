# Canonical transcript schema v5

`transcript.json` is the canonical Phase 4.1 representation. Schema v5 adds stable review
identifiers and an auditable human-review layer while retaining the complete Phase 4 machine
state.

Every original segment has an ID allocated once in transcript order (`SEG_000001`,
`SEG_000002`, ...). Every segment whose Phase 3 cluster attribution was null also receives an
independent provenance ID (`UNK_000001`, `UNK_000002`, ...). Both sequences are monotonic.
Neither deletion, merging, assignment nor re-export renumbers or recycles an ID.

A segment record has this shape (abridged):

```json
{
  "id": "SEG_000019",
  "unknown_id": "UNK_000004",
  "start": 36.12,
  "end": 36.71,
  "text": "cosa.",
  "words": [],
  "speaker": null,
  "confidence": null,
  "original": {
    "start": 36.12,
    "end": 36.71,
    "text": "cosa.",
    "words": [],
    "speaker": null,
    "confidence": null
  },
  "review": {
    "status": "active",
    "accepted": false,
    "speaker_assignment": {
      "kind": "identity",
      "identity": {"id": "sonia-greco", "display_name": "Sonia Greco"},
      "cluster": null,
      "method": "explicit_user_input"
    },
    "merged_segment_ids": [],
    "merged_into": null
  },
  "effective": {
    "status": "active",
    "start": 36.12,
    "end": 36.71,
    "text": "cosa.",
    "words": [],
    "speaker": {
      "label": "Sonia Greco",
      "original_cluster": null,
      "target_cluster": null,
      "identity": {"id": "sonia-greco", "display_name": "Sonia Greco"},
      "layer": "segment_manual_override",
      "method": "explicit_user_input"
    },
    "confidence": null,
    "source_segment_ids": ["SEG_000019"]
  }
}
```

The duplicated top-level `start`, `end`, `text`, `words`, `speaker` and `confidence` fields are
the original Phase 4 values retained for straightforward v4-era consumers. `original` labels
that contract explicitly. `effective` is derived from the original data plus review state; it
is not new ML evidence.

The root `review.cluster_assignments` stores manual identities for original diarization
clusters. Effective speaker precedence is:

1. segment-level manual assignment;
2. cluster-level manual identity;
3. Phase 4 resolver identity;
4. anonymous diarization cluster;
5. Phase 3 `UNKNOWN [?]`.

All lower-precedence evidence remains present. In particular, resolving an `UNK_*` leaves its
original speaker null and preserves the UNKNOWN ID.

Deletion sets `review.status` to `deleted`; the original record remains in canonical JSON and
review history, while human-readable exports omit it. Merging requires adjacent active
segments. The earlier ID survives, its effective timestamps span all source segments, text and
words retain source order, and the later record becomes `merged` with `merged_into` pointing to
the survivor. Different effective speakers require an explicit merge assignment. Later IDs are
never renumbered.

`review/revisions.json` schema v1 contains ordered `REV_000001` operations with operation type,
targets, before state, after/effective state, method and UTC timestamp. No operating-system user
identity is inferred. It is intentionally sufficient for a future undo implementation.

Schema v4 is migrated conservatively on the first saved review: original order becomes the
stable `SEG_*` order, original null-speaker occurrences receive `UNK_*`, Phase 4 evidence
segment references are remapped, and a `schema_migration` revision records the old-to-new ID
map. Read-only list/show commands do not persist migration. Other historical schema versions
are rejected rather than silently reinterpreted.

`raw/asr.json`, `raw/alignment.json`, `raw/diarization.json`, `raw/diarization.rttm` and
`debug/speaker_mapping.json` remain independent and immutable. Human review never rewrites
them.
