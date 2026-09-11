# Privacy

Meeting recordings may contain confidential information. IHateMeetings is local-first by default:

- no telemetry containing transcript or audio content;
- no automatic cloud uploads;
- no bundled model weights;
- explicit documentation for cache, model and output locations;
- local runtime checks through `ihm doctor`.

Phase 4 sends no meeting or identity content over the network. FFmpeg, FFprobe, ASR, alignment, Community-1 inference and textual speaker resolution run locally. Network operations are limited to user-initiated model acquisition commands; they download model files and do not upload meeting data. Normal diarization sets Hugging Face offline mode, disables pyannote metrics, and passes audio directly as an in-memory waveform. IHateMeetings does not integrate pyannoteAI cloud APIs.

Participant names and cluster-to-identity mappings are sensitive meeting data. Anchor and context files stay local and are never logged wholesale or uploaded. No telemetry may contain audio, transcript content, participant names, speaker embeddings or voiceprints.

Voice reference samples and embeddings are biometric-like sensitive data. Phase 4 defines only a future `VoiceEmbeddingBackend` boundary and the local storage location `~/.local/share/ihatemeetings/speakers/`; it does not enroll, extract or compare voiceprints. Future enrollment must be explicit, user-confirmed and removable. The storage helper creates its directory with mode `0700`, and meeting audio must never become a permanent profile automatically.

The project Python runtime is installed by `uv` in user-owned storage. Installers do not replace or downgrade the operating system's Python.

Generated transcripts are stored under the ignored `output/` directory with user-only file permissions. ASR, alignment and diarization caches live below `~/.cache/ihatemeetings/`. Hugging Face tokens are read from `HF_TOKEN` only for explicit gated acquisition and are never written into repository files, transcripts, logs or metadata. The recordings currently under the historically named `tests/private_audio/` path are explicitly authorized test fixtures; confidential recordings must stay outside the repository. Use `./install/uninstall.sh --yes` for project output and `./install/uninstall.sh --yes --user-data` to include model caches.
