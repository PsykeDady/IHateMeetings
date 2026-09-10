# Privacy

Meeting recordings may contain confidential information. IHateMeetings is local-first by default:

- no telemetry containing transcript or audio content;
- no automatic cloud uploads;
- no bundled model weights;
- explicit documentation for cache, model and output locations;
- local runtime checks through `ihm doctor`.

Phase 2 sends no meeting content over the network. FFmpeg, FFprobe, ASR and alignment run locally. The only network operations are the user-initiated `ihm models download MODEL` and `ihm models download-alignment LANGUAGE` commands; they download model files and do not upload meeting data.

The project Python runtime is installed by `uv` in user-owned storage. Installers do not replace or downgrade the operating system's Python.

Generated transcripts are stored under `output/` with user-only file permissions. ASR models are stored under `~/.cache/ihatemeetings/models` and alignment models under `~/.cache/ihatemeetings/alignment`. Private regression recordings belong in the ignored `tests/private_audio/` directory. Use `./install/uninstall.sh --yes` for project output and `./install/uninstall.sh --yes --user-data` to include model caches.
