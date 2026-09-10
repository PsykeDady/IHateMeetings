import pytest

from ihatemeetings.metrics import character_error_rate, word_error_rate


def test_error_rates_are_zero_for_normalization_only_differences():
    reference = "DynamoDB, API Gateway e deploy."
    hypothesis = "dynamodb API gateway e deploy"

    assert word_error_rate(reference, hypothesis) == 0
    assert character_error_rate(reference, hypothesis) == 0


def test_word_and_character_error_rates_use_levenshtein_distance():
    assert word_error_rate("uno due tre", "uno quattro tre") == pytest.approx(1 / 3)
    assert character_error_rate("abc", "adc") == pytest.approx(1 / 3)


def test_error_rate_rejects_empty_reference():
    with pytest.raises(ValueError, match="must not be empty"):
        word_error_rate("", "test")
