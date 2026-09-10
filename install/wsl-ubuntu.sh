#!/usr/bin/env bash
set -euo pipefail

if ! grep -qiE "microsoft|wsl" /proc/version 2>/dev/null; then
  echo "This script is intended for Ubuntu running under WSL2." >&2
fi

"$(dirname "$0")/ubuntu.sh"

