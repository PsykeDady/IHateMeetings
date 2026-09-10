#!/usr/bin/env bash
set -euo pipefail

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This installer expects Ubuntu or another apt-based distribution." >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y ffmpeg python3 python3-venv git

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Install uv from https://docs.astral.sh/uv/ before syncing Python dependencies." >&2
fi

echo "System dependencies checked. Run: uv sync --extra dev && uv run ihm doctor"

