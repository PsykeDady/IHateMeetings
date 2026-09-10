# IHateMeetings

> **You attend. We listen.**

Local-first intelligent meeting transcription.

Repository name:

```
ihatemeetings
```

Primary CLI:

```
ihm
```

Long CLI alias:

```
ihatemeetings
```

---

# 1. Mission

Build a reliable, local-first application that converts meeting recordings into structured, speaker-aware, auditable transcripts.

IHateMeetings is NOT a thin wrapper around Whisper.

The application must combine specialized tools for:

* media processing;
* voice activity detection;
* speech recognition;
* word-level alignment;
* speaker diarization;
* speaker identification;
* confidence analysis;
* contextual correction;
* optional video/OCR intelligence;
* transcript reconstruction;
* structured export;
* optional meeting understanding.

The fundamental architectural rule is:

> **Use specialized models for perception. Use LLMs for reasoning.**

Do not send an entire recording to an LLM simply because an LLM is available.

Prefer:

```
FFmpeg            → media processing
VAD               → speech detection
faster-whisper    → speech recognition
WhisperX          → word alignment
pyannote          → speaker diarization
voice embeddings  → speaker recognition
OCR               → visible textual context
LLM/Codex         → ambiguity and reasoning
```

The application must remain useful without any LLM.

---

# 2. Primary use case

Typical input:

```
meeting.mkv
```

or:

```
meeting.mp3
```

Typical invocation:

```
ihm meeting.mkv
```

Expected output:

```
output/meeting/
    transcript.md
    transcript.txt
    transcript.json
    transcript.srt
    transcript.vtt
```

The transcript should resemble:

```
[00:00:03] Federica Orsini
...

[00:00:17] Giovanni Taranto
...

[00:14:52] SPEAKER_03 [?]
...
```

Unknown speakers MUST remain unknown.

Never invent speaker identities.

---

# 3. Supported platforms

Tier-1:

* Arch Linux
* Ubuntu
* Fedora
* Windows 11 through WSL2

Native Windows support is NOT required for v1.

Windows users should use:

```
Windows 11
    ↓
  WSL2
    ↓
Ubuntu
    ↓
```

IHateMeetings

The core Python code MUST NOT contain distribution-specific assumptions.

Platform-specific operations must be isolated.

---

# 4. Installation

Provide:

```
install/
    arch.sh
    ubuntu.sh
    fedora.sh
    wsl-ubuntu.sh
```

Documentation:

```
docs/install/
    arch-linux.md
    ubuntu.md
    fedora.md
    windows-wsl.md
```

Installation scripts should be:

* readable;
* conservative;
* reasonably idempotent;
* safe to rerun.

Check before installing.

Do not alter unrelated system configuration.

Do not require root privileges during normal runtime.

---

# 5. Dependency management

Use:

* Python 3.11+;
* `uv`;
* `pyproject.toml`;
* `uv.lock`.

Do not globally install Python dependencies using pip.

System package managers are used only for system dependencies such as:

* FFmpeg;
* Git;
* optional OCR components.

Python/ML dependencies belong to the project environment.

---

# 6. Linux installation targets

## Arch Linux

Basic system dependencies should be installable using official repositories whenever possible.

Example:

```
sudo pacman -S --needed ffmpeg python git
```

Avoid mandatory AUR dependencies.

---

## Ubuntu

Support current compatible Ubuntu LTS versions.

Expected bootstrap resembles:

```
sudo apt update
sudo apt install ffmpeg python3 python3-venv git
```

Do not assume Ubuntu and Arch provide identical Python versions.

---

## Fedora

Expected bootstrap resembles:

```
sudo dnf install ffmpeg python3 git
```

Detect and explain multimedia repository problems rather than failing mysteriously.

---

# 7. Windows / WSL2

Document initial setup:

```
wsl --install -d Ubuntu-24.04
```

Then use the normal Linux pipeline.

Support files from:

```
/mnt/c/Users/...
```

However, recommend storing:

* virtual environments;
* caches;
* models;
* temporary processing files;

inside the WSL Linux filesystem for performance.

Example:

```
~/.cache/ihatemeetings/
~/ihm-work/
```

---

# 8. Architecture

The application MUST use a staged pipeline.

Conceptual architecture:

