from open_conjugator_mcp.unicode_utils import (
    normalize_arabic_lookup,
    normalize_display,
    strip_arabic_diacritics,
)


def test_arabic_diacritics_are_preserved_for_display() -> None:
    value = "  يَكْتُبُونَ  "
    assert normalize_display(value) == "يَكْتُبُونَ"
    assert strip_arabic_diacritics(value) == "يكتبون"


def test_lookup_normalizes_wasla_but_not_display() -> None:
    assert normalize_arabic_lookup("ٱِسْتَمَرّ") == "استمر"
    assert normalize_display("ٱِسْتَمَرّ") == "ٱِسْتَمَرّ"

