from __future__ import annotations

import math
import unicodedata
import wave
from collections import defaultdict
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from itertools import pairwise
from pathlib import Path

from ihatemeetings.alignment.base import (
    AlignmentBackend,
    AlignmentOptions,
    AlignmentResult,
    AlignmentSegment,
)
from ihatemeetings.errors import IHMError
from ihatemeetings.models import ASRSegment, Word


@dataclass(frozen=True)
class _TokenSpan:
    token_index: int
    start_frame: int
    end_frame: int
    confidence: float


class CTCAlignmentBackend(AlignmentBackend):
    """Language-specific CTC forced alignment without WhisperX runtime coupling."""

    def align(
        self,
        audio_path: Path,
        segments: tuple[ASRSegment, ...],
        options: AlignmentOptions,
    ) -> AlignmentResult:
        try:
            import torch
            from transformers import AutoFeatureExtractor, AutoModelForCTC, AutoTokenizer
            from transformers import logging as transformers_logging
        except (ImportError, OSError, RuntimeError) as exc:
            raise IHMError(
                "Alignment dependencies are unavailable.",
                "Run 'uv sync --python 3.13 --extra alignment' and retry.",
            ) from exc

        transformers_logging.set_verbosity_error()
        transformers_logging.disable_progress_bar()
        audio = _read_pcm_audio(audio_path)
        try:
            feature_extractor = AutoFeatureExtractor.from_pretrained(
                options.model_path, local_files_only=True
            )
            tokenizer = AutoTokenizer.from_pretrained(options.model_path, local_files_only=True)
            model = AutoModelForCTC.from_pretrained(options.model_path, local_files_only=True)
            model = model.to(options.device).eval()
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            raise IHMError(
                f"Could not load alignment model '{options.model_name}': {exc}",
                "Verify the cached model or retry with alignment disabled.",
            ) from exc

        vocabulary = tokenizer.get_vocab()
        blank_id = getattr(model.config, "pad_token_id", None)
        if blank_id is None:
            blank_id = tokenizer.pad_token_id
        if blank_id is None:
            raise IHMError("The alignment model does not define a CTC blank token.")

        aligned_segments: list[AlignmentSegment] = []
        warnings: list[str] = []
        for index, segment in enumerate(segments):
            try:
                words = _align_segment(
                    audio,
                    segment,
                    feature_extractor,
                    model,
                    vocabulary,
                    int(blank_id),
                    options.device,
                    torch,
                )
            except IHMError as exc:
                words = tuple(
                    Word(text=word, start=None, end=None, confidence=None)
                    for word in segment.text.split()
                )
                warnings.append(f"segment {index + 1}: {exc}")
            aligned_segments.append(
                AlignmentSegment(index, segment.start, segment.end, segment.text, words)
            )

        all_words = [word for segment in aligned_segments for word in segment.words]
        aligned_count = sum(word.start is not None for word in all_words)
        status = "completed" if aligned_count == len(all_words) else "partial"
        if not all_words:
            status = "completed"
        try:
            backend_version = version("transformers")
        except PackageNotFoundError:
            backend_version = "unknown"
        return AlignmentResult(
            backend="ctc-transformers",
            backend_version=backend_version,
            model=options.model_name,
            language=options.language,
            status=status,
            segments=tuple(aligned_segments),
            warnings=tuple(warnings),
        )


def _read_pcm_audio(path: Path):
    try:
        import numpy as np

        with wave.open(str(path), "rb") as audio_file:
            if (
                audio_file.getnchannels() != 1
                or audio_file.getframerate() != 16000
                or audio_file.getsampwidth() != 2
            ):
                raise IHMError("Alignment requires mono 16 kHz 16-bit PCM audio.")
            frames = audio_file.readframes(audio_file.getnframes())
    except (OSError, wave.Error) as exc:
        raise IHMError(f"Could not read normalized audio for alignment: {exc}") from exc
    return np.frombuffer(frames, dtype="<i2").astype("float32") / 32768.0


def _align_segment(
    audio,
    segment: ASRSegment,
    feature_extractor,
    model,
    vocabulary: dict[str, int],
    blank_id: int,
    device: str,
    torch,
) -> tuple[Word, ...]:
    original_words = segment.text.split()
    if not original_words:
        return ()
    start_sample = max(0, round(segment.start * 16000))
    end_sample = min(len(audio), round(segment.end * 16000))
    if end_sample <= start_sample:
        raise IHMError("segment has no audio inside its timestamp bounds")

    targets, word_indices = _tokenize_words(original_words, vocabulary)
    if not targets:
        raise IHMError("segment text has no characters supported by the alignment model")
    inputs = feature_extractor(
        audio[start_sample:end_sample], sampling_rate=16000, return_tensors="pt"
    )
    input_values = inputs.input_values.to(device)
    with torch.inference_mode():
        emission = model(input_values).logits[0].log_softmax(dim=-1).cpu()
    spans = _forced_align(emission, targets, blank_id, torch)
    return _word_timestamps(
        original_words,
        word_indices,
        spans,
        start_sample / 16000,
        end_sample / 16000,
        emission.shape[0],
    )


