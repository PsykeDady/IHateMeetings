# Ubuntu

Install system dependencies:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
./install/ubuntu.sh
```

Start a new shell after installing `uv` if the current shell cannot find the command. Equivalent project setup after FFmpeg, Git and `uv` are available is:

```bash
sudo apt update
sudo apt install ffmpeg git
uv python install 3.13
uv sync --python 3.13 --extra dev --extra alignment --extra diarization
```

Then validate:

```bash
uv run ihm models download small
uv run ihm models download-alignment it
HF_TOKEN=hf_read_token uv run ihm models download-diarization
uv run ihm doctor
uv run ihm meeting.mp3 --language it --align --diarize
```

Use a current compatible Ubuntu LTS. Python 3.13 and project dependencies remain managed by `uv`; Ubuntu's system Python is not changed. The explicit ASR model requires about 490 MB and the Italian alignment model about 1.3 GB. Community-1 must first be accepted on Hugging Face; it is CC-BY-4.0 and currently about 34 MB, excluding runtime dependencies. No model is downloaded by the installer.

To remove project-local generated files:

```bash
./install/uninstall.sh --yes
```

This does not remove system packages installed with `apt`.
