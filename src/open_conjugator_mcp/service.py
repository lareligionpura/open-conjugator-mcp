from __future__ import annotations

from datetime import UTC, datetime
from functools import cached_property, lru_cache
from typing import Any

from .arabic import ArabicMorphology
from .config import settings
from .languages import LANGUAGES, Language, resolve_language
from .unimorph_store import UniMorphStore


UNIMORPH_SCHEMA_URL = "https://unimorph.github.io/schema/"
CAMEL_FEATURES_URL = (
    "https://camel-tools.readthedocs.io/en/latest/reference/"
    "camel_morphology_features.html"
)


def now() -> str:
    return datetime.now(UTC).isoformat()


class ConjugationService:
    @cached_property
    def arabic(self) -> ArabicMorphology:
        return ArabicMorphology(settings.camel_morph_db)

    @cached_property
    def unimorph(self) -> UniMorphStore:
        return UniMorphStore(settings.unimorph_db)

    @staticmethod
    def _source_metadata(language: Language) -> tuple[list[dict[str, str]], dict[str, Any]]:
        if language.code == "ar":
            sources = ArabicMorphology.sources()
        else:
            sources = UniMorphStore.sources()
        return sources, {
            "source": "local open linguistic resources",
            "normalization": "NFC display; NFKC/casefold matching; Arabic diacritics preserved in output",
            "inference": "Only grouping and label expansion are performed by this MCP.",
        }

    @staticmethod
    def _finish(result: dict[str, Any], language: Language) -> dict[str, Any]:
        sources, provenance = ConjugationService._source_metadata(language)
        result["language"] = language.code
        result["languageName"] = language.name
        result["sources"] = sources
        result["sourceUrl"] = sources[0]["url"]
        result["retrievedAt"] = now()
        result["provenance"] = provenance
        return result

    @lru_cache(maxsize=256)
    def conjugate(
        self,
        verb: str,
        language_value: str,
        include_transliteration: bool,
        include_passive: bool,
        max_forms: int,
    ) -> dict[str, Any]:
        language = resolve_language(language_value)
        if language.code == "ar":
            result = self.arabic.conjugate(
                verb,
                include_transliteration=include_transliteration,
                include_passive=include_passive,
                max_forms=max_forms,
            )
        else:
            result = self.unimorph.conjugate(language.iso3, verb, max_forms)
        return self._finish(result, language)

    @lru_cache(maxsize=512)
    def identify(
        self, verb_form: str, language_value: str, include_transliteration: bool
    ) -> dict[str, Any]:
        language = resolve_language(language_value)
        if language.code == "ar":
            result = self.arabic.identify(verb_form, include_transliteration)
        else:
            result = self.unimorph.identify(language.iso3, verb_form)
        return self._finish(result, language)

    @lru_cache(maxsize=512)
    def search(
        self, query: str, language_value: str, include_transliteration: bool, max_results: int
    ) -> dict[str, Any]:
        language = resolve_language(language_value)
        if language.code == "ar":
            result = self.arabic.search(query, include_transliteration, max_results)
        else:
            result = self.unimorph.search(language.iso3, query, max_results)
        return self._finish(result, language)

    @lru_cache(maxsize=128)
    def models(self, language_value: str, query: str | None, limit: int) -> dict[str, Any]:
        language = resolve_language(language_value)
        if language.code == "ar":
            result = self.arabic.models(query, limit)
        else:
            result = self.unimorph.models(language.iso3, query, limit)
        return self._finish(result, language)

    @lru_cache(maxsize=32)
    def help(self, language_value: str, topic: str | None) -> dict[str, Any]:
        language = resolve_language(language_value)
        if language.code == "ar":
            sections = [
                {
                    "topic": "analysis",
                    "summary": (
                        "CAMeL Tools returns every compatible out-of-context analysis. "
                        "A surface form can therefore map to several lemmas, voices, or feature bundles."
                    ),
                },
                {
                    "topic": "features",
                    "summary": (
                        "Arabic verb paradigms use aspect (perfect, imperfect, command), person, "
                        "gender, number, voice, and mood. Raw CAMeL feature codes remain available."
                    ),
                },
                {
                    "topic": "diacritics",
                    "summary": (
                        "The MCP preserves ḥarakāt in returned lemmas and forms. Diacritic-free "
                        "normalization is used only as an internal lookup aid."
                    ),
                },
                {
                    "topic": "patterns",
                    "summary": (
                        "Roots, surface patterns, and abstract patterns come directly from CAMeL Morph. "
                        "The MCP does not invent a traditional wazn number when the database does not provide one."
                    ),
                },
            ]
            references = [
                {"title": "CAMeL morphology features", "url": CAMEL_FEATURES_URL},
                *ArabicMorphology.sources(),
            ]
        else:
            sections = [
                {
                    "topic": "schema",
                    "summary": (
                        "UniMorph encodes each inflected form as lemma, surface form, and a universal "
                        "semicolon-separated feature bundle."
                    ),
                },
                {
                    "topic": "paradigms",
                    "summary": (
                        "Mood, tense, aspect, voice, person, number, gender, and non-finite tags are "
                        "expanded when present; the original feature bundle is always retained."
                    ),
                },
            ]
            references = [
                {"title": "UniMorph schema", "url": UNIMORPH_SCHEMA_URL},
                *UniMorphStore.sources(),
            ]
        if topic:
            key = topic.casefold().strip()
            filtered = [section for section in sections if key in section["topic"].casefold()]
            if filtered:
                sections = filtered
        result = {"topic": topic, "sections": sections, "references": references}
        return self._finish(result, language)

    def supported_languages(self) -> dict[str, Any]:
        languages = []
        for language in LANGUAGES:
            item = language.as_dict()
            item["status"] = "available"
            if language.code == "ar":
                item["capabilities"] = [
                    "analysis",
                    "generation",
                    "active-and-passive",
                    "root",
                    "pattern",
                    "buckwalter-transliteration",
                ]
            else:
                item["capabilities"] = ["inflection-table", "form-identification", "feature-bundles"]
            languages.append(item)
        return {
            "languages": languages,
            "defaultLanguage": "ar",
            "arabicPriority": True,
            "runtimeNetworkRequired": False,
            "retrievedAt": now(),
            "sources": [*ArabicMorphology.sources(), *UniMorphStore.sources()],
        }

    def readiness(self) -> dict[str, Any]:
        return {
            "status": "ok" if settings.camel_morph_db.is_file() and settings.unimorph_db.is_file() else "not-ready",
            "camelMorphDatabase": settings.camel_morph_db.is_file(),
            "uniMorphIndex": settings.unimorph_db.is_file(),
            "version": "2.0.0",
        }


service = ConjugationService()

