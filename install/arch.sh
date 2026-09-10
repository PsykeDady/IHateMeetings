#!/usr/bin/env bash
set -euo pipefail

if ! command -v pacman >/dev/null 2>&1; then
  echo "This installer expects Arch Linux with pacman." >&2
  exit 1
fi

sudo pacman -S --needed ffmpeg python git

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Install uv from https://docs.astral.sh/uv/ before syncing Python dependencies." >&2
fi

echo "System dependencies checked. Run: uv sync --extra dev && uv run ihm doctor"

