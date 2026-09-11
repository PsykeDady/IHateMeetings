# Dependency decisions

Phase 1 pins `faster-whisper==1.2.1`, the maintained upstream implementation by SYSTRAN. It uses CTranslate2 and supports CPU INT8 as well as CUDA compute modes. The project and listed converted model repositories use the MIT license. The turbo model selected by faster-whisper upstream is now hosted under the `dropbox-dash` namespace after a repository redirect.

Upstream references:

- https://github.com/SYSTRAN/faster-whisper
- https://pypi.org/project/faster-whisper/1.2.1/
- https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE
- https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/utils.py
- https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo

The package supports Python 3.9+, while IHateMeetings v1 pins its application runtime to CPython 3.13 through `uv` and `.python-version`. CPU inference does not require PyTorch or a GPU. GPU execution follows the CUDA and cuDNN requirements documented by the installed CTranslate2/faster-whisper release and should be confirmed with `ihm doctor` on each machine.

Model access uses public Hugging Face repositories and requires Internet only during an explicit `ihm models download` command. Once cached, transcription resolves models with offline-only lookup. No model license or access token gate is currently required for the listed Phase 1 models.

## Phase 2 alignment

WhisperX was evaluated but is not installed. Current stable WhisperX 3.8.6 accepts Python 3.13 (`>=3.10,<3.14`), but its dependency graph includes pyannote-audio and TorchCodec, which would pull diarization/media components outside this consolidation pass. WhisperX itself is BSD-2-Clause, while its default Italian `VOXPOPULI_ASR_BASE_10K_IT` bundle is CC-BY-NC 4.0. It remains a possible future `AlignmentBackend`, to be evaluated separately; the existing CTC backend remains the Phase 2 implementation.

IHateMeetings instead implements the same class of CTC forced alignment behind its own `AlignmentBackend`, using:

- `torch==2.14.0` from the official CPU wheel index;
- `transformers==5.16.1`;
- English: `facebook/wav2vec2-base-960h`, Apache-2.0, about 380 MB;
- Italian: `jonatasgrosman/wav2vec2-large-xlsr-53-italian`, Apache-2.0, about 1.3 GB.

The runtime dependencies are an optional `alignment` extra. PyTorch 2.14, Transformers 5.16.1 and faster-whisper 1.2.1 are compatible with CPython 3.13. CPU is mandatory and is the default alignment device unless a working CUDA PyTorch runtime is present. Only one model weight format is downloaded per configured model. The Italian repository advertises an optional LM processor, but IHateMeetings loads its feature extractor and tokenizer separately and does not require `pyctcdecode` for forced alignment.

Alignment model acquisition is explicit. `ihm models download-alignment LANGUAGE` is the only code path that permits network access; inference uses Hugging Face local-only resolution. No meeting media or transcript is sent to Hugging Face.

Upstream references:

- https://github.com/m-bain/whisperX/blob/main/pyproject.toml
- https://github.com/m-bain/whisperX/blob/main/LICENSE
- https://github.com/m-bain/whisperX/blob/main/whisperx/alignment.py
- https://docs.pytorch.org/audio/stable/generated/torchaudio.pipelines.VOXPOPULI_ASR_BASE_10K_IT.html
- https://huggingface.co/facebook/wav2vec2-base-960h
- https://huggingface.co/jonatasgrosman/wav2vec2-large-xlsr-53-italian
- https://pypi.org/project/torch/
- https://pypi.org/project/transformers/

## Phase 3 diarization

Phase 3 pins `pyannote-audio==4.0.7` behind `DiarizationBackend`, with Community-1 revision `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee` as the first model. pyannote.audio is MIT licensed; `pyannote/speaker-diarization-community-1` weights are CC-BY-4.0. The model is gated: the user must accept its Hugging Face conditions, share the requested contact information, and provide a read token for explicit acquisition. IHateMeetings neither accepts terms nor authenticates silently.

The resolved runtime uses `torch==2.14.0+cpu`, `torchaudio==2.11.0+cpu` and `torchcodec==0.16.0+cpu` on CPython 3.13.15. A pre-lock binary test imported this exact set successfully. The ordinary PyPI torchaudio 2.11 wheel was rejected because it linked `libcudart.so.13` on this CPU host; `uv` therefore sources torch, torchaudio and TorchCodec from the official PyTorch CPU index. TorchAudio 2.11's stable ABI supports PyTorch 2.11 and later, and TorchCodec 0.16 documents Python 3.10–3.14 with PyTorch 2.11 or later.

Community-1 runs locally on CPU by default and supports exact/minimum/maximum speaker-count hints. Upstream returns both regular and exclusive diarization; IHateMeetings consumes regular diarization so overlapping turns remain representable. Community-1 can be cloned/downloaded and loaded from local disk for offline use. Normal IHateMeetings inference additionally sets `HF_HUB_OFFLINE=1` and `PYANNOTE_METRICS_ENABLED=0`, and supplies a local waveform rather than a remote URI. pyannoteAI cloud services are not integrated.

`HF_TOKEN=... ihm models download-diarization` explicitly downloads and prepares Community-1. The token is not persisted by IHateMeetings. The current Hugging Face repository reports 33,682,422 bytes (about 34 MB) of model files; Python/ML runtime dependencies use separate storage and actual cache use can vary with upstream revisions.

Upstream references:

- https://pypi.org/project/pyannote-audio/4.0.7/
- https://github.com/pyannote/pyannote-audio/blob/main/pyproject.toml
- https://github.com/pyannote/pyannote-audio/blob/main/LICENSE
- https://huggingface.co/pyannote/speaker-diarization-community-1
- https://docs.pytorch.org/audio/main/installation.html
- https://github.com/meta-pytorch/torchcodec#installing-torchcodec
