# Fedora

Install system dependencies:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
./install/fedora.sh
```

Start a new shell after installing `uv` if the current shell cannot find the command. Equivalent project setup after FFmpeg, Git and `uv` are available is:

```bash
sudo dnf install ffmpeg git
uv python install 3.13
uv sync --python 3.13 --extra dev --extra alignment
```

Then validate:

```bash
uv run ihm models download small
uv run ihm models download-alignment it
uv run ihm doctor
uv run ihm meeting.mp3 --language it --align
```

Python 3.13 is managed by `uv`; Fedora's system Python is not changed. The explicit ASR model requires about 490 MB and the Italian alignment model about 1.3 GB. Neither model is downloaded by the installer. If FFmpeg is unavailable or lacks expected codecs, check Fedora multimedia repository configuration and rerun `ihm doctor`.

To remove project-local generated files:

```bash
./install/uninstall.sh --yes
```

This does not remove system packages installed with `dnf`.
