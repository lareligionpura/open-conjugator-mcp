from __future__ import annotations

import difflib
import threading
from collections import Counter, defaultdict
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any

from camel_tools.morphology.analyzer import Analyzer
from camel_tools.morphology.database import MorphologyDB
from camel_tools.morphology.generator import Generator
from camel_tools.utils.charmap import CharMapper

from .unicode_utils import contains_arabic, normalize_arabic_lookup, normalize_display


CAMEL_MORPH_SOURCE = (
    "https://github.com/CAMeL-Lab/camel_morph/tree/"
    "15f5aede4b609db54abd6f87aded1f5ec5d930af/"
    "official_releases/lrec-coling2024_release"
)
CAMEL_TOOLS_SOURCE = "https://github.com/CAMeL-Lab/camel_tools"

FEATURE_KEYS = (
    "lex",
    "diac",
    "gloss",
    "root",
    "pattern",
    "pattern_abstract",
    "asp",
    "per",
    "gen",
    "num",
    "vox",
    "mod",
    "pos",
    "source",
    "stem",
    "bw",
    "caphi",
    "lex_logprob",
    "prc3",
    "prc2",
    "prc1",
    "prc0",
    "enc0",
)

PERSONS = (
    ("3", "m", "s"),
    ("3", "f", "s"),
    ("3", "m", "d"),
    ("3", "f", "d"),
    ("3", "m", "p"),
    ("3", "f", "p"),
    ("2", "m", "s"),
    ("2", "f", "s"),
    ("2", "m", "d"),
    ("2", "f", "d"),
    ("2", "m", "p"),
    ("2", "f", "p"),
    ("1", "m", "s"),
    ("1", "m", "p"),
)
COMMAND_PERSONS = tuple(person for person in PERSONS if person[0] == "2")

PRONOUNS = {
    ("3", "m", "s"): "هُوَ",
    ("3", "f", "s"): "هِيَ",
    ("3", "m", "d"): "هُمَا",
    ("3", "f", "d"): "هُمَا",
    ("3", "m", "p"): "هُمْ",
    ("3", "f", "p"): "هُنَّ",
    ("2", "m", "s"): "أَنْتَ",
    ("2", "f", "s"): "أَنْتِ",
    ("2", "m", "d"): "أَنْتُمَا",
    ("2", "f", "d"): "أَنْتُمَا",
    ("2", "m", "p"): "أَنْتُمْ",
    ("2", "f", "p"): "أَنْتُنَّ",
    ("1", "m", "s"): "أَنَا",
    ("1", "m", "p"): "نَحْنُ",
}

NUMBER_LABELS = {"s": "singular", "d": "dual", "p": "plural"}
GENDER_LABELS = {"m": "masculine", "f": "feminine"}
VOICE_LABELS = {"a": "active", "p": "passive"}
MODE_LABELS = {"i": "indicative", "s": "subjunctive", "j": "jussive", "e": "energetic"}


def _clean(analysis: dict[str, Any]) -> dict[str, Any]:
    return {key: analysis.get(key) for key in FEATURE_KEYS if analysis.get(key) is not None}


def _person_code(person: str, gender: str, number: str) -> str:
    if person == "1":
        return f"1{number}"
    if number == "d":
        return f"{person}{gender}d"
    return f"{person}{gender}{number}"


