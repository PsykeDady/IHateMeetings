# IHateMeetings

**You attend. We listen.**

IHateMeetings is a local-first meeting transcription project. The goal is a staged pipeline for media processing, speech recognition, alignment, diarization, speaker resolution, confidence analysis and auditable exports.

This repository is currently at **Phase 0: Bootstrap**. It provides the Python project, CLI entry points, platform detection, `ihm doctor`, installer skeletons, documentation and baseline tests. It does not yet perform transcription.

## Install for Development

```bash
uv sync --extra dev
uv run ihm --help
uv run ihm doctor
uv run pytest
```

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
ihm speakers list
ihm transcribe FILE
ihm FILE
```

`ihm transcribe FILE` validates the input and prints the selected Phase 0 plan, then exits with an explicit "not implemented" message.

## Roadmap

1. Phase 0: project bootstrap, CLI, doctor, installers, docs, CI.
2. Phase 1: FFmpeg preprocessing, faster-whisper ASR, canonical JSON, Markdown/TXT/SRT/VTT export.
3. Phase 2: word-level alignment.
4. Phase 3: diarization.
5. Phase 4: manual and anchor-based speaker resolution.
6. Phase 5: cache/resume, confidence engine and improved hardware profiles.

Core transcription must remain local-first. Network-dependent features must be explicit, and meeting audio must never be uploaded silently.

