# Privacy

Meeting recordings may contain confidential information. IHateMeetings is local-first by default:

- no telemetry containing transcript or audio content;
- no automatic cloud uploads;
- no bundled model weights;
- explicit documentation for cache, model and output locations;
- local runtime checks through `ihm doctor`.

Phase 3 sends no meeting content over the network. FFmpeg, FFprobe, ASR, alignment and Community-1 inference run locally. Network operations are limited to user-initiated model acquisition commands; they download model files and do not upload meeting data. Normal diarization sets Hugging Face offline mode, disables pyannote metrics, and passes audio directly as an in-memory waveform. IHateMeetings does not integrate pyannoteAI cloud APIs.

The project Python runtime is installed by `uv` in user-owned storage. Installers do not replace or downgrade the operating system's Python.

Generated transcripts are stored under `output/` with user-only file permissions. ASR, alignment and diarization caches live below `~/.cache/ihatemeetings/`. Hugging Face tokens are read from `HF_TOKEN` only for explicit gated acquisition and are never written into repository files, transcripts, logs or metadata. Private regression recordings belong in the ignored `tests/private_audio/` directory. Use `./install/uninstall.sh --yes` for project output and `./install/uninstall.sh --yes --user-data` to include model caches.
