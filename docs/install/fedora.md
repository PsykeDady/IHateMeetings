# Fedora

Install system dependencies:

```bash
./install/fedora.sh
```

Then validate:

```bash
uv run ihm doctor
```

If FFmpeg is unavailable or lacks expected codecs, check Fedora multimedia repository configuration and rerun `ihm doctor`.

