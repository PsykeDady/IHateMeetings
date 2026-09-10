# Privacy

Meeting recordings may contain confidential information. IHateMeetings is local-first by default:

- no telemetry containing transcript or audio content;
- no automatic cloud uploads;
- no bundled model weights;
- explicit documentation for cache, model and output locations;
- local runtime checks through `ihm doctor`.

Phase 1 sends no meeting content over the network. FFmpeg, FFprobe and inference run locally. The only network operation is the user-initiated `ihm models download MODEL`, which downloads model files and does not upload meeting data.

Generated transcripts are stored under `output/` with user-only file permissions. Models are stored under `~/.cache/ihatemeetings/models`. Use `./install/uninstall.sh --yes` for project output and `./install/uninstall.sh --yes --user-data` to include the model cache.
