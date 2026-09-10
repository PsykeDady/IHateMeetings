#!/usr/bin/env bash
set -euo pipefail

if ! command -v dnf >/dev/null 2>&1; then
  echo "This installer expects Fedora with dnf." >&2
  exit 1
fi

sudo dnf install -y ffmpeg python3 git

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "FFmpeg is still unavailable. Check Fedora multimedia repository configuration." >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Install uv from https://docs.astral.sh/uv/ before syncing Python dependencies." >&2
  exit 1
fi

uv sync --extra dev

echo "Phase 1 runtime dependencies are ready."
echo "Download a model explicitly: uv run ihm models download small"
echo "Then validate with: uv run ihm doctor"
