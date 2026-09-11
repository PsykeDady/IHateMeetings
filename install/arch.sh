#!/usr/bin/env bash
set -euo pipefail

if ! command -v pacman >/dev/null 2>&1; then
  echo "This installer expects Arch Linux with pacman." >&2
  exit 1
fi

sudo pacman -S --needed ffmpeg git uv

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Install uv from https://docs.astral.sh/uv/ before syncing Python dependencies." >&2
  exit 1
fi

uv python install 3.13
uv sync --python 3.13 --extra dev --extra alignment --extra diarization

echo "Phase 3 runtime dependencies are ready."
echo "Download a model explicitly: uv run ihm models download small"
echo "Download an alignment model explicitly: uv run ihm models download-alignment it"
echo "Optional gated diarization setup: HF_TOKEN=... uv run ihm models download-diarization"
echo "Then validate with: uv run ihm doctor"
