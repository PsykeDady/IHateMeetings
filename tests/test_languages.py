import pytest

from ihatemeetings.errors import IHMError
from ihatemeetings.languages import (
    normalize_language_code,
    require_supported_language,
    unsupported_detection_warning,
)


@pytest.mark.parametrize("language", ("it", "en"))
def test_official_languages_are_supported(language):
    assert require_supported_language(language) == language


def test_language_variants_normalize_to_v1_codes():
    assert normalize_language_code("it-IT") == "it"
    assert normalize_language_code("EN_us") == "en"


def test_explicit_unsupported_language_is_rejected():
    with pytest.raises(IHMError, match="not officially supported"):
        require_supported_language("fr")


def test_automatic_unsupported_language_has_explicit_warning():
    warning = unsupported_detection_warning("fr")
    assert warning is not None
    assert "supported: it, en" in warning
