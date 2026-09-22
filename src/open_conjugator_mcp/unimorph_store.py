from __future__ import annotations

import difflib
import sqlite3
import threading
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any


UNIMORPH_SOURCE = "https://unimorph.github.io/"

TAG_LABELS = {
    "IND": ("mood", "indicative"),
    "SBJV": ("mood", "subjunctive"),
    "IMP": ("mood", "imperative"),
    "COND": ("mood", "conditional"),
    "PRS": ("tense", "present"),
    "PST": ("tense", "past"),
    "FUT": ("tense", "future"),
    "IPFV": ("aspect", "imperfective"),
    "PFV": ("aspect", "perfective"),
    "PRF": ("aspect", "perfect"),
    "PROG": ("aspect", "progressive"),
    "ACT": ("voice", "active"),
    "PASS": ("voice", "passive"),
    "MID": ("voice", "middle"),
    "SG": ("number", "singular"),
    "DU": ("number", "dual"),
    "PL": ("number", "plural"),
    "MASC": ("gender", "masculine"),
    "FEM": ("gender", "feminine"),
}


def normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def parse_features(bundle: str) -> dict[str, Any]:
    tags = bundle.split(";")
    parsed: dict[str, Any] = {"raw": bundle, "tags": tags}
    for tag in tags:
        if tag in TAG_LABELS:
            key, value = TAG_LABELS[tag]
            parsed[key] = value
        elif tag in {"1", "2", "3"}:
            parsed["person"] = int(tag)
        elif tag == "NFIN":
            parsed["nonFinite"] = "infinitive"
        elif tag == "V.PTCP":
            parsed["nonFinite"] = "participle"
        elif tag == "V.CVB":
            parsed["nonFinite"] = "converb"
    return parsed


