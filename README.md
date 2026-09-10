# IHateMeetings

**You attend. We listen.**

IHateMeetings is a local-first meeting transcription project. The goal is a staged pipeline for media processing, speech recognition, alignment, diarization, speaker resolution, confidence analysis and auditable exports.

This repository is currently at **Phase 1: Basic transcription**. It performs local media inspection, FFmpeg audio preparation, faster-whisper inference and canonical JSON/Markdown/TXT/SRT/VTT export. Alignment, diarization and speaker identification are deliberately not part of this phase.

## Install for Development

Install `uv` first if needed (Arch: `sudo pacman -S uv`; other Linux/WSL: `curl -LsSf https://astral.sh/uv/install.sh | sh`), then:

```bash
uv sync --extra dev
uv run ihm --help
uv run ihm doctor
uv run ihm models download small
uv run ihm meeting.mp3 --language it
uv run pytest
```

The repository includes three short, distributable Italian WAV fixtures. Normal tests verify their integrity without downloading a model. To run the real faster-whisper regression tests locally:

```bash
uv run ihm models download tiny
IHM_RUN_REAL_ASR=1 uv run pytest -m real_asr -v
```

Use `IHM_TEST_MODEL=small` (or another cached model) to compare a different model. Real-ASR tests are opt-in and never download weights themselves.

Model download is always explicit. The Phase 1 profiles are:

| Profile | Model | Approximate model storage |
| --- | --- | ---: |
| `fast` | `small` | 490 MB |
| `balanced` | `large-v3-turbo` | 1.6 GB |
| `accurate` | `large-v3` | 3.1 GB |

CPU-only operation uses INT8 and defaults to `fast`. A detected CTranslate2 CUDA runtime defaults to `balanced` and FP16. Override these choices with `--model`, `--device` and `--compute-type`. Models are stored under `~/.cache/ihatemeetings/models`; meeting media never leaves the machine.

Output is written to `output/<input-stem>/`. Raw FFprobe and ASR records remain in `raw/media.json` and `raw/asr.json`; final exporters consume `transcript.json` schema version 1.

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
ihm speakers list
ihm transcribe FILE
ihm FILE
```

Both transcription forms run the same Phase 1 pipeline:

```bash
uv run ihm meeting.mp3 --language it --profile fast
uv run ihm transcribe meeting.mp3 --language it --model small
```

`--language` may be omitted for automatic detection. Custom converted CTranslate2 model directories can be supplied to `--model`. Context, anchors, alignment, diarization and reasoning remain unavailable in Phase 1.

## Roadmap

1. Phase 0: complete — project bootstrap, CLI, doctor, installers, docs, CI.
2. Phase 1: complete — FFmpeg preprocessing, faster-whisper ASR, canonical JSON, Markdown/TXT/SRT/VTT export.
3. Phase 2: word-level alignment.
4. Phase 3: diarization.
5. Phase 4: manual and anchor-based speaker resolution.
6. Phase 5: cache/resume, confidence engine and improved hardware profiles.

Core transcription must remain local-first. Network-dependent features must be explicit, and meeting audio must never be uploaded silently.
