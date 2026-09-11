# IHateMeetings

**You attend. We listen.**

IHateMeetings is a local-first meeting transcription project. The goal is a staged pipeline for media processing, speech recognition, alignment, diarization, speaker resolution, confidence analysis and auditable exports.

This repository is currently at **Phase 3: Speaker diarization**. It performs local media inspection, FFmpeg audio preparation, faster-whisper inference, optional CTC word alignment, optional pyannote Community-1 speaker diarization and canonical JSON/Markdown/TXT/SRT/VTT export. Speaker identification is deliberately not part of this phase: output uses anonymous clusters such as `SPEAKER_00`.

## Install for Development

IHateMeetings v1 uses CPython 3.13 managed by `uv`; the host's system Python is not changed or downgraded. Install `uv` first if needed (Arch: `sudo pacman -S uv`; other Linux/WSL: `curl -LsSf https://astral.sh/uv/install.sh | sh`), then:

```bash
uv python install 3.13
uv sync --python 3.13 --extra dev --extra alignment --extra diarization
uv run ihm --help
uv run ihm doctor
uv run ihm models download small
uv run ihm models download-alignment it
uv run ihm meeting.mp3 --language it --align
uv run pytest
```

Private/local recordings may be placed in the ignored `tests/private_audio/` directory. To run the real faster-whisper regression tests locally:

```bash
uv run ihm models download tiny
IHM_RUN_REAL_ASR=1 uv run pytest -m real_asr -v
```

Use `IHM_TEST_MODEL=small` (or another cached model) to compare a different model. Real-ASR tests are opt-in and never download weights themselves.

When private ground truth and both models are locally available, run the isolated ASR and alignment benchmarks with:

```bash
uv run env IHM_RUN_REAL_ASR=1 IHM_TEST_MODEL=small pytest -m real_asr -v -s
uv run env IHM_RUN_REAL_ALIGNMENT=1 IHM_TEST_MODEL=small pytest -m real_alignment -v -s
# Requires explicitly prepared Community-1 assets:
uv run env IHM_RUN_REAL_DIARIZATION=1 pytest -m real_diarization -v -s
```

These report WER/CER per fixture and verify ordered, bounded word timestamps. Private audio and generated outputs remain outside version control.

Model download is always explicit. The Phase 1 profiles are:

| Profile | Model | Approximate model storage |
| --- | --- | ---: |
| `fast` | `small` | 490 MB |
| `balanced` | `large-v3-turbo` | 1.6 GB |
| `accurate` | `large-v3` | 3.1 GB |

CPU-only operation uses INT8 and defaults to `fast`. A detected CTranslate2 CUDA runtime defaults to `balanced` and FP16. Override these choices with `--model`, `--device` and `--compute-type`. Models are stored under `~/.cache/ihatemeetings/models`; meeting media never leaves the machine.

Alignment requires the optional local runtime and a language model. `en` uses `facebook/wav2vec2-base-960h` (about 380 MB); `it` uses `jonatasgrosman/wav2vec2-large-xlsr-53-italian` (about 1.3 GB). Both are Apache-2.0. Download is always explicit:

```bash
uv sync --python 3.13 --extra alignment
uv run ihm models download-alignment it
uv run ihm meeting.mp3 --language it --align
```

With neither `--align` nor `--no-align`, alignment runs only when the runtime and detected-language model are already local. `--align` reports an unavailable backend/model clearly but still exports the Phase 1 transcript. `--no-align` disables it. Custom compatible local CTC model directories can be passed through `--alignment-model`.

Diarization uses `pyannote.audio==4.0.7` with `pyannote/speaker-diarization-community-1`. The package is MIT; Community-1 weights are CC-BY-4.0 and gated. Accept the model conditions on Hugging Face, create a read token, and make the approximately 34 MB model download explicit (Python/ML runtime dependencies require separate storage):

```bash
HF_TOKEN=hf_read_token uv run ihm models download-diarization
uv run ihm meeting.mp3 --language it --align --diarize
```

The token is read only from the environment and is not persisted by IHateMeetings. Normal inference forces Hugging Face offline mode and disables pyannote metrics; audio is passed to the local pipeline as an in-memory waveform. With neither `--diarize` nor `--no-diarize`, diarization runs only when both runtime and prepared local model are available. Speaker-count hints are optional: use one of `--num-speakers N` or `--min-speakers N --max-speakers N`.

## Language policy

IHateMeetings v1 officially supports exactly Italian (`it`) and English (`en`). Explicit selection accepts `--language it` and `--language en`; omitting the option lets faster-whisper detect the language and routes either supported result to its matching alignment model. Other languages may be recognized by faster-whisper but are unsupported and untested: automatic detection emits a warning, exports raw/canonical ASR text, and skips alignment with status `unsupported_language`. Explicit unsupported language codes are rejected.

Italian speech containing English technical vocabulary is a first-class input. ASR always uses transcription rather than translation and IHateMeetings does not rewrite or Italianize terms such as `deploy`, `commit`, `merge`, `timeout`, `backend`, `frontend`, `Lambda`, `API Gateway`, `OpenSearch`, `DynamoDB`, `STAG`, `DEV` and `PROD`. The ASR contract already accepts typed glossary prompt terms for the future `glossary.yaml` stage; Phase 3 does not parse glossaries or correct transcript text.

Output is written to `output/<input-stem>/`. Raw FFprobe, ASR, alignment and diarization records remain separate in `raw/media.json`, `raw/asr.json`, `raw/alignment.json`, `raw/diarization.json` and `raw/diarization.rttm`; final exporters consume `transcript.json` schema version 3.

## Uninstall / Cleanup

To remove project-local generated files:

```bash
./install/uninstall.sh --dry-run
./install/uninstall.sh --yes
```

To also remove IHateMeetings user cache/data directories:

```bash
./install/uninstall.sh --yes --user-data
```

The uninstall script intentionally does not remove shared system packages such as FFmpeg, Python, Git or `uv`.

The CLI entry points are:

```bash
ihm
ihatemeetings
```

## Current Commands

```bash
ihm --help
ihm doctor
ihm models list
ihm models download small
ihm models download-alignment it
ihm models download-diarization
ihm speakers list
ihm transcribe FILE
ihm FILE
```

Both transcription forms run the same Phase 3 pipeline:

```bash
uv run ihm meeting.mp3 --language it --profile fast --align --diarize
uv run ihm transcribe meeting.mp3 --language it --model small --align --diarize
```

`--language` may be omitted for automatic detection. Custom converted CTranslate2 model directories can be supplied to `--model`. Context, anchors, speaker identification and reasoning remain unavailable in Phase 3.

## Roadmap

1. Phase 0: complete — project bootstrap, CLI, doctor, installers, docs, CI.
2. Phase 1: complete — FFmpeg preprocessing, faster-whisper ASR, canonical JSON, Markdown/TXT/SRT/VTT export.
3. Phase 2: complete — optional local word-level CTC alignment and schema v2.
4. Phase 3: complete — optional local Community-1 diarization, cluster attribution and schema v3.
5. Phase 4: manual and anchor-based speaker resolution.
6. Phase 5: cache/resume, confidence engine and improved hardware profiles.

Core transcription must remain local-first. Network-dependent features must be explicit, and meeting audio must never be uploaded silently.
