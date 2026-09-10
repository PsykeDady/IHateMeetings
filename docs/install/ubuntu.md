# Ubuntu

Install system dependencies:

```bash
./install/ubuntu.sh
```

Then validate:

```bash
uv run ihm doctor
```

Use a current compatible Ubuntu LTS. Python dependencies are managed by `uv`, not by global `pip`.

