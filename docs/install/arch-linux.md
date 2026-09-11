# Arch Linux

Install system dependencies:

```bash
./install/arch.sh
```

The script installs `uv` from the official Arch `extra` repository. Equivalent manual setup:

```bash
sudo pacman -S --needed ffmpeg git uv
uv python install 3.13
uv sync --python 3.13 --extra dev --extra alignment --extra diarization
```

Then validate:

```bash
uv run ihm models download small
uv run ihm models download-alignment it
# After accepting the Community-1 Hugging Face conditions:
HF_TOKEN=hf_read_token uv run ihm models download-diarization
uv run ihm doctor
uv run ihm meeting.mp3 --language it --align --diarize
```

The script uses official repositories for FFmpeg, Git and `uv`. It installs CPython 3.13 through `uv` and does not alter Arch's system Python. The explicit ASR model command downloads about 490 MB; the Italian alignment model requires about 1.3 GB. Community-1 is gated, CC-BY-4.0 and currently about 34 MB, excluding runtime dependencies. Use `tiny` (about 80 MB) with `--model tiny` for a smaller smoke test. Models are never downloaded by the installer.

To remove project-local generated files:

```bash
./install/uninstall.sh --yes
```

This does not remove system packages installed with `pacman`.
