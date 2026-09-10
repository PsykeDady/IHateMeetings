# Windows 11 with WSL2

Native Windows is not a v1 target. Use Ubuntu under WSL2:

```powershell
wsl --install -d Ubuntu-24.04
```

Inside WSL:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
./install/wsl-ubuntu.sh
uv run python --version
uv run ihm models download small
uv run ihm models download-alignment it
uv run ihm doctor
uv run ihm /mnt/c/Users/NAME/meeting.mp3 --language it --align
```

Files under `/mnt/c/Users/...` are supported, but keep virtual environments, caches, models and temporary processing files inside the Linux filesystem for performance:

```text
~/.cache/ihatemeetings/
~/ihm-work/
```

The installer provisions CPython 3.13 with `uv` and does not alter Ubuntu's system Python. Run the repository and its `.venv` from the Linux filesystem. The explicit `small` model download uses about 490 MB and the Italian alignment model about 1.3 GB; their caches remain under the WSL Linux home directory. Neither model is downloaded by the installer.

To remove project-local generated files inside WSL:

```bash
./install/uninstall.sh --yes
```

This does not uninstall Ubuntu, WSL, FFmpeg, Python, Git or `uv`.
