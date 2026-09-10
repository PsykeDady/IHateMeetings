# Fedora

Install system dependencies:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
./install/fedora.sh
```

Start a new shell after installing `uv` if the current shell cannot find the command. Equivalent project setup after the Fedora packages and `uv` are available is `uv sync --extra dev`.

Then validate:

```bash
uv run ihm models download small
uv run ihm doctor
uv run ihm meeting.mp3 --language it
```

The script runs `uv sync --extra dev`. The explicit model command downloads about 490 MB into `~/.cache/ihatemeetings/models`. If FFmpeg is unavailable or lacks expected codecs, check Fedora multimedia repository configuration and rerun `ihm doctor`.

To remove project-local generated files:

```bash
./install/uninstall.sh --yes
```

This does not remove system packages installed with `dnf`.
