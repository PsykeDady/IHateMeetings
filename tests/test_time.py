import pytest

from ihatemeetings.utils.time import format_timestamp


def test_format_timestamp_with_hours():
    assert format_timestamp(3) == "00:00:03"
    assert format_timestamp(3723) == "01:02:03"


def test_format_timestamp_with_milliseconds():
    assert format_timestamp(1.234, milliseconds=True) == "00:00:01.234"
    assert format_timestamp(1.9996, milliseconds=True) == "00:00:02.000"


def test_format_timestamp_rejects_negative_values():
    with pytest.raises(ValueError):
        format_timestamp(-0.1)
