# Italian audio fixtures

These three short PCM WAV recordings were supplied explicitly for use as distributable IHateMeetings test fixtures. They contain synthetic test phrases and no private meeting material.

`manifest.json` records the expected text, stable file hash, duration and a conservative set of words recognized by the Phase 1 `tiny` baseline. Exact transcript equality is intentionally not required because ASR output may vary by model and runtime.

The normal suite validates fixture integrity without loading an ML model. Real local inference is opt-in:

```bash
uv run ihm models download tiny
IHM_RUN_REAL_ASR=1 uv run pytest -m real_asr -v
```

Set `IHM_TEST_MODEL` to test another explicitly cached model.