def _tokenize_words(
    words: list[str], vocabulary: dict[str, int]
) -> tuple[list[int], list[int | None]]:
    normalized_vocabulary = {key.casefold(): value for key, value in vocabulary.items()}
    delimiter_id = normalized_vocabulary.get("|")
    targets: list[int] = []
    word_indices: list[int | None] = []
    for word_index, word in enumerate(words):
        token_ids = []
        for character in word.casefold():
            token_id = normalized_vocabulary.get(character)
            if token_id is None:
                base = "".join(
                    candidate
                    for candidate in unicodedata.normalize("NFKD", character)
                    if not unicodedata.combining(candidate)
                )
                token_id = normalized_vocabulary.get(base)
            if token_id is not None:
                token_ids.append(token_id)
        if not token_ids:
            continue
        if targets and delimiter_id is not None:
            targets.append(delimiter_id)
            word_indices.append(None)
        targets.extend(token_ids)
        word_indices.extend([word_index] * len(token_ids))
    return targets, word_indices


def _forced_align(emission, targets: list[int], blank_id: int, torch) -> tuple[_TokenSpan, ...]:
    frame_count, _ = emission.shape
    token_count = len(targets)
    repeated_tokens = sum(left == right for left, right in pairwise(targets))
    minimum_frames = token_count + repeated_tokens
    if frame_count < minimum_frames:
        raise IHMError(
            f"too few acoustic frames ({frame_count}) for transcript tokens "
            f"({minimum_frames} required)"
        )

    extended = [blank_id]
    for target in targets:
        extended.extend((target, blank_id))
    state_count = len(extended)
    extended_tensor = torch.tensor(extended, dtype=torch.long)
    scores = torch.full((state_count,), -math.inf)
    scores[0] = emission[0, blank_id]
    scores[1] = emission[0, targets[0]]
    backpointers = torch.zeros((frame_count, state_count), dtype=torch.int8)

    skip_allowed = torch.zeros(state_count, dtype=torch.bool)
    for state in range(3, state_count, 2):
        token_index = (state - 1) // 2
        skip_allowed[state] = targets[token_index] != targets[token_index - 1]

    for frame in range(1, frame_count):
        stay = scores
        step = torch.cat((torch.tensor([-math.inf]), scores[:-1]))
        skip = torch.cat((torch.full((2,), -math.inf), scores[:-2]))
        skip = torch.where(skip_allowed, skip, torch.full_like(skip, -math.inf))
        candidates = torch.stack((stay, step, skip))
        best_scores, transitions = torch.max(candidates, dim=0)
        scores = best_scores + emission[frame, extended_tensor]
        backpointers[frame] = transitions.to(torch.int8)

    final_states = (state_count - 2, state_count - 1)
    state = max(final_states, key=lambda item: float(scores[item].item()))
    path: list[tuple[int, int, float]] = []
    for frame in range(frame_count - 1, -1, -1):
        if state % 2 == 1:
            token_index = (state - 1) // 2
            probability = float(emission[frame, targets[token_index]].exp().item())
            path.append((token_index, frame, probability))
        if frame > 0:
            state -= int(backpointers[frame, state].item())
    if state not in {0, 1}:
        raise IHMError("CTC backtracking could not align the complete transcript")
    path.reverse()

    grouped: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for token_index, frame_index, probability in path:
        grouped[token_index].append((frame_index, probability))
    return tuple(
        _TokenSpan(
            token_index=index,
            start_frame=points[0][0],
            end_frame=points[-1][0] + 1,
            confidence=sum(point[1] for point in points) / len(points),
        )
        for index, points in sorted(grouped.items())
    )


def _word_timestamps(
    words: list[str],
    word_indices: list[int | None],
    spans: tuple[_TokenSpan, ...],
    segment_start: float,
    segment_end: float,
    frame_count: int,
) -> tuple[Word, ...]:
    by_word: dict[int, list[_TokenSpan]] = defaultdict(list)
    for span in spans:
        word_index = word_indices[span.token_index]
        if word_index is not None:
            by_word[word_index].append(span)
    seconds_per_frame = (segment_end - segment_start) / frame_count
    aligned: list[Word] = []
    for index, text in enumerate(words):
        word_spans = by_word.get(index)
        if not word_spans:
            aligned.append(Word(text, None, None, None))
            continue
        start = max(segment_start, segment_start + word_spans[0].start_frame * seconds_per_frame)
        end = min(segment_end, segment_start + word_spans[-1].end_frame * seconds_per_frame)
        confidence = sum(span.confidence for span in word_spans) / len(word_spans)
        aligned.append(Word(text, start, end, confidence))
    return tuple(aligned)
