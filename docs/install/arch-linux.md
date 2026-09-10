# Arch Linux

Install system dependencies:

```bash
./install/arch.sh
```

The script installs `uv` from the official Arch `extra` repository. Equivalent manual setup:

```bash
sudo pacman -S --needed ffmpeg python git uv
uv sync --extra dev
```

Then validate:

```bash
uv run ihm models download small
uv run ihm doctor
uv run ihm meeting.mp3 --language it
```

The script uses official repositories for FFmpeg, Python and Git, then runs `uv sync --extra dev`. The explicit model command downloads about 490 MB into `~/.cache/ihatemeetings/models`. Use `tiny` (about 80 MB) with `--model tiny` for a smaller smoke-test model.

To remove project-local generated files:

```bash
./install/uninstall.sh --yes
```

This does not remove system packages installed with `pacman`.