```
Input
  │
  ▼
Media inspection
  │
  ▼
Audio extraction
  │
  ▼
Audio normalization
  │
  ▼
Voice Activity Detection
  │
  ▼
Speech Recognition
  │
  ▼
Word Alignment
  │
  ▼
Speaker Diarization
  │
  ▼
Speaker Resolution
  │
  ▼
Confidence Analysis
  │
  ▼
Intelligent Review
  │
  ▼
Transcript Reconstruction
  │
  ▼
Export
```

Each stage must have explicit input/output contracts.

Intermediate results MUST be serializable and cacheable.

---

# 9. Media input

Initially support:

* WAV
* MP3
* M4A
* FLAC
* OGG
* MKV
* MP4
* WEBM

Use `ffprobe` for media inspection.

Never modify the source file.

---

# 10. Audio preprocessing

Use FFmpeg.

Generate a normalized internal audio representation suitable for speech recognition.

A reasonable baseline:

```
PCM
mono
16 kHz
16 bit
```

Equivalent operation:

```
ffmpeg \
    -i input \
    -vn \
    -ac 1 \
    -ar 16000 \
    -c:a pcm_s16le \
    audio.wav
```

Do not blindly normalize volume if doing so damages speech quality.

Preserve original timestamps.

---

# 11. Voice Activity Detection

Use an appropriate VAD implementation.

Silero VAD is an acceptable initial candidate.

VAD should detect:

* speech;
* silence;
* long pauses.

Where possible preserve information useful for detecting:

* overlapping speech;
* questionable audio regions.

Do not send long silence regions unnecessarily through ASR.

---

# 12. ASR abstraction

Define an abstraction similar to:

```
ASRBackend
```

Initial preferred implementation:

```
FasterWhisperBackend
```

Secondary implementation:

```
WhisperCppBackend
```

Do NOT couple the pipeline permanently to one ASR engine.

---

# 13. Primary ASR

Prefer `faster-whisper`.

Evaluate currently appropriate Whisper models rather than hardcoding assumptions permanently.

Initial profiles may use:

FAST:

```
small / medium
```

BALANCED:

```
large-v3-turbo or equivalent
```

ACCURATE:

```
large-v3 or best validated local model
```

Exact defaults must eventually be determined by benchmarks.

Support:

```
--language it
```

and automatic language detection.

Do NOT translate foreign technical terminology simply because the primary language is Italian.

---

# 14. Hardware adaptation

IHateMeetings MUST work without a GPU.

Detect:

* operating system;
* CPU;
* architecture;
* RAM;
* GPU;
* CUDA;
* VRAM;
* WSL GPU availability.

Choose an appropriate execution configuration.

Typical CPU:

```
int8
```

Typical NVIDIA GPU:

```
float16
```

or an appropriate optimized compute type.

Allow manual overrides.

---

# 15. Profiles

Provide:

```
ihm meeting.mkv --profile fast
ihm meeting.mkv --profile balanced
ihm meeting.mkv --profile accurate
```

When no profile is provided:

```
ihm meeting.mkv
```

automatically select a reasonable configuration.

The selected execution plan must be displayed before expensive processing begins.

Example:

```
IHateMeetings

Input ............ meeting.mkv
Duration ......... 00:57:32
Language ......... Italian
Device ........... CUDA
ASR .............. faster-whisper
Model ............ large-v3
Diarization ...... enabled
Alignment ........ enabled
Reasoning ........ disabled
```

---

# 16. Word-level alignment

Use WhisperX or another validated alignment implementation.

Target representation:

```
{
  "text": "example",
  "start": 42.15,
  "end": 42.63,
  "confidence": 0.94
}
```

Keep:

* raw ASR segments;
* aligned words;
* final transcript;

as separate artifacts.

Never destroy raw inference results.

---

# 17. Speaker diarization

Define:

```
DiarizationBackend
```

Initial implementation:

```
PyannoteBackend
```

Prefer a current locally runnable pyannote pipeline.

The output must represent:

```
SPEAKER_00
SPEAKER_01
SPEAKER_02
```

with timestamps.

Support optional hints:

```
--speakers 5
```

or:

```
--min-speakers 3
--max-speakers 8
```

Do not confuse diarization with speaker identification.

Diarization answers:

> Who spoke when?

Identification answers:

> Who is that person?

---

# 18. Overlapping speech

Meetings frequently contain interruptions.

Do not assume only one person can speak at a time.