class UniMorphStore:
    def __init__(self, database_path: Path):
        if not database_path.is_file():
            raise FileNotFoundError(
                f"UniMorph index not found at {database_path}. Run: python scripts/prepare_data.py"
            )
        self.database_path = database_path
        self._local = threading.local()

    def _connection(self) -> sqlite3.Connection:
        connection = getattr(self._local, "connection", None)
        if connection is None:
            uri = f"file:{self.database_path}?mode=ro&immutable=1"
            connection = sqlite3.connect(uri, uri=True, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            self._local.connection = connection
        return connection

    def _rows(self, sql: str, parameters: tuple[Any, ...]) -> list[dict[str, Any]]:
        return [dict(row) for row in self._connection().execute(sql, parameters).fetchall()]

    @lru_cache(maxsize=1024)
    def by_lemma(self, language: str, lemma: str) -> tuple[dict[str, Any], ...]:
        rows = self._rows(
            "SELECT lemma, form, features FROM forms WHERE language=? AND lemma_norm=? "
            "ORDER BY features, form",
            (language, normalize(lemma)),
        )
        return tuple(rows)

    @lru_cache(maxsize=1024)
    def by_form(self, language: str, form: str) -> tuple[dict[str, Any], ...]:
        rows = self._rows(
            "SELECT lemma, form, features FROM forms WHERE language=? AND form_norm=? "
            "ORDER BY lemma, features",
            (language, normalize(form)),
        )
        return tuple(rows)

    @lru_cache(maxsize=8)
    def lemmas(self, language: str) -> tuple[str, ...]:
        rows = self._rows(
            "SELECT lemma FROM lemmas WHERE language=? ORDER BY lemma", (language,)
        )
        return tuple(row["lemma"] for row in rows)

    def suggestions(self, language: str, query: str, limit: int) -> list[str]:
        normalized_to_lemma: dict[str, str] = {}
        for lemma in self.lemmas(language):
            normalized_to_lemma.setdefault(normalize(lemma), lemma)
        keys = difflib.get_close_matches(
            normalize(query), normalized_to_lemma.keys(), n=limit, cutoff=0.6
        )
        return [normalized_to_lemma[key] for key in keys]

    @staticmethod
    def _decorate(row: dict[str, Any]) -> dict[str, Any]:
        features = parse_features(row["features"])
        return {"lemma": row["lemma"], "value": row["form"], "features": features}

    def conjugate(self, language: str, query: str, max_forms: int) -> dict[str, Any]:
        rows = list(self.by_lemma(language, query))
        candidates: list[str] = []
        if not rows:
            identified = self.by_form(language, query)
            candidates = list(dict.fromkeys(row["lemma"] for row in identified))
            if candidates:
                rows = list(self.by_lemma(language, candidates[0]))
        lemma = rows[0]["lemma"] if rows else None
        forms = [self._decorate(row) for row in rows[:max_forms]]
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        non_finite = []
        for form in forms:
            features = form["features"]
            if features.get("nonFinite"):
                non_finite.append(form)
            key = (
                features.get("voice"),
                features.get("mood"),
                features.get("tense"),
                features.get("aspect"),
            )
            groups.setdefault(key, []).append(form)
        paradigms = [
            {
                "voice": key[0],
                "mood": key[1],
                "tense": key[2],
                "aspect": key[3],
                "forms": grouped,
            }
            for key, grouped in groups.items()
        ]
        return {
            "query": {"original": query, "resolved": query},
            "canonicalVerb": lemma,
            "language": language,
            "found": bool(rows),
            "model": None,
            "candidateLemmas": candidates or ([lemma] if lemma else []),
            "suggestions": self.suggestions(language, query, 8),
            "voices": sorted({f["features"].get("voice") for f in forms if f["features"].get("voice")}),
            "moods": sorted({f["features"].get("mood") for f in forms if f["features"].get("mood")}),
            "tenses": sorted({f["features"].get("tense") for f in forms if f["features"].get("tense")}),
            "paradigms": paradigms,
            "forms": forms,
            "nonFiniteForms": non_finite,
            "truncated": len(rows) > max_forms,
        }

    def identify(self, language: str, query: str) -> dict[str, Any]:
        matches = [self._decorate(row) for row in self.by_form(language, query)]
        lemmas = list(dict.fromkeys(match["lemma"] for match in matches))
        return {
            "query": {"original": query, "resolved": query},
            "language": language,
            "found": bool(matches),
            "canonicalVerb": lemmas[0] if lemmas else None,
            "candidateLemmas": lemmas,
            "matches": matches,
            "suggestions": [] if matches else self.suggestions(language, query, 8),
        }

    def search(self, language: str, query: str, max_results: int) -> dict[str, Any]:
        exact_lemmas = self.by_lemma(language, query)
        exact_forms = self.by_form(language, query)
        results: list[dict[str, Any]] = []
        if exact_lemmas:
            results.append({"lemma": exact_lemmas[0]["lemma"], "matchType": "lemma"})
        for row in exact_forms:
            if not any(item["lemma"] == row["lemma"] for item in results):
                results.append({"lemma": row["lemma"], "matchType": "inflected-form"})
        suggestions = self.suggestions(language, query, max_results)
        for lemma in suggestions:
            if len(results) >= max_results:
                break
            if not any(item["lemma"] == lemma for item in results):
                results.append({"lemma": lemma, "matchType": "fuzzy"})
        return {
            "query": {"original": query, "resolved": query},
            "language": language,
            "found": bool(results),
            "results": results[:max_results],
            "suggestions": suggestions,
        }

    def models(self, language: str, query: str | None, limit: int) -> dict[str, Any]:
        if query:
            rows = list(self.by_lemma(language, query))
            if not rows:
                identified = self.by_form(language, query)
                if identified:
                    rows = list(self.by_lemma(language, identified[0]["lemma"]))
            bundles = sorted({row["features"] for row in rows})[:limit]
            return {
                "query": query,
                "models": [
                    {"featureBundle": bundle, "features": parse_features(bundle)} for bundle in bundles
                ],
                "note": "UniMorph describes paradigms with feature bundles, not named conjugation models.",
            }
        rows = self._rows(
            "SELECT features, form_count, sample_lemma FROM models WHERE language=? "
            "ORDER BY form_count DESC LIMIT ?",
            (language, limit),
        )
        return {
            "query": None,
            "models": [
                {
                    "featureBundle": row["features"],
                    "features": parse_features(row["features"]),
                    "formCount": row["form_count"],
                    "sampleLemma": row["sample_lemma"],
                }
                for row in rows
            ],
            "note": "UniMorph describes paradigms with feature bundles, not named conjugation models.",
        }

    @staticmethod
    def sources() -> list[dict[str, str]]:
        return [
            {
                "name": "UniMorph English, Spanish and French datasets",
                "url": UNIMORPH_SOURCE,
                "license": "CC BY-SA 3.0",
            }
        ]

