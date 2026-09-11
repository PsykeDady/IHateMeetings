# Italian audio fixture setup

The three recordings currently stored in `tests/private_audio/` are explicitly authorized test fixtures and may be committed. Despite the historical directory name, they are not private meeting recordings.

Do not place confidential meeting recordings in that directory or anywhere else inside the repository. Keep additional private recordings outside the repository and pass their absolute path to local commands. The fixture manifest records expected text, stable file hashes, duration and conservative Phase 1 keywords. Exact transcript equality is intentionally not required because ASR output may vary by model and runtime.

The normal suite validates the authorized fixture integrity without loading an ML model. Real inference remains opt-in:

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
