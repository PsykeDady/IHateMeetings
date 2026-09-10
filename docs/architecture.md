# Architecture

IHateMeetings is designed as a staged local-first pipeline:

1. Media inspection.
2. Audio extraction and normalization.
3. Voice activity detection.
4. Speech recognition.
5. Word alignment.
6. Speaker diarization.
7. Speaker resolution.
8. Confidence analysis.
9. Optional reasoning over uncertain regions.
10. Transcript reconstruction and export.

Phase 0 implements only the bootstrap surface: package structure, CLI, configuration precedence hooks, platform detection and doctor diagnostics. Expensive ML integrations are intentionally deferred until the foundation is tested.

External ML libraries must be wrapped behind internal interfaces before use, so third-party response shapes do not leak through the application.

