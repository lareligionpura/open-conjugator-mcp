from __future__ import annotations

import pytest

from open_conjugator_mcp.service import service


@pytest.mark.parametrize(
    ("language", "lemma", "expected_form"),
    [("es", "hablar", "hablo"), ("en", "write", "wrote"), ("fr", "parler", "parle")],
)
def test_unimorph_conjugation(language: str, lemma: str, expected_form: str) -> None:
    result = service.conjugate(lemma, language, True, True, 500)
    assert result["canonicalVerb"] == lemma
    assert expected_form in {form["value"] for form in result["forms"]}
    assert result["sources"][0]["name"].startswith("UniMorph")


def test_unimorph_identifies_an_inflected_form() -> None:
    result = service.identify("habló", "es", True)
    assert result["found"] is True
    assert "hablar" in result["candidateLemmas"]


def test_language_inventory_is_truthful() -> None:
    result = service.supported_languages()
    assert [item["code"] for item in result["languages"]] == ["ar", "es", "en", "fr"]
    assert result["runtimeNetworkRequired"] is False

