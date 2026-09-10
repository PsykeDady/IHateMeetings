#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSUME_YES=0
INCLUDE_USER_DATA=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage:
  ./install/uninstall.sh [--yes] [--user-data] [--all] [--dry-run]

Removes IHateMeetings project-local generated files.

Options:
  --yes        Required to actually delete files.
  --user-data  Also remove IHateMeetings user cache/data directories.
  --all        Same as --user-data for the current Phase 0 footprint.
  --dry-run    Print what would be removed without deleting anything.
  --help       Show this help.

This script does not uninstall shared system packages such as FFmpeg, Python,
Git or uv. Remove those with your operating system package manager only if you
know they are not used by other software.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes)
      ASSUME_YES=1
      ;;
    --user-data|--all)
      INCLUDE_USER_DATA=1
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

targets=(
  "$PROJECT_ROOT/.venv"
  "$PROJECT_ROOT/.pytest_cache"
  "$PROJECT_ROOT/.ruff_cache"
  "$PROJECT_ROOT/.mypy_cache"
  "$PROJECT_ROOT/.ihm"
  "$PROJECT_ROOT/output"
)

if [[ "$INCLUDE_USER_DATA" -eq 1 ]]; then
  targets+=(
    "${XDG_CACHE_HOME:-$HOME/.cache}/ihatemeetings"
    "${XDG_DATA_HOME:-$HOME/.local/share}/ihatemeetings"
  )
fi

echo "IHateMeetings uninstall"
echo
echo "Project root: $PROJECT_ROOT"
echo
echo "Targets:"
for target in "${targets[@]}"; do
  echo "  $target"
done
echo "  Python __pycache__ directories under project root"
echo

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry run only. No files were removed."
  exit 0
fi

if [[ "$ASSUME_YES" -ne 1 ]]; then
  echo "No files removed. Re-run with --yes to confirm deletion."
  exit 1
fi

for target in "${targets[@]}"; do
  if [[ -e "$target" ]]; then
    rm -rf -- "$target"
    echo "Removed: $target"
  fi
done

find "$PROJECT_ROOT" -type d -name __pycache__ -prune -exec rm -rf {} +

echo "Uninstall cleanup complete."

