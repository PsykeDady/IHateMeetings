# Arch Linux

Install system dependencies:

```bash
./install/arch.sh
```

Then validate:

```bash
uv run ihm doctor
```

The script uses official repositories and installs only basic system tools such as FFmpeg, Python and Git. Python dependencies are managed by `uv` inside the project environment.

