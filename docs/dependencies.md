# Phase 1 dependency decision

Phase 1 pins `faster-whisper==1.2.1`, the maintained upstream implementation by SYSTRAN. It uses CTranslate2 and supports CPU INT8 as well as CUDA compute modes. The project and listed converted model repositories use the MIT license. The turbo model selected by faster-whisper upstream is now hosted under the `dropbox-dash` namespace after a repository redirect.

Upstream references:

- https://github.com/SYSTRAN/faster-whisper
- https://pypi.org/project/faster-whisper/1.2.1/
- https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE
- https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/utils.py
- https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo

The package supports Python 3.9+, while IHateMeetings retains its stricter Python 3.11+ baseline. CPU inference does not require PyTorch or a GPU. GPU execution follows the CUDA and cuDNN requirements documented by the installed CTranslate2/faster-whisper release and should be confirmed with `ihm doctor` on each machine.

Model access uses public Hugging Face repositories and requires Internet only during an explicit `ihm models download` command. Once cached, transcription resolves models with offline-only lookup. No model license or access token gate is currently required for the listed Phase 1 models.