class ArabicMorphology:
    def __init__(self, database_path: Path):
        if not database_path.is_file():
            raise FileNotFoundError(
                f"CAMeL Morph database not found at {database_path}. "
                "Run: python scripts/prepare_data.py"
            )
        self.database_path = database_path
        self._lock = threading.RLock()
        self.analysis_db = MorphologyDB(str(database_path), "a")
        self.generation_db = MorphologyDB(str(database_path), "g")
        self.analyzer = Analyzer(self.analysis_db)
        self.generator = Generator(self.generation_db)
        self.ar_to_bw = CharMapper.builtin_mapper("ar2bw")
        self.bw_to_ar = CharMapper.builtin_mapper("bw2ar")

    def resolve_query(self, query: str) -> tuple[str, str | None]:
        original = normalize_display(query)
        if contains_arabic(original):
            return original, None
        transliterated = normalize_display(self.bw_to_ar(original))
        return transliterated, "buckwalter"

    @staticmethod
    def _is_unaffixed(analysis: dict[str, Any]) -> bool:
        return all(analysis.get(key, "0") == "0" for key in ("prc3", "prc2", "prc1", "prc0", "enc0"))

    @staticmethod
    def _score(analysis: dict[str, Any], query: str) -> float:
        score = 0.0
        if normalize_display(analysis.get("diac", "")) == query:
            score += 50
        if analysis.get("vox") == "a":
            score += 12
        if analysis.get("asp") == "p":
            score += 8
        if (
            analysis.get("per") == "3"
            and analysis.get("gen") == "m"
            and analysis.get("num") == "s"
        ):
            score += 8
        if ArabicMorphology._is_unaffixed(analysis):
            score += 5
        try:
            score += max(float(analysis.get("lex_logprob", -99)), -99) / 25
        except (TypeError, ValueError):
            pass
        return score

    @lru_cache(maxsize=1024)
    def analyze(self, query: str) -> tuple[dict[str, Any], ...]:
        resolved, _ = self.resolve_query(query)
        with self._lock:
            raw = self.analyzer.analyze(resolved)
        analyses = [item for item in raw if item.get("pos") == "verb"]
        analyses.sort(key=lambda item: self._score(item, resolved), reverse=True)
        seen: set[tuple[Any, ...]] = set()
        result: list[dict[str, Any]] = []
        for item in analyses:
            key = tuple(item.get(name) for name in ("lex", "diac", "asp", "per", "gen", "num", "vox", "mod"))
            if key in seen:
                continue
            seen.add(key)
            result.append(_clean(item))
        return tuple(result)

    @cached_property
    def verb_lemmas(self) -> dict[str, tuple[str, ...]]:
        values: dict[str, set[str]] = defaultdict(set)
        for lemma, entries in self.generation_db.lemma_hash.items():
            if any(entry.get("pos") == "verb" for entry in entries):
                values[normalize_arabic_lookup(lemma)].add(lemma)
        return {key: tuple(sorted(items)) for key, items in values.items()}

    @cached_property
    def lemma_metadata(self) -> dict[str, tuple[dict[str, Any], ...]]:
        result: dict[str, tuple[dict[str, Any], ...]] = {}
        for lemma, entries in self.generation_db.lemma_hash.items():
            verbs = tuple(_clean(entry) for entry in entries if entry.get("pos") == "verb")
            if verbs:
                result[lemma] = verbs
        return result

    def canonical_candidates(self, query: str) -> list[str]:
        resolved, _ = self.resolve_query(query)
        analyses = self.analyze(query)
        candidates: list[str] = []
        for analysis in analyses:
            lemma = analysis.get("lex")
            if lemma and lemma not in candidates:
                candidates.append(lemma)
        for lemma in self.verb_lemmas.get(normalize_arabic_lookup(resolved), ()):
            if lemma not in candidates:
                candidates.append(lemma)
        return candidates

    def transliterate(self, text: str) -> str:
        return self.ar_to_bw(text)

    def model_for(self, lemma: str) -> dict[str, Any]:
        entries = self.lemma_metadata.get(lemma, ())
        selected = next((entry for entry in entries if entry.get("vox") == "a"), entries[0] if entries else {})
        return {
            "root": selected.get("root"),
            "pattern": selected.get("pattern"),
            "patternAbstract": selected.get("pattern_abstract"),
            "gloss": selected.get("gloss"),
            "dataSource": "CAMeL Morph MSA v1.0",
        }

    @lru_cache(maxsize=256)
    def generate_paradigm(
        self, lemma: str, include_passive: bool, include_transliteration: bool, max_forms: int
    ) -> tuple[dict[str, Any], ...]:
        requests: list[dict[str, str]] = []
        voices = ("a", "p") if include_passive else ("a",)
        for voice in voices:
            for person, gender, number in PERSONS:
                requests.append(
                    {"asp": "p", "vox": voice, "mod": "i", "per": person, "gen": gender, "num": number}
                )
                for mode in ("i", "s", "j", "e"):
                    requests.append(
                        {"asp": "i", "vox": voice, "mod": mode, "per": person, "gen": gender, "num": number}
                    )
        for person, gender, number in COMMAND_PERSONS:
            requests.append(
                {"asp": "c", "vox": "a", "mod": "i", "per": person, "gen": gender, "num": number}
            )

        forms: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()
        for features in requests:
            with self._lock:
                generated = self.generator.generate(lemma, {"pos": "verb", **features})
            for item in generated:
                surface = item.get("diac")
                if not surface:
                    continue
                person_key = (features["per"], features["gen"], features["num"])
                aspect = features["asp"]
                if aspect == "p":
                    tense, mood = "past", "perfect"
                elif aspect == "i":
                    tense, mood = "non-past", MODE_LABELS.get(features["mod"], features["mod"])
                else:
                    tense, mood = None, "imperative"
                key = (surface, features["vox"], mood, _person_code(*person_key))
                if key in seen:
                    continue
                seen.add(key)
                form = {
                    "value": surface,
                    "person": _person_code(*person_key),
                    "pronoun": PRONOUNS.get(person_key),
                    "personNumber": int(features["per"]),
                    "gender": GENDER_LABELS.get(features["gen"]),
                    "number": NUMBER_LABELS.get(features["num"]),
                    "voice": VOICE_LABELS[features["vox"]],
                    "mood": mood,
                    "tense": tense,
                    "features": features,
                }
                if include_transliteration:
                    form["transliteration"] = self.transliterate(surface)
                forms.append(form)
                if len(forms) >= max_forms:
                    return tuple(forms)
        return tuple(forms)

    def conjugate(
        self,
        query: str,
        *,
        include_transliteration: bool = True,
        include_passive: bool = True,
        max_forms: int = 250,
    ) -> dict[str, Any]:
        resolved, input_scheme = self.resolve_query(query)
        candidates = self.canonical_candidates(query)
        suggestions = self.suggestions(resolved, 8)
        if not candidates:
            return {
                "query": {"original": query, "resolved": resolved, "inputTransliteration": input_scheme},
                "canonicalVerb": None,
                "language": "ar",
                "found": False,
                "suggestions": suggestions,
                "forms": [],
            }
        lemma = candidates[0]
        forms = list(
            self.generate_paradigm(lemma, include_passive, include_transliteration, max_forms)
        )
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for form in forms:
            groups[(form["voice"], form["mood"], form["tense"])].append(form)
        paradigms = [
            {"voice": voice, "mood": mood, "tense": tense, "forms": grouped}
            for (voice, mood, tense), grouped in groups.items()
        ]
        return {
            "query": {"original": query, "resolved": resolved, "inputTransliteration": input_scheme},
            "canonicalVerb": lemma,
            "canonicalTransliteration": self.transliterate(lemma) if include_transliteration else None,
            "language": "ar",
            "found": True,
            "model": self.model_for(lemma),
            "candidateLemmas": candidates[:10],
            "suggestions": suggestions,
            "voices": sorted({form["voice"] for form in forms}),
            "moods": sorted({form["mood"] for form in forms}),
            "tenses": sorted({form["tense"] for form in forms if form["tense"]}),
            "paradigms": paradigms,
            "forms": forms,
            "nonFiniteForms": [],
            "truncated": len(forms) >= max_forms,
        }

    def identify(self, query: str, include_transliteration: bool = True) -> dict[str, Any]:
        resolved, input_scheme = self.resolve_query(query)
        analyses = list(self.analyze(query))
        matches = []
        for analysis in analyses:
            match = {
                "lemma": analysis.get("lex"),
                "form": analysis.get("diac"),
                "root": analysis.get("root"),
                "pattern": analysis.get("pattern"),
                "gloss": analysis.get("gloss"),
                "voice": VOICE_LABELS.get(analysis.get("vox"), analysis.get("vox")),
                "aspect": {"p": "perfect", "i": "imperfect", "c": "imperative"}.get(
                    analysis.get("asp"), analysis.get("asp")
                ),
                "mood": MODE_LABELS.get(analysis.get("mod"), analysis.get("mod")),
                "person": _person_code(
                    analysis.get("per", ""), analysis.get("gen", ""), analysis.get("num", "")
                ),
                "pronoun": PRONOUNS.get(
                    (analysis.get("per"), analysis.get("gen"), analysis.get("num"))
                ),
                "rawFeatures": analysis,
            }
            if include_transliteration:
                match["transliteration"] = self.transliterate(analysis.get("diac", ""))
            matches.append(match)
        lemmas = list(dict.fromkeys(match["lemma"] for match in matches if match.get("lemma")))
        return {
            "query": {"original": query, "resolved": resolved, "inputTransliteration": input_scheme},
            "language": "ar",
            "found": bool(matches),
            "canonicalVerb": lemmas[0] if lemmas else None,
            "candidateLemmas": lemmas,
            "matches": matches,
            "suggestions": [] if matches else self.suggestions(resolved, 8),
        }

    def suggestions(self, query: str, limit: int) -> list[dict[str, str]]:
        key = normalize_arabic_lookup(query)
        candidates = difflib.get_close_matches(key, self.verb_lemmas.keys(), n=limit, cutoff=0.55)
        return [
            {"lemma": self.verb_lemmas[item][0], "transliteration": self.transliterate(self.verb_lemmas[item][0])}
            for item in candidates
        ]

    def search(self, query: str, include_transliteration: bool, max_results: int) -> dict[str, Any]:
        identification = self.identify(query, include_transliteration)
        results = []
        for lemma in identification["candidateLemmas"][:max_results]:
            item = {"lemma": lemma, "model": self.model_for(lemma), "matchType": "analysis"}
            if include_transliteration:
                item["transliteration"] = self.transliterate(lemma)
            results.append(item)
        suggestions = self.suggestions(identification["query"]["resolved"], max_results)
        if not results:
            results = [{**item, "matchType": "fuzzy"} for item in suggestions]
        return {
            "query": identification["query"],
            "language": "ar",
            "found": bool(results),
            "results": results,
            "suggestions": suggestions,
        }

    @cached_property
    def pattern_catalog(self) -> list[dict[str, Any]]:
        counts: Counter[tuple[str | None, str | None]] = Counter()
        examples: dict[tuple[str | None, str | None], list[str]] = defaultdict(list)
        for lemma, entries in self.lemma_metadata.items():
            for entry in entries:
                key = (entry.get("pattern_abstract"), entry.get("pattern"))
                counts[key] += 1
                if len(examples[key]) < 5 and lemma not in examples[key]:
                    examples[key].append(lemma)
        return [
            {
                "patternAbstract": key[0],
                "pattern": key[1],
                "lemmaCount": count,
                "examples": examples[key],
            }
            for key, count in counts.most_common()
        ]

    def models(self, query: str | None, limit: int) -> dict[str, Any]:
        if query:
            candidates = self.canonical_candidates(query)
            models = []
            roots: set[str] = set()
            for lemma in candidates[:limit]:
                model = self.model_for(lemma)
                roots.add(model.get("root"))
                models.append({"lemma": lemma, **model})
            related = []
            if roots:
                for lemma, entries in self.lemma_metadata.items():
                    if lemma in candidates:
                        continue
                    if any(entry.get("root") in roots for entry in entries):
                        related.append({"lemma": lemma, **self.model_for(lemma)})
                        if len(related) >= limit:
                            break
            return {"query": query, "models": models, "relatedByRoot": related}
        return {"query": None, "models": self.pattern_catalog[:limit], "relatedByRoot": []}

    @staticmethod
    def sources() -> list[dict[str, str]]:
        return [
            {"name": "CAMeL Morph MSA v1.0", "url": CAMEL_MORPH_SOURCE, "license": "CC BY 4.0"},
            {"name": "CAMeL Tools 1.6.0", "url": CAMEL_TOOLS_SOURCE, "license": "MIT"},
        ]

