from __future__ import annotations

import pytest

from open_conjugator_mcp.service import service


@pytest.mark.parametrize(
    ("query", "lemma", "root"),
    [
        ("كتب", "كَتَب", "ك.ت.ب"),
        ("كَتَبَ", "كَتَب", "ك.ت.ب"),
        ("يَكْتُبُونَ", "كَتَب", "ك.ت.ب"),
        ("قال", "قَال", "ق.و.ل"),
        ("رأى", "رَأَى", "ر.أ.ي"),
        ("استمر", "ٱِسْتَمَرّ", "م.ر.ر"),
        ("kataba", "كَتَب", "ك.ت.ب"),
    ],
)
def test_required_arabic_queries(query: str, lemma: str, root: str) -> None:
    result = service.conjugate(query, "ar", True, True, 250)
    assert result["found"] is True
    assert result["canonicalVerb"] == lemma
    assert result["model"]["root"] == root
    assert len(result["forms"]) >= 50
    assert all(form["value"] for form in result["forms"])
    assert any(form.get("transliteration") for form in result["forms"])


def test_identify_preserves_ambiguity_and_diacritics() -> None:
    result = service.identify("يَكْتُبُونَ", "ar", True)
    assert result["canonicalVerb"] == "كَتَب"
    assert "كَتَب" in result["candidateLemmas"]
    assert len(result["matches"]) >= 2
    assert any(match["form"] == "يَكْتُبُونَ" for match in result["matches"])


def test_arabic_models_return_attested_data() -> None:
    result = service.models("ar", "كتب", 10)
    assert result["models"][0]["root"] == "ك.ت.ب"
    assert result["models"][0]["pattern"]
    assert result["models"][0]["patternAbstract"]

