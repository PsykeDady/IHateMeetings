# Private Italian audio fixture setup

Private audio is intentionally not stored in this directory or committed to the repository.

For local validation, place recordings and `manifest.json` in `tests/private_audio/`. That directory is ignored by Git. The manifest records expected text, stable file hashes, duration and conservative Phase 1 keywords. Exact transcript equality is intentionally not required because ASR output may vary by model and runtime.

The normal suite validates fixture integrity without loading an ML model. Real local inference is opt-in:

```bash
uv run ihm models download tiny
IHM_RUN_REAL_ASR=1 uv run pytest -m real_asr -v
```

Set `IHM_TEST_MODEL` to test another explicitly cached model.

Ground-truth text in the private manifest enables normalized WER and CER reporting:

```bash
uv run env IHM_RUN_REAL_ASR=1 IHM_TEST_MODEL=small pytest -m real_asr -v -s
uv run env IHM_RUN_REAL_ALIGNMENT=1 IHM_TEST_MODEL=small pytest -m real_alignment -v -s
uv run env IHM_RUN_REAL_DIARIZATION=1 pytest -m real_diarization -v -s
```

Normalization uses Unicode NFKC, case folding, punctuation removal and whitespace collapse. WER operates on normalized words; CER operates on the normalized string including spaces. Alignment tests also prove that canonical text equals immutable raw ASR text.