Preserve overlap information whenever supported by the diarization backend.

When attribution cannot be reliably resolved, represent uncertainty instead of arbitrarily selecting a speaker.

---

# 19. Speaker identification

Support multiple evidence sources.

Speaker resolution should combine evidence rather than rely on a single heuristic.

Possible evidence:

* diarization cluster;
* anchor phrase;
* voice embedding;
* conversational relationships;
* video active-speaker metadata;
* OCR;
* explicit user mapping.

Every resolved identity should include:

```
name
confidence
provenance
```

Example:

```
{
  "cluster": "SPEAKER_02",
  "name": "Sonia Greco",
  "confidence": 0.97,
  "reason": "anchor_phrase"
}
```

---

# 20. Manual speaker mapping

Support:

```
ihm ... \
  --speaker SPEAKER_00="Federica Orsini"
```

Manual mappings have higher authority than automatic inference.

---

# 21. Anchor-based speaker resolution

This is a core feature.

Support:

```
anchors.yaml
```

Example:

```
meeting:
  date: 2026-08-26

speakers:

  Federica Orsini:
    first_speaker: true

  Giovanni Taranto:
    responds_to_first_speaker: true

  Sonia Greco:
    phrases:
      - "però Fede voglio aggiungere solo una cosa"

  Davide:
    semantic_hints:
      - "promuoverò in STAG"
      - "modifiche aggiornate"
      - "stasera"

  Andrea Berardis:
    phrases:
      - "io stamattina ho fatto un giro con Davide"
```

Resolution strategy:

1. exact match;
2. normalized match;
3. fuzzy textual match;
4. semantic match only if necessary.

Once an anchor is confidently located:

```
phrase
   ↓
timestamp
   ↓
diarization segment
   ↓
speaker cluster
   ↓
real identity
```

Then propagate that identity to other segments in the same cluster.

Never propagate a weak identification as fact.

---

# 22. Voiceprints

Future/second-stage capability:

```
ihm speakers
```

Commands should eventually include:

```
ihm speakers list
ihm speakers add
ihm speakers remove
ihm speakers inspect
```

Maintain a local speaker database.

Suggested storage:

```
~/.local/share/ihatemeetings/speakers/
```

Each identity may have multiple verified samples.

Never train/update a person's reference voice using a low-confidence automatic prediction.

Prefer explicit confirmation.

---

# 23. Speaker recognition

Use voice embeddings to compare known reference voices with diarization clusters.

Do not require exact acoustic equality.

Account for:

* microphones;
* compression;
* room acoustics;
* calls;
* noise.

Thresholds must be configurable and benchmarked.

Below threshold:

```
UNKNOWN
```

is preferable to a false identity.

---

# 24. Meeting context

Support:

```
context.md
```

Example:

```
# Meeting context

Date: 2026-08-26

Participants:
- Federica Orsini
- Giovanni Taranto
- Sonia Greco
- Davide
- Andrea Berardis

Subject:
Deployment and STAG updates.
```

Context is supporting evidence.

A participant being listed does NOT prove that every unidentified voice belongs to that person.

---

# 25. Glossary

Support:

```
glossary.yaml
```

Example:

```
terms:
  - STAG
  - DEV
  - PREPROD
  - PROD
  - Quarkus
  - OpenSearch
  - DynamoDB
  - Prometeia
```

Use glossary information for:

* ASR prompting where supported;
* candidate generation;
* post-ASR analysis.

Never perform unconditional search-and-replace.

Example:

```
"stag"
   ↓
maybe "STAG"
```

is acceptable only when context/confidence supports it.

---

# 26. Confidence engine

Confidence analysis is a first-class component.

Compute useful confidence indicators from:

* ASR probability;
* no-speech probability;
* alignment quality;
* diarization certainty;
* speaker resolution confidence;
* language consistency;
* glossary candidates;
* contextual anomalies.

Classify segments:

```
HIGH
MEDIUM
LOW
```

Example:

```
LOW
00:23:41
SPEAKER_03

"dobbiamo promuovere sulla stacca"
```

These become candidates for intelligent review.

---

# 27. Intelligent review

Do NOT ask an LLM to rewrite the entire transcript.

The reasoning layer should primarily receive problematic segments.

For each candidate provide useful context:

* questionable sentence;
* preceding transcript;
* following transcript;
* speaker information;
* ASR confidence;
* glossary;
* meeting context;
* alternative hypotheses where available.

Example conceptual request:

```
Original:
  "domani promuovo sulla stacca"

Nearby context:
  deployment discussion

Glossary:
  STAG
  PROD

Determine whether a transcription error is likely.
Do not change the sentence unless evidence is sufficient.
```

---

# 28. Correction audit

Every automatic correction must be auditable.

Store:

```
{
  "original": "...",
  "corrected": "...",
  "reason": "...",
  "provider": "...",
  "confidence": 0.91
}
```

Never overwrite raw transcription.

---

# 29. Reasoning abstraction

Define:

```
ReasoningProvider
```

Initial implementations:

```
NoOpProvider
```

Future implementations:

```
LocalLLMProvider
OpenAIProvider
```

Potential integrations may include Codex during development or review workflows.

Do NOT architect runtime around an undocumented or unstable Codex CLI interface.

Codex is primarily the development agent for this repository.

The application must work without Codex.

---

# 30. Local-first requirement

Core transcription must be local-first.

After required models have been downloaded, the following should operate offline where technically possible:

```
FFmpeg
VAD
ASR
alignment
diarization
speaker recognition
transcript generation
```

Any network-dependent feature must be explicit.

Never silently upload meeting audio.

---

# 31. Video intelligence

SECOND PHASE.

For video inputs optionally support:

```
--video-intelligence
```

Potential information sources:

* Teams overlays;
* Meet overlays;
* Zoom overlays;
* participant names;
* active-speaker highlighting;
* subtitles;
* screen sharing;
* slides;
* chat;
* visible application content.

---

# 32. OCR

OCR is optional and is NOT an audio transcription engine.

Tesseract is an acceptable initial OCR backend.

Define:

```
OCRBackend
```

Do not OCR every video frame.

Use intelligent sampling:

* scene change detection;
* periodic sampling;
* region of interest;
* perceptual hashes;
* duplicate suppression.

OCR results are evidence, not ground truth.

Example:

```
00:13:21
active speaker frame
OCR: "Federica Orsini"
```

may strengthen a speaker hypothesis.

---

# 33. Models

Provide:

```
ihm models list
ihm models download
ihm models remove
```

Do not store model weights in the repository.

Use user cache directories.

Never silently download a multi-gigabyte model.

Inform the user before large downloads.

---

# 34. Doctor

`ihm doctor` is a core feature, not an afterthought.

Implement it early.

Example:

```
$ ihm doctor

IHateMeetings Doctor

Platform
├─ OS ................ Arch Linux
├─ Architecture ...... x86_64
└─ WSL ............... no

Runtime
├─ Python ............ 3.13 ✓
├─ FFmpeg ............ ✓
└─ FFprobe ........... ✓

ML
├─ faster-whisper .... ✓
├─ WhisperX .......... ✓
├─ PyTorch ........... ✓
└─ pyannote .......... ✓

Hardware
├─ GPU ............... none
├─ CUDA .............. unavailable
└─ CPU inference ..... available ✓

Optional
├─ OCR ............... not installed
└─ LLM provider ...... disabled

Ready to transcribe. ✓
```

Errors must include actionable remediation.

Example:

```
FFmpeg missing.

Arch:
  sudo pacman -S ffmpeg

Ubuntu:
  sudo apt install ffmpeg

Fedora:
  sudo dnf install ffmpeg
```

---

# 35. Cache and resume

Long recordings are expensive to process.

Every expensive stage must be cacheable.

Suggested workspace:

```
.ihm/
  jobs/
    <job-id>/
```

Each job stores:

```
source metadata
configuration
hashes
preprocessing output
ASR output
alignment
diarization
speaker mapping
correction state
```

Support:

```
--resume
```

and eventually:

```
--force-stage asr
--force-stage diarization
```

If diarization fails after ASR completed, rerunning MUST NOT unnecessarily repeat ASR.

---

# 36. Cache invalidation

Cache keys should consider:

* source file hash;
* relevant configuration;
* model;
* model version;
* backend;
* pipeline version.

Changing transcript export formatting must not invalidate ASR.

Changing ASR model must invalidate ASR and dependent stages.

Design dependency-aware invalidation.

---

# 37. Output

For each job produce:

```
output/<meeting>/

    transcript.md
    transcript.txt
    transcript.json
    transcript.srt
    transcript.vtt

    metadata.json

    raw/
        media.json
        vad.json
        asr.json
        words.json
        diarization.json
        diarization.rttm

    debug/
        confidence.json
        speaker_mapping.json
        corrections.json
        warnings.json
```

---

# 38. Canonical JSON

`transcript.json` should be the canonical machine-readable final representation.

Design and document a versioned schema.

Conceptual example:

```
{
  "schema_version": 1,
  "meeting": {
    "duration": 3452.2,
    "language": "it"
  },
  "speakers": [...],
  "segments": [
    {
      "id": "...",
      "start": 12.4,
      "end": 17.9,
      "speaker": {
        "cluster": "SPEAKER_01",
        "name": "Federica Orsini",
        "confidence": 0.97
      },
      "text": "...",
      "confidence": 0.93,
      "words": [...]
    }
  ]
}
```

Other exporters should consume the canonical representation rather than rebuilding inference logic.

---

# 39. Markdown transcript

Example:

```
# Meeting transcript

**Date:** 2026-08-26
**Language:** Italian
**Duration:** 00:57:32

## Participants

- Federica Orsini
- Giovanni Taranto
- Sonia Greco
- Davide
- Andrea Berardis

## Transcript

### [00:00:03] Federica Orsini

...

### [00:00:17] Giovanni Taranto

...
```

For uncertain attribution:

```
### [00:17:42] SPEAKER_04 [?]
```

Do not hide uncertainty for readability.

---

# 40. Future meeting intelligence

NOT part of the initial transcription MVP.

Once transcription quality is validated, support optional:

```
ihm summarize ...
ihm minutes ...
ihm actions ...
```

Possible outputs:

* executive summary;
* meeting minutes;
* decisions;
* action items;
* unresolved questions;
* deadlines;
* owners;
* technical topics.

These MUST consume the final transcript.

Do not couple them to ASR internals.

---

# 41. CLI

Target interface:

```
ihm FILE
```

Equivalent explicit form:

```
ihm transcribe FILE
```

Examples:

```
ihm meeting.mp3

ihm meeting.mkv \
    --language it

ihm meeting.mkv \
    --diarize

ihm meeting.mkv \
    --profile accurate \
    --context context.md \
    --anchors anchors.yaml \
    --glossary glossary.yaml
```

Useful commands:

```
ihm doctor

ihm models list

ihm speakers list
```

Eventually:

```
ihm summarize meeting
ihm minutes meeting
ihm actions meeting
```

---

# 42. Progress reporting

Long-running commands must show meaningful progress.

Example:

```
IHateMeetings

[1/7] Preparing audio ............ done
[2/7] Detecting speech ........... done
[3/7] Transcribing ............... 62%
[4/7] Aligning words
[5/7] Detecting speakers
[6/7] Resolving identities
[7/7] Building transcript
```

Avoid fake progress percentages.

If a backend cannot report reliable percentage completion, show elapsed stage information instead.

---

# 43. Logging

Use structured logging internally.

Support:

```
--verbose
--debug
```

Normal users should see concise progress.

Debug logs should contain enough information to diagnose:

* backend failures;
* model loading;
* CUDA errors;
* FFmpeg errors;
* cache invalidation;
* diarization issues.

Never log secrets.

---

# 44. Error handling

Do not hide failures behind silent fallback.

If GPU inference fails and CPU fallback is possible:

1. report what failed;
2. explain the fallback;
3. continue only when safe.

Example:

```
CUDA initialization failed.
Falling back to CPU INT8 inference.
```

For significant behavioral changes, record the fallback in metadata.

---

# 45. Security and privacy

Meeting recordings may contain confidential information.

Therefore:

* local-first by default;
* no telemetry containing transcript/audio content;
* no automatic cloud uploads;
* no secrets committed;
* API tokens through environment/secret mechanisms;
* temporary files should have sensible permissions;
* document where recordings, caches and models are stored.

Provide a way to clean job data:

```
ihm clean <job>
```

and eventually:

```
ihm clean --all-jobs
```

Do NOT remove shared models unless explicitly requested.

---

# 46. Repository structure

Target:

```
ihatemeetings/
│
├── AGENTS.md
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
│
├── src/
│   └── ihatemeetings/
│       ├── __init__.py
│       ├── cli/
│       ├── config/
│       ├── platform/
│       ├── media/
│       ├── vad/
│       ├── asr/
│       ├── alignment/
│       ├── diarization/
│       ├── speakers/
│       ├── confidence/
│       ├── reasoning/
│       ├── video/
│       ├── ocr/
│       ├── pipeline/
│       ├── models/
│       ├── cache/
│       └── exporters/
│
├── install/
│   ├── arch.sh
│   ├── ubuntu.sh
│   ├── fedora.sh
│   └── wsl-ubuntu.sh
│
├── docs/
│   ├── architecture.md
│   ├── pipeline.md
│   ├── privacy.md
│   └── install/
│       ├── arch-linux.md
│       ├── ubuntu.md
│       ├── fedora.md
│       └── windows-wsl.md
│
├── examples/
│   ├── context.example.md
│   ├── anchors.example.yaml
│   └── glossary.example.yaml
│
└── tests/
```

Do not create empty architecture layers purely to satisfy this diagram.

Create modules as functionality is implemented.

---

# 47. Testing strategy

Use automated tests.

Unit tests must cover at minimum:

* timestamp conversion;
* config parsing;
* anchor normalization;
* fuzzy anchor matching;
* speaker mapping;
* confidence aggregation;
* cache keys;
* cache invalidation;
* canonical transcript schema;
* exporters.

Integration tests should cover representative short samples.

---

# 48. Audio test cases

Eventually test:

* clean Italian;
* noisy Italian;
* Italian + English technical terminology;
* one speaker;
* two speakers;
* five speakers;
* interruptions;
* overlapping speech;
* long silence;
* poor microphone;
* compressed call audio;
* unknown speaker;
* known voiceprint;
* ambiguous anchor;
* incorrect anchor.

Do not commit confidential real meeting recordings.

Use public, generated or explicitly distributable fixtures.

---

# 49. Metrics

When ground truth exists, calculate appropriate metrics.

ASR:

* WER;
* CER.

Diarization:

* DER.

Speaker resolution:

* identification accuracy;
* unknown rejection quality.

Track performance separately from correctness.

Do not optimize speed by silently degrading transcript quality.

---

# 50. CI

Use GitHub Actions.

Required baseline:

* Ubuntu;
* supported Python versions;
* CPU-compatible tests.

Where practical, test installation/bootstrap behavior for:

* Arch;
* Fedora;

using containers.

GPU tests may be optional/manual.

Normal CI MUST NOT require a GPU.

---

# 51. Development priorities

Codex MUST build the project incrementally.

Do not attempt the complete vision in one implementation pass.

## Phase 0 — Bootstrap

Implement:

* project structure;
* pyproject;
* CLI;
* configuration;
* logging;
* basic CI;
* installer skeletons.

Acceptance:

```
ihm --help
ihm doctor
```

work.

---

## Phase 1 — Basic transcription

Implement:

```
media
  ↓
FFmpeg
  ↓
faster-whisper
  ↓
canonical JSON
  ↓
Markdown/TXT/SRT/VTT
```

Acceptance:

```
ihm sample.mp3
```

produces a usable transcript.

---

## Phase 2 — Alignment

Add:

* word-level timestamps;
* WhisperX integration;
* raw aligned-word artifact.

Acceptance:

each aligned word has timestamps where supported.

---

## Phase 3 — Diarization

Add:

* pyannote;
* speaker clusters;
* merge ASR/alignment with diarization.

Acceptance:

output contains consistent:

```
SPEAKER_00
SPEAKER_01
...
```

---

## Phase 4 — Speaker resolution

Add:

* manual mapping;
* anchors.yaml;
* exact matching;
* normalized matching;
* fuzzy matching;
* confidence/provenance.

Acceptance:

known anchors can convert diarization clusters into verified identities.

---

## Phase 5 — Reliability

Add:

* cache;
* resume;
* stage invalidation;
* confidence engine;
* improved doctor;
* hardware profiles.

Acceptance:

interrupting a long job does not require repeating completed expensive stages.

---

## Phase 6 — Speaker memory

Add:

* voice embeddings;
* reference samples;
* speaker database;
* similarity thresholds;
* explicit confirmation workflow.

---

## Phase 7 — Intelligent review

Add reasoning-provider abstraction.

Start with:

```
NoOpProvider
```

Then evaluate:

* local LLM;
* optional OpenAI reasoning.

Only LOW/MEDIUM-confidence candidates should normally be reviewed.

---

## Phase 8 — Video intelligence

Add:

* selective frame extraction;
* OCR;
* active-speaker evidence where feasible;
* slide/screen textual context.

Do not implement before audio pipeline quality is acceptable.

---

## Phase 9 — Meeting intelligence

Add:

* summary;
* minutes;
* decisions;
* action items.

This is downstream of transcription and must remain architecturally separate.

---

# 52. MVP definition

The first serious MVP consists of Phases 0–5.

It MUST provide:

* multiplatform installation;
* `ihm doctor`;
* audio/video ingestion;
* FFmpeg preprocessing;
* faster-whisper transcription;
* word alignment;
* pyannote diarization;
* speaker clusters;
* anchor-based identification;
* glossary;
* confidence indicators;
* canonical JSON;
* Markdown;
* TXT;
* SRT;
* VTT;
* cache;
* resume.

It does NOT need:

* GUI;
* web server;
* OCR;
* voiceprint database;
* cloud AI;
* summaries;
* action items;
* native Windows.

---

# 53. MVP acceptance scenario

The following is an important real-world acceptance scenario.

Input:

```
approximately one-hour Italian meeting recording
```

Known context:

```
meeting date: 2026-08-26
```

Known participants include:

```
Federica Orsini
Giovanni Taranto
Sonia Greco
Davide
Andrea Berardis
```

Known anchors include:

```
Federica Orsini:
  first speaker

Giovanni Taranto:
  first person responding to Federica

Sonia Greco:
  "però Fede voglio aggiungere solo una cosa"

Davide:
  discussion about promoting updated changes to STAG that evening

Andrea Berardis:
  "io stamattina ho fatto un giro con Davide"
```

The system should use these hints to identify diarization clusters.

It MUST NOT assume every hint is transcribed literally.

It should tolerate normal ASR errors through normalized/fuzzy matching.

This scenario is a private validation case.

Do NOT commit the recording, transcript or participant voiceprints to a public repository.

---

# 54. Cross-platform acceptance

MVP is not complete until installation documentation exists and the expected workflow is validated for:

## Arch Linux

```
./install/arch.sh
ihm doctor
```

## Ubuntu

```
./install/ubuntu.sh
ihm doctor
```

## Fedora

```
./install/fedora.sh
ihm doctor
```

## Windows 11

PowerShell:

```
wsl --install -d Ubuntu-24.04
```

Inside WSL:

```
./install/wsl-ubuntu.sh
ihm doctor
```

All platforms must generate the same canonical JSON schema.

Bit-identical inference output is NOT required.

---

# 55. Dependency research rule

Before adding a significant ML dependency:

1. inspect the official upstream project;
2. check current maintenance status;
3. check license;
4. check supported Python/PyTorch versions;
5. check CPU support;
6. check GPU requirements;
7. check model licensing/access requirements;
8. document why it was chosen.

Do not rely on abandoned forks when a maintained upstream exists.

Pin versions intentionally.

Do not blindly use whatever version a blog post recommends.

---

# 56. Dependency isolation

External ML frameworks are volatile.

Wrap them behind internal interfaces.

For example:

```
ASRBackend
AlignmentBackend
DiarizationBackend
OCRBackend
ReasoningProvider
```

Do not leak third-party response structures throughout the application.

Convert external outputs into IHateMeetings internal models immediately.

---

# 57. Data models

Use explicit typed internal models.

Prefer dataclasses or Pydantic where appropriate.

Core concepts should include:

```
MediaInfo
SpeechRegion
ASRSegment
Word
DiarizationTurn
SpeakerCluster
SpeakerIdentity
TranscriptSegment
Transcript
Correction
JobMetadata
```

Avoid passing arbitrary dictionaries between pipeline stages.

---

# 58. Configuration precedence

Use predictable precedence:

```
defaults
   ↓
configuration file
   ↓
environment
   ↓
CLI arguments
```

Document it.

Never make behavior depend on hidden machine state when it can be explicit.

---

# 59. Reproducibility

Every job should record enough metadata to explain how its transcript was produced.

Record:

* IHateMeetings version;
* OS;
* ASR backend/version;
* ASR model;
* alignment backend;
* diarization backend/model;
* compute device;
* compute type;
* relevant configuration;
* optional reasoning provider;
* timestamps.

