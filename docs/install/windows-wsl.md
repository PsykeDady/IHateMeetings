# Windows 11 with WSL2

Native Windows is not a v1 target. Use Ubuntu under WSL2:

```powershell
wsl --install -d Ubuntu-24.04
```

Inside WSL:

```bash
./install/wsl-ubuntu.sh
uv run ihm doctor
```

Files under `/mnt/c/Users/...` are supported, but keep virtual environments, caches, models and temporary processing files inside the Linux filesystem for performance:

```text
~/.cache/ihatemeetings/
~/ihm-work/
```

