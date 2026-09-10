from __future__ import annotations

import pytest

from ihatemeetings.alignment.ctc import _forced_align, _TokenSpan, _word_timestamps
from ihatemeetings.models import Word


def test_word_timestamps_are_ordered_and_inside_segment():
    words = _word_timestamps(
        ["ciao", "mondo"],
        [0, 0, None, 1, 1],
        (
            _TokenSpan(0, 2, 4, 0.8),
            _TokenSpan(1, 4, 6, 0.9),
            _TokenSpan(2, 6, 7, 0.7),
            _TokenSpan(3, 7, 9, 0.85),
            _TokenSpan(4, 9, 11, 0.95),
        ),
        segment_start=10.0,
        segment_end=12.0,
        frame_count=20,
    )

    assert [word.text for word in words] == ["ciao", "mondo"]
    assert 10.0 <= words[0].start < words[0].end <= words[1].start
    assert words[1].start < words[1].end <= 12.0
    assert words[0].confidence == pytest.approx(0.85)


def test_unalignable_word_preserves_text_without_inventing_timestamps():
    words = _word_timestamps(
        ["known", "???"],
        [0],
        (_TokenSpan(0, 1, 2, 0.75),),
        segment_start=0.0,
        segment_end=1.0,
        frame_count=10,
    )
    assert words[1] == Word("???", None, None, None)


def test_ctc_alignment_requires_blank_between_repeated_tokens():
    torch = pytest.importorskip("torch")
    logits = torch.full((7, 3), -10.0)
    for frame, token in enumerate((1, 0, 1, 0, 2, 0, 0)):
        logits[frame, token] = 10.0

    spans = _forced_align(logits.log_softmax(dim=-1), [1, 1, 2], 0, torch)

    assert [(span.token_index, span.start_frame) for span in spans] == [
        (0, 0),
        (1, 2),
        (2, 4),
    ]


@pytest.mark.parametrize(
    "word",
    (
        Word("missing", None, None, None),
        Word("aligned", 0.0, 0.2, 0.5),
    ),
)
def test_word_accepts_aligned_or_explicitly_unaligned_state(word):
    assert word.text


def test_word_rejects_partial_or_invalid_timestamps():
    with pytest.raises(ValueError):
        Word("partial", 1.0, None, None)
    with pytest.raises(ValueError):
        Word("reversed", 2.0, 1.0, 0.5)
    with pytest.raises(ValueError):
        Word("confidence", 1.0, 2.0, 1.1)