This metadata is important for debugging differences between machines.

---

# 60. Agent operating rules

When working on this repository, Codex MUST:

1. inspect existing code before editing;
2. read this file before architectural changes;
3. preserve working functionality;
4. make small coherent changes;
5. add/update tests;
6. execute relevant tests;
7. execute lint/type checks where configured;
8. update documentation when behavior changes;
9. report what was implemented;
10. report tests actually executed;
11. report unresolved problems;
12. never claim something was tested when it was not.

---

# 61. Agent autonomy

Codex may make normal engineering decisions without asking for confirmation when they:

* follow this architecture;
* are reversible;
* do not introduce paid services;
* do not upload private data;
* do not fundamentally change scope.

Codex SHOULD NOT stop for trivial questions such as naming an internal helper or choosing a reasonable test framework.

Make the reasonable choice and document it.

---

# 62. When Codex must ask

Ask before:

* introducing a paid API;
* sending audio/transcripts to external services;
* changing the project's core architecture;
* removing a supported platform;
* removing a major feature requirement;
* storing biometric voice information outside the local machine;
* performing destructive operations;
* changing licensing assumptions.

---

# 63. No fake implementation

Do not satisfy requirements using placeholder logic while presenting it as complete.

Examples of unacceptable behavior:

* random speaker assignment;
* hard-coded transcripts;
* fake confidence values presented as real;
* progress bars unrelated to actual work;
* claiming CUDA acceleration without verifying device use;
* silently returning raw Whisper output when diarization failed.

Temporary stubs are allowed only when clearly marked and not exposed as completed functionality.

---

# 64. Uncertainty is data

A central philosophy of IHateMeetings:

> **It is better to say “I don't know who said this” than to confidently name the wrong person.**

Preserve uncertainty throughout the pipeline.

This applies to:

* words;
* timestamps;
* speaker identity;
* corrections;
* OCR;
* semantic reasoning.

Do not discard uncertainty merely to produce prettier output.

---

# 65. Raw data is immutable

Never mutate raw inference output.

Store processing layers separately:

```
raw
  ↓
normalized
  ↓
aligned
  ↓
speaker-attributed
  ↓
corrected
  ↓
final
```

Every final statement should be traceable backwards where reasonably possible.

---

# 66. Performance philosophy

Optimize intelligently.

Do not use an LLM for tasks solvable by:

* regex;
* FFmpeg;
* fuzzy matching;
* embeddings;
* specialized ML models.

Do not rerun ASR because Markdown formatting changed.

Do not OCR identical frames.

Do not run expensive reasoning on HIGH-confidence segments without a reason.

Do not load models repeatedly within one job.

Measure before optimizing.

---

# 67. Privacy philosophy

Assume meeting content may be confidential.

Default behavior should therefore be safe enough for professional recordings.

The user should always be able to determine:

* what runs locally;
* what requires Internet access;
* whether anything leaves the machine;
* where artifacts are stored;
* how to delete them.

---

# 68. Definition of Done

A feature is complete only when:

* implementation exists;
* errors are handled;
* tests exist where reasonable;
* tests pass;
* CLI behavior is documented;
* platform implications are considered;
* privacy implications are considered;
* generated data remains auditable.

"Works on my machine" is not sufficient.

---

# 69. First Codex task

When this repository initially contains only this AGENTS.md, begin with Phase 0.

Do NOT attempt all phases at once.

Perform the following:

1. inspect the environment and repository;
2. research current maintained upstream dependencies where needed;
3. create the Python/uv project;
4. establish package structure;
5. implement the `ihm` CLI;
6. implement platform detection;
7. implement an initial `ihm doctor`;
8. create installation documentation for:

   * Arch Linux;
   * Ubuntu;
   * Fedora;
   * Windows/WSL2;
9. add baseline tests;
10. add GitHub Actions CI;
11. create a README describing the project and roadmap;
12. run the test suite;
13. report the resulting repository state.

Stop after Phase 0 is operational.

Do not begin expensive ML integration until the foundation is working.

---

# 70. Final principle

IHateMeetings should not try to make one enormous AI model solve every problem.

Build a pipeline where each component performs the task it is best suited for.

Then use reasoning only where reasoning actually adds value.

> **IHateMeetings — You attend. We listen.**
